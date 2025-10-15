"""
Glassdoor job board scraper using GraphQL API

This scraper uses Glassdoor's GraphQL API with CSRF token authentication.
Requires initial page visit to obtain token, then makes GraphQL queries.

Based on JobSpy by speedyapply: https://github.com/speedyapply/JobSpy
Copyright (c) 2023 Cullen Watson
Licensed under MIT License. See LICENSE-JOBSPY for details.
"""

import json
import os
import re
import time
import random
import string
import asyncio
import requests
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from markdownify import markdownify as md
from playwright.async_api import async_playwright, Browser, Page
from playwright_stealth import Stealth

from ..models import JobPost
from ..config import (
    GLASSDOOR_API_URL,
    GLASSDOOR_API_HEADERS,
    GLASSDOOR_GRAPHQL_QUERY,
    GLASSDOOR_DESCRIPTION_QUERY,
    GLASSDOOR_FALLBACK_TOKEN,
    RATE_LIMIT_DELAY,
    DEFAULT_PROXIES,
)
from ..utils import create_session
from .base import BaseScraper


class GlassdoorScraper(BaseScraper):
    """Scraper for Glassdoor.com using GraphQL API"""

    def __init__(self, proxies: Optional[List[str]] = None, use_proxies: bool = True, proxy_session: Optional[str] = None):
        super().__init__("glassdoor", proxies=proxies, use_proxies=use_proxies)
        self.api_url = GLASSDOOR_API_URL
        self.api_headers = GLASSDOOR_API_HEADERS.copy()
        self.base_url = "https://www.glassdoor.com"

        # Pagination settings
        self.jobs_per_page = 30
        self.max_pages = 30  # Glassdoor max ~900 jobs

        # Track seen job URLs to avoid duplicates
        self.seen_urls = set()

        # Playwright browser (lazy initialization)
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self._stealth_ctx = None  # Store stealth context manager

        # CSRF token (will be fetched on first scrape)
        self.csrf_token = None

    @staticmethod
    def _generate_session_id(length: int = 10) -> str:
        """
        Generate a random session ID for proxy rotation

        Args:
            length: Length of session ID

        Returns:
            Random alphanumeric session ID
        """
        return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

    def _build_session_proxy(self, base_proxy_url: str, session_id: Optional[str] = None) -> str:
        """
        Build proxy URL with IPRoyal session ID for IP rotation

        IPRoyal format: http://username:password_country-us_session-{id}_lifetime-30m@host:port

        Args:
            base_proxy_url: Base proxy URL (http://username:password@host:port)
            session_id: Optional session ID (generates random if None)

        Returns:
            Proxy URL with session parameters embedded in password field
        """
        if not session_id:
            return base_proxy_url

        # Parse the proxy URL
        if "@" in base_proxy_url:
            protocol_and_auth, host_and_port = base_proxy_url.split("@", 1)
            protocol, auth = protocol_and_auth.split("://", 1)
            username, password = auth.split(":", 1)

            # Add session parameters to password (IPRoyal format)
            password_with_session = f"{password}_country-us_session-{session_id}_lifetime-30m"

            # Rebuild proxy URL
            proxy_url = f"{protocol}://{username}:{password_with_session}@{host_and_port}"

            if os.getenv("DEBUG", "false").lower() == "true":
                masked_proxy = f"{protocol}://{username}:****_country-us_session-{session_id}_lifetime-30m@{host_and_port}"
                print(f"[INFO] Built session proxy: {masked_proxy}")

            return proxy_url
        else:
            return base_proxy_url

    async def _ensure_browser(self) -> Page:
        """
        Ensure Playwright browser is running with stealth mode

        Returns:
            Playwright Page object
        """
        if self.page and not self.page.is_closed():
            return self.page

        # Start Playwright with stealth context manager
        if not self.playwright:
            # Create and enter stealth context manager
            self._stealth_ctx = Stealth().use_async(async_playwright())
            self.playwright = await self._stealth_ctx.__aenter__()

        # Launch browser
        if not self.browser:
            self.browser = await self.playwright.chromium.launch(
                headless=True,  # Set to False for debugging
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                ]
            )

        # Create context
        self.context = await self.browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        # Create page - stealth is automatically applied!
        self.page = await self.context.new_page()

        return self.page

    async def _close_browser(self):
        """Close Playwright browser and cleanup resources"""
        try:
            if self.page:
                try:
                    if not self.page.is_closed():
                        await self.page.close()
                except Exception:
                    pass  # Already closed or connection lost

            if self.context:
                try:
                    await self.context.close()
                except Exception:
                    pass

            if self.browser:
                try:
                    await self.browser.close()
                except Exception:
                    pass

            # Exit stealth context manager properly
            if self._stealth_ctx and self.playwright:
                try:
                    await self._stealth_ctx.__aexit__(None, None, None)
                except Exception:
                    pass
            elif self.playwright:
                # Fallback if no stealth context
                try:
                    await self.playwright.stop()
                except Exception:
                    pass
        finally:
            # Always reset to None
            self.page = None
            self.context = None
            self.browser = None
            self.playwright = None
            self._stealth_ctx = None

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
        Scrape job postings from Glassdoor using GraphQL API with Playwright

        Synchronous wrapper for async implementation

        Args:
            search_term: Job title or keywords
            location: Geographic location (or "Remote")
            results_wanted: Number of results to retrieve
            hours_old: Filter jobs posted within X hours
            is_remote: Filter for remote jobs
            **kwargs: Additional parameters

        Returns:
            List of JobPost objects
        """
        return asyncio.run(self._scrape_async(
            search_term, location, results_wanted, hours_old, is_remote, **kwargs
        ))

    async def _scrape_async(
        self,
        search_term: str,
        location: str,
        results_wanted: int = 10,
        hours_old: Optional[int] = None,
        is_remote: Optional[bool] = None,
        **kwargs,
    ) -> List[JobPost]:
        """Actual async scraping implementation"""
        jobs = []

        try:
            print(f"[INFO] Scraping Glassdoor for '{search_term}' in '{location}'...")

            # Get CSRF token
            if not self.csrf_token:
                self.csrf_token = await self._get_csrf_token()
                if self.csrf_token:
                    self.api_headers["gd-csrf-token"] = self.csrf_token
                else:
                    print("[ERROR] Failed to get CSRF token")
                    return jobs

            # Resolve location to Glassdoor location ID and type
            location_id, location_type = await self._get_location_id(location, is_remote)

            if not location_id or not location_type:
                print("[ERROR] Failed to resolve location")
                return jobs

            # Calculate page range
            range_start = 1
            range_end = min((results_wanted // self.jobs_per_page) + 2, self.max_pages + 1)

            cursor = None

            for page_num in range(range_start, range_end):
                cursor_type = "cursor-based" if (cursor and not cursor.startswith("__page_")) else "page-based"
                print(f"[INFO] Fetching page {page_num}/{range_end - 1} ({cursor_type} pagination)")

                # Fetch jobs for this page
                page_jobs, cursor = await self._fetch_jobs_page(
                    search_term=search_term,
                    location_id=location_id,
                    location_type=location_type,
                    page_num=page_num,
                    cursor=cursor,
                    hours_old=hours_old,
                )

                if not page_jobs:
                    print(f"[INFO] No jobs returned for page {page_num}")
                    # If this is the first page with no jobs, stop
                    # Otherwise, might be a temporary issue, continue
                    if page_num == range_start:
                        print("[ERROR] No jobs found on first page, stopping")
                        break
                    else:
                        print("[WARNING] Empty page encountered, stopping pagination")
                        break

                print(f"[SUCCESS] Retrieved {len(page_jobs)} jobs from page {page_num} (total: {len(jobs) + len(page_jobs)})")
                jobs.extend(page_jobs)

                if len(jobs) >= results_wanted:
                    print(f"[SUCCESS] Reached target of {results_wanted} jobs")
                    jobs = jobs[:results_wanted]
                    break

                if not cursor:
                    print("[INFO] No more pages available (no cursor returned)")
                    break

                # Rate limiting - use longer delay for Glassdoor to avoid 429 errors
                # Glassdoor is more aggressive with rate limiting than other sites
                glassdoor_delay = max(RATE_LIMIT_DELAY, 5.0)  # Minimum 5 seconds between pages
                print(f"[INFO] Waiting {glassdoor_delay}s before next page...")
                await asyncio.sleep(glassdoor_delay)

            print(f"[SUCCESS] Successfully scraped {len(jobs)} jobs from Glassdoor")
            return jobs[:results_wanted]

        finally:
            # Clean up browser resources
            await self._close_browser()

    async def _get_csrf_token(self) -> Optional[str]:
        """
        Fetch CSRF token using Playwright browser

        Returns:
            CSRF token string or None if failed
        """
        try:
            page = await self._ensure_browser()

            # Build search URL
            keyword = "software-engineer"
            location = "remote-us"
            location_id = 11047

            loc_start, loc_end = 0, len(location)
            keyword_start = len(location) + 1
            keyword_end = keyword_start + len(keyword)

            url = f"{self.base_url}/Job/{location}-{keyword}-jobs-SRCH_IL.{loc_start},{loc_end}_IS{location_id}_KO{keyword_start},{keyword_end}.htm"

            print(f"→ Navigating to Glassdoor page for token extraction...")

            # Navigate to page
            response = await page.goto(url, wait_until="networkidle", timeout=30000)

            if response.status != 200:
                print(f"[WARNING] Page returned status {response.status}")
                return None

            # Wait for JavaScript execution
            await page.wait_for_timeout(3000)

            # Extract token from HTML
            html_content = await page.content()

            # Try multiple regex patterns (handles escaped quotes)
            patterns = [
                (r'\\"?token\\"?\s*:\s*\\"([^\\"]+)\\"', "JSON token field (escaped quotes)"),
                (r'"token"\s*:\s*"([^"]+)"', "JSON token field (normal quotes)"),
                (r'window\.__INITIAL_STATE__\s*=\s*.*?\\"token\\":\s*\\"([^\\"]+)\\"', "Initial state (escaped)"),
                (r'window\.__INITIAL_STATE__\s*=\s*.*?"token":\s*"([^"]+)"', "Initial state (normal)"),
            ]

            for pattern, description in patterns:
                matches = re.findall(pattern, html_content, re.DOTALL)
                if matches:
                    token = matches[0]
                    print(f"[SUCCESS] Retrieved CSRF token using {description}: {token[:20]}...")
                    return token

            # Fallback: JavaScript extraction
            print("→ Trying JavaScript extraction...")
            js_token = await page.evaluate("""() => {
                if (window.__INITIAL_STATE__ && window.__INITIAL_STATE__.token) {
                    return window.__INITIAL_STATE__.token;
                }
                const scripts = document.querySelectorAll('script');
                for (let script of scripts) {
                    const match = script.textContent.match(/"token"\\s*:\\s*"([^"]+)"/);
                    if (match) return match[1];
                }
                return null;
            }""")

            if js_token:
                print(f"[SUCCESS] Retrieved CSRF token via JavaScript: {js_token[:20]}...")
                return js_token

            print("[WARNING] Could not find CSRF token")
            return None

        except Exception as e:
            print(f"[ERROR] Error fetching CSRF token: {e}")
            return None

    async def _get_location_id(self, location: str, is_remote: Optional[bool] = None) -> Tuple[Optional[int], Optional[str]]:
        """
        Resolve location string to Glassdoor location ID and type

        Args:
            location: Location string (e.g., "San Francisco, CA")
            is_remote: Whether searching for remote jobs

        Returns:
            Tuple of (location_id, location_type) or (None, None) if failed
        """
        # Handle remote/no location
        if not location or is_remote or location.lower() == "remote":
            return 11047, "STATE"  # Remote location ID

        try:
            page = await self._ensure_browser()

            url = f"{self.base_url}/findPopularLocationAjax.htm?maxLocationsToReturn=10&term={location}"

            # Use page.evaluate to make the API call
            api_result = await page.evaluate("""async (url) => {
                try {
                    const response = await fetch(url, {
                        method: 'GET',
                        credentials: 'include'
                    });

                    const data = await response.text();

                    return {
                        status: response.status,
                        body: data
                    };
                } catch (error) {
                    return {
                        status: 0,
                        error: error.toString()
                    };
                }
            }""", url)

            status = api_result.get("status", 0)

            if status != 200:
                if status == 429:
                    print("[ERROR] Rate limited by Glassdoor (429)")
                else:
                    print(f"[ERROR] Location lookup failed: {status}")
                return None, None

            items = json.loads(api_result.get("body", "[]"))

            if not items:
                print(f"[WARNING] Location '{location}' not found, using remote")
                return 11047, "STATE"

            # Get first match
            location_id = int(items[0]["locationId"])
            location_type = items[0]["locationType"]

            # Map location type codes to enum
            type_map = {
                "C": "CITY",
                "S": "STATE",
                "N": "COUNTRY",
            }
            location_type = type_map.get(location_type, "CITY")

            print(f"[INFO] Resolved location: ID={location_id}, Type={location_type}")
            return location_id, location_type

        except Exception as e:
            print(f"[ERROR] Error resolving location: {e}")
            return None, None

    async def _fetch_jobs_page(
        self,
        search_term: str,
        location_id: int,
        location_type: str,
        page_num: int,
        cursor: Optional[str] = None,
        hours_old: Optional[int] = None,
    ) -> Tuple[List[JobPost], Optional[str]]:
        """
        Fetch a single page of jobs from Glassdoor

        Args:
            search_term: Job search keywords
            location_id: Glassdoor location ID
            location_type: Location type (CITY, STATE, COUNTRY)
            page_num: Page number (1-indexed)
            cursor: Pagination cursor from previous page
            hours_old: Filter for jobs posted within X hours

        Returns:
            Tuple of (job list, next cursor)
        """
        jobs = []

        try:
            # Build GraphQL payload
            payload = self._build_graphql_payload(
                search_term=search_term,
                location_id=location_id,
                location_type=location_type,
                page_num=page_num,
                cursor=cursor,
                hours_old=hours_old,
            )

            # Make GraphQL request
            response_data = await self._make_graphql_request(payload)

            if not response_data:
                return jobs, None

            # Extract job listings
            job_listings_data = response_data.get("data", {}).get("jobListings", {})
            job_listings = job_listings_data.get("jobListings", [])

            if not job_listings:
                return jobs, None

            # Process jobs sequentially (async)
            for job_data in job_listings:
                try:
                    job_post = await self._process_job(job_data)
                    if job_post:
                        jobs.append(job_post)
                except Exception as e:
                    print(f"[WARNING] Error processing job: {e}")
                    continue

            # Get next page cursor
            pagination_cursors = job_listings_data.get("paginationCursors", [])

            # Debug logging for pagination
            if os.getenv("DEBUG", "false").lower() == "true":
                print(f"\n[INFO] Pagination Debug (Page {page_num}):")
                print(f"  Total cursors available: {len(pagination_cursors)}")
                print(f"  Looking for page: {page_num + 1}")
                if pagination_cursors:
                    print(f"  Available pages: {[c.get('pageNumber') for c in pagination_cursors]}")
                    print(f"  Cursor sample: {pagination_cursors[0] if pagination_cursors else 'None'}")

            next_cursor = self._get_cursor_for_page(pagination_cursors, page_num + 1)

            # Fallback: If no cursor found but we have jobs, try to continue anyway
            # This handles cases where API doesn't provide cursors but supports page numbers
            if not next_cursor and jobs and page_num < self.max_pages:
                print(f"[INFO] No cursor for page {page_num + 1}, attempting fallback pagination")
                # Return a sentinel value to indicate we should try the next page
                # The scraper will use page numbers instead
                next_cursor = f"__page_{page_num + 1}__"

            return jobs, next_cursor

        except Exception as e:
            print(f"[ERROR] Error fetching jobs page: {e}")
            return jobs, None

    def _build_graphql_payload(
        self,
        search_term: str,
        location_id: int,
        location_type: str,
        page_num: int,
        cursor: Optional[str] = None,
        hours_old: Optional[int] = None,
    ) -> str:
        """
        Build GraphQL query payload for job search

        Args:
            search_term: Job search keywords
            location_id: Glassdoor location ID
            location_type: Location type enum
            page_num: Page number
            cursor: Pagination cursor (or None for page-based pagination)
            hours_old: Filter for job age

        Returns:
            JSON string payload
        """
        # Build filter parameters
        filter_params = []

        if hours_old:
            # Convert hours to days (minimum 1 day)
            days = max(1, hours_old // 24)
            filter_params.append({"filterKey": "fromAge", "values": str(days)})

        # Handle fallback cursor (sentinel value for page-based pagination)
        # If cursor starts with "__page_", it's our fallback - use None instead
        actual_cursor = None if (cursor and cursor.startswith("__page_")) else cursor

        # Build variables
        variables = {
            "excludeJobListingIds": [],
            "keyword": search_term,
            "locationId": location_id,
            "locationType": location_type,
            "numJobsToShow": self.jobs_per_page,
            "pageNumber": page_num,
            "pageCursor": actual_cursor,  # Will be None for fallback pagination
            "filterParams": filter_params,
            "parameterUrlInput": f"IL.0,12_I{location_type}{location_id}",
            "seoUrl": False,
        }

        payload = {
            "operationName": "JobSearchResultsQuery",
            "variables": variables,
            "query": GLASSDOOR_GRAPHQL_QUERY,
        }

        return json.dumps([payload])

    async def _make_graphql_request(self, payload: str, retry_count: int = 0, max_retries: int = 3) -> Optional[Dict]:
        """
        Make a GraphQL API request using Playwright browser context with retry logic

        Args:
            payload: JSON payload string
            retry_count: Current retry attempt (internal use)
            max_retries: Maximum number of retries for rate limiting

        Returns:
            Parsed JSON response or None on failure
        """
        try:
            page = await self._ensure_browser()

            # Parse payload to dict
            payload_dict = json.loads(payload)

            # Execute fetch inside browser context
            api_result = await page.evaluate("""async (args) => {
                const { url, token, payload } = args;

                try {
                    const response = await fetch(url, {
                        method: 'POST',
                        headers: {
                            'accept': '*/*',
                            'accept-language': 'en-US,en;q=0.9',
                            'apollographql-client-name': 'job-search-next',
                            'apollographql-client-version': '4.65.5',
                            'content-type': 'application/json',
                            'gd-csrf-token': token,
                        },
                        body: JSON.stringify(payload),
                        credentials: 'include'
                    });

                    const data = await response.text();

                    return {
                        status: response.status,
                        body: data
                    };
                } catch (error) {
                    return {
                        status: 0,
                        error: error.toString()
                    };
                }
            }""", {
                "url": self.api_url,
                "token": self.csrf_token,
                "payload": payload_dict
            })

            status = api_result.get("status", 0)

            if status == 200:
                body = api_result.get("body", "")
                return json.loads(body)[0]  # Glassdoor returns array
            elif status == 429 and retry_count < max_retries:
                # Rate limited - implement exponential backoff
                wait_time = (2 ** retry_count) * 5  # 5s, 10s, 20s
                print(f"[WARNING] Rate limited (429). Retrying in {wait_time}s (attempt {retry_count + 1}/{max_retries})...")
                await asyncio.sleep(wait_time)
                # Retry with incremented counter
                return await self._make_graphql_request(payload, retry_count + 1, max_retries)
            else:
                print(f"[ERROR] API request failed with status {status}")
                if os.getenv("DEBUG", "false").lower() == "true":
                    print(f"Response: {api_result.get('body', 'N/A')[:200]}")
                return None

        except Exception as e:
            print(f"[ERROR] Error making API request: {e}")
            return None

    def _get_cursor_for_page(self, pagination_cursors: List[Dict], page_num: int) -> Optional[str]:
        """
        Extract cursor token for a specific page number

        Args:
            pagination_cursors: List of cursor objects
            page_num: Target page number

        Returns:
            Cursor string or None
        """
        for cursor_data in pagination_cursors:
            if cursor_data.get("pageNumber") == page_num:
                return cursor_data.get("cursor")
        return None

    async def _process_job(self, job_data: Dict) -> Optional[JobPost]:
        """
        Process a single job listing

        Args:
            job_data: Job data from GraphQL response

        Returns:
            JobPost object or None
        """
        try:
            jobview = job_data.get("jobview", {})
            header = jobview.get("header", {})
            job = jobview.get("job", {})
            overview = jobview.get("overview", {})

            # Debug logging for missing fields (enabled with DEBUG=true in .env)
            if os.getenv("DEBUG", "false").lower() == "true":
                job_title = header.get("jobTitleText", "Unknown")
                print(f"\n[INFO] Processing job: {job_title}")

                # Log null/missing critical fields
                if not header.get("employerNameFromSearch") and not (header.get("employer", {}).get("name")):
                    print("  [WARNING]  Missing company name (both employerNameFromSearch and employer.name)")
                if not header.get("payPeriodAdjustedPay"):
                    print("  [WARNING]  Missing salary data (payPeriodAdjustedPay)")
                if not header.get("locationName"):
                    print("  [WARNING]  Missing location data")
                if not job.get("description"):
                    print("  [INFO]  Description will be fetched separately")
                if not header.get("rating"):
                    print("  [INFO]  No company rating available")

            # Extract basic info
            job_id = job.get("listingId")
            if not job_id:
                return None

            job_url = f"{self.base_url}/job-listing/j?jl={job_id}"

            # Skip if already seen
            if job_url in self.seen_urls:
                return None
            self.seen_urls.add(job_url)

            title = header.get("jobTitleText") or job.get("jobTitleText")

            # Company name fallback chain (employerNameFromSearch may differ from actual employer)
            # Priority: employerNameFromSearch → employer.name → employer.shortName → "Unknown Company"
            employer_obj = header.get("employer", {})
            company = (
                header.get("employerNameFromSearch") or
                (employer_obj.get("name") if employer_obj else None) or
                (employer_obj.get("shortName") if employer_obj else None) or
                "Unknown Company"
            )

            location_name = header.get("locationName", "")
            location_type_code = header.get("locationType", "")

            # Determine if remote
            remote = (location_type_code == "S")  # S = remote in Glassdoor

            # Parse location for non-remote jobs
            location = location_name if not remote else "Remote"
            location_city = None
            location_state = None

            if not remote and location_name:
                # Parse "City, State" format with defensive type checking
                try:
                    if ", " in location_name:
                        parts = location_name.split(", ")
                        location_city = parts[0].strip() if len(parts) > 0 else None
                        location_state = parts[1].strip() if len(parts) > 1 else None
                except (AttributeError, IndexError, TypeError):
                    location_city = None
                    location_state = None

            # Date posted calculation
            age_in_days = header.get("ageInDays")
            date_posted = None
            if age_in_days is not None:
                date_diff = datetime.now() - timedelta(days=age_in_days)
                date_posted = str(date_diff.date())

            # Salary information (p10/p90 percentiles)
            salary_min = None
            salary_max = None
            salary_currency = None
            salary_period = None

            pay_period = header.get("payPeriod")
            pay_currency = header.get("payCurrency")
            adjusted_pay = header.get("payPeriodAdjustedPay")

            if pay_period and adjusted_pay:
                # Use p10 (10th percentile) as min, p90 (90th percentile) as max
                # Defensive type conversion with proper None handling
                try:
                    p10 = adjusted_pay.get("p10")
                    p90 = adjusted_pay.get("p90")
                    salary_min = int(p10) if p10 is not None else None
                    salary_max = int(p90) if p90 is not None else None
                except (ValueError, TypeError):
                    salary_min = None
                    salary_max = None

                salary_currency = pay_currency or "USD"

                # Map pay period to our format
                period_map = {
                    "ANNUAL": "yearly",
                    "MONTHLY": "monthly",
                    "WEEKLY": "weekly",
                    "DAILY": "daily",
                    "HOURLY": "hourly",
                }
                salary_period = period_map.get(pay_period, "yearly")

            # Company information with defensive type checking
            employer = header.get("employer", {})
            try:
                company_id = int(employer.get("id")) if employer and employer.get("id") else None
            except (ValueError, TypeError):
                company_id = None

            company_url = f"{self.base_url}/Overview/W-EI_IE{company_id}.htm" if company_id else None
            company_logo_url = overview.get("squareLogoUrl")

            # Extract Glassdoor-specific fields
            glassdoor_tracking_key = header.get("jobResultTrackingKey")
            glassdoor_job_link = header.get("jobLink")
            easy_apply = header.get("easyApply", False)

            # Job classification
            occupation_code = header.get("goc")
            occupation_id = header.get("gocId")
            occupation_confidence = header.get("gocConfidence")

            # Enhanced company information with defensive type checking
            company_full_name = employer.get("name") if employer else None
            company_short_name = employer.get("shortName") if employer else None
            company_division = header.get("divisionEmployerName")

            # Rating with type conversion
            try:
                rating_val = header.get("rating")
                company_rating = float(rating_val) if rating_val is not None else None
            except (ValueError, TypeError):
                company_rating = None

            # Salary source
            salary_source = header.get("salarySource")

            # Sponsorship information
            is_sponsored = header.get("sponsored", False)
            sponsorship_level = header.get("adOrderSponsorshipLevel")

            # Enhanced location IDs
            location_id_val = header.get("locId")
            location_country_id = header.get("jobCountryId")

            # Fetch full description (separate API call)
            description = await self._fetch_job_description(job_id)

            # Create JobPost
            return JobPost(
                # Core fields
                title=title,
                company=company,
                location=location,
                job_url=job_url,
                site="glassdoor",
                description=description,
                date_posted=date_posted,
                salary_min=salary_min,
                salary_max=salary_max,
                salary_currency=salary_currency,
                salary_period=salary_period,
                company_url=company_url,
                remote=remote,

                # Enhanced location
                location_city=location_city,
                location_state=location_state,

                # Company enrichment
                company_logo_url=company_logo_url,

                # Glassdoor metadata
                glassdoor_listing_id=job_id,
                glassdoor_tracking_key=glassdoor_tracking_key,
                glassdoor_job_link=glassdoor_job_link,
                easy_apply=easy_apply,

                # Job classification
                occupation_code=occupation_code,
                occupation_id=occupation_id,
                occupation_confidence=occupation_confidence,

                # Enhanced company data
                company_full_name=company_full_name,
                company_short_name=company_short_name,
                company_division=company_division,
                company_rating=company_rating,
                company_glassdoor_id=company_id,

                # Salary enhancement
                salary_source=salary_source,

                # Sponsorship info
                is_sponsored=is_sponsored,
                sponsorship_level=sponsorship_level,

                # Enhanced location IDs
                location_id=location_id_val,
                location_country_id=location_country_id,

                # Note: Glassdoor doesn't provide as much enrichment as Indeed
                # Skills, requirements, benefits would need to be extracted from description
            )

        except Exception as e:
            print(f"[WARNING] Error parsing job: {e}")
            if os.getenv("DEBUG", "false").lower() == "true":
                import traceback
                traceback.print_exc()
            return None

    async def _fetch_job_description(self, job_id: int) -> Optional[str]:
        """
        Fetch full job description for a specific job using Playwright

        Args:
            job_id: Glassdoor job listing ID

        Returns:
            Description text (markdown) or None
        """
        try:
            payload = [{
                "operationName": "JobDetailQuery",
                "variables": {
                    "jl": job_id,
                    "queryString": "q",
                    "pageTypeEnum": "SERP",
                },
                "query": GLASSDOOR_DESCRIPTION_QUERY,
            }]

            # Use _make_graphql_request but need to handle array format
            page = await self._ensure_browser()

            # Execute fetch inside browser context
            api_result = await page.evaluate("""async (args) => {
                const { url, token, payload } = args;

                try {
                    const response = await fetch(url, {
                        method: 'POST',
                        headers: {
                            'accept': '*/*',
                            'accept-language': 'en-US,en;q=0.9',
                            'apollographql-client-name': 'job-search-next',
                            'apollographql-client-version': '4.65.5',
                            'content-type': 'application/json',
                            'gd-csrf-token': token,
                        },
                        body: JSON.stringify(payload),
                        credentials: 'include'
                    });

                    const data = await response.text();

                    return {
                        status: response.status,
                        body: data
                    };
                } catch (error) {
                    return {
                        status: 0,
                        error: error.toString()
                    };
                }
            }""", {
                "url": self.api_url,
                "token": self.csrf_token,
                "payload": payload
            })

            status = api_result.get("status", 0)

            if status == 200:
                body = api_result.get("body", "")
                data = json.loads(body)[0]
                desc_html = data.get("data", {}).get("jobview", {}).get("job", {}).get("description")

                if desc_html:
                    # Convert HTML to markdown
                    return md(desc_html).strip()

            return None

        except Exception as e:
            if os.getenv("DEBUG", "false").lower() == "true":
                print(f"[WARNING] Error fetching description: {e}")
            return None

    def close(self):
        """Close browser and cleanup resources"""
        if self.browser or self.playwright:
            try:
                asyncio.run(self._close_browser())
            except RuntimeError:
                # Event loop already closed, resources already cleaned up
                pass
