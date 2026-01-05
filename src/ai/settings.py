"""
AI Settings Management

Handles loading, saving, and validation of AI provider settings.
Settings are stored in ai_settings.json in the project root.
Falls back to .env configuration for backwards compatibility.
"""

import ast
import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional, Dict, Any

from dotenv import load_dotenv


def get_project_root() -> Path:
    """Get the project root directory."""
    # Start from this file and go up to find the project root
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / ".env").exists() or (parent / "pyproject.toml").exists():
            return parent
    # Fallback to current working directory
    return Path.cwd()


# Settings file location
SETTINGS_FILE = get_project_root() / "ai_settings.json"


@dataclass
class AISettings:
    """Configuration for AI provider."""

    # Provider type (currently only "openai_compatible" supported)
    provider_type: str = "openai_compatible"

    # API endpoint (base URL without trailing slash)
    base_url: str = "http://localhost:8080/v1"

    # API key (optional for local servers)
    api_key: Optional[str] = None

    # Model name/ID for text generation
    model: str = "default"

    # Model name/ID for vision (None = same as model, empty string = no vision)
    vision_model: Optional[str] = None

    # Whether vision is explicitly enabled/disabled
    # None = auto-detect, True = force enabled, False = force disabled
    vision_enabled: Optional[bool] = None

    # Generation parameters
    temperature: float = 0.3
    max_tokens: int = 2048
    timeout: int = 300

    # Concurrency for batch operations
    max_concurrent: int = 4

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AISettings":
        """Create from dictionary."""
        # Filter to only known fields
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)

    def get_effective_vision_model(self) -> Optional[str]:
        """Get the effective vision model name."""
        if self.vision_enabled is False:
            return None
        if self.vision_model is not None:
            return self.vision_model if self.vision_model else None
        return self.model  # Default to same model


def _normalize_base_url(url: str) -> str:
    """
    Normalize a base URL to ensure proper format.

    - Strips trailing slashes
    - Ensures /v1 suffix for OpenAI compatibility
    - Handles comma-separated URLs (takes first)

    Args:
        url: The URL to normalize

    Returns:
        Normalized URL string
    """
    # Handle comma-separated URLs (take first one)
    if "," in url:
        url = url.split(",")[0].strip()
    elif url.strip().startswith("["):
        # Handle list format [url1, url2]
        try:
            urls = ast.literal_eval(url)
            if isinstance(urls, list) and urls:
                url = urls[0]
        except (ValueError, SyntaxError):
            pass

    # Ensure URL has /v1 suffix for OpenAI compatibility
    base_url = url.rstrip("/")
    if not base_url.endswith("/v1"):
        base_url = f"{base_url}/v1"

    return base_url


def load_ai_settings() -> AISettings:
    """
    Load AI settings from file or environment.

    Priority:
    1. ai_settings.json if it exists (with env var overrides)
    2. Environment variables (.env) as fallback

    Environment variable overrides (useful for Docker):
    - AI_BASE_URL: Overrides base_url from JSON
      Example: AI_BASE_URL=http://host.docker.internal:8080/v1

    Returns:
        AISettings instance
    """
    # Load environment variables first (needed for potential overrides)
    load_dotenv(override=True)

    # Try loading from JSON file first
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, "r") as f:
                data = json.load(f)
            settings = AISettings.from_dict(data)

            # Allow environment variable overrides (useful for Docker)
            env_base_url = os.getenv("AI_BASE_URL")
            if env_base_url:
                settings.base_url = _normalize_base_url(env_base_url)

            return settings
        except (json.JSONDecodeError, IOError) as e:
            print(f"[WARNING] Failed to load ai_settings.json: {e}")
            # Fall through to env-based settings

    # Parse base URL from env (AI_BASE_URL takes priority for Docker compatibility)
    env_url = os.getenv("AI_BASE_URL") or os.getenv("LLAMA_SERVER_URL", "http://localhost:8080")
    base_url = _normalize_base_url(env_url)

    return AISettings(
        provider_type="openai_compatible",
        base_url=base_url,
        api_key=os.getenv("OPENAI_API_KEY"),
        model=os.getenv("AI_MODEL", "default"),
        temperature=float(os.getenv("LLAMA_TEMPERATURE", "0.3")),
        max_tokens=int(os.getenv("LLAMA_MAX_TOKENS", "2048")),
        timeout=int(os.getenv("LLAMA_REQUEST_TIMEOUT", "300")),
        max_concurrent=int(os.getenv("MATCH_THREADS", "4")),
    )


def save_ai_settings(settings: AISettings) -> bool:
    """
    Save AI settings to file.

    Args:
        settings: AISettings instance to save

    Returns:
        True if saved successfully, False otherwise
    """
    try:
        data = settings.to_dict()
        # Don't save None api_key as null in JSON
        if data.get("api_key") is None:
            data["api_key"] = ""

        with open(SETTINGS_FILE, "w") as f:
            json.dump(data, f, indent=2)
        return True
    except IOError as e:
        print(f"[ERROR] Failed to save ai_settings.json: {e}")
        return False


