"""
VLM-driven Glassdoor scraper.

Uses VLM State Manager to orchestrate visual interactions,
with Playwright for browser control and DOM extraction.

This scraper uses a singleton browser instance to ensure only one
Glassdoor browser is open at a time, preventing rate limiting issues.
"""

import time
import logging
import threading
from typing import List, Optional, Tuple
from datetime import datetime
from urllib.parse import urlencode, quote_plus

from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext

from ..models import JobPost
from .base import BaseScraper

logger = logging.getLogger(__name__)

# Glassdoor search URL template
GLASSDOOR_BASE_URL = "https://www.glassdoor.com/Job/jobs.htm"

# Singleton browser instance for Glassdoor (only one browser at a time)
_glassdoor_browser_lock = threading.Lock()
_glassdoor_browser: Optional[Browser] = None
_glassdoor_playwright = None
_glassdoor_context: Optional[BrowserContext] = None


def build_glassdoor_search_url(search_term: str, location: str) -> str:
    """Build a Glassdoor search URL with query parameters."""
    params = {
        "sc.keyword": search_term,
        "locKeyword": location,
    }
    return f"{GLASSDOOR_BASE_URL}?{urlencode(params)}"


def get_singleton_browser() -> Tuple[Browser, BrowserContext, Page]:
    """
    Get or create the singleton Glassdoor browser.

    Returns:
        Tuple of (browser, context, page)
    """
    global _glassdoor_browser, _glassdoor_playwright, _glassdoor_context

    with _glassdoor_browser_lock:
        if _glassdoor_browser is None or not _glassdoor_browser.is_connected():
            print("[VLM] Creating singleton Glassdoor browser...", flush=True)
            _glassdoor_playwright = sync_playwright().start()
            _glassdoor_browser = _glassdoor_playwright.chromium.launch(
                headless=False,
                args=[
                    "--start-maximized",
                    "--disable-blink-features=AutomationControlled",
                ]
            )
            _glassdoor_context = _glassdoor_browser.new_context(
                no_viewport=True,
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )

        # Create new page in existing context
        page = _glassdoor_context.new_page()
        return _glassdoor_browser, _glassdoor_context, page


def close_singleton_browser():
    """Close the singleton browser."""
    global _glassdoor_browser, _glassdoor_playwright, _glassdoor_context

    with _glassdoor_browser_lock:
        if _glassdoor_context:
            try:
                _glassdoor_context.close()
            except:
                pass
            _glassdoor_context = None

        if _glassdoor_browser:
            try:
                _glassdoor_browser.close()
            except:
                pass
            _glassdoor_browser = None

        if _glassdoor_playwright:
            try:
                _glassdoor_playwright.stop()
            except:
                pass
            _glassdoor_playwright = None

        print("[VLM] Singleton browser closed", flush=True)


