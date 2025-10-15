"""
System Utility Tools

Tools for system health checks, initialization, and configuration management.
"""

import sys
import os
from pathlib import Path
from typing import Any, Dict

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from .base import system_registry, BaseTool
from ..utils.response_formatter import format_success_response


class SystemDoctorTool(BaseTool):
    """Run system health checks"""

    def __init__(self):
        super().__init__("doctor", "Run comprehensive system health checks")

    async def execute(self, **kwargs) -> Dict[str, Any]:
        checks = []

        # Check Python version
        python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        python_ok = sys.version_info >= (3, 8)
        checks.append({
            "check": "Python Version",
            "status": python_version,
            "passed": python_ok,
        })

        # Check .env file
        env_file = Path(".env")
        checks.append({
            "check": ".env File",
            "status": "Found" if env_file.exists() else "Missing",
            "passed": env_file.exists(),
        })

        # Check directories
        for dir_name in ["profiles", "mcp_server"]:
            dir_path = Path(dir_name)
            checks.append({
                "check": f"{dir_name}/ directory",
                "status": "Found" if dir_path.exists() else "Missing",
                "passed": dir_path.exists(),
            })

        # Check dependencies
        dependencies = ["requests", "pandas", "click", "rich", "fastapi", "pydantic"]
        for dep in dependencies:
            try:
                __import__(dep)
                checks.append({"check": f"Package: {dep}", "status": "Installed", "passed": True})
            except ImportError:
                checks.append({"check": f"Package: {dep}", "status": "Missing", "passed": False})

        all_passed = all(c["passed"] for c in checks)

        return format_success_response({
            "checks": checks,
            "all_passed": all_passed,
            "total_checks": len(checks),
            "passed_checks": sum(1 for c in checks if c["passed"]),
        })


class SystemEnvGetTool(BaseTool):
    """Get environment variable value"""

    def __init__(self):
        super().__init__("env_get", "Get environment variable value (non-sensitive)")

    async def execute(self, **kwargs) -> Dict[str, Any]:
        from ..config import MCPServerConfig

        params = self.validate_parameters(kwargs, required=["key"])

        key = params["key"]

        # Check if key is sensitive
        if MCPServerConfig.is_sensitive_key(key):
            return format_success_response(
                data={
                    "key": key,
                    "value": "***FILTERED***",
                    "filtered": True,
                },
                message="This key contains sensitive data and cannot be retrieved",
            )

        value = os.getenv(key)

        return format_success_response({
            "key": key,
            "value": value,
            "exists": value is not None,
        })


class SystemEnvSetTool(BaseTool):
    """Set environment variable value"""

    def __init__(self):
        super().__init__("env_set", "Set environment variable value")

    async def execute(self, **kwargs) -> Dict[str, Any]:
        from dotenv import set_key, find_dotenv

        params = self.validate_parameters(kwargs, required=["key", "value"])

        key = params["key"]
        value = str(params["value"])

        env_file = find_dotenv() or ".env"
        set_key(env_file, key, value)

        return format_success_response(
            data={"key": key, "note": "Restart MCP server for changes to take effect"},
            message=f"Environment variable '{key}' updated successfully",
        )


