#!/usr/bin/env python3
"""
Job Search CLI - Unified Command-Line Interface

A comprehensive CLI for job searching, matching, and management.

Usage:
    python cli.py [COMMAND] [OPTIONS]

Commands:
    scraper    Job scraping commands
    matcher    Job matching commands
    email      Email configuration and delivery
    tracker    Job tracker management
    system     System utilities and health checks

Common Aliases:
    search     Run job search (alias for scraper search)
    match      Run full matching pipeline (alias for matcher full-pipeline)
    stats      Show tracker statistics (alias for tracker stats)
"""

import sys
from pathlib import Path

import click
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.cli.utils import (
    console,
    print_header,
    print_error,
    print_info,
    cli_state,
    handle_error,
)

# Load environment variables
load_dotenv()


# =============================================================================
# Main CLI Group
# =============================================================================

@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.option("--quiet", "-q", is_flag=True, help="Minimal output")
@click.option("--config", type=click.Path(exists=True), help="Custom config file")
@click.version_option(version="1.0.0", prog_name="Job Search CLI")
@click.pass_context
def cli(ctx, verbose, quiet, config):
    """Job Search CLI - Unified interface for job hunting automation"""

    # Set CLI state
    cli_state.set_verbose(verbose)
    cli_state.set_quiet(quiet)
    cli_state.set_config_file(config)

    # Ensure context object exists
    ctx.ensure_object(dict)
    ctx.obj["state"] = cli_state


# =============================================================================
# Import Command Groups
# =============================================================================

def import_command_groups():
    """Dynamically import command groups"""
    try:
        # Import scraper commands
        try:
            from src.cli.scraper import scraper_group
            cli.add_command(scraper_group, name="scraper")
        except (ImportError, ModuleNotFoundError) as e:
            if cli_state.verbose:
                print_error(f"Failed to load scraper commands: {e}")

        # Import matcher commands
        try:
            from src.job_matcher.cli import matcher_group
            cli.add_command(matcher_group, name="matcher")
        except (ImportError, ModuleNotFoundError) as e:
            if cli_state.verbose:
                print_error(f"Failed to load matcher commands: {e}")

        # Import email commands
        try:
            from src.job_matcher.cli_email import email_group
            cli.add_command(email_group, name="email")
        except (ImportError, ModuleNotFoundError) as e:
            if cli_state.verbose:
                print_error(f"Failed to load email commands: {e}")

        # Import tracker commands
        try:
            from src.job_matcher.cli_tracker import tracker_group
            cli.add_command(tracker_group, name="tracker")
        except (ImportError, ModuleNotFoundError) as e:
            if cli_state.verbose:
                print_error(f"Failed to load tracker commands: {e}")

        # Import profile commands
        try:
            from src.cli.profile import profile_group
            cli.add_command(profile_group, name="profile")
        except (ImportError, ModuleNotFoundError) as e:
            if cli_state.verbose:
                print_error(f"Failed to load profile commands: {e}")

        # Import MCP commands
        try:
            from src.cli.mcp import mcp_group
            cli.add_command(mcp_group, name="mcp")
        except (ImportError, ModuleNotFoundError) as e:
            if cli_state.verbose:
                print_error(f"Failed to load MCP commands: {e}")

        # Import system commands (defined below)
        cli.add_command(system_group, name="system")

    except Exception as e:
        if cli_state.verbose:
            handle_error(e, verbose=True)
        else:
            print_error(f"Failed to initialize CLI: {e}")
        sys.exit(1)


# =============================================================================
# System Commands
# =============================================================================

@click.group()
def system_group():
    """System utilities and health checks"""
    pass


