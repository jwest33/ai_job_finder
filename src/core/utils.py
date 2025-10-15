"""
Utility functions for core
"""

import random
import time
import requests
from typing import Optional, Dict, List
from itertools import cycle
from requests.adapters import HTTPAdapter, Retry
from .config import USER_AGENTS, REQUEST_TIMEOUT, RATE_LIMIT_DELAY, DEFAULT_PROXIES


class ProxyRotator:
    """Handles proxy rotation for requests"""

    def __init__(self, proxies: Optional[List[str]] = None):
        """
        Initialize proxy rotator

        Args:
            proxies: List of proxy URLs. If None, uses DEFAULT_PROXIES from config
        """
        self.proxies = proxies if proxies else DEFAULT_PROXIES.copy()
        self.current_index = 0
        self.failed_proxies = set()

    def get_next_proxy(self) -> Optional[Dict[str, str]]:
        """
        Get the next proxy in rotation

        Returns:
            Dictionary with proxy settings or None if no proxies available
        """
        if not self.proxies:
            return None

        available_proxies = [p for p in self.proxies if p not in self.failed_proxies]

        if not available_proxies:
            # Reset failed proxies if all have failed
            self.failed_proxies.clear()
            available_proxies = self.proxies

        proxy_url = available_proxies[self.current_index % len(available_proxies)]
        self.current_index += 1

        return {
            "http": proxy_url,
            "https": proxy_url,
        }

    def mark_failed(self, proxy_dict: Dict[str, str]):
        """Mark a proxy as failed"""
        if proxy_dict and "http" in proxy_dict:
            self.failed_proxies.add(proxy_dict["http"])