class GlassdoorVLMScraper(BaseScraper):
    """
    VLM-driven Glassdoor scraper using visual automation
    for all interactions and Playwright for DOM extraction.
    """

    def __init__(
        self,
        proxies: Optional[List[str]] = None,
        use_proxies: bool = True,
        proxy_session: Optional[str] = None,
    ):
        super().__init__("glassdoor_vlm", proxies=proxies, use_proxies=use_proxies)

        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self._context: Optional[BrowserContext] = None
        self.vlm_agent = None
        self.vlm_available = False

        self._init_vlm()

    def _init_vlm(self) -> bool:
        """Initialize VLM components."""
        try:
            from src.vlm import Agent, config as vlm_config

            self._Agent = Agent
            self._vlm_config = vlm_config
            self.vlm_available = True
            logger.info("VLM components loaded")
            return True

        except ImportError as e:
            logger.warning(f"VLM not available: {e}")
            self.vlm_available = False
            return False

    def _start_browser(self) -> bool:
        """Get or create the singleton browser for Glassdoor."""
        try:
            self.browser, self._context, self.page = get_singleton_browser()
            logger.info("Browser page created successfully")
            print("[VLM] Browser page ready", flush=True)
            return True
        except Exception as e:
            logger.error(f"Failed to start browser: {e}")
            print(f"[VLM] Browser start error: {e}", flush=True)
            return False

    def _maximize_and_focus_browser(self):
        """Maximize browser window and bring to foreground using Windows API."""
        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.windll.user32

            def get_chrome_window():
                windows = []
                def enum_callback(hwnd, _):
                    if user32.IsWindowVisible(hwnd):
                        length = user32.GetWindowTextLengthW(hwnd)
                        if length > 0:
                            buff = ctypes.create_unicode_buffer(length + 1)
                            user32.GetWindowTextW(hwnd, buff, length + 1)
                            title = buff.value
                            if any(x in title for x in ["Chromium", "Glassdoor", "Jobs", "Chrome"]):
                                windows.append(hwnd)
                    return True

                WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
                user32.EnumWindows(WNDENUMPROC(enum_callback), 0)
                return windows[0] if windows else None

            hwnd = get_chrome_window()
            if hwnd:
                user32.ShowWindow(hwnd, 3)  # SW_MAXIMIZE
                user32.SetForegroundWindow(hwnd)
                time.sleep(0.3)
                print("[VLM] Browser window maximized and focused", flush=True)
            else:
                print("[VLM] Could not find browser window", flush=True)
        except Exception as e:
            print(f"[VLM] Could not maximize browser: {e}", flush=True)

    def _stop_browser(self):
        """Close the current page (browser stays open for reuse)."""
        try:
            if self.page:
                self.page.close()
                print("[VLM] Page closed (browser remains open for reuse)", flush=True)
        except:
            pass
        finally:
            self.page = None

    def _wait_for_page_load(self, timeout: int = 15000):
        """
        Wait for the page to fully load with job listings.

        Args:
            timeout: Maximum time to wait in milliseconds
        """
        print("[VLM] Waiting for page to load...", flush=True)

        # List of selectors that indicate the page has loaded
        job_selectors = [
            '[data-test="jobListing"]',
            '.JobsList_jobListItem__JBBUV',
            '.react-job-listing',
            'li[data-id]',
        ]

        # Try to wait for any job listing selector
        for selector in job_selectors:
            try:
                self.page.wait_for_selector(selector, timeout=timeout)
                print(f"[VLM] Page loaded - found {selector}", flush=True)
                # Additional small wait for dynamic content
                time.sleep(1)
                return
            except:
                continue

        # If no job listings found, wait a bit and check for captcha/error
        print("[VLM] No job selectors found, waiting for any content...", flush=True)
        time.sleep(3)

    def scrape(
        self,
        search_term: str,
        location: str,
        results_wanted: int = 10,
        hours_old: Optional[int] = None,
        is_remote: Optional[bool] = None,
        **kwargs,
    ) -> List[JobPost]:
        """
        Scrape jobs from Glassdoor using direct URL navigation.
        VLM is only used if a captcha is encountered.
        """
        print(f"[VLM] Starting Glassdoor scrape: '{search_term}' in '{location}'", flush=True)
        logger.info(f"Starting Glassdoor scrape: '{search_term}' in '{location}'")

        jobs = []

        try:
            # Start browser
            print("[VLM] Starting browser...", flush=True)
            if not self._start_browser():
                print("[VLM] Browser start failed, using fallback", flush=True)
                return self._fallback_scrape(search_term, location, results_wanted, hours_old, is_remote, **kwargs)
            print("[VLM] Browser started", flush=True)

            # Build search URL directly (skip homepage navigation)
            search_url = build_glassdoor_search_url(search_term, location)
            print(f"[VLM] Navigating directly to search: {search_url}", flush=True)

            # Navigate and wait for DOM to be ready
            self.page.goto(search_url, wait_until="domcontentloaded", timeout=60000)
            print(f"[VLM] Initial load complete: {self.page.url}", flush=True)

            # Wait for job listings to appear (with timeout)
            self._wait_for_page_load()

            # Maximize and focus browser
            self._maximize_and_focus_browser()

            # Check if we hit a captcha
            if self._is_captcha_page():
                print("[VLM] Captcha detected, using VLM to solve...", flush=True)

                # Initialize VLM agent only if needed
                if not self._init_vlm_agent():
                    print("[VLM] VLM init failed, using fallback", flush=True)
                    return self._fallback_scrape(search_term, location, results_wanted, hours_old, is_remote, **kwargs)

                # Use VLM to solve captcha
                if not self._solve_captcha_with_vlm():
                    print("[VLM] Captcha solving failed, using fallback", flush=True)
                    return self._fallback_scrape(search_term, location, results_wanted, hours_old, is_remote, **kwargs)

                print("[VLM] Captcha solved!", flush=True)

            # Verify we have search results
            if not self._check_search_complete():
                print("[VLM] No search results found, trying to wait...", flush=True)
                time.sleep(3)

                if not self._check_search_complete():
                    print("[VLM] Still no results, using fallback", flush=True)
                    return self._fallback_scrape(search_term, location, results_wanted, hours_old, is_remote, **kwargs)

            # Extract jobs using DOM
            print("[VLM] Extracting jobs from DOM...", flush=True)
            jobs = self._extract_jobs_from_dom(results_wanted)

            print(f"[VLM] Extracted {len(jobs)} jobs", flush=True)
            logger.info(f"Extracted {len(jobs)} jobs")
            return jobs

        except Exception as e:
            logger.error(f"Scraping failed: {e}")
            import traceback
            traceback.print_exc()
            return self._fallback_scrape(search_term, location, results_wanted, hours_old, is_remote, **kwargs)

        finally:
            self._stop_browser()
            if self.vlm_agent:
                try:
                    self.vlm_agent.shutdown()
                except:
                    pass
                self.vlm_agent = None

    def _init_vlm_agent(self) -> bool:
        """Initialize the VLM agent."""
        if not self.vlm_available:
            return False

        try:
            if self.vlm_agent is None:
                self.vlm_agent = self._Agent(self._vlm_config)
                if not self.vlm_agent.initialize():
                    logger.error("Failed to initialize VLM agent")
                    return False
            return True
        except Exception as e:
            logger.error(f"VLM agent init error: {e}")
            return False

    def _solve_captcha_with_vlm(self, max_attempts: int = 3) -> bool:
        """Use VLM to solve captcha."""
        from .vlm_prompts import CAPTCHA_SOLVE_PROMPT

        print("[VLM] Starting captcha solving...", flush=True)

        for attempt in range(max_attempts):
            print(f"[VLM] Captcha attempt {attempt + 1}/{max_attempts}", flush=True)

            # Focus browser for VLM
            self._maximize_and_focus_browser()
            time.sleep(1)

            try:
                # Run VLM with captcha prompt
                result = self.vlm_agent.run(
                    task=CAPTCHA_SOLVE_PROMPT,
                    max_actions=15,
                )
                print(f"[VLM] VLM result: {result}", flush=True)

                # Wait for page to update
                time.sleep(3)

                # Check if captcha is solved
                if not self._is_captcha_page():
                    print("[VLM] Captcha appears to be solved!", flush=True)
                    return True

            except Exception as e:
                logger.error(f"Captcha solving error: {e}")
                print(f"[VLM] Error: {e}", flush=True)

        print("[VLM] Failed to solve captcha after all attempts", flush=True)
        return False

    def _check_search_complete(self) -> bool:
        """Check if search stage is complete (results visible)."""
        try:
            # Check for job listings
            job_selectors = [
                '[data-test="jobListing"]',
                '.JobsList_jobListItem__JBBUV',
                '.react-job-listing',
                'li[data-id]',
                '.JobCard',
            ]
            for selector in job_selectors:
                elements = self.page.query_selector_all(selector)
                if elements and len(elements) > 0:
                    print(f"[VLM] Search checkpoint: found {len(elements)} job cards", flush=True)
                    return True

            # Also check URL for search results
            if "/Job/" in self.page.url and ("keyword" in self.page.url.lower() or "jobs" in self.page.url.lower()):
                print("[VLM] Search checkpoint: URL indicates search results", flush=True)
                return True

            return False
        except:
            return False

    def _is_captcha_page(self) -> bool:
        """Check if current page is a captcha/challenge page."""
        try:
            # First check: if we have normal page content, not a captcha
            normal_selectors = [
                '[data-test="search-bar"]',
                'input[id*="keyword"]',
                '.JobCard',
                '[data-test="jobListing"]',
                'header nav',
            ]
            for selector in normal_selectors:
                if self.page.query_selector(selector):
                    return False

            # Check for captcha indicators
            captcha_selectors = [
                "#challenge-running",
                "#challenge-stage",
                ".cf-browser-verification",
                "iframe[src*='challenges.cloudflare.com']",
            ]
            for selector in captcha_selectors:
                if self.page.query_selector(selector):
                    return True

            # Check content
            content = self.page.content().lower()
            captcha_phrases = [
                "verify you are human",
                "checking your browser",
                "i'm not a robot",
                "recaptcha",
                "hcaptcha",
            ]
            for phrase in captcha_phrases:
                if phrase in content:
                    return True

            return False
        except:
            return False

    def _extract_jobs_from_dom(self, results_wanted: int) -> List[JobPost]:
        """Extract job listings from the page DOM."""
        jobs = []
        page_num = 1
        max_pages = 10

        while len(jobs) < results_wanted and page_num <= max_pages:
            print(f"[VLM] Extracting jobs from page {page_num}...", flush=True)

            page_jobs = self._extract_job_cards()
            jobs.extend(page_jobs)
            print(f"[VLM] Found {len(page_jobs)} jobs on page {page_num}", flush=True)

            if len(jobs) >= results_wanted:
                break

            if not self._go_to_next_page():
                break

            page_num += 1
            time.sleep(2)

        return jobs[:results_wanted]

    def _extract_job_cards(self) -> List[JobPost]:
        """Extract job data from job cards on the current page."""
        # Use JavaScript extraction - more reliable than DOM selectors
        # since Glassdoor uses dynamic class names
        print("[VLM] Using JavaScript extraction for reliability...", flush=True)
        return self._extract_jobs_via_js()

    def _parse_job_card(self, card) -> Optional[JobPost]:
        """Parse a single job card element into a JobPost."""
        try:
            # Extract title
            title_el = card.query_selector('[data-test="job-title"], .JobCard_jobTitle__GLyJ1, .job-title, a[data-test="job-link"]')
            title = title_el.inner_text().strip() if title_el else None

            if not title:
                return None

            # Extract company
            company_el = card.query_selector('[data-test="employer-name"], .EmployerProfile_compactEmployerName__9MGcV, .employer-name')
            company = company_el.inner_text().strip() if company_el else "Unknown"

            # Extract location
            location_el = card.query_selector('[data-test="emp-location"], .JobCard_location__Ds1fM, .location')
            location = location_el.inner_text().strip() if location_el else ""

            # Extract salary if available
            salary_el = card.query_selector('[data-test="detailSalary"], .JobCard_salaryEstimate__QpbTW, .salary-estimate')
            salary = salary_el.inner_text().strip() if salary_el else None

            # Extract job URL
            link_el = card.query_selector('a[href*="/job-listing/"], a[data-test="job-link"]')
            job_url = link_el.get_attribute("href") if link_el else ""
            if job_url and not job_url.startswith("http"):
                job_url = f"https://www.glassdoor.com{job_url}"

            return JobPost(
                title=title,
                company=company,
                location=location,
                job_url=job_url or "https://glassdoor.com",
                site="glassdoor",
                date_posted=datetime.now().isoformat(),
                salary_min=self._parse_salary(salary)[0] if salary else None,
                salary_max=self._parse_salary(salary)[1] if salary else None,
                description="",
            )

        except Exception as e:
            logger.debug(f"Error parsing job card: {e}")
            return None

    def _extract_jobs_via_js(self) -> List[JobPost]:
        """Extract jobs using JavaScript evaluation."""
        try:
            # First, debug what's in the cards
            debug_info = self.page.evaluate("""
                () => {
                    const cards = document.querySelectorAll('[data-test="jobListing"], .react-job-listing, li[data-id]');
                    if (cards.length > 0) {
                        const firstCard = cards[0];
                        return {
                            cardCount: cards.length,
                            innerHTML: firstCard.innerHTML.substring(0, 500),
                            links: Array.from(firstCard.querySelectorAll('a')).map(a => ({
                                text: a.textContent.trim().substring(0, 50),
                                href: a.href,
                                className: a.className
                            })).slice(0, 5),
                            divs: Array.from(firstCard.querySelectorAll('div')).map(d => ({
                                className: d.className,
                                text: d.textContent.trim().substring(0, 30)
                            })).slice(0, 10)
                        };
                    }
                    return {cardCount: 0};
                }
            """)
            print(f"[VLM] Debug - Card count: {debug_info.get('cardCount', 0)}", flush=True)
            if debug_info.get('links'):
                print(f"[VLM] Debug - First card links: {debug_info['links']}", flush=True)

            # Extract jobs with flexible selectors
            jobs_data = self.page.evaluate("""
                () => {
                    const jobs = [];
                    const cards = document.querySelectorAll('[data-test="jobListing"], .react-job-listing, li[data-id]');

                    cards.forEach(card => {
                        // Try multiple strategies to find the job title
                        let title = '';
                        let jobUrl = '';

                        // Strategy 1: Look for job link with href containing "job-listing"
                        const jobLink = card.querySelector('a[href*="job-listing"], a[href*="/partner/"]');
                        if (jobLink) {
                            title = jobLink.textContent.trim();
                            jobUrl = jobLink.href;
                        }

                        // Strategy 2: If no title, find the first substantial link
                        if (!title) {
                            const links = card.querySelectorAll('a');
                            for (const link of links) {
                                const text = link.textContent.trim();
                                // Skip short text (likely icons) and common patterns
                                if (text.length > 3 && !text.includes('Easy Apply') && !text.match(/^\\d/)) {
                                    title = text;
                                    jobUrl = link.href || jobUrl;
                                    break;
                                }
                            }
                        }

                        // Strategy 3: Look for any h2/h3 or role/heading element
                        if (!title) {
                            const heading = card.querySelector('h2, h3, [role="heading"]');
                            if (heading) {
                                title = heading.textContent.trim();
                            }
                        }

                        // Find company - look for employer-related classes or second link
                        let company = 'Unknown';
                        const companyEl = card.querySelector('[class*="employer"], [class*="company"], [data-test*="employer"]');
                        if (companyEl) {
                            company = companyEl.textContent.trim();
                        } else {
                            // Try to find company from text patterns
                            const allText = card.textContent;
                            const links = Array.from(card.querySelectorAll('a'));
                            if (links.length > 1) {
                                // Second link often is the company
                                company = links[1].textContent.trim() || 'Unknown';
                            }
                        }

                        // Find location
                        let location = '';
                        const locationEl = card.querySelector('[class*="location"], [data-test*="location"]');
                        if (locationEl) {
                            location = locationEl.textContent.trim();
                        }

                        // Find salary if present
                        let salary = '';
                        const salaryEl = card.querySelector('[class*="salary"], [data-test*="salary"]');
                        if (salaryEl) {
                            salary = salaryEl.textContent.trim();
                        }

                        if (title && title.length > 2) {
                            jobs.push({
                                title: title.substring(0, 200),
                                company: company.substring(0, 100),
                                location: location.substring(0, 100),
                                salary: salary,
                                url: jobUrl
                            });
                        }
                    });
                    return jobs;
                }
            """)

            print(f"[VLM] JS extracted {len(jobs_data)} raw job entries", flush=True)
            if jobs_data and len(jobs_data) > 0:
                print(f"[VLM] First job sample: {jobs_data[0]}", flush=True)

            result = [
                JobPost(
                    title=j["title"],
                    company=j["company"],
                    location=j["location"],
                    job_url=j["url"] or "https://glassdoor.com",
                    site="glassdoor",
                    date_posted=datetime.now().isoformat(),
                    description="",
                )
                for j in jobs_data
                if j.get("title")
            ]
            print(f"[VLM] Created {len(result)} JobPost objects", flush=True)
            return result

        except Exception as e:
            logger.error(f"JS extraction failed: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _parse_salary(self, salary_text: str) -> Tuple[Optional[int], Optional[int]]:
        """Parse salary text into min/max values."""
        if not salary_text:
            return None, None

        import re
        numbers = re.findall(r'\$?([\d,]+)K?', salary_text.replace(',', ''))
        if len(numbers) >= 2:
            min_sal = int(numbers[0]) * (1000 if 'K' in salary_text else 1)
            max_sal = int(numbers[1]) * (1000 if 'K' in salary_text else 1)
            return min_sal, max_sal
        elif len(numbers) == 1:
            sal = int(numbers[0]) * (1000 if 'K' in salary_text else 1)
            return sal, sal
        return None, None

    def _go_to_next_page(self) -> bool:
        """Navigate to the next page of results."""
        try:
            # Get current job count before pagination
            current_count = len(self.page.query_selector_all('[data-test="jobListing"]'))
            print(f"[VLM] Current job count before pagination: {current_count}", flush=True)

            # Try clicking pagination buttons first
            next_selectors = [
                'button[data-test="pagination-next"]',
                'a[data-test="pagination-next"]',
                '[aria-label="Next"]',
                '.nextButton',
                'button:has-text("Next")',
            ]

            for selector in next_selectors:
                try:
                    next_btn = self.page.query_selector(selector)
                    if next_btn and next_btn.is_visible():
                        print(f"[VLM] Clicking pagination button: {selector}", flush=True)
                        next_btn.click()

                        # Wait for page to load new content
                        self._wait_for_page_load(timeout=10000)

                        new_count = len(self.page.query_selector_all('[data-test="jobListing"]'))
                        print(f"[VLM] Job count after pagination: {new_count}", flush=True)

                        if new_count > 0:
                            return True
                except:
                    continue

            # Try "Show more jobs" button
            show_more_selectors = [
                'button[data-test="load-more"]',
                'button:has-text("Show more jobs")',
                '[class*="showMore"]',
            ]

            for selector in show_more_selectors:
                try:
                    show_more = self.page.query_selector(selector)
                    if show_more and show_more.is_visible():
                        print(f"[VLM] Clicking show more: {selector}", flush=True)
                        show_more.click()
                        time.sleep(3)  # Wait for new jobs to load

                        new_count = len(self.page.query_selector_all('[data-test="jobListing"]'))
                        if new_count > current_count:
                            print(f"[VLM] Loaded more jobs: {current_count} -> {new_count}", flush=True)
                            return True
                except:
                    continue

            # Try scrolling to load more (infinite scroll)
            print("[VLM] Trying infinite scroll...", flush=True)
            for _ in range(3):  # Try scrolling a few times
                self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(2)

                new_count = len(self.page.query_selector_all('[data-test="jobListing"]'))
                if new_count > current_count:
                    print(f"[VLM] Loaded more jobs via scroll: {current_count} -> {new_count}", flush=True)
                    return True

            print("[VLM] No more pages available", flush=True)
            return False

        except Exception as e:
            logger.debug(f"Could not go to next page: {e}")
            print(f"[VLM] Pagination error: {e}", flush=True)
            return False

    def _fallback_scrape(
        self,
        search_term: str,
        location: str,
        results_wanted: int,
        hours_old: Optional[int],
        is_remote: Optional[bool],
        **kwargs,
    ) -> List[JobPost]:
        """Fall back to GraphQL scraper."""
        print("[VLM] Falling back to GraphQL scraper", flush=True)
        logger.info("Falling back to GraphQL scraper")

        try:
            from .glassdoor import GlassdoorScraper

            fallback = GlassdoorScraper(
                proxies=self.request_handler.proxies if hasattr(self.request_handler, 'proxies') else None,
                use_proxies=True,
            )

            return fallback.scrape(
                search_term=search_term,
                location=location,
                results_wanted=results_wanted,
                hours_old=hours_old,
                is_remote=is_remote,
                **kwargs,
            )

        except Exception as e:
            logger.error(f"Fallback also failed: {e}")
            return []

    def close(self, close_browser: bool = False):
        """
        Clean up resources.

        Args:
            close_browser: If True, close the singleton browser entirely.
                          If False (default), only close the current page.
        """
        self._stop_browser()
        if self.vlm_agent:
            try:
                self.vlm_agent.shutdown()
            except:
                pass
            self.vlm_agent = None

        if close_browser:
            close_singleton_browser()

        super().close()