@system_group.command(name="doctor")
def system_doctor():
    """Run system health checks"""
    from src.cli.utils import print_section, print_success, print_warning, print_table

    print_header("System Health Check")

    checks = []
    all_passed = True

    # Check Python version
    import sys
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    python_ok = sys.version_info >= (3, 8)
    checks.append(["Python Version", python_version, "✓" if python_ok else "✗"])
    if not python_ok:
        all_passed = False

    # Check .env file
    env_file = Path(".env")
    env_exists = env_file.exists()
    checks.append([".env File", "Found" if env_exists else "Missing", "✓" if env_exists else "✗"])
    if not env_exists:
        all_passed = False

    # Check directories
    for dir_name in ["data", "reports", "templates"]:
        dir_path = Path(dir_name)
        exists = dir_path.exists()
        checks.append([f"{dir_name}/ directory", "Found" if exists else "Missing", "✓" if exists else "⚠"])

    # Check required files
    required_files = [
        ("templates/resume.txt", "Resume"),
        ("templates/requirements.yaml", "Requirements"),
    ]

    for file_path, label in required_files:
        path = Path(file_path)
        exists = path.exists()
        checks.append([label, "Found" if exists else "Missing", "✓" if exists else "⚠"])

    # Check dependencies
    print_section("Checking Dependencies")

    dependencies = [
        ("requests", "Job Scraper"),
        ("pandas", "Job Scraper"),
        ("click", "CLI"),
        ("rich", "CLI"),
        ("questionary", "CLI"),
        ("yaml", "Job Matcher", "pyyaml"),
    ]

    for dep_info in dependencies:
        if len(dep_info) == 3:
            module_name, label, package_name = dep_info
        else:
            module_name, label = dep_info
            package_name = module_name

        try:
            __import__(module_name)
            checks.append([f"{label} ({package_name})", "Installed", "✓"])
        except ImportError:
            checks.append([f"{label} ({package_name})", "Missing", "✗"])
            all_passed = False

    # Print results
    print_section("Results")
    print_table(
        title="Health Check Results",
        columns=["Check", "Status", "Result"],
        rows=checks,
        show_lines=True,
    )

    if all_passed:
        print_success("\nAll critical checks passed!")
    else:
        print_warning("\nSome checks failed. Please review above.")

    return 0 if all_passed else 1


@system_group.command(name="init")
@click.option("--force", is_flag=True, help="Overwrite existing configuration")
def system_init(force):
    """Initialize project for first-time use"""
    from src.cli.utils import print_section, print_success, print_warning, ensure_dir_exists, confirm

    print_header("Project Initialization")

    # Check if already initialized
    env_file = Path(".env")
    if env_file.exists() and not force:
        print_warning(".env file already exists")
        if not confirm("Overwrite existing configuration?"):
            print_info("Initialization cancelled")
            return

    # Create directories
    print_section("Creating Directories")
    dirs = ["data", "reports", "templates", "credentials"]

    for dir_name in dirs:
        dir_path = ensure_dir_exists(dir_name)
        print_success(f"Created: {dir_path}")

    # Create template .env if needed
    print_section("Creating Configuration")

    if not env_file.exists() or force:
        env_template = """# =============================================================================
# Job Scraper Configuration
# =============================================================================

# IPRoyal Proxy Credentials
IPROYAL_HOST=geo.iproyal.com
IPROYAL_PORT=12321
IPROYAL_USERNAME=your_username
IPROYAL_PASSWORD=your_password

# Job Search Configuration
JOBS=['software engineer', 'python developer']
LOCATIONS=['Remote']
RESULTS_PER_SEARCH=50
OUTPUT_FORMAT=both
DEDUPLICATE=true
PROXY_ROTATION_COUNT=1
RATE_LIMIT_DELAY=2.5

# =============================================================================
# Job Matcher Configuration
# =============================================================================

# llama-server Configuration
LLAMA_SERVER_URL=http://localhost:8080
LLAMA_CONTEXT_SIZE=8192
LLAMA_TEMPERATURE=0.3
LLAMA_MAX_TOKENS=2560

# Job Matching Configuration
RESUME_PATH=templates/resume.txt
REQUIREMENTS_PATH=templates/requirements.yaml
MIN_MATCH_SCORE=70
REPORT_OUTPUT_DIR=reports/
MATCH_THREADS=4

# Job Tracker Database
JOB_TRACKER_DB=job_tracker.db

# =============================================================================
# Email Configuration
# =============================================================================

# Enable/disable automatic email delivery
EMAIL_ENABLED=false

# Email address to send reports to
EMAIL_RECIPIENT=

# Send email automatically when pipeline completes
EMAIL_SEND_ON_COMPLETION=true

# Only send email if at least this many matches are found
EMAIL_MIN_MATCHES=1

# Email subject line prefix
EMAIL_SUBJECT_PREFIX=[Job Matcher]
"""
        with open(env_file, "w") as f:
            f.write(env_template)

        print_success(f"Created: {env_file}")
    else:
        print_info(f"Keeping existing: {env_file}")

    # Create template resume
    resume_file = Path("templates/resume.txt")
    if not resume_file.exists() or force:
        resume_template = """Your Name
your.email@example.com | (123) 456-7890 | City, State

PROFESSIONAL SUMMARY
[Write a brief 2-3 sentence summary of your professional background]

EXPERIENCE
[Company Name] - [Job Title]
[Start Date] - [End Date]
- [Responsibility/Achievement]
- [Responsibility/Achievement]

EDUCATION
[Degree] in [Field]
[University Name] - [Graduation Year]

SKILLS
- [Skill Category]: [Skills]
- [Skill Category]: [Skills]
"""
        with open(resume_file, "w") as f:
            f.write(resume_template)
        print_success(f"Created: {resume_file}")
    else:
        print_info(f"Keeping existing: {resume_file}")

    # Create template requirements
    requirements_file = Path("templates/requirements.yaml")
    if not requirements_file.exists() or force:
        requirements_template = """candidate_profile:
  summary: |
    Brief description of who you are and your experience

  core_strengths:
    - Your main professional strengths

  technical_skills:
    - Software/tools with proficiency levels

  career_goals: |
    What you're looking for in your next role

  must_haves:
    - Non-negotiable requirements (remote work, salary, etc.)

  avoid:
    - Things you don't want in a job

preferences:
  remote_only: true
  min_salary: 70000
  max_salary: 130000
  salary_period: yearly
  locations:
    - Remote
"""
        with open(requirements_file, "w") as f:
            f.write(requirements_template)
        print_success(f"Created: {requirements_file}")
    else:
        print_info(f"Keeping existing: {requirements_file}")

    # Summary
    print_section("Next Steps")
    print_info("1. Edit .env with your IPRoyal proxy credentials")
    print_info("2. Edit templates/resume.txt with your resume")
    print_info("3. Edit templates/requirements.yaml with your job requirements")
    print_info("4. Run: python cli.py system doctor")
    print_info("5. Run: python cli.py scraper search")

    print_success("\nInitialization complete!")


