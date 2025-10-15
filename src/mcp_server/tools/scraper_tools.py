"""
Job Scraper Tools

Tools for running job searches and managing scraper configuration.
"""

import sys
import os
from pathlib import Path
from typing import Any, Dict

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.cli.scraper import get_scraper_config, estimate_bandwidth
from .base import scraper_registry, BaseTool
from ..utils.response_formatter import format_success_response, format_error_response


class ScraperSearchTool(BaseTool):
    """Run job search"""

    def __init__(self):
        super().__init__("search", "Run job search with specified parameters")

    async def execute(self, **kwargs) -> Dict[str, Any]:
        params = self.validate_parameters(
            kwargs,
            required=[],
            optional=["jobs", "locations", "results", "scraper", "dry_run"],
        )

        # Get current configuration
        config = get_scraper_config()

        # Override with provided parameters
        if "jobs" in params:
            config["jobs"] = params["jobs"] if isinstance(params["jobs"], list) else [params["jobs"]]
        if "locations" in params:
            config["locations"] = params["locations"] if isinstance(params["locations"], list) else [params["locations"]]
        if "results" in params:
            config["results_per_search"] = int(params["results"])

        scraper_choice = params.get("scraper", "all").lower()
        config["scrapers"] = ["indeed", "glassdoor"] if scraper_choice == "all" else [scraper_choice]

        # Validate
        if not config["jobs"]:
            raise ValueError("No jobs specified. Provide 'jobs' parameter or configure in requirements.yaml")

        if not config["locations"]:
            raise ValueError("No locations specified. Provide 'locations' parameter or configure in requirements.yaml")

        # If dry_run, just return configuration
        if params.get("dry_run", False):
            bandwidth = estimate_bandwidth(config)
            return format_success_response(
                data={
                    "mode": "dry_run",
                    "configuration": {
                        "scrapers": config["scrapers"],
                        "jobs": config["jobs"],
                        "locations": config["locations"],
                        "results_per_search": config["results_per_search"],
                        "total_searches": bandwidth["num_searches"],
                    },
                    "estimates": {
                        "requests": bandwidth["total_requests"],
                        "bandwidth_mb": round(bandwidth["bandwidth_mb"], 2),
                    },
                },
                message="Dry run - no actual search performed",
            )

        # Execute search
        try:
            from src.core import scrape_jobs
            from src.core.storage import JobStorage
            from src.core.models import JobPost
            from src.core.scrapers.indeed import IndeedScraper
            import time
            import random
            import string
        except ImportError as e:
            return format_error_response(
                error=f"Failed to import scraper modules: {e}",
                error_type="ImportError",
                details={"suggestion": "Ensure src.core package is properly installed"},
            )

        # Initialize storage
        from src.utils.profile_manager import ProfilePaths
        storage = JobStorage(output_dir=str(ProfilePaths().data_dir))

        all_jobs = []
        search_count = 0
        total_searches = len(config['jobs']) * len(config['locations']) * len(config['scrapers'])
        failed_searches = []

        # Search for each scraper/job/location combination
        for scraper_name in config['scrapers']:
            for job_title in config['jobs']:
                for location in config['locations']:
                    search_count += 1

                    try:
                        # Generate session ID for IP rotation (if needed)
                        proxy_session = None

                        # Scrape jobs
                        jobs_df = scrape_jobs(
                            site_name=scraper_name,
                            search_term=job_title,
                            location=location,
                            results_wanted=config['results_per_search'],
                            proxy_session=proxy_session,
                        )

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
                                    )
                                )

                    except Exception as e:
                        failed_searches.append({
                            "scraper": scraper_name,
                            "job_title": job_title,
                            "location": location,
                            "error": str(e),
                        })
                        continue

                    # Rate limiting
                    if search_count < total_searches:
                        time.sleep(config['rate_limit_delay'])

        # Save results
        saved_files = {}
        if all_jobs:
            # Group jobs by source
            jobs_by_source = {}
            for job in all_jobs:
                source = job.site
                if source not in jobs_by_source:
                    jobs_by_source[source] = []
                jobs_by_source[source].append(job)

            # Save each source separately
            for source, jobs in jobs_by_source.items():
                source_files = storage.save_jobs(
                    jobs=jobs,
                    format=config['output_format'],
                    deduplicate=config['deduplicate'],
                    append_to_latest=True,
                    source=source,
                )
                saved_files[source] = source_files

        # Build response
        result_data = {
            "searches_completed": search_count,
            "total_jobs_found": len(all_jobs),
            "jobs_by_source": {source: len(jobs) for source, jobs in (jobs_by_source.items() if all_jobs else [])},
            "saved_files": saved_files,
            "configuration": {
                "scrapers": config["scrapers"],
                "jobs": config["jobs"],
                "locations": config["locations"],
                "results_per_search": config["results_per_search"],
            },
        }

        if failed_searches:
            result_data["failed_searches"] = failed_searches
            result_data["failures_count"] = len(failed_searches)

        message = f"Search complete: {len(all_jobs)} jobs found from {search_count} searches"
        if failed_searches:
            message += f" ({len(failed_searches)} searches failed)"

        return format_success_response(data=result_data, message=message)


