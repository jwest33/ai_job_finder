"""
Job Scraper CLI Commands

Commands for running job searches, testing proxies, and managing scraper configuration.
"""

import os
import ast
import time
import yaml
import random
import string
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import click
from dotenv import load_dotenv

from src.utils.profile_manager import ProfilePaths
from src.cli.utils import (
    print_header,
    print_section,
    print_success,
    print_error,
    print_warning,
    print_info,
    print_key_value_table,
    print_table,
    confirm,
    prompt_text,
    prompt_int,
    prompt_checkbox,
    format_bytes,
    create_progress_bar,
    handle_error,
    cli_state,
)

load_dotenv()


# =============================================================================
# Scraper Command Group
# =============================================================================

@click.group(name="scraper")
def scraper_group():
    """Job scraping commands"""
    pass


# =============================================================================
# Helper Functions
# =============================================================================

def parse_env_list(env_var: str, default: list = None) -> list:
    """Parse a list from environment variable"""
    value = os.getenv(env_var)
    if not value:
        return default or []

    try:
        return ast.literal_eval(value)
    except Exception:
        return [item.strip() for item in value.split(",")]


def load_jobs_from_requirements() -> list:
    """
    Load job search terms from active profile's requirements.yaml

    Returns:
        List of job titles to search, or empty list if not found
    """
    requirements_path = ProfilePaths().requirements_path

    if not requirements_path.exists():
        return []

    try:
        with open(requirements_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        job_requirements = data.get('job_requirements', {})
        search_jobs = job_requirements.get('search_jobs', [])

        return search_jobs if search_jobs else []
    except Exception:
        return []


def load_locations_from_requirements() -> list:
    """
    Load job search locations from active profile's requirements.yaml

    Returns:
        List of locations to search, or empty list if not found
    """
    requirements_path = ProfilePaths().requirements_path

    if not requirements_path.exists():
        return []

    try:
        with open(requirements_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        # Read from preferences.locations (single source of truth)
        preferences = data.get('preferences', {})
        locations = preferences.get('locations', [])

        return locations if locations else []
    except Exception:
        return []


def get_scraper_config():
    """Get scraper configuration from requirements.yaml and environment"""
    return {
        "jobs": load_jobs_from_requirements() or [],
        "locations": load_locations_from_requirements() or [],
        "results_per_search": int(os.getenv("RESULTS_PER_SEARCH", "50")),
        "output_format": os.getenv("OUTPUT_FORMAT", "both").lower(),
        "deduplicate": os.getenv("DEDUPLICATE", "true").lower() == "true",
        "proxy_rotation_count": int(os.getenv("PROXY_ROTATION_COUNT", "1")),
        "rate_limit_delay": float(os.getenv("RATE_LIMIT_DELAY", "2.5")),
        "iproyal_host": os.getenv("IPROYAL_HOST", "geo.iproyal.com"),
        "iproyal_port": os.getenv("IPROYAL_PORT", "12321"),
        "iproyal_username": os.getenv("IPROYAL_USERNAME", ""),
        "iproyal_password": os.getenv("IPROYAL_PASSWORD", ""),
    }


def estimate_bandwidth(config: dict) -> dict:
    """Estimate bandwidth usage for scraping"""
    num_searches = len(config["jobs"]) * len(config["locations"]) * config["proxy_rotation_count"]
    requests_per_search = config["results_per_search"] // 100 + 1
    total_requests = num_searches * requests_per_search
    bandwidth_kb = total_requests * 50  # ~50KB per request
    bandwidth_mb = bandwidth_kb / 1024

    return {
        "num_searches": num_searches,
        "total_requests": total_requests,
        "bandwidth_kb": bandwidth_kb,
        "bandwidth_mb": bandwidth_mb,
    }


# =============================================================================
# Commands
# =============================================================================

@scraper_group.command(name="search")
@click.option("--jobs", "-j", multiple=True, help="Job titles to search (overrides .env)")
@click.option("--locations", "-l", multiple=True, help="Locations to search (overrides .env)")
@click.option("--results", "-r", type=int, help="Results per search (overrides .env)")
@click.option("--scraper", "-s", type=click.Choice(['indeed', 'glassdoor', 'all'], case_sensitive=False), default='all', help="Scraper to use (default: all)")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation")
@click.option("--dry-run", is_flag=True, help="Preview configuration without searching")
def search(jobs, locations, results, scraper, yes, dry_run):
    """Run job search with current configuration"""

    print_header("Job Search")

    # Load configuration
    config = get_scraper_config()

    # Override with command-line options
    if jobs:
        config["jobs"] = list(jobs)
    if locations:
        config["locations"] = list(locations)
    if results:
        config["results_per_search"] = results

    # Determine which scraper(s) to use
    scraper = scraper.lower()
    if scraper == 'all':
        scrapers_to_use = ['indeed', 'glassdoor']
    else:
        scrapers_to_use = [scraper]

    config["scrapers"] = scrapers_to_use

    # Validate
    if not config["jobs"]:
        print_error("No jobs specified. Set JOBS in .env or use --jobs flag", exit_code=1)

    if not config["locations"]:
        print_error("No locations specified. Set LOCATIONS in .env or use --locations flag", exit_code=1)

    if not config["iproyal_username"] or not config["iproyal_password"]:
        print_error("IPRoyal credentials not configured. Check .env file", exit_code=1)

    # Display configuration
    print_section("Configuration")

    config_display = {
        "Scraper(s)": ", ".join(config['scrapers']),
        "Job Titles": f"{len(config['jobs'])} titles",
        "Locations": f"{len(config['locations'])} locations",
        "Results per Search": config["results_per_search"],
        "IP Rotation": f"{config['proxy_rotation_count']} IPs per search",
        "Output Format": config["output_format"],
        "Deduplication": "Enabled" if config["deduplicate"] else "Disabled",
        "Total Searches": len(config['jobs']) * len(config['locations']) * config['proxy_rotation_count'] * len(config['scrapers']),
    }

    print_key_value_table(config_display, title="Search Configuration")

    # Estimate bandwidth
    bandwidth = estimate_bandwidth(config)

    print_section("Bandwidth Estimate")
    print_info(f"  Requests: ~{bandwidth['total_requests']}")
    print_info(f"  Bandwidth: ~{bandwidth['bandwidth_mb']:.1f} MB")

    if config["proxy_rotation_count"] > 1:
        print_warning(f"\nIP Rotation enabled: Each search runs {config['proxy_rotation_count']} times")
        print_warning(f"Expect ~60-75% duplicate rate with IP rotation")

    # Dry run
    if dry_run:
        print_info("\nDry run mode - no actual search performed")
        return

    # Confirm
    if not yes and not cli_state.quiet:
        print()
        if not confirm("Proceed with job search?"):
            print_info("Search cancelled")
            return

    # Run search
    print_header("Running Search")

    try:
        # Import scraper dependencies
        try:
            from core import scrape_jobs
            from core.storage import JobStorage
            from core.models import JobPost
            from core.scrapers.indeed import IndeedScraper
        except ImportError as e:
            print_error(f"Failed to import scraper modules: {e}", exit_code=1)

        # Initialize storage
        storage = JobStorage(output_dir=str(ProfilePaths().data_dir))
        all_jobs = []
        search_count = 0
        total_searches = len(config['jobs']) * len(config['locations']) * config['proxy_rotation_count'] * len(config['scrapers'])

        # Progress tracking
        with create_progress_bar() as progress:
            task = progress.add_task("[cyan]Searching...", total=total_searches)

            # Search for each scraper/job/location combination
            for scraper_name in config['scrapers']:
                for job_title in config['jobs']:
                    for location in config['locations']:
                        for ip_iteration in range(config['proxy_rotation_count']):
                            search_count += 1

                            # Update progress
                            progress.update(
                                task,
                                description=f"[cyan]Search {search_count}/{total_searches} ({scraper_name}): '{job_title}' in '{location}'",
                            )

                            try:
                                # Generate session ID for IP rotation
                                if scraper_name == 'indeed':
                                    proxy_session = IndeedScraper._generate_session_id() if config['proxy_rotation_count'] > 1 else None
                                else:
                                    # For glassdoor, use a generic session generation
                                    proxy_session = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10)) if config['proxy_rotation_count'] > 1 else None

                                if proxy_session:
                                    print_info(f"[INFO] Using proxy session: {proxy_session}")

                                # Scrape jobs
                                start_time = time.time()

                                jobs_df = scrape_jobs(
                                    site_name=scraper_name,
                                    search_term=job_title,
                                    location=location,
                                    results_wanted=config['results_per_search'],
                                    proxy_session=proxy_session,
                                )

                                elapsed = time.time() - start_time

                                if not jobs_df.empty:
                                    # Convert DataFrame to JobPost objects
                                    for _, row in jobs_df.iterrows():
                                        all_jobs.append(
                                            JobPost(
                                                # Core fields
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

                                                # Phase 2: Rich Attributes
                                                skills=row.get("skills", []),
                                                requirements=row.get("requirements", []),
                                                benefits=row.get("benefits", []),
                                                work_arrangements=row.get("work_arrangements", []),

                                                # Phase 3: Enhanced Location
                                                location_country_code=row.get("location_country_code"),
                                                location_country_name=row.get("location_country_name"),
                                                location_city=row.get("location_city"),
                                                location_state=row.get("location_state"),
                                                location_postal_code=row.get("location_postal_code"),

                                                # Phase 4: Company Enrichment
                                                company_size=row.get("company_size"),
                                                company_revenue=row.get("company_revenue"),
                                                company_description=row.get("company_description"),
                                                company_ceo=row.get("company_ceo"),
                                                company_website=row.get("company_website"),
                                                company_logo_url=row.get("company_logo_url"),
                                                company_header_image_url=row.get("company_header_image_url"),

                                                # Phase 5: Advanced Fields
                                                work_schedule=row.get("work_schedule"),
                                                detailed_salary=row.get("detailed_salary"),
                                                source_site=row.get("source_site"),
                                                tracking_key=row.get("tracking_key"),
                                                date_on_site=row.get("date_on_site"),

                                                # Phase 6: Glassdoor-Specific Fields
                                                glassdoor_listing_id=row.get("glassdoor_listing_id"),
                                                glassdoor_tracking_key=row.get("glassdoor_tracking_key"),
                                                glassdoor_job_link=row.get("glassdoor_job_link"),
                                                easy_apply=row.get("easy_apply"),
                                                occupation_code=row.get("occupation_code"),
                                                occupation_id=row.get("occupation_id"),
                                                occupation_confidence=row.get("occupation_confidence"),
                                                company_full_name=row.get("company_full_name"),
                                                company_short_name=row.get("company_short_name"),
                                                company_division=row.get("company_division"),
                                                company_rating=row.get("company_rating"),
                                                company_glassdoor_id=row.get("company_glassdoor_id"),
                                                salary_source=row.get("salary_source"),
                                                is_sponsored=row.get("is_sponsored"),
                                                sponsorship_level=row.get("sponsorship_level"),
                                                location_id=row.get("location_id"),
                                                location_country_id=row.get("location_country_id"),
                                            )
                                        )

                                    cli_state.log(f"Found {len(jobs_df)} jobs in {elapsed:.1f}s", "debug")

                            except Exception as e:
                                print_warning(f"Search failed: {e}")
                                continue

                            # Rate limiting
                            if search_count < total_searches:
                                time.sleep(config['rate_limit_delay'])

                            progress.advance(task)

        # Save results
        print_section("Saving Results")

        if all_jobs:
            # Always save jobs separately by source (never combine into "multi")
            jobs_by_source = {}

            # Group jobs by source
            for job in all_jobs:
                source = job.site
                if source not in jobs_by_source:
                    jobs_by_source[source] = []
                jobs_by_source[source].append(job)

            # Save each source separately
            all_saved_files = {}
            for source, jobs in jobs_by_source.items():
                print_info(f"\nSaving {len(jobs)} jobs from {source}...")

                saved_files = storage.save_jobs(
                    jobs=jobs,
                    format=config['output_format'],
                    deduplicate=config['deduplicate'],
                    append_to_latest=True,
                    source=source,
                )

                all_saved_files[source] = saved_files

            print_success(f"Collected {len(all_jobs)} total jobs")

            # Display saved files by source
            print_info("\nSaved files by source:")
            for source, saved_files in all_saved_files.items():
                print_info(f"\n  {source.upper()}:")
                for file_type, file_path in saved_files.items():
                    print_info(f"    {file_type}: {file_path}")

        else:
            print_warning("No jobs collected")

        # Summary
        print_section("Summary")
        print_success(f"Searches completed: {search_count}/{total_searches}")
        print_success(f"Jobs collected: {len(all_jobs)}")

    except KeyboardInterrupt:
        print_error("\nSearch interrupted by user")
        raise
    except Exception as e:
        handle_error(e, verbose=cli_state.verbose)
        raise
    finally:
        # Clean up Glassdoor browser if it was used
        if 'glassdoor' in config.get('scrapers', []):
            try:
                from src.core.scraper import cleanup_glassdoor_browser
                cleanup_glassdoor_browser()
            except:
                pass