@system_group.group(name="templates")
def templates_group():
    """Template file management commands"""
    pass


@templates_group.command(name="import-resume")
@click.argument("source_file", type=click.Path(exists=True))
@click.option("--backup", is_flag=True, help="Backup existing resume before overwriting")
def import_resume(source_file, backup):
    """Import resume from external file (supports .txt, .pdf, .docx)"""
    from src.cli.utils import print_section, print_success, print_warning, print_info, confirm
    from datetime import datetime
    import shutil

    print_header("Import Resume")

    source_path = Path(source_file)
    dest_path = Path("templates/resume.txt")

    # Display file info
    print_section("Source File")
    file_size = source_path.stat().st_size / 1024  # KB
    print_info(f"  Path: {source_path}")
    print_info(f"  Type: {source_path.suffix.upper()[1:]}")
    print_info(f"  Size: {file_size:.1f} KB")

    # Convert file to text using ResumeAnalyzer
    print_section("Converting to Text")

    try:
        from src.job_matcher.resume_analyzer import ResumeAnalyzer

        analyzer = ResumeAnalyzer()
        resume_text = analyzer._load_resume_file(str(source_path))

        if not resume_text or not resume_text.strip():
            print_error("Failed to extract text from resume")
            sys.exit(1)

        print_success(f"Conversion successful ({len(resume_text)} characters)")

    except Exception as e:
        print_error(f"Failed to load resume: {e}")
        sys.exit(1)

    # Backup existing resume if requested
    if backup and dest_path.exists():
        print_section("Backing Up Existing Resume")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = Path(f"templates/resume.txt.backup.{timestamp}")

        try:
            shutil.copy2(dest_path, backup_path)
            print_success(f"Backup saved to: {backup_path}")
        except Exception as e:
            print_warning(f"Failed to create backup: {e}")

    # Save new resume
    print_section("Saving Resume")

    try:
        # Ensure templates directory exists
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        with open(dest_path, "w", encoding="utf-8") as f:
            f.write(resume_text)

        print_success(f"Resume saved to: {dest_path}")

    except Exception as e:
        print_error(f"Failed to save resume: {e}")
        sys.exit(1)

    # Validate new resume
    print_section("Validating Resume")

    try:
        analyzer = ResumeAnalyzer()
        analyzer.load_resume(str(dest_path))

        print_success("Resume loaded successfully")

        # Show some stats
        lines = resume_text.split('\n')
        non_empty_lines = [l for l in lines if l.strip()]
        print_info(f"  - {len(resume_text)} characters")
        print_info(f"  - {len(non_empty_lines)} non-empty lines")

    except Exception as e:
        print_warning(f"Resume validation warning: {e}")

    print_success("\nImport complete!")


