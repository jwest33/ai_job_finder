"""
Profile CLI Commands

Command-line interface for profile management.
"""

import sys
import click
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.utils.profile_manager import ProfileManager, ProfilePaths, migrate_legacy_structure
from src.cli.utils import (
    console,
    print_header,
    print_section,
    print_success,
    print_warning,
    print_error,
    print_info,
    print_table,
    print_key_value_table,
    confirm,
)


@click.group()
def profile_group():
    """Profile management commands"""
    pass


@profile_group.command(name="list")
def list_profiles():
    """List all available profiles"""
    print_header("Available Profiles")

    manager = ProfileManager()
    profiles = manager.list_profiles()

    if not profiles:
        print_warning("No profiles found")
        print_info("\nCreate a profile with: python cli.py profile create <name>")
        return

    active_profile = manager.get_active_profile()

    # Build table data
    rows = []
    for profile_name in profiles:
        try:
            info = manager.get_profile_info(profile_name)

            # Active indicator
            status = "[SUCCESS] Active" if info["is_active"] else ""

            # File counts
            files_summary = (
                f"{info['files']['data_files']} data, "
                f"{info['files']['reports']} reports"
            )

            # Job count
            job_count = ""
            if info["tracker_stats"]:
                job_count = str(info["tracker_stats"]["total_jobs"])

            rows.append([profile_name, status, files_summary, job_count])

        except Exception as e:
            rows.append([profile_name, "Error", str(e), ""])

    print_table(
        title="Profiles",
        columns=["Profile", "Status", "Files", "Jobs Tracked"],
        rows=rows,
        show_lines=True,
    )

    print_info(f"\nActive profile: {active_profile}")
    print_info("Switch profiles with: python cli.py profile switch <name>")


@profile_group.command(name="current")
def show_current():
    """Show current active profile details"""
    manager = ProfileManager()
    profile_name = manager.get_active_profile()

    print_header(f"Current Profile: {profile_name}")

    try:
        info = manager.get_profile_info(profile_name)

        # Basic info
        print_section("Profile Information")
        basic_info = {
            "Name": info["name"],
            "Description": info["description"],
            "Created": info["created_at"],
            "Status": "[SUCCESS] Active" if info["is_active"] else "Inactive",
        }

        if "cloned_from" in info:
            basic_info["Cloned From"] = info["cloned_from"]

        print_key_value_table(basic_info)

        # Paths
        print_section("Paths")
        print_key_value_table(info["paths"])

        # Files
        print_section("Files")
        files_info = {
            "Resume": "[SUCCESS] Found" if info["files"]["resume_exists"] else "[ERROR] Missing",
            "Requirements": "[SUCCESS] Found"
            if info["files"]["requirements_exists"]
            else "[ERROR] Missing",
            "Data Files": info["files"]["data_files"],
            "Reports": info["files"]["reports"],
        }
        print_key_value_table(files_info)

        # Tracker stats
        if info["tracker_stats"]:
            print_section("Job Tracker Statistics")
            stats = info["tracker_stats"]
            tracker_info = {
                "Total Jobs": stats["total_jobs"],
                "Average Score": f"{stats['avg_score']:.1f}",
                "High Matches (≥80)": stats["high_matches"],
                "Medium Matches (70-79)": stats["medium_matches"],
                "Reposted Jobs": stats["reposted_jobs"],
            }
            print_key_value_table(tracker_info)

        # Email configuration
        print_section("Email Configuration")
        profile_config = manager.get_profile_email_config(profile_name)

        if profile_config:
            email_info = {
                "Source": "Profile-specific",
                "Recipients": ", ".join(profile_config.get("recipients", [])),
            }
            if "subject_prefix" in profile_config:
                email_info["Subject Prefix"] = profile_config["subject_prefix"]
            if "enabled" in profile_config:
                email_info["Enabled"] = "Yes" if profile_config["enabled"] else "No"
            if "min_matches" in profile_config:
                email_info["Min Matches"] = str(profile_config["min_matches"])
            print_key_value_table(email_info)
        else:
            import os
            from dotenv import load_dotenv
            load_dotenv()
            global_recipient = os.getenv("EMAIL_RECIPIENT", "")
            global_recipients = [e.strip() for e in global_recipient.split(",") if e.strip()]

            email_info = {
                "Source": "Global (.env)",
                "Recipients": ", ".join(global_recipients) if global_recipients else "Not configured",
            }
            print_key_value_table(email_info)
            print_info("\nConfigure profile-specific email:")
            print_info(f"  python cli.py profile email-set {profile_name} your@email.com")

    except Exception as e:
        print_error(f"Failed to get profile info: {e}")
        sys.exit(1)