def settings_file_exists() -> bool:
    """Check if custom settings file exists."""
    return SETTINGS_FILE.exists()


def delete_settings_file() -> bool:
    """
    Delete the settings file to revert to env-based settings.

    Returns:
        True if deleted, False if didn't exist or error
    """
    try:
        if SETTINGS_FILE.exists():
            SETTINGS_FILE.unlink()
            return True
        return False
    except IOError as e:
        print(f"[ERROR] Failed to delete ai_settings.json: {e}")
        return False


# Provider presets for common configurations
# Note: For Docker, set AI_BASE_URL env var to use host.docker.internal instead of localhost
PROVIDER_PRESETS = {
    "llama-server": {
        "name": "llama-server (Local)",
        "base_url": "http://localhost:8080/v1",
        "docker_base_url": "http://host.docker.internal:8080/v1",
        "api_key": "",
        "model": "default",
        "description": "Local llama.cpp server. Start with: llama-server -m model.gguf",
    },
    "ollama": {
        "name": "Ollama (Local)",
        "base_url": "http://localhost:11434/v1",
        "docker_base_url": "http://host.docker.internal:11434/v1",
        "api_key": "",
        "model": "llama3.2",
        "description": "Ollama local inference. Install: https://ollama.ai",
    },
    "lm-studio": {
        "name": "LM Studio (Local)",
        "base_url": "http://localhost:1234/v1",
        "docker_base_url": "http://host.docker.internal:1234/v1",
        "api_key": "",
        "model": "default",
        "description": "LM Studio local server. Enable API in settings.",
    },
    "openai": {
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "api_key": "",  # User must provide
        "model": "gpt-4o",
        "description": "OpenAI API. Requires API key from platform.openai.com",
    },
    "anthropic": {
        "name": "Anthropic Claude",
        "base_url": "https://api.anthropic.com/v1",
        "api_key": "",  # User must provide
        "model": "claude-sonnet-4-20250514",
        "description": "Anthropic Claude API (requires OpenAI-compatible proxy). Get key from console.anthropic.com",
    },
}


def get_preset(preset_name: str) -> Optional[Dict[str, Any]]:
    """Get a provider preset by name."""
    return PROVIDER_PRESETS.get(preset_name)


def list_presets() -> Dict[str, Dict[str, Any]]:
    """Get all available presets."""
    return PROVIDER_PRESETS.copy()


# ============================================================================
# Match Quality Threshold Settings
# ============================================================================

THRESHOLD_SETTINGS_FILE = get_project_root() / "threshold_settings.json"


@dataclass
class MatchThresholdSettings:
    """Configuration for match quality score thresholds."""

    # Score thresholds (scores >= threshold get that label)
    excellent: int = 80  # Scores >= this are "Excellent" (green)
    good: int = 60       # Scores >= this are "Good" (yellow)
    fair: int = 40       # Scores >= this are "Fair" (orange)
    # Anything below 'fair' is "Low" (red)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MatchThresholdSettings":
        """Create from dictionary."""
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)

    def validate(self) -> Optional[str]:
        """Validate thresholds are in correct order. Returns error message or None."""
        if not (0 <= self.fair < self.good < self.excellent <= 100):
            return "Thresholds must be in order: 0 <= fair < good < excellent <= 100"
        return None


def load_threshold_settings() -> MatchThresholdSettings:
    """Load threshold settings from file or return defaults."""
    if THRESHOLD_SETTINGS_FILE.exists():
        try:
            with open(THRESHOLD_SETTINGS_FILE, "r") as f:
                data = json.load(f)
            return MatchThresholdSettings.from_dict(data)
        except (json.JSONDecodeError, IOError) as e:
            print(f"[WARNING] Failed to load threshold_settings.json: {e}")

    return MatchThresholdSettings()


def save_threshold_settings(settings: MatchThresholdSettings) -> bool:
    """Save threshold settings to file."""
    error = settings.validate()
    if error:
        print(f"[ERROR] Invalid threshold settings: {error}")
        return False

    try:
        with open(THRESHOLD_SETTINGS_FILE, "w") as f:
            json.dump(settings.to_dict(), f, indent=2)
        return True
    except IOError as e:
        print(f"[ERROR] Failed to save threshold_settings.json: {e}")
        return False


def threshold_settings_file_exists() -> bool:
    """Check if custom threshold settings file exists."""
    return THRESHOLD_SETTINGS_FILE.exists()


def delete_threshold_settings_file() -> bool:
    """Delete threshold settings file to revert to defaults."""
    try:
        if THRESHOLD_SETTINGS_FILE.exists():
            THRESHOLD_SETTINGS_FILE.unlink()
            return True
        return False
    except IOError as e:
        print(f"[ERROR] Failed to delete threshold_settings.json: {e}")
        return False