@templates_group.command(name="import-requirements")
@click.argument("source_file", type=click.Path(exists=True))
@click.option("--backup", is_flag=True, help="Backup existing requirements before overwriting")
@click.option("--validate/--no-validate", default=True, help="Validate YAML syntax")
def import_requirements(source_file, backup, validate):
    """Import requirements from external YAML file"""
    from src.cli.utils import print_section, print_success, print_warning, print_info
    from datetime import datetime
    import shutil
    import yaml

    print_header("Import Requirements")

    source_path = Path(source_file)
    dest_path = Path("templates/requirements.yaml")

    # Display file info
    print_section("Source File")
    file_size = source_path.stat().st_size / 1024  # KB
    print_info(f"  Path: {source_path}")
    print_info(f"  Type: {source_path.suffix.upper()[1:]}")
    print_info(f"  Size: {file_size:.1f} KB")

    # Validate YAML if requested
    if validate:
        print_section("Validating YAML")

        try:
            with open(source_path, "r", encoding="utf-8") as f:
                requirements_data = yaml.safe_load(f)

            if not requirements_data:
                print_error("YAML file is empty")
                sys.exit(1)

            print_success("YAML syntax is valid")

            # Check for required sections
            if "candidate_profile" in requirements_data:
                print_info("  ✓ Found candidate_profile section")
            else:
                print_warning("  ⚠ Missing candidate_profile section")

            if "preferences" in requirements_data:
                print_info("  ✓ Found preferences section")
            else:
                print_warning("  ⚠ Missing preferences section")

        except yaml.YAMLError as e:
            print_error(f"Invalid YAML syntax: {e}")
            sys.exit(1)
        except Exception as e:
            print_error(f"Failed to validate requirements: {e}")
            sys.exit(1)

    # Backup existing requirements if requested
    if backup and dest_path.exists():
        print_section("Backing Up Existing Requirements")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = Path(f"templates/requirements.yaml.backup.{timestamp}")

        try:
            shutil.copy2(dest_path, backup_path)
            print_success(f"Backup saved to: {backup_path}")
        except Exception as e:
            print_warning(f"Failed to create backup: {e}")

    # Copy new requirements
    print_section("Saving Requirements")

    try:
        # Ensure templates directory exists
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        shutil.copy2(source_path, dest_path)
        print_success(f"Requirements saved to: {dest_path}")

    except Exception as e:
        print_error(f"Failed to save requirements: {e}")
        sys.exit(1)

    # Test loading with ResumeAnalyzer
    print_section("Testing Requirements")

    try:
        from src.job_matcher.resume_analyzer import ResumeAnalyzer

        analyzer = ResumeAnalyzer()
        analyzer.load_requirements(str(dest_path))

        print_success("Requirements loaded successfully")

    except Exception as e:
        print_warning(f"Requirements validation warning: {e}")

    print_success("\nImport complete!")