@profile_group.command(name="create")
@click.argument("profile_name")
@click.option("--description", "-d", help="Profile description")
@click.option(
    "--clone",
    "-c",
    help="Clone settings from existing profile",
)
def create_profile(profile_name, description, clone):
    """Create a new profile"""
    print_header(f"Create Profile: {profile_name}")

    manager = ProfileManager()

    # Check if profile already exists
    if manager.profile_exists(profile_name):
        print_error(f"Profile '{profile_name}' already exists")
        sys.exit(1)

    # Check clone source if specified
    if clone and not manager.profile_exists(clone):
        print_error(f"Clone source profile '{clone}' does not exist")
        sys.exit(1)

    try:
        if clone:
            print_info(f"Cloning from profile: {clone}")

        manager.create_profile(
            profile_name=profile_name, description=description, clone_from=clone
        )

        print_success(f"Profile '{profile_name}' created successfully!")

        # Show paths
        paths = ProfilePaths(profile_name)
        print_section("Profile Paths")
        print_info(f"  Templates: {paths.templates_dir}")
        print_info(f"  Data:      {paths.data_dir}")
        print_info(f"  Reports:   {paths.reports_dir}")

        print_section("Next Steps")
        if not clone:
            print_info("1. Edit your resume:")
            print_info(f"   {paths.resume_path}")
            print_info("2. Edit your job requirements:")
            print_info(f"   {paths.requirements_path}")

        print_info("3. Switch to this profile:")
        print_info(f"   python cli.py profile switch {profile_name}")
        print_info("4. Start searching:")
        print_info("   python cli.py search")

    except Exception as e:
        print_error(f"Failed to create profile: {e}")
        sys.exit(1)


@profile_group.command(name="switch")
@click.argument("profile_name")
def switch_profile(profile_name):
    """Switch to a different profile"""
    print_header(f"Switch to Profile: {profile_name}")

    manager = ProfileManager()

    if not manager.profile_exists(profile_name):
        print_error(f"Profile '{profile_name}' does not exist")
        print_info("\nAvailable profiles:")
        for p in manager.list_profiles():
            print_info(f"  - {p}")
        sys.exit(1)

    try:
        manager.switch_profile(profile_name)
        print_success(f"Switched to profile: {profile_name}")

        # Show profile info
        info = manager.get_profile_info(profile_name)
        print_section("Profile Info")
        print_info(f"  Description: {info['description']}")
        print_info(f"  Resume: {'[SUCCESS]' if info['files']['resume_exists'] else '[ERROR]'}")
        print_info(
            f"  Requirements: {'[SUCCESS]' if info['files']['requirements_exists'] else '[ERROR]'}"
        )

        if info["tracker_stats"]:
            print_info(f"  Jobs tracked: {info['tracker_stats']['total_jobs']}")

    except Exception as e:
        print_error(f"Failed to switch profile: {e}")
        sys.exit(1)


@profile_group.command(name="delete")
@click.argument("profile_name")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation")
def delete_profile(profile_name, yes):
    """Delete a profile"""
    print_header(f"Delete Profile: {profile_name}")

    manager = ProfileManager()

    if not manager.profile_exists(profile_name):
        print_error(f"Profile '{profile_name}' does not exist")
        sys.exit(1)

    # Get profile info
    try:
        info = manager.get_profile_info(profile_name)
    except Exception as e:
        print_error(f"Failed to get profile info: {e}")
        sys.exit(1)

    # Warn if active
    if info["is_active"]:
        print_warning("[WARNING] This is the currently active profile!")
        print_info("You should switch to another profile first")

        if not yes:
            if not confirm("Are you sure you want to delete the active profile?"):
                print_info("Deletion cancelled")
                return

    # Show what will be deleted
    print_section("Profile Contents")
    print_info(f"  Data files: {info['files']['data_files']}")
    print_info(f"  Reports: {info['files']['reports']}")

    if info["tracker_stats"]:
        print_info(f"  Tracked jobs: {info['tracker_stats']['total_jobs']}")

    print_warning("\n[WARNING] All data will be permanently deleted!")

    if not yes:
        if not confirm("Are you sure you want to delete this profile?"):
            print_info("Deletion cancelled")
            return

    try:
        manager.delete_profile(profile_name, force=True)
        print_success(f"Profile '{profile_name}' deleted successfully")

        if info["is_active"]:
            print_warning(
                "\nWarning: Deleted active profile. Switch to another profile:"
            )
            remaining = manager.list_profiles()
            if remaining:
                print_info(f"  python cli.py profile switch {remaining[0]}")

    except Exception as e:
        print_error(f"Failed to delete profile: {e}")
        sys.exit(1)