class ScraperConfigShowTool(BaseTool):
    """Show current scraper configuration"""

    def __init__(self):
        super().__init__("config_show", "Display current scraper configuration")

    async def execute(self, **kwargs) -> Dict[str, Any]:
        config = get_scraper_config()
        bandwidth = estimate_bandwidth(config)

        return format_success_response({
            "configuration": {
                "jobs": config["jobs"],
                "locations": config["locations"],
                "results_per_search": config["results_per_search"],
                "proxy_rotation_count": config["proxy_rotation_count"],
                "output_format": config["output_format"],
                "deduplicate": config["deduplicate"],
                "rate_limit_delay": config["rate_limit_delay"],
            },
            "proxy": {
                "host": config["iproyal_host"],
                "port": config["iproyal_port"],
                "username_configured": bool(config["iproyal_username"]),
                "password_configured": bool(config["iproyal_password"]),
            },
            "estimates": {
                "total_searches": bandwidth["num_searches"],
                "total_requests": bandwidth["total_requests"],
                "bandwidth_mb": round(bandwidth["bandwidth_mb"], 2),
            },
        })


class ScraperConfigUpdateTool(BaseTool):
    """Update scraper configuration"""

    def __init__(self):
        super().__init__("config_update", "Update scraper configuration settings")

    async def execute(self, **kwargs) -> Dict[str, Any]:
        from dotenv import set_key, find_dotenv

        params = self.validate_parameters(
            kwargs,
            required=[],
            optional=[
                "results_per_search",
                "proxy_rotation_count",
                "output_format",
                "deduplicate",
                "rate_limit_delay",
            ],
        )

        env_file = find_dotenv() or ".env"
        updated = []

        # Update environment variables
        if "results_per_search" in params:
            set_key(env_file, "RESULTS_PER_SEARCH", str(params["results_per_search"]))
            updated.append("results_per_search")

        if "proxy_rotation_count" in params:
            set_key(env_file, "PROXY_ROTATION_COUNT", str(params["proxy_rotation_count"]))
            updated.append("proxy_rotation_count")

        if "output_format" in params:
            set_key(env_file, "OUTPUT_FORMAT", params["output_format"])
            updated.append("output_format")

        if "deduplicate" in params:
            set_key(env_file, "DEDUPLICATE", str(params["deduplicate"]).lower())
            updated.append("deduplicate")

        if "rate_limit_delay" in params:
            set_key(env_file, "RATE_LIMIT_DELAY", str(params["rate_limit_delay"]))
            updated.append("rate_limit_delay")

        return format_success_response(
            data={"updated_fields": updated, "note": "Changes will take effect on next search"},
            message=f"Updated {len(updated)} configuration field(s)",
        )


class ScraperTestProxyTool(BaseTool):
    """Test proxy connection"""

    def __init__(self):
        super().__init__("test_proxy", "Test IPRoyal proxy connection")

    async def execute(self, **kwargs) -> Dict[str, Any]:
        import requests

        config = get_scraper_config()

        if not config["iproyal_username"] or not config["iproyal_password"]:
            return format_error_response(
                error="IPRoyal credentials not configured",
                details={"message": "Configure IPROYAL_USERNAME and IPROYAL_PASSWORD in .env"},
            )

        # Build proxy URL
        proxy_url = (
            f"http://{config['iproyal_username']}:{config['iproyal_password']}"
            f"@{config['iproyal_host']}:{config['iproyal_port']}"
        )
        proxies = {"http": proxy_url, "https": proxy_url}

        try:
            # Test with httpbin
            response = requests.get(
                "http://httpbin.org/ip",
                proxies=proxies,
                timeout=10,
            )

            if response.status_code == 200:
                data = response.json()
                return format_success_response(
                    data={
                        "ip_address": data.get("origin", "Unknown"),
                        "proxy": {
                            "host": config["iproyal_host"],
                            "port": config["iproyal_port"],
                        },
                    },
                    message="Proxy connection successful",
                )
            else:
                return format_error_response(
                    error=f"HTTP {response.status_code}",
                    details={"status_code": response.status_code},
                )

        except requests.exceptions.ProxyError:
            return format_error_response(
                error="Proxy authentication failed",
                error_type="ProxyError",
                details={"message": "Check IPRoyal credentials in .env"},
            )

        except requests.exceptions.Timeout:
            return format_error_response(
                error="Connection timeout",
                error_type="TimeoutError",
                details={"message": "Check internet connection or IPRoyal service status"},
            )

        except Exception as e:
            return format_error_response(
                error=str(e),
                error_type=type(e).__name__,
            )


# Register tools
scraper_registry.register("search", ScraperSearchTool())
scraper_registry.register("config_show", ScraperConfigShowTool())
scraper_registry.register("config_update", ScraperConfigUpdateTool())
scraper_registry.register("test_proxy", ScraperTestProxyTool())


async def execute(tool_action: str, parameters: Dict[str, Any]) -> Any:
    """Execute a scraper tool"""
    tool = scraper_registry.get(tool_action)

    if not tool:
        available = scraper_registry.list_tools()
        raise ValueError(
            f"Unknown scraper tool: {tool_action}. "
            f"Available tools: {', '.join(available)}"
        )

    return await tool.execute(**parameters)