@scraper_group.command(name="config")
@click.option("--edit", is_flag=True, help="Open .env file for editing")
def show_config(edit):
    """Show current scraper configuration"""

    if edit:
        # Open .env in default editor
        env_file = Path(".env")
        if not env_file.exists():
            print_error(".env file not found", exit_code=1)

        import subprocess
        import platform

        try:
            if platform.system() == "Windows":
                os.startfile(str(env_file))
            elif platform.system() == "Darwin":  # macOS
                subprocess.run(["open", str(env_file)])
            else:  # Linux
                subprocess.run(["xdg-open", str(env_file)])

            print_success(f"Opened {env_file} in default editor")
        except Exception as e:
            print_error(f"Failed to open editor: {e}")
        return

    print_header("Scraper Configuration")

    config = get_scraper_config()

    # Display config
    print_section("Job Search Settings")
    print_table(
        title="Job Titles",
        columns=["#", "Title"],
        rows=[[i + 1, title] for i, title in enumerate(config["jobs"])],
    )

    print_table(
        title="Locations",
        columns=["#", "Location"],
        rows=[[i + 1, loc] for i, loc in enumerate(config["locations"])],
    )

    print_section("Search Parameters")
    params = {
        "Results per Search": config["results_per_search"],
        "IP Rotation": f"{config['proxy_rotation_count']} IPs per search",
        "Rate Limit Delay": f"{config['rate_limit_delay']}s",
        "Output Format": config["output_format"],
        "Deduplication": "Enabled" if config["deduplicate"] else "Disabled",
    }
    print_key_value_table(params, title="Parameters")

    print_section("Proxy Configuration")
    proxy_config = {
        "Host": config["iproyal_host"],
        "Port": config["iproyal_port"],
        "Username": config["iproyal_username"] or "(not set)",
        "Password": "********" if config["iproyal_password"] else "(not set)",
    }
    print_key_value_table(proxy_config, title="IPRoyal Settings")

    # Bandwidth estimate
    bandwidth = estimate_bandwidth(config)

    print_section("Estimates")
    estimates = {
        "Total Searches": bandwidth["num_searches"],
        "API Requests": f"~{bandwidth['total_requests']}",
        "Bandwidth Usage": f"~{bandwidth['bandwidth_mb']:.1f} MB",
    }
    print_key_value_table(estimates, title="Bandwidth Estimate")