@profile_group.command(name="clone")
@click.argument("source_profile")
@click.argument("destination_profile")
@click.option("--description", "-d", help="Description for new profile")
def clone_profile(source_profile, destination_profile, description):
    """Clone an existing profile"""
    print_header(f"Clone Profile: {source_profile} → {destination_profile}")

    manager = ProfileManager()

    if not manager.profile_exists(source_profile):
        print_error(f"Source profile '{source_profile}' does not exist")
        sys.exit(1)

    if manager.profile_exists(destination_profile):
        print_error(f"Destination profile '{destination_profile}' already exists")
        sys.exit(1)

    try:
        manager.create_profile(
            profile_name=destination_profile,
            description=description,
            clone_from=source_profile,
        )

        print_success(f"Profile cloned successfully!")
        print_info(f"  Source:      {source_profile}")
        print_info(f"  Destination: {destination_profile}")

        print_section("Next Steps")
        print_info(f"1. Switch to new profile:")
        print_info(f"   python cli.py profile switch {destination_profile}")
        print_info("2. Customize settings as needed")

    except Exception as e:
        print_error(f"Failed to clone profile: {e}")
        sys.exit(1)


@profile_group.command(name="stats")
def show_all_stats():
    """Show statistics for all profiles"""
    print_header("Profile Statistics")

    manager = ProfileManager()
    profiles = manager.get_all_profiles_info()

    if not profiles:
        print_warning("No profiles found")
        return

    for info in profiles:
        profile_name = info["name"]
        is_active = info["is_active"]

        status = "[SUCCESS] ACTIVE" if is_active else ""
        print_section(f"{profile_name} {status}")

        # Basic stats
        print_info(f"  Description: {info['description']}")
        print_info(f"  Data files: {info['files']['data_files']}")
        print_info(f"  Reports: {info['files']['reports']}")

        # Tracker stats
        if info["tracker_stats"]:
            stats = info["tracker_stats"]
            print_info(f"  Jobs tracked: {stats['total_jobs']}")
            print_info(f"  Average score: {stats['avg_score']:.1f}")
            print_info(f"  High matches: {stats['high_matches']}")
        else:
            print_info("  No jobs tracked yet")

        print()


@profile_group.command(name="migrate")
def migrate_legacy():
    """Migrate from legacy structure to profile-based structure"""
    print_header("Migrate to Profile Structure")

    print_info("This will move your existing templates/, data/, and reports/")
    print_info("directories into a 'default' profile under profiles/default/")
    print()

    # Check if migration needed
    default_profile = Path("profiles/default")
    if default_profile.exists():
        print_warning("Profile structure already exists!")
        print_info(f"Default profile found at: {default_profile}")

        if not confirm("Do you want to force migration anyway?"):
            print_info("Migration cancelled")
            return

    try:
        migrated = migrate_legacy_structure()

        if migrated:
            print_success("Migration completed successfully!")
            print_section("Next Steps")
            print_info("Your existing data has been moved to: profiles/default/")
            print_info("You can now create additional profiles:")
            print_info("  python cli.py profile create <name>")
        else:
            print_info("No migration needed - profile structure already in place")

    except Exception as e:
        print_error(f"Migration failed: {e}")
        sys.exit(1)


# =============================================================================
# Profile Email Management Commands
# =============================================================================