@templates_group.command(name="export")
@click.argument("destination_dir", type=click.Path())
@click.option("--timestamp", is_flag=True, help="Add timestamp to exported files")
def export_templates(destination_dir, timestamp):
    """Export templates to external directory for backup/sharing"""
    from src.cli.utils import print_section, print_success, print_warning, print_info, ensure_dir_exists
    from datetime import datetime
    import shutil

    print_header("Export Templates")

    dest_dir = Path(destination_dir)

    # Create destination directory
    print_section("Preparing Destination")

    try:
        ensure_dir_exists(str(dest_dir))
        print_success(f"Destination: {dest_dir}")
    except Exception as e:
        print_error(f"Failed to create destination directory: {e}")
        sys.exit(1)

    # Prepare filenames
    if timestamp:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        resume_name = f"resume_{ts}.txt"
        requirements_name = f"requirements_{ts}.yaml"
    else:
        resume_name = "resume.txt"
        requirements_name = "requirements.yaml"

    # Export files
    print_section("Exporting Files")

    exported_count = 0

    # Export resume
    resume_src = Path("templates/resume.txt")
    if resume_src.exists():
        try:
            resume_dest = dest_dir / resume_name
            shutil.copy2(resume_src, resume_dest)
            print_success(f"✓ Exported resume: {resume_dest}")
            exported_count += 1
        except Exception as e:
            print_warning(f"Failed to export resume: {e}")
    else:
        print_warning("⚠ Resume not found: templates/resume.txt")

    # Export requirements
    req_src = Path("templates/requirements.yaml")
    if req_src.exists():
        try:
            req_dest = dest_dir / requirements_name
            shutil.copy2(req_src, req_dest)
            print_success(f"✓ Exported requirements: {req_dest}")
            exported_count += 1
        except Exception as e:
            print_warning(f"Failed to export requirements: {e}")
    else:
        print_warning("⚠ Requirements not found: templates/requirements.yaml")

    if exported_count > 0:
        print_success(f"\nExport complete! {exported_count} file(s) exported")
    else:
        print_error("\nNo files exported")
        sys.exit(1)


