"""
Utils - Shared utility modules

Provides profile management, email setup, and other utilities.
"""

from .profile_manager import ProfileManager, ProfilePaths, migrate_legacy_structure

__all__ = ["ProfileManager", "ProfilePaths", "migrate_legacy_structure"]
