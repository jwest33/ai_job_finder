"""
AI Provider Module

Provides a unified interface for interacting with various AI providers.
Supports OpenAI-compatible APIs (llama-server, Ollama, OpenAI, etc.)

Usage:
    from src.ai import get_ai_provider

    provider = get_ai_provider()
    result = provider.generate("Hello, world!")
"""

import threading
from typing import Optional

from .provider import AIProvider, AICapabilities, ConnectionTestResult
from .settings import (
    AISettings,
    load_ai_settings,
    save_ai_settings,
    settings_file_exists,
    delete_settings_file,
    get_preset,
    list_presets,
    PROVIDER_PRESETS,
    # Threshold settings
    MatchThresholdSettings,
    load_threshold_settings,
    save_threshold_settings,
    threshold_settings_file_exists,
    delete_threshold_settings_file,
)
from .openai_provider import OpenAICompatibleProvider


# Cached provider instance with thread safety
_provider_lock = threading.Lock()
_provider_instance: Optional[AIProvider] = None
_provider_settings_hash: Optional[str] = None


def _settings_hash(settings: AISettings) -> str:
    """Generate a hash of settings for cache invalidation."""
    return f"{settings.base_url}:{settings.api_key}:{settings.model}:{settings.vision_model}"


def get_ai_provider(force_reload: bool = False) -> AIProvider:
    """
    Get the AI provider instance.

    Uses a cached instance unless force_reload is True or settings have changed.
    Thread-safe.

    Args:
        force_reload: Force creation of a new provider instance

    Returns:
        AIProvider instance configured from settings
    """
    global _provider_instance, _provider_settings_hash

    with _provider_lock:
        settings = load_ai_settings()
        current_hash = _settings_hash(settings)

        if force_reload or _provider_instance is None or _provider_settings_hash != current_hash:
            _provider_instance = create_provider(settings)
            _provider_settings_hash = current_hash

        return _provider_instance


def create_provider(settings: Optional[AISettings] = None) -> AIProvider:
    """
    Create a new AI provider from settings.

    Args:
        settings: AISettings to use, or None to load from file/env

    Returns:
        AIProvider instance
    """
    if settings is None:
        settings = load_ai_settings()

    if settings.provider_type == "openai_compatible":
        return OpenAICompatibleProvider(settings)
    else:
        raise ValueError(f"Unknown provider type: {settings.provider_type}")


def clear_provider_cache():
    """Clear the cached provider instance."""
    global _provider_instance, _provider_settings_hash
    _provider_instance = None
    _provider_settings_hash = None


__all__ = [
    # Provider classes
    "AIProvider",
    "AICapabilities",
    "ConnectionTestResult",
    "OpenAICompatibleProvider",
    # AI Settings
    "AISettings",
    "load_ai_settings",
    "save_ai_settings",
    "settings_file_exists",
    "delete_settings_file",
    "get_preset",
    "list_presets",
    "PROVIDER_PRESETS",
    # Threshold Settings
    "MatchThresholdSettings",
    "load_threshold_settings",
    "save_threshold_settings",
    "threshold_settings_file_exists",
    "delete_threshold_settings_file",
    # Factory functions
    "get_ai_provider",
    "create_provider",
    "clear_provider_cache",
]
