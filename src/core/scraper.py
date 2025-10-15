"""
Main scraper module for core
"""

from typing import List, Optional, Union
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd

from .models import JobPost
from .scrapers import IndeedScraper, GlassdoorScraper

# Disabled scrapers (need GraphQL/API implementation):
# from .scrapers import LinkedInScraper, ZipRecruiterScraper


def scrape_jobs(
    site_name: Union[str, List[str]],
    search_term: str,
    location: str,
    results_wanted: int = 10,
    hours_old: Optional[int] = None,
    country_indeed: str = "USA",
    proxies: Optional[List[str]] = None,
    use_proxies: bool = True,
    proxy_session: Optional[str] = None,
    **kwargs,
) -> pd.DataFrame:
    """
    Scrape job postings from multiple job boards

    Args:
        site_name: Job board(s) to scrape. Can be a string or list of strings.
                   Options: "indeed", "linkedin", "zip_recruiter", "glassdoor"
        search_term: Job title or keywords to search for
        location: Geographic location for job search
        results_wanted: Number of results to retrieve per site (default: 10)
        hours_old: Filter jobs posted within X hours (optional)
        country_indeed: Country code for Indeed searches (default: "USA")
        proxies: List of proxy URLs to use for requests (optional)
        use_proxies: Whether to use proxies for requests (default: True)
        proxy_session: Optional session ID for IP rotation (generates different IPs)
        **kwargs: Additional site-specific parameters

    Returns:
        pandas DataFrame with job postings

    Example:
        >>> jobs = scrape_jobs(
        ...     site_name=["indeed", "linkedin"],
        ...     search_term="software engineer",
        ...     location="San Francisco, CA",
        ...     results_wanted=20
        ... )
    """
    # Normalize site_name to list
    if isinstance(site_name, str):
        site_names = [site_name.lower()]
    else:
        site_names = [name.lower() for name in site_name]

    # Validate site names
    valid_sites = {"indeed", "glassdoor"}  # Indeed and Glassdoor are currently supported
    disabled_sites = {"linkedin", "zip_recruiter"}
    invalid_sites = set(site_names) - valid_sites - disabled_sites

    if invalid_sites:
        raise ValueError(
            f"Invalid site names: {invalid_sites}. "
            f"Valid options are: {valid_sites}"
        )

    # Check for disabled sites
    requested_disabled = set(site_names) & disabled_sites
    if requested_disabled:
        raise ValueError(
            f"Sites {requested_disabled} are currently disabled. "
            f"They need GraphQL/API implementation. "
            f"Currently supported: {valid_sites}"
        )

    print(f"Scraping {len(site_names)} site(s) for '{search_term}' in {location}...")

    # Create scrapers with proxy support
    scrapers = []

    if "indeed" in site_names:
        scrapers.append(
            (
                "indeed",
                IndeedScraper(proxies=proxies, use_proxies=use_proxies, proxy_session=proxy_session),
                {"country": country_indeed},
            )
        )

    if "glassdoor" in site_names:
        scrapers.append(
            (
                "glassdoor",
                GlassdoorScraper(proxies=proxies, use_proxies=use_proxies, proxy_session=proxy_session),
                {},
            )
        )

    # Disabled scrapers - need GraphQL/API implementation
    # if "linkedin" in site_names:
    #     scrapers.append(
    #         ("linkedin", LinkedInScraper(proxies=proxies, use_proxies=use_proxies), {})
    #     )
    #
    # if "zip_recruiter" in site_names:
    #     scrapers.append(
    #         (
    #             "zip_recruiter",
    #             ZipRecruiterScraper(proxies=proxies, use_proxies=use_proxies),
    #             {},
    #         )
    #     )

    # Scrape jobs concurrently
    all_jobs = []

    with ThreadPoolExecutor(max_workers=len(scrapers)) as executor:
        # Submit all scraping tasks
        future_to_scraper = {}

        for site, scraper, site_kwargs in scrapers:
            future = executor.submit(
                _scrape_site,
                scraper,
                search_term,
                location,
                results_wanted,
                hours_old,
                site_kwargs,
            )
            future_to_scraper[future] = (site, scraper)

        # Collect results as they complete
        for future in as_completed(future_to_scraper):
            site, scraper = future_to_scraper[future]
            try:
                jobs = future.result()
                all_jobs.extend(jobs)
                print(f"Found {len(jobs)} jobs from {site}")
            except Exception as e:
                print(f"Error scraping {site}: {e}")
            finally:
                # Close scraper session
                try:
                    scraper.close()
                except:
                    pass

    # Convert to DataFrame
    if not all_jobs:
        print("No jobs found")
        return pd.DataFrame()

    df = pd.DataFrame([job.to_dict() for job in all_jobs])

    # Sort by site and date (if available)
    if "date_posted" in df.columns:
        df = df.sort_values(by=["site", "date_posted"], ascending=[True, False])
    else:
        df = df.sort_values(by="site")

    print(f"\nTotal jobs found: {len(df)}")

    return df


def _scrape_site(
    scraper,
    search_term: str,
    location: str,
    results_wanted: int,
    hours_old: Optional[int],
    site_kwargs: dict,
) -> List[JobPost]:
    """
    Helper function to scrape a single site

    Args:
        scraper: Scraper instance
        search_term: Job title or keywords
        location: Geographic location
        results_wanted: Number of results to retrieve
        hours_old: Filter jobs posted within X hours
        site_kwargs: Additional site-specific parameters

    Returns:
        List of JobPost objects
    """
    return scraper.scrape(
        search_term=search_term,
        location=location,
        results_wanted=results_wanted,
        hours_old=hours_old,
        **site_kwargs,
    )