@templates_group.command(name="list")
def list_templates():
    """Show current template files and their status"""
    from src.cli.utils import print_section, print_success, print_warning, print_info, print_key_value_table
    from datetime import datetime

    print_header("Template Files")

    # Check resume
    print_section("Resume")

    resume_path = Path("templates/resume.txt")
    if resume_path.exists():
        stat = resume_path.stat()
        size_kb = stat.st_size / 1024
        modified = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")

        # Try to get some stats
        try:
            with open(resume_path, "r", encoding="utf-8") as f:
                content = f.read()
                lines = content.split('\n')
                non_empty = [l for l in lines if l.strip()]

            resume_info = {
                "Path": str(resume_path),
                "Status": "✓ Valid",
                "Size": f"{size_kb:.1f} KB",
                "Modified": modified,
                "Characters": f"{len(content):,}",
                "Lines (non-empty)": len(non_empty),
            }

        except Exception as e:
            resume_info = {
                "Path": str(resume_path),
                "Status": f"✗ Error: {e}",
                "Size": f"{size_kb:.1f} KB",
                "Modified": modified,
            }

        print_key_value_table(resume_info, title="Resume Details")

    else:
        print_warning("⚠ Resume not found: templates/resume.txt")

    # Check requirements
    print_section("Requirements")

    req_path = Path("templates/requirements.yaml")
    if req_path.exists():
        stat = req_path.stat()
        size_kb = stat.st_size / 1024
        modified = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")

        # Try to load and get some stats
        try:
            import yaml

            with open(req_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            profile_sections = 0
            preferences = 0

            if data:
                if "candidate_profile" in data and data["candidate_profile"]:
                    profile_sections = len(data["candidate_profile"])
                if "preferences" in data and data["preferences"]:
                    preferences = len(data["preferences"])

            req_info = {
                "Path": str(req_path),
                "Status": "✓ Valid",
                "Size": f"{size_kb:.1f} KB",
                "Modified": modified,
                "Profile Sections": profile_sections,
                "Preferences": preferences,
            }

        except Exception as e:
            req_info = {
                "Path": str(req_path),
                "Status": f"✗ Error: {e}",
                "Size": f"{size_kb:.1f} KB",
                "Modified": modified,
            }

        print_key_value_table(req_info, title="Requirements Details")

    else:
        print_warning("⚠ Requirements not found: templates/requirements.yaml")


@templates_group.command(name="validate")
def validate_templates():
    """Validate template files"""
    from src.cli.utils import print_section, print_success, print_warning, print_error, print_info

    print_header("Template Validation")

    issues = 0
    warnings_count = 0

    # Validate resume
    print_section("Resume (templates/resume.txt)")

    resume_path = Path("templates/resume.txt")

    if not resume_path.exists():
        print_error("✗ File does not exist")
        issues += 1
    else:
        print_success("✓ File exists")

        try:
            with open(resume_path, "r", encoding="utf-8") as f:
                content = f.read()

            print_success("✓ File readable")

            if not content.strip():
                print_error("✗ File is empty")
                issues += 1
            else:
                print_success(f"✓ Contains text content ({len(content)} characters)")

                # Check for common resume sections
                content_lower = content.lower()

                if "@" not in content:
                    print_warning("⚠ Warning: No email address found")
                    warnings_count += 1

                if "experience" not in content_lower and "work history" not in content_lower:
                    print_warning("⚠ Warning: No experience section found")
                    warnings_count += 1

                if "education" not in content_lower:
                    print_warning("⚠ Warning: No education section found")
                    warnings_count += 1

                if "skill" not in content_lower:
                    print_warning("⚠ Warning: No skills section found")
                    warnings_count += 1

                # Try loading with ResumeAnalyzer
                try:
                    from src.job_matcher.resume_analyzer import ResumeAnalyzer

                    analyzer = ResumeAnalyzer()
                    analyzer.load_resume(str(resume_path))
                    print_success("✓ Loads successfully with ResumeAnalyzer")

                except Exception as e:
                    print_warning(f"⚠ ResumeAnalyzer warning: {e}")
                    warnings_count += 1

        except Exception as e:
            print_error(f"✗ Failed to read file: {e}")
            issues += 1

    # Validate requirements
    print_section("Requirements (templates/requirements.yaml)")

    req_path = Path("templates/requirements.yaml")

    if not req_path.exists():
        print_error("✗ File does not exist")
        issues += 1
    else:
        print_success("✓ File exists")

        try:
            with open(req_path, "r", encoding="utf-8") as f:
                content = f.read()

            print_success("✓ File readable")

            # Validate YAML syntax
            import yaml

            try:
                data = yaml.safe_load(content)
                print_success("✓ Valid YAML syntax")

                if not data:
                    print_error("✗ File is empty")
                    issues += 1
                else:
                    # Check for required sections
                    if "candidate_profile" in data:
                        print_success("✓ Contains candidate_profile section")
                    else:
                        print_warning("⚠ Warning: Missing candidate_profile section")
                        warnings_count += 1

                    if "preferences" in data:
                        print_success("✓ Contains preferences section")
                    else:
                        print_warning("⚠ Warning: Missing preferences section")
                        warnings_count += 1

                    # Try loading with ResumeAnalyzer
                    try:
                        from src.job_matcher.resume_analyzer import ResumeAnalyzer

                        analyzer = ResumeAnalyzer()
                        analyzer.load_requirements(str(req_path))
                        print_success("✓ Loads successfully with ResumeAnalyzer")

                    except Exception as e:
                        print_warning(f"⚠ ResumeAnalyzer warning: {e}")
                        warnings_count += 1

            except yaml.YAMLError as e:
                print_error(f"✗ Invalid YAML syntax: {e}")
                issues += 1

        except Exception as e:
            print_error(f"✗ Failed to read file: {e}")
            issues += 1

    # Summary
    print_section("Summary")

    if issues == 0 and warnings_count == 0:
        print_success("✓ All validations passed!")
    elif issues == 0:
        print_warning(f"⚠ Validation passed with {warnings_count} warning(s)")
    else:
        print_error(f"✗ Validation failed: {issues} error(s), {warnings_count} warning(s)")
        sys.exit(1)


@system_group.command(name="clean")
@click.option("--data", is_flag=True, help="Clean data directory")
@click.option("--reports", is_flag=True, help="Clean reports directory")
@click.option("--checkpoints", is_flag=True, help="Clean checkpoint files")
@click.option("--all", "clean_all", is_flag=True, help="Clean everything")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation")
def system_clean(data, reports, checkpoints, clean_all, yes):
    """Clean generated files and directories"""
    from src.cli.utils import confirm, print_section, print_success, print_warning
    import shutil

    print_header("System Cleanup")

    if not any([data, reports, checkpoints, clean_all]):
        print_error("Please specify what to clean: --data, --reports, --checkpoints, or --all")
        return

    targets = []

    if data or clean_all:
        targets.append(("data/*.json", "Data files"))
        targets.append(("data/*.csv", "CSV files"))

    if reports or clean_all:
        targets.append(("reports/*.html", "Report files"))

    if checkpoints or clean_all:
        targets.append(("data/.checkpoint_active.json", "Checkpoint file"))

    if not targets:
        print_info("Nothing to clean")
        return

    # Confirm
    if not yes:
        print_section("Files to Clean")
        for pattern, description in targets:
            print_info(f"  - {description}: {pattern}")

        if not confirm("\nProceed with cleanup?"):
            print_info("Cleanup cancelled")
            return

    # Clean
    print_section("Cleaning")
    for pattern, description in targets:
        if "*" in pattern:
            import glob
            files = glob.glob(pattern)
            for file_path in files:
                try:
                    Path(file_path).unlink()
                    print_success(f"Deleted: {file_path}")
                except Exception as e:
                    print_warning(f"Failed to delete {file_path}: {e}")
        else:
            file_path = Path(pattern)
            if file_path.exists():
                try:
                    file_path.unlink()
                    print_success(f"Deleted: {file_path}")
                except Exception as e:
                    print_warning(f"Failed to delete {file_path}: {e}")

    print_success("\nCleanup complete!")


# =============================================================================
# Convenience Aliases
# =============================================================================

@cli.command(name="search")
@click.option("--jobs", "-j", multiple=True, help="Job titles to search")
@click.option("--locations", "-l", multiple=True, help="Locations to search")
@click.option("--results", "-r", type=int, help="Results per search")
@click.option("--scraper", "-s", type=click.Choice(['indeed', 'glassdoor', 'all'], case_sensitive=False), default='all', help="Scraper to use (default: all)")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation")
@click.pass_context
def search_alias(ctx, jobs, locations, results, scraper, yes):
    """Quick search (alias for 'scraper search')"""
    from src.cli.scraper import search
    ctx.invoke(search, jobs=jobs, locations=locations, results=results, scraper=scraper, yes=yes, dry_run=False)


@cli.command(name="match")
@click.option("--input", "-i", "input_file", default=None, help="Input jobs JSON")
@click.option("--source", "-s", type=click.Choice(['indeed', 'glassdoor', 'linkedin', 'ziprecruiter'], case_sensitive=False), help="Filter by job source")
@click.option("--min-score", type=int, help="Minimum match score")
@click.option("--resume", "resume_checkpoint", is_flag=True, help="Resume from checkpoint")
@click.option("--no-skip", is_flag=True, help="Process all jobs (ignore tracker)")
@click.option("--email", is_flag=True, help="Force send email after completion")
@click.option("--no-email", is_flag=True, help="Disable email after completion")
@click.pass_context
def match_alias(ctx, input_file, source, min_score, resume_checkpoint, no_skip, email, no_email):
    """Quick match (alias for 'matcher full-pipeline')"""
    from src.job_matcher.cli import full_pipeline
    ctx.invoke(full_pipeline, input_file=input_file, source=source, min_score=min_score, resume_checkpoint=resume_checkpoint, no_skip=no_skip, yes=False, email=email, no_email=no_email)


@cli.command(name="stats")
@click.pass_context
def stats_alias(ctx):
    """Show stats (alias for 'tracker stats')"""
    from src.job_matcher.cli_tracker import show_stats
    ctx.invoke(show_stats)


# =============================================================================
# Main Entry Point
# =============================================================================

def main():
    """Main entry point"""
    try:
        # Check for and run migration if needed (silent unless migration occurs)
        try:
            from src.utils.profile_manager import migrate_legacy_structure

            migrated = migrate_legacy_structure()
            if migrated:
                # Give user a moment to see migration message
                import time

                time.sleep(2)
        except Exception:
            # Silently ignore migration errors - user can run manually if needed
            pass

        # Import command groups
        import_command_groups()

        # Run CLI
        cli()

    except KeyboardInterrupt:
        print_error("\n\nInterrupted by user")
        sys.exit(130)
    except Exception as e:
        handle_error(e, verbose=cli_state.verbose)
        sys.exit(1)


if __name__ == "__main__":
    main()