@scraper_group.command(name="test-proxy")
def test_proxy():
    """Test IPRoyal proxy connection"""
    import requests

    print_header("Proxy Connection Test")

    config = get_scraper_config()

    if not config["iproyal_username"] or not config["iproyal_password"]:
        print_error("IPRoyal credentials not configured in .env", exit_code=1)

    # Build proxy URL
    proxy_url = f"http://{config['iproyal_username']}:{config['iproyal_password']}@{config['iproyal_host']}:{config['iproyal_port']}"
    proxies = {"http": proxy_url, "https": proxy_url}

    print_info("Testing connection...")
    print_info(f"  Host: {config['iproyal_host']}:{config['iproyal_port']}")
    print_info(f"  Username: {config['iproyal_username']}")

    try:
        # Test with httpbin
        response = requests.get(
            "http://httpbin.org/ip",
            proxies=proxies,
            timeout=10,
        )

        if response.status_code == 200:
            data = response.json()
            ip_address = data.get("origin", "Unknown")

            print_success("Proxy connection successful!")
            print_info(f"  Your IP: {ip_address}")

        else:
            print_error(f"Proxy test failed: HTTP {response.status_code}")

    except requests.exceptions.ProxyError as e:
        print_error("Proxy authentication failed")
        print_info("Check your IPRoyal credentials in .env")
        if cli_state.verbose:
            handle_error(e, verbose=True)

    except requests.exceptions.Timeout:
        print_error("Connection timeout")
        print_info("Check your internet connection or IPRoyal service status")

    except Exception as e:
        handle_error(e, verbose=cli_state.verbose)