class RequestHandler:
    """Handles HTTP requests with proxy rotation and user agent spoofing"""

    def __init__(self, proxies: Optional[List[str]] = None, use_proxies: bool = True):
        """
        Initialize request handler

        Args:
            proxies: List of proxy URLs
            use_proxies: Whether to use proxies for requests (default: True)
        """
        self.proxy_rotator = ProxyRotator(proxies) if use_proxies else None
        self.session = requests.Session()
        self.last_request_time = 0

    def get_random_user_agent(self) -> str:
        """Get a random user agent string"""
        return random.choice(USER_AGENTS)

    def get_realistic_headers(self, url: str) -> Dict[str, str]:
        """
        Generate realistic browser headers to avoid detection

        Args:
            url: The URL being requested (for Referer)

        Returns:
            Dictionary of HTTP headers
        """
        from urllib.parse import urlparse
        parsed = urlparse(url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"

        headers = {
            "User-Agent": self.get_random_user_agent(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
        }

        # Add referer for navigational requests
        if random.random() > 0.3:  # 70% of the time
            headers["Referer"] = base_url

        return headers

    def make_request(
        self,
        url: str,
        method: str = "GET",
        headers: Optional[Dict] = None,
        params: Optional[Dict] = None,
        data: Optional[Dict] = None,
        max_retries: int = 3,
    ) -> Optional[requests.Response]:
        """
        Make an HTTP request with proxy rotation and retry logic

        Args:
            url: URL to request
            method: HTTP method (GET, POST, etc.)
            headers: Optional headers dictionary
            params: Optional query parameters
            data: Optional request body data
            max_retries: Maximum number of retry attempts

        Returns:
            Response object or None if all retries failed
        """
        # Rate limiting with random jitter (more human-like)
        elapsed = time.time() - self.last_request_time
        jitter = random.uniform(0, 0.5)  # Add 0-0.5s random delay
        total_delay = RATE_LIMIT_DELAY + jitter

        if elapsed < total_delay:
            time.sleep(total_delay - elapsed)

        # Prepare headers with realistic browser headers
        if headers is None:
            headers = self.get_realistic_headers(url)
        else:
            # Merge provided headers with realistic defaults
            realistic_headers = self.get_realistic_headers(url)
            realistic_headers.update(headers)
            headers = realistic_headers

        for attempt in range(max_retries):
            try:
                # Get proxy if using proxies
                proxy = self.proxy_rotator.get_next_proxy() if self.proxy_rotator else None

                # Make request
                response = self.session.request(
                    method=method,
                    url=url,
                    headers=headers,
                    params=params,
                    data=data,
                    proxies=proxy,
                    timeout=REQUEST_TIMEOUT,
                )

                self.last_request_time = time.time()

                # Check if request was successful
                if response.status_code == 200:
                    return response
                elif response.status_code == 429:  # Too many requests
                    wait_time = RATE_LIMIT_DELAY * (attempt + 1) * 2
                    print(f"Rate limited. Waiting {wait_time} seconds...")
                    time.sleep(wait_time)
                elif response.status_code >= 400:
                    print(f"Request failed with status {response.status_code}")
                    if self.proxy_rotator and proxy:
                        self.proxy_rotator.mark_failed(proxy)

            except requests.exceptions.ProxyError as e:
                print(f"Proxy error on attempt {attempt + 1}: {e}")
                if self.proxy_rotator and proxy:
                    self.proxy_rotator.mark_failed(proxy)

            except requests.exceptions.Timeout:
                print(f"Request timeout on attempt {attempt + 1}")

            except Exception as e:
                print(f"Request error on attempt {attempt + 1}: {e}")

            # Wait before retry
            if attempt < max_retries - 1:
                time.sleep(RATE_LIMIT_DELAY * (attempt + 1))

        return None

    def close(self):
        """Close the session"""
        self.session.close()


def format_location(location: str) -> str:
    """
    Format location string for API requests

    Args:
        location: Location string (e.g., "San Francisco, CA")

    Returns:
        Formatted location string
    """
    return location.strip().replace(" ", "+")


def parse_salary(salary_text: Optional[str]) -> Dict[str, Optional[float]]:
    """
    Parse salary information from text

    Args:
        salary_text: Salary text to parse

    Returns:
        Dictionary with salary_min, salary_max, currency, and period
    """
    result = {
        "salary_min": None,
        "salary_max": None,
        "salary_currency": None,
        "salary_period": None,
    }

    if not salary_text:
        return result

    # This is a simplified parser - can be enhanced with regex
    salary_text = salary_text.lower().strip()

    # Detect currency
    if "$" in salary_text or "usd" in salary_text:
        result["salary_currency"] = "USD"
    elif "£" in salary_text or "gbp" in salary_text:
        result["salary_currency"] = "GBP"
    elif "€" in salary_text or "eur" in salary_text:
        result["salary_currency"] = "EUR"

    # Detect period
    if "hour" in salary_text:
        result["salary_period"] = "hourly"
    elif "year" in salary_text or "annual" in salary_text:
        result["salary_period"] = "yearly"
    elif "month" in salary_text:
        result["salary_period"] = "monthly"

    # Extract numbers (simplified - would need better parsing in production)
    import re

    numbers = re.findall(r"[\d,]+", salary_text.replace("$", "").replace(",", ""))
    if numbers:
        try:
            nums = [float(n) for n in numbers[:2]]
            result["salary_min"] = min(nums) if nums else None
            result["salary_max"] = max(nums) if len(nums) > 1 else None
        except ValueError:
            pass

    return result


def create_session(
    proxies: Optional[List[str]] = None,
    has_retry: bool = False,
    delay: int = 1,
) -> requests.Session:
    """
    Creates a requests session with optional proxy rotation and retry settings.

    Args:
        proxies: List of proxy URLs or None
        has_retry: Whether to add retry logic (default: False)
        delay: Backoff delay multiplier for retries (default: 1)

    Returns:
        Configured requests.Session object
    """
    session = requests.Session()

    # Setup proxy rotation if proxies provided
    if proxies:
        if isinstance(proxies, str):
            proxy_list = [proxies]
        else:
            proxy_list = proxies

        # Format proxies
        formatted_proxies = []
        for proxy in proxy_list:
            if proxy.startswith("http://") or proxy.startswith("https://") or proxy.startswith("socks5://"):
                formatted_proxies.append({"http": proxy, "https": proxy})
            else:
                formatted_proxies.append({"http": f"http://{proxy}", "https": f"http://{proxy}"})

        # Create proxy cycle
        proxy_cycle = cycle(formatted_proxies)

        # Monkey-patch session.request to rotate proxies
        original_request = session.request

        def rotating_request(method, url, **kwargs):
            if proxy_cycle:
                kwargs['proxies'] = next(proxy_cycle)
            return original_request(method, url, **kwargs)

        session.request = rotating_request

    # Setup retry logic
    if has_retry:
        retries = Retry(
            total=3,
            connect=3,
            status=3,
            status_forcelist=[500, 502, 503, 504, 429],
            backoff_factor=delay,
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retries)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

    return session
