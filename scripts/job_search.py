"""
Production Job Search Script

Reads job titles and locations from .env file and scrapes Indeed for all combinations.
Saves results to CSV/JSON with deduplication.

Usage:
    python run_job_search.py

Configuration:
    Edit .env file to set:
    - JOBS: List of job titles to search
    - LOCATIONS: List of locations to search
    - RESULTS_PER_SEARCH: Number of results per search (default: 50)
    - OUTPUT_FORMAT: csv, json, or both (default: both)
    - DEDUPLICATE: Remove duplicate jobs (default: true)
"""

import os
import ast
import time
import yaml
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from src.core import scrape_jobs
from src.core.storage import JobStorage
from src.utils.profile_manager import ProfilePaths

# Load environment variables
load_dotenv()


def parse_env_list(env_var: str, default: list = None) -> list:
    """
    Parse a list from environment variable

    Args:
        env_var: Environment variable name
        default: Default value if not found

    Returns:
        List of strings
    """
    value = os.getenv(env_var)
    if not value:
        return default or []

    try:
        # Try to parse as Python list
        return ast.literal_eval(value)
    except:
        # Fall back to comma-separated
        return [item.strip() for item in value.split(",")]


def load_jobs_from_requirements(profile_name: str = None) -> list:
    """
    Load job search terms from requirements.yaml

    Args:
        profile_name: Profile name (default: from .env ACTIVE_PROFILE)

    Returns:
        List of job titles to search, or None if not found
    """
    # Get profile paths
    paths = ProfilePaths(profile_name)
    requirements_path = Path(os.getenv("REQUIREMENTS_PATH", str(paths.requirements_path)))

    if not requirements_path.exists():
        return None

    try:
        with open(requirements_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        job_requirements = data.get('job_requirements', {})
        search_jobs = job_requirements.get('search_jobs', [])

        return search_jobs if search_jobs else None
    except Exception as e:
        print(f"[WARNING] Could not load search_jobs from requirements.yaml: {e}")
        return None


def load_locations_from_requirements(profile_name: str = None) -> list:
    """
    Load job search locations from requirements.yaml

    Args:
        profile_name: Profile name (default: from .env ACTIVE_PROFILE)

    Returns:
        List of locations to search, or None if not found
    """
    # Get profile paths
    paths = ProfilePaths(profile_name)
    requirements_path = Path(os.getenv("REQUIREMENTS_PATH", str(paths.requirements_path)))

    if not requirements_path.exists():
        return None

    try:
        with open(requirements_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        # Read from preferences.locations (single source of truth)
        preferences = data.get('preferences', {})
        locations = preferences.get('locations', [])

        return locations if locations else None
    except Exception as e:
        print(f"[WARNING] Could not load locations from requirements.yaml: {e}")
        return None


def main():
    """Main job search execution"""

    # Get active profile
    profile_name = os.getenv("ACTIVE_PROFILE", "default")
    paths = ProfilePaths(profile_name)

    print("=" * 80)
    print("JOB SEARCH SCRIPT - Production Run")
    print("=" * 80)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Profile: {profile_name}")
    print()

    # Read configuration - try requirements.yaml first, then fall back to .env
    jobs = load_jobs_from_requirements(profile_name)
    if jobs:
        print("[INFO] Loaded job titles from requirements.yaml")
    else:
        print("[INFO] Loading job titles from .env (fallback)")
        jobs = parse_env_list("JOBS", ["software engineer"])

    locations = load_locations_from_requirements(profile_name)
    if locations:
        print("[INFO] Loaded locations from requirements.yaml")
    else:
        print("[INFO] Loading locations from .env (fallback)")
        locations = parse_env_list("LOCATIONS", ["Remote"])
    results_per_search = int(os.getenv("RESULTS_PER_SEARCH", "50"))
    output_format = os.getenv("OUTPUT_FORMAT", "both").lower()
    deduplicate = os.getenv("DEDUPLICATE", "true").lower() == "true"
    use_proxy = os.getenv("USE_PROXY", "true").lower() == "true"
    proxy_rotation_count = max(1, int(os.getenv("PROXY_ROTATION_COUNT", "1")))

    # Validate configuration
    if not jobs or all(not j.strip() for j in jobs if isinstance(j, str)):
        print("[ERROR] No valid jobs defined!")
        print("   Please add search_jobs to templates/requirements.yaml or JOBS to .env")
        return

    if not locations or all(not loc.strip() for loc in locations if isinstance(loc, str)):
        print("[ERROR] No valid locations defined!")
        print("   Please add locations to preferences section in templates/requirements.yaml or LOCATIONS to .env")
        return

    # Display configuration
    print(f"[INFO] Configuration:")
    print(f"   Jobs to search: {len(jobs)}")
    print(f"   Locations: {len(locations)}")
    print(f"   Results per search: {results_per_search}")
    print(f"   Proxy: {'enabled' if use_proxy else 'disabled (using local network)'}")
    if use_proxy:
        print(f"   IP rotation: {proxy_rotation_count} different IPs per search")
    print(f"   Output format: {output_format}")
    print(f"   Deduplication: {'enabled' if deduplicate else 'disabled'}")
    print(f"   Total searches: {len(jobs) * len(locations) * proxy_rotation_count}")
    print()

    # Estimate bandwidth
    estimated_requests = len(jobs) * len(locations) * proxy_rotation_count * (results_per_search // 100 + 1)
    estimated_bandwidth_kb = estimated_requests * 50
    estimated_bandwidth_mb = estimated_bandwidth_kb / 1024

    print(f"[INFO] Estimated bandwidth usage:")
    print(f"   Requests: ~{estimated_requests}")
    print(f"   Bandwidth: ~{estimated_bandwidth_mb:.1f} MB")
    print()

    if proxy_rotation_count > 1:
        print(f"[INFO] IP Rotation Strategy:")
        print(f"   Each search will run {proxy_rotation_count} times with different IPs")
        print(f"   to capture location-based result variations")
        print(f"   Results will be merged and deduplicated")
        print()

    # Confirm before proceeding
    try:
        response = input("Continue with job search? (y/n): ").lower().strip()
        if response != "y":
            print("[INFO] Search cancelled by user")
            return
    except KeyboardInterrupt:
        print("\n[INFO] Search cancelled by user")
        return

    print("\n" + "=" * 80)
    print("STARTING JOB SEARCH")
    print("=" * 80 + "\n")

    # Initialize storage with profile-specific data directory
    storage = JobStorage(output_dir=str(paths.data_dir))

    # Track all jobs
    all_jobs = []
    search_count = 0
    total_searches = len(jobs) * len(locations) * proxy_rotation_count

    # Search for each job/location combination with IP rotation
    for job_title in jobs:
        for location in locations:

            # Run the same search with multiple IPs
            for ip_iteration in range(proxy_rotation_count):
                search_count += 1

                print(f"\n{'─' * 80}")
                print(f"Search {search_count}/{total_searches}")
                print(f"Job: '{job_title}' | Location: '{location}'", end="")
                if proxy_rotation_count > 1:
                    print(f" | IP Rotation: {ip_iteration + 1}/{proxy_rotation_count}")
                else:
                    print()
                print(f"{'─' * 80}\n")

                try:
                    # Generate unique session ID for IP rotation (only if using proxy)
                    from core.scrapers.indeed import IndeedScraper
                    proxy_session = IndeedScraper._generate_session_id() if (use_proxy and proxy_rotation_count > 1) else None

                    if proxy_session:
                        print(f"[INFO] Using proxy session: {proxy_session}")

                    # Scrape jobs
                    start_time = time.time()

                    jobs_df = scrape_jobs(
                        site_name="indeed",
                        search_term=job_title,
                        location=location,
                        results_wanted=results_per_search,
                        use_proxies=use_proxy,
                        proxy_session=proxy_session,
                    )

                    elapsed = time.time() - start_time

                    if not jobs_df.empty:
                        print(f"Found {len(jobs_df)} jobs in {elapsed:.1f}s")
                        # Convert DataFrame rows back to JobPost objects for storage
                        from core.models import JobPost

                        for _, row in jobs_df.iterrows():
                            all_jobs.append(
                                JobPost(
                                    title=row["title"],
                                    company=row["company"],
                                    location=row["location"],
                                    job_url=row["job_url"],
                                    site=row["site"],
                                    description=row.get("description"),
                                    job_type=row.get("job_type"),
                                    date_posted=row.get("date_posted"),
                                    salary_min=row.get("salary_min"),
                                    salary_max=row.get("salary_max"),
                                    salary_currency=row.get("salary_currency"),
                                    salary_period=row.get("salary_period"),
                                    company_url=row.get("company_url"),
                                    company_industry=row.get("company_industry"),
                                    remote=row.get("remote", False),
                                )
                            )
                    else:
                        print(f"[WARNING] No jobs found in {elapsed:.1f}s")

                except Exception as e:
                    print(f"[ERROR] Error during search: {e}")
                    continue

                # Rate limiting between searches (be nice to Indeed API)
                if search_count < total_searches:
                    wait_time = 3  # 3 seconds between searches
                    print(f"[INFO] Waiting {wait_time}s before next search...")
                    time.sleep(wait_time)

    # Save all collected jobs
    print("\n" + "=" * 80)
    print("SAVING RESULTS")
    print("=" * 80 + "\n")

    if all_jobs:
        # Use batch save for much better performance (single DB connection)
        result = storage.save_jobs_batch(
            jobs=all_jobs,
            source="indeed",  # Indeed is the only active scraper
        )

        print(f"\nTotal jobs processed: {len(all_jobs)}")
        print(f"New jobs saved: {result.get('saved', 0)}")
        print(f"Existing jobs updated: {result.get('updated', 0)}")
    else:
        print("[WARNING] No jobs collected")

    # Final summary
    print("\n" + "=" * 80)
    print("SEARCH COMPLETE")
    print("=" * 80)
    print(f"Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Searches completed: {search_count}/{total_searches}")
    print(f"Jobs collected: {len(all_jobs)}")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[INFO] Search interrupted by user")
    except Exception as e:
        print(f"\n\n[ERROR] Fatal error: {e}")
        raise