@scraper_group.command(name="interactive")
def interactive_search():
    """Interactive mode for configuring and running a search"""
    from src.cli.utils import prompt_checkbox, prompt_choice

    print_header("Interactive Job Search")

    # Get job titles
    print_section("Job Titles")
    print_info("Enter job titles to search (comma-separated):")

    default_jobs = ", ".join(get_scraper_config()["jobs"])
    jobs_input = prompt_text("Job titles", default=default_jobs)
    jobs = [j.strip() for j in jobs_input.split(",") if j.strip()]

    # Get locations
    print_section("Locations")
    print_info("Enter locations to search (comma-separated):")

    default_locations = ", ".join(get_scraper_config()["locations"])
    locations_input = prompt_text("Locations", default=default_locations)
    locations = [l.strip() for l in locations_input.split(",") if l.strip()]

    # Get results per search
    print_section("Results")
    results = prompt_int("Results per search", default=50)

    # Get IP rotation
    print_section("IP Rotation")
    rotation_choices = [
        "1 - No rotation (fastest, least bandwidth)",
        "3 - Geographic diversity (recommended)",
        "5 - Maximum diversity (slow, high bandwidth)",
    ]
    rotation_choice = prompt_choice("IP rotation strategy", rotation_choices, default=rotation_choices[0])
    rotation_count = int(rotation_choice.split()[0])

    # Summary
    print_section("Summary")

    total_searches = len(jobs) * len(locations) * rotation_count
    bandwidth_mb = (total_searches * (results // 100 + 1) * 50) / 1024

    summary = {
        "Job Titles": len(jobs),
        "Locations": len(locations),
        "Results per Search": results,
        "IP Rotation": rotation_count,
        "Total Searches": total_searches,
        "Est. Bandwidth": f"~{bandwidth_mb:.1f} MB",
    }

    print_key_value_table(summary, title="Search Configuration")

    # Confirm
    if not confirm("\nProceed with search?"):
        print_info("Search cancelled")
        return

    # Run search
    from click.testing import CliRunner
    runner = CliRunner()

    # Build command
    job_args = []
    for job in jobs:
        job_args.extend(["--jobs", job])

    location_args = []
    for loc in locations:
        location_args.extend(["--locations", loc])

    result = runner.invoke(
        search,
        [*job_args, *location_args, "--results", str(results), "--yes"],
        catch_exceptions=False,
    )

    if result.exit_code != 0:
        print_error("Search failed")
