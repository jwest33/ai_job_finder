"""
ProfileManager - Manage multiple job search profiles

Enables profile swapping for completely different job searches with
isolated resumes, requirements, data, and reports.
"""

import os
import yaml
import shutil
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime
from dotenv import load_dotenv, set_key, find_dotenv

load_dotenv()


class ProfilePaths:
    """Dynamic path resolution for profile-aware file access"""

    def __init__(self, profile_name: Optional[str] = None):
        """
        Initialize ProfilePaths

        Args:
            profile_name: Profile name (default: from .env ACTIVE_PROFILE)
        """
        self.profile_name = profile_name or os.getenv("ACTIVE_PROFILE", "default")
        self.base_dir = Path("profiles") / self.profile_name

    @property
    def templates_dir(self) -> Path:
        """Get templates directory for profile"""
        return self.base_dir / "templates"

    @property
    def data_dir(self) -> Path:
        """Get data directory for profile"""
        return self.base_dir / "data"

    @property
    def reports_dir(self) -> Path:
        """Get reports directory for profile"""
        return self.base_dir / "reports"

    @property
    def resume_path(self) -> Path:
        """Get resume file path for profile"""
        return self.templates_dir / "resume.txt"

    @property
    def requirements_path(self) -> Path:
        """Get requirements file path for profile"""
        return self.templates_dir / "requirements.yaml"

    @property
    def job_tracker_db(self) -> Path:
        """Get job tracker database path for profile"""
        return self.data_dir / "job_tracker.db"

    @property
    def failure_tracker_db(self) -> Path:
        """Get failure tracker database path for profile"""
        return self.data_dir / "job_failures.db"

    @property
    def checkpoint_file(self) -> Path:
        """Get checkpoint file path for profile"""
        return self.data_dir / ".checkpoint_active.json"

    @property
    def profile_config(self) -> Path:
        """Get profile-specific config file"""
        return self.base_dir / "profile.yaml"

    def ensure_directories(self):
        """Create all necessary directories for profile"""
        self.templates_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)


class ProfileManager:
    """Manage job search profiles"""

    def __init__(self):
        """Initialize ProfileManager"""
        self.profiles_root = Path("profiles")
        self.profiles_root.mkdir(exist_ok=True)

    def list_profiles(self) -> List[str]:
        """
        List all available profiles

        Returns:
            List of profile names
        """
        if not self.profiles_root.exists():
            return []

        profiles = []
        for item in self.profiles_root.iterdir():
            if item.is_dir() and not item.name.startswith("."):
                profiles.append(item.name)

        return sorted(profiles)

    def get_active_profile(self) -> str:
        """
        Get currently active profile name

        Returns:
            Active profile name
        """
        return os.getenv("ACTIVE_PROFILE", "default")

    def profile_exists(self, profile_name: str) -> bool:
        """
        Check if profile exists

        Args:
            profile_name: Name of profile

        Returns:
            True if profile exists
        """
        profile_path = self.profiles_root / profile_name
        return profile_path.exists() and profile_path.is_dir()

    def create_profile(
        self,
        profile_name: str,
        description: Optional[str] = None,
        clone_from: Optional[str] = None,
    ) -> bool:
        """
        Create a new profile

        Args:
            profile_name: Name for new profile
            description: Optional profile description
            clone_from: Optional profile to clone from

        Returns:
            True if created successfully

        Raises:
            ValueError: If profile already exists or clone source doesn't exist
        """
        # Validate profile name
        if not profile_name or "/" in profile_name or "\\" in profile_name:
            raise ValueError("Invalid profile name")

        profile_path = self.profiles_root / profile_name

        if profile_path.exists():
            raise ValueError(f"Profile '{profile_name}' already exists")

        # Clone from existing profile if specified
        if clone_from:
            source_path = self.profiles_root / clone_from
            if not source_path.exists():
                raise ValueError(f"Source profile '{clone_from}' does not exist")

            # Copy entire profile directory
            shutil.copytree(source_path, profile_path)

            # Update profile config
            config_path = profile_path / "profile.yaml"
            if config_path.exists():
                with open(config_path, "r", encoding="utf-8") as f:
                    config = yaml.safe_load(f) or {}
            else:
                config = {}

            config["name"] = profile_name
            config["description"] = description or f"Cloned from {clone_from}"
            config["created_at"] = datetime.now().isoformat()
            config["cloned_from"] = clone_from

            with open(config_path, "w", encoding="utf-8") as f:
                yaml.dump(config, f, default_flow_style=False)

        else:
            # Create new profile from scratch
            paths = ProfilePaths(profile_name)
            paths.ensure_directories()

            # Create profile config
            config = {
                "name": profile_name,
                "description": description or f"Job search profile: {profile_name}",
                "created_at": datetime.now().isoformat(),
            }

            config_path = profile_path / "profile.yaml"
            with open(config_path, "w", encoding="utf-8") as f:
                yaml.dump(config, f, default_flow_style=False)

            # Create template resume
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
            with open(paths.resume_path, "w", encoding="utf-8") as f:
                f.write(resume_template)

            # Create template requirements
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