@profile_group.command(name="email-set")
@click.argument("profile_name")
@click.argument("recipients")
@click.option("--subject", "-s", help="Email subject prefix")
@click.option("--enabled/--disabled", default=None, help="Enable/disable email for profile")
@click.option("--min-matches", type=int, help="Minimum matches to send email")
def set_profile_email(profile_name, recipients, subject, enabled, min_matches):
    """Set email recipients for a profile (comma-separated)"""
    print_header(f"Configure Email for Profile: {profile_name}")

    manager = ProfileManager()

    if not manager.profile_exists(profile_name):
        print_error(f"Profile '{profile_name}' does not exist")
        sys.exit(1)

    # Parse recipients
    recipient_list = [e.strip() for e in recipients.split(",") if e.strip()]

    if not recipient_list:
        print_error("No valid email addresses provided")
        sys.exit(1)

    # Validate email format
    for email in recipient_list:
        if "@" not in email or "." not in email:
            print_error(f"Invalid email format: {email}")
            sys.exit(1)

    try:
        manager.set_profile_email_config(
            profile_name=profile_name,
            recipients=recipient_list,
            subject_prefix=subject,
            enabled=enabled,
            min_matches=min_matches,
        )

        print_success("Email configuration updated!")
        print_section("Configuration")
        print_info(f"  Recipients: {', '.join(recipient_list)}")
        if subject:
            print_info(f"  Subject prefix: {subject}")
        if enabled is not None:
            print_info(f"  Enabled: {enabled}")
        if min_matches is not None:
            print_info(f"  Min matches: {min_matches}")

    except Exception as e:
        print_error(f"Failed to set email config: {e}")
        sys.exit(1)


@profile_group.command(name="email-show")
@click.argument("profile_name")
def show_profile_email(profile_name):
    """Show email configuration for a profile"""
    print_header(f"Email Configuration: {profile_name}")

    manager = ProfileManager()

    if not manager.profile_exists(profile_name):
        print_error(f"Profile '{profile_name}' does not exist")
        sys.exit(1)

    try:
        # Get profile-specific config
        profile_config = manager.get_profile_email_config(profile_name)

        # Get global config for comparison
        import os
        from dotenv import load_dotenv

        load_dotenv()
        global_recipient = os.getenv("EMAIL_RECIPIENT", "")
        global_recipients = [e.strip() for e in global_recipient.split(",") if e.strip()]
        global_prefix = os.getenv("EMAIL_SUBJECT_PREFIX", "[Job Matcher]")
        global_enabled = os.getenv("EMAIL_ENABLED", "true").lower() == "true"
        global_min = int(os.getenv("EMAIL_MIN_MATCHES", "1"))

        print_section("Configuration Source")
        if profile_config:
            print_success("Profile-specific configuration")
        else:
            print_info("Using global configuration from .env")

        print_section("Email Settings")

        # Recipients
        if profile_config and "recipients" in profile_config:
            recipients = profile_config["recipients"]
            print_info(f"  Recipients: {', '.join(recipients)}")
        else:
            print_info(f"  Recipients: {', '.join(global_recipients)} (inherited from global)")

        # Subject prefix
        if profile_config and "subject_prefix" in profile_config:
            print_info(f"  Subject Prefix: {profile_config['subject_prefix']}")
        else:
            print_info(f"  Subject Prefix: {global_prefix} (inherited from global)")

        # Enabled
        if profile_config and "enabled" in profile_config:
            print_info(f"  Enabled: {profile_config['enabled']}")
        else:
            print_info(f"  Enabled: {global_enabled} (inherited from global)")

        # Min matches
        if profile_config and "min_matches" in profile_config:
            print_info(f"  Min Matches: {profile_config['min_matches']}")
        else:
            print_info(f"  Min Matches: {global_min} (inherited from global)")

        if not profile_config:
            print_section("To Configure Profile-Specific Email")
            print_info(
                f"python cli.py profile email-set {profile_name} your@email.com"
            )

    except Exception as e:
        print_error(f"Failed to get email config: {e}")
        sys.exit(1)


@profile_group.command(name="email-clear")
@click.argument("profile_name")
def clear_profile_email(profile_name):
    """Clear email configuration for a profile (use global defaults)"""
    print_header(f"Clear Email Configuration: {profile_name}")

    manager = ProfileManager()

    if not manager.profile_exists(profile_name):
        print_error(f"Profile '{profile_name}' does not exist")
        sys.exit(1)

    try:
        manager.clear_profile_email_config(profile_name)
        print_success("Email configuration cleared")
        print_info("Profile will now use global email settings from .env")

    except Exception as e:
        print_error(f"Failed to clear email config: {e}")
        sys.exit(1)


if __name__ == "__main__":
    profile_group()