class SystemFullPipelineTool(BaseTool):
    """Run complete pipeline for all sources (scraper + matcher + email)"""

    def __init__(self):
        super().__init__("full_pipeline", "Run scraper and matcher for all sources with unified email")

    async def execute(self, **kwargs) -> Dict[str, Any]:
        """
        Execute complete pipeline for multiple job sources:

        Phase 1: Run all scrapers (Indeed, Glassdoor, etc.)
        Phase 2: Run all matchers (with send_email=False)
        Phase 3: Reports are auto-generated (color-coded by source)
        Phase 4: Send ONE unified email with all reports attached

        Returns single response at the end only.
        """
        params = self.validate_parameters(
            kwargs,
            required=[],
            optional=["jobs", "locations", "results", "min_score", "scrapers"],
        )

        # Import required modules
        from ..tools import scraper_tools, matcher_tools
        from src.job_matcher import EmailService
        from src.utils.profile_manager import ProfilePaths
        import os
        from dotenv import load_dotenv
        load_dotenv()

        # Get scrapers to run
        scrapers = params.get("scrapers", ["indeed", "glassdoor"])
        if isinstance(scrapers, str):
            scrapers = [scrapers]

        # ====================================================================================
        # PHASE 1: Run ALL scrapers first (collect all jobs from all sources)
        # ====================================================================================
        all_results = {}
        scraper_errors = []

        for scraper in scrapers:
            try:
                # Run scraper for this source
                scraper_params = {
                    "scraper": scraper,
                }
                if "jobs" in params:
                    scraper_params["jobs"] = params["jobs"]
                if "locations" in params:
                    scraper_params["locations"] = params["locations"]
                if "results" in params:
                    scraper_params["results"] = params["results"]

                scraper_result = await scraper_tools.execute("search", scraper_params)

                if scraper_result.get("success"):
                    all_results[scraper] = {
                        "scraper": scraper_result.get("data", {}),
                        "matcher": None,
                    }
                else:
                    scraper_errors.append({
                        "scraper": scraper,
                        "error": scraper_result.get("error", "Unknown error"),
                    })
            except Exception as e:
                scraper_errors.append({
                    "scraper": scraper,
                    "error": str(e),
                })

        # ====================================================================================
        # PHASE 2: Run ALL matchers (process each source's jobs through AI matching)
        # ====================================================================================
        matcher_errors = []
        all_reports = []
        all_matched_jobs = []

        for scraper in scrapers:
            if scraper not in all_results:
                continue  # Skip if scraper failed

            try:
                # Run matcher for this source
                # IMPORTANT: send_email=False - we send ONE email at the end
                matcher_params = {
                    "source": scraper,
                    "send_email": False,  # DON'T send email per source
                }
                if "min_score" in params:
                    matcher_params["min_score"] = params["min_score"]

                matcher_result = await matcher_tools.execute("full_pipeline", matcher_params)

                if matcher_result.get("success"):
                    matcher_data = matcher_result.get("data", {})
                    all_results[scraper]["matcher"] = matcher_data

                    # PHASE 3: Reports are auto-generated by matcher (color-coded by source)
                    # Each report has data-source="indeed" or data-source="glassdoor" in HTML
                    # CSS applies color themes based on data-source attribute
                    report_path = matcher_data.get("output_files", {}).get("report")
                    if report_path:
                        all_reports.append({
                            "source": scraper,
                            "path": report_path,
                            "matched_count": matcher_data.get("stats", {}).get("matched", 0),
                        })

                    # Load matched jobs for email consolidation
                    matched_file = matcher_data.get("output_files", {}).get("matched_jobs")
                    if matched_file:
                        import json
                        from pathlib import Path
                        try:
                            with open(matched_file, "r", encoding="utf-8") as f:
                                matched_jobs = json.load(f)
                                all_matched_jobs.extend(matched_jobs)
                        except Exception as e:
                            # Non-fatal - just log
                            pass
                else:
                    matcher_errors.append({
                        "scraper": scraper,
                        "error": matcher_result.get("error", "Unknown error"),
                    })
            except Exception as e:
                matcher_errors.append({
                    "scraper": scraper,
                    "error": str(e),
                })

        # ====================================================================================
        # PHASE 4: Send ONE unified email with all sources combined
        # ====================================================================================
        email_sent = False
        profile_name = os.getenv("ACTIVE_PROFILE", "default")
        email_service = EmailService(profile_name=profile_name)
        email_enabled = os.getenv("EMAIL_ENABLED", "false").lower() == "true"

        if email_enabled and email_service.is_configured() and all_matched_jobs:
            email_min_matches = int(os.getenv("EMAIL_MIN_MATCHES", "1"))
            if len(all_matched_jobs) >= email_min_matches:
                email_recipients_str = os.getenv("EMAIL_RECIPIENT", "")
                email_recipients = [e.strip() for e in email_recipients_str.split(',') if e.strip()]
                if email_recipients:
                    subject_prefix = os.getenv("EMAIL_SUBJECT_PREFIX", "[Job Matcher]")

                    # Prepare data for multi-source email
                    # Format: [(source, jobs), (source, jobs), ...]
                    jobs_by_source = []
                    report_paths = []

                    for scraper in scrapers:
                        if scraper in all_results and all_results[scraper]["matcher"]:
                            # Load matched jobs for this source
                            matched_file = all_results[scraper]["matcher"].get("output_files", {}).get("matched_jobs")
                            if matched_file:
                                import json
                                from pathlib import Path
                                try:
                                    with open(matched_file, "r", encoding="utf-8") as f:
                                        source_jobs = json.load(f)
                                        jobs_by_source.append((scraper, source_jobs))
                                except Exception:
                                    pass

                            # Add color-coded report to attachments
                            report_path = all_results[scraper]["matcher"].get("output_files", {}).get("report")
                            if report_path:
                                report_paths.append(report_path)

                    # Send ONE email with:
                    # - Multi-source subject: "30 Total Matches (Indeed: 20, Glassdoor: 10)"
                    # - Email body with sections for each source (color-coded with icons)
                    # - All reports attached (each color-coded by source)
                    for recipient in email_recipients:
                        try:
                            email_service.send_multi_source_report(
                                recipient,
                                jobs_by_source,
                                report_paths,
                                subject_prefix
                            )
                            email_sent = True
                        except Exception as e:
                            # Log but don't fail the pipeline
                            pass

        # ====================================================================================
        # Build final comprehensive response (SINGLE response returned to LLM)
        # ====================================================================================
        result_data = {
            "pipeline_summary": {
                "scrapers_run": scrapers,
                "scrapers_succeeded": len([s for s in scrapers if s in all_results]),
                "scrapers_failed": len(scraper_errors),
                "matchers_succeeded": len([s for s in scrapers if s in all_results and all_results[s]["matcher"] is not None]),
                "matchers_failed": len(matcher_errors),
                "total_matched_jobs": len(all_matched_jobs),
                "reports_generated": len(all_reports),
                "email_sent": email_sent,
            },
            "results_by_source": {
                scraper: {
                    "jobs_scraped": all_results[scraper]["scraper"].get("total_jobs_found", 0) if scraper in all_results else 0,
                    "jobs_matched": all_results[scraper]["matcher"].get("stats", {}).get("matched", 0) if scraper in all_results and all_results[scraper]["matcher"] else 0,
                    "report_path": next((r["path"] for r in all_reports if r["source"] == scraper), None),
                    "report_color_coded": True if scraper in all_results and all_results[scraper]["matcher"] else False,
                }
                for scraper in scrapers
            },
            "all_reports": all_reports,
        }

        # Add error details if any
        if scraper_errors:
            result_data["scraper_errors"] = scraper_errors
        if matcher_errors:
            result_data["matcher_errors"] = matcher_errors

        # Build summary message
        message_parts = [
            f"[SUCCESS] Full pipeline complete across {len(scrapers)} sources ({', '.join(scrapers)})",
            f"[SUCCESS] Total matches: {len(all_matched_jobs)} jobs",
            f"[SUCCESS] Reports generated: {len(all_reports)} color-coded HTML reports",
        ]

        if email_sent:
            message_parts.append(f"[SUCCESS] Email sent with all {len(all_reports)} reports attached")

        if scraper_errors or matcher_errors:
            message_parts.append(f"[WARNING] Errors: {len(scraper_errors)} scraper, {len(matcher_errors)} matcher")

        message = "\n".join(message_parts)

        return format_success_response(data=result_data, message=message)


# Register tools
system_registry.register("doctor", SystemDoctorTool())
system_registry.register("env_get", SystemEnvGetTool())
system_registry.register("env_set", SystemEnvSetTool())
system_registry.register("full_pipeline", SystemFullPipelineTool())


async def execute(tool_action: str, parameters: Dict[str, Any]) -> Any:
    """Execute a system tool"""
    tool = system_registry.get(tool_action)
    if not tool:
        raise ValueError(f"Unknown system tool: {tool_action}")
    return await tool.execute(**parameters)