job_requirements:
  target_roles:
    - Job Title 1
    - Job Title 2

  search_jobs:
    - search term 1
    - search term 2

  skills:
    required:
      - Required skill 1
      - Required skill 2
    preferred:
      - Preferred skill 1
      - Preferred skill 2

preferences:
  remote_only: true
  min_salary: 70000
  max_salary: 130000
  salary_period: yearly
  locations:
    - Remote
    - Your City, State
"""
            with open(paths.requirements_path, "w", encoding="utf-8") as f:
                f.write(requirements_template)

        return True

    def switch_profile(self, profile_name: str) -> bool:
        """
        Switch active profile

        Args:
            profile_name: Name of profile to switch to

        Returns:
            True if switched successfully

        Raises:
            ValueError: If profile doesn't exist
        """
        if not self.profile_exists(profile_name):
            raise ValueError(f"Profile '{profile_name}' does not exist")

        # Update .env file
        env_file = find_dotenv()
        if not env_file:
            env_file = ".env"

        set_key(env_file, "ACTIVE_PROFILE", profile_name, quote_mode="never")

        # Reload environment
        load_dotenv(override=True)

        return True

    def delete_profile(self, profile_name: str, force: bool = False) -> bool:
        """
        Delete a profile

        Args:
            profile_name: Name of profile to delete
            force: Skip confirmation if True

        Returns:
            True if deleted successfully

        Raises:
            ValueError: If profile doesn't exist or is currently active
        """
        if not self.profile_exists(profile_name):
            raise ValueError(f"Profile '{profile_name}' does not exist")

        if profile_name == self.get_active_profile() and not force:
            raise ValueError(
                "Cannot delete active profile. Switch to another profile first."
            )

        profile_path = self.profiles_root / profile_name
        shutil.rmtree(profile_path)

        return True

    def get_profile_email_config(self, profile_name: str) -> Optional[Dict[str, Any]]:
        """
        Get email configuration for a profile

        Args:
            profile_name: Name of profile

        Returns:
            Dict with email config, or None if not configured

        Raises:
            ValueError: If profile doesn't exist
        """
        if not self.profile_exists(profile_name):
            raise ValueError(f"Profile '{profile_name}' does not exist")

        profile_path = self.profiles_root / profile_name
        config_path = profile_path / "profile.yaml"

        if not config_path.exists():
            return None

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}

            return config.get("email")
        except Exception:
            return None

    def set_profile_email_config(
        self,
        profile_name: str,
        recipients: Optional[List[str]] = None,
        subject_prefix: Optional[str] = None,
        enabled: Optional[bool] = None,
        min_matches: Optional[int] = None,
    ) -> bool:
        """
        Set email configuration for a profile

        Args:
            profile_name: Name of profile
            recipients: List of email addresses
            subject_prefix: Email subject prefix
            enabled: Enable/disable email for this profile
            min_matches: Minimum matches to send email

        Returns:
            True if successful

        Raises:
            ValueError: If profile doesn't exist
        """
        if not self.profile_exists(profile_name):
            raise ValueError(f"Profile '{profile_name}' does not exist")

        profile_path = self.profiles_root / profile_name
        config_path = profile_path / "profile.yaml"

        # Load existing config
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
        else:
            config = {"name": profile_name}

        # Update email section
        if "email" not in config:
            config["email"] = {}

        if recipients is not None:
            config["email"]["recipients"] = recipients

        if subject_prefix is not None:
            config["email"]["subject_prefix"] = subject_prefix

        if enabled is not None:
            config["email"]["enabled"] = enabled

        if min_matches is not None:
            config["email"]["min_matches"] = min_matches

        # Save config
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(config, f, default_flow_style=False)

        return True

    def clear_profile_email_config(self, profile_name: str) -> bool:
        """
        Clear email configuration for a profile (use global defaults)

        Args:
            profile_name: Name of profile

        Returns:
            True if successful

        Raises:
            ValueError: If profile doesn't exist
        """
        if not self.profile_exists(profile_name):
            raise ValueError(f"Profile '{profile_name}' does not exist")

        profile_path = self.profiles_root / profile_name
        config_path = profile_path / "profile.yaml"

        if not config_path.exists():
            return True

        # Load config
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}

        # Remove email section
        if "email" in config:
            del config["email"]

        # Save config
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(config, f, default_flow_style=False)

        return True

    def get_profile_info(self, profile_name: str) -> Dict[str, Any]:
        """
        Get information about a profile

        Args:
            profile_name: Name of profile

        Returns:
            Dict with profile information

        Raises:
            ValueError: If profile doesn't exist
        """
        if not self.profile_exists(profile_name):
            raise ValueError(f"Profile '{profile_name}' does not exist")

        profile_path = self.profiles_root / profile_name
        paths = ProfilePaths(profile_name)

        # Load config
        config_path = profile_path / "profile.yaml"
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
        else:
            config = {}

        # Get file counts
        data_files = list(paths.data_dir.glob("*.json")) if paths.data_dir.exists() else []
        report_files = (
            list(paths.reports_dir.glob("*.html")) if paths.reports_dir.exists() else []
        )

        # Get tracker stats if database exists
        tracker_stats = None
        if paths.job_tracker_db.exists():
            try:
                from job_matcher.job_tracker import JobTracker

                tracker = JobTracker(str(paths.job_tracker_db))
                tracker_stats = tracker.get_stats()
            except Exception:
                pass

        info = {
            "name": profile_name,
            "description": config.get("description", "No description"),
            "created_at": config.get("created_at", "Unknown"),
            "is_active": profile_name == self.get_active_profile(),
            "paths": {
                "base": str(profile_path),
                "templates": str(paths.templates_dir),
                "data": str(paths.data_dir),
                "reports": str(paths.reports_dir),
            },
            "files": {
                "resume_exists": paths.resume_path.exists(),
                "requirements_exists": paths.requirements_path.exists(),
                "data_files": len(data_files),
                "reports": len(report_files),
            },
            "tracker_stats": tracker_stats,
        }

        if "cloned_from" in config:
            info["cloned_from"] = config["cloned_from"]

        # Add email configuration if present
        email_config = config.get("email")
        if email_config:
            info["email_config"] = email_config

        return info

    def get_all_profiles_info(self) -> List[Dict[str, Any]]:
        """
        Get information about all profiles

        Returns:
            List of profile info dicts
        """
        profiles = []
        for profile_name in self.list_profiles():
            try:
                info = self.get_profile_info(profile_name)
                profiles.append(info)
            except Exception:
                # Skip profiles with errors
                continue

        return profiles


def migrate_legacy_structure():
    """
    Migrate legacy structure (templates/, data/, reports/ at root)
    to new profile structure (profiles/default/)

    Returns:
        True if migration performed, False if already migrated
    """
    # Check if old structure exists
    old_templates = Path("templates")
    old_data = Path("data")
    old_reports = Path("reports")

    profiles_root = Path("profiles")
    default_profile = profiles_root / "default"

    # Skip if already migrated
    if default_profile.exists():
        return False

    # Check if any old directories exist
    has_old_structure = (
        old_templates.exists() or old_data.exists() or old_reports.exists()
    )

    if not has_old_structure:
        return False

    print("[INFO] Migrating to profile-based structure...")

    # Create default profile
    manager = ProfileManager()
    manager.create_profile("default", description="Default profile (migrated)")

    paths = ProfilePaths("default")

    # Move old directories
    if old_templates.exists():
        print(f"  Moving templates/ → {paths.templates_dir}")
        # Remove empty template directory created by create_profile
        if paths.templates_dir.exists():
            shutil.rmtree(paths.templates_dir)
        shutil.move(str(old_templates), str(paths.templates_dir))

    if old_data.exists():
        print(f"  Moving data/ → {paths.data_dir}")
        if paths.data_dir.exists():
            shutil.rmtree(paths.data_dir)
        shutil.move(str(old_data), str(paths.data_dir))

    if old_reports.exists():
        print(f"  Moving reports/ → {paths.reports_dir}")
        if paths.reports_dir.exists():
            shutil.rmtree(paths.reports_dir)
        shutil.move(str(old_reports), str(paths.reports_dir))

    # Set default profile as active
    env_file = find_dotenv()
    if not env_file:
        env_file = ".env"

    set_key(env_file, "ACTIVE_PROFILE", "default", quote_mode="never")

    print("[SUCCESS] Migration complete! All files moved to profiles/default/")
    print("   Use 'python cli.py profile create <name>' to create new profiles")

    return True


if __name__ == "__main__":
    # Test the profile manager
    print("Testing ProfileManager...")

    # Check for migration
    migrated = migrate_legacy_structure()
    if migrated:
        print("\nMigration completed successfully")

    manager = ProfileManager()

    print(f"\nProfiles root: {manager.profiles_root}")
    print(f"Active profile: {manager.get_active_profile()}")

    profiles = manager.list_profiles()
    print(f"\nAvailable profiles: {profiles}")

    if profiles:
        print("\nProfile details:")
        for profile in profiles:
            info = manager.get_profile_info(profile)
            print(f"\n  {profile}:")
            print(f"    Description: {info['description']}")
            print(f"    Active: {info['is_active']}")
            print(f"    Resume exists: {info['files']['resume_exists']}")
            print(f"    Data files: {info['files']['data_files']}")
            print(f"    Reports: {info['files']['reports']}")
            if info['tracker_stats']:
                print(f"    Total jobs tracked: {info['tracker_stats']['total_jobs']}")

    print("\nProfileManager test complete")
