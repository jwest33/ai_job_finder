"""
AI Provider API Endpoints

REST endpoints for managing AI provider settings and testing connections.
"""

from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.ai import (
    AISettings,
    load_ai_settings,
    save_ai_settings,
    settings_file_exists,
    delete_settings_file,
    get_ai_provider,
    create_provider,
    clear_provider_cache,
    list_presets,
    get_preset,
    # Threshold settings
    MatchThresholdSettings,
    load_threshold_settings,
    save_threshold_settings,
    threshold_settings_file_exists,
    delete_threshold_settings_file,
)


router = APIRouter()


# Request/Response Models

class AISettingsResponse(BaseModel):
    """Response model for AI settings."""
    provider_type: str
    base_url: str
    api_key: str = ""  # Masked or empty for security
    model: str
    vision_model: Optional[str] = None
    vision_enabled: Optional[bool] = None
    temperature: float
    max_tokens: int
    timeout: int
    max_concurrent: int
    has_custom_settings: bool = False

    class Config:
        from_attributes = True


class AISettingsUpdate(BaseModel):
    """Request model for updating AI settings."""
    provider_type: str = "openai_compatible"
    base_url: str
    api_key: Optional[str] = None
    model: str
    vision_model: Optional[str] = None
    vision_enabled: Optional[bool] = None
    temperature: float = Field(default=0.3, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2048, ge=1, le=32768)
    timeout: int = Field(default=300, ge=10, le=3600)
    max_concurrent: int = Field(default=4, ge=1, le=32)


class ConnectionTestRequest(BaseModel):
    """Request model for testing connection."""
    base_url: str
    api_key: Optional[str] = None
    model: str = "default"
    vision_enabled: Optional[bool] = None


class ConnectionTestResponse(BaseModel):
    """Response model for connection test."""
    success: bool
    capabilities: dict
    models: List[str] = []
    error: Optional[str] = None
    model_info: Optional[dict] = None


class PresetInfo(BaseModel):
    """Provider preset information."""
    id: str
    name: str
    base_url: str
    model: str
    description: str


# Endpoints

@router.get("/settings", response_model=AISettingsResponse)
async def get_settings():
    """Get current AI provider settings."""
    settings = load_ai_settings()

    # Mask API key for security - only show last 4 chars
    masked_key = ""
    if settings.api_key and len(settings.api_key) > 4:
        masked_key = "****" + settings.api_key[-4:]
    elif settings.api_key:
        masked_key = "****"

    return AISettingsResponse(
        provider_type=settings.provider_type,
        base_url=settings.base_url,
        api_key=masked_key,
        model=settings.model,
        vision_model=settings.vision_model,
        vision_enabled=settings.vision_enabled,
        temperature=settings.temperature,
        max_tokens=settings.max_tokens,
        timeout=settings.timeout,
        max_concurrent=settings.max_concurrent,
        has_custom_settings=settings_file_exists(),
    )


@router.put("/settings", response_model=AISettingsResponse)
async def update_settings(update: AISettingsUpdate):
    """Update AI provider settings."""
    # Load current settings to preserve API key if not provided
    current = load_ai_settings()

    # Create new settings
    settings = AISettings(
        provider_type=update.provider_type,
        base_url=update.base_url.rstrip("/"),
        api_key=update.api_key if update.api_key else current.api_key,
        model=update.model,
        vision_model=update.vision_model,
        vision_enabled=update.vision_enabled,
        temperature=update.temperature,
        max_tokens=update.max_tokens,
        timeout=update.timeout,
        max_concurrent=update.max_concurrent,
    )

    # Save settings
    if not save_ai_settings(settings):
        raise HTTPException(status_code=500, detail="Failed to save settings")

    # Clear provider cache to use new settings
    clear_provider_cache()

    # Return updated settings
    return await get_settings()


@router.delete("/settings")
async def reset_settings():
    """Reset to environment-based settings by deleting custom settings file."""
    deleted = delete_settings_file()
    clear_provider_cache()

    return {
        "success": True,
        "message": "Settings reset to environment defaults" if deleted else "No custom settings to reset",
    }


@router.post("/test", response_model=ConnectionTestResponse)
async def test_connection(request: ConnectionTestRequest):
    """Test connection to AI provider and detect capabilities."""
    try:
        # Create temporary settings for testing
        test_settings = AISettings(
            provider_type="openai_compatible",
            base_url=request.base_url.rstrip("/"),
            api_key=request.api_key or "",
            model=request.model,
            vision_enabled=request.vision_enabled,
        )

        # Create provider and test connection
        provider = create_provider(test_settings)
        result = provider.test_connection()

        return ConnectionTestResponse(
            success=result.success,
            capabilities={
                "text": result.capabilities.text,
                "vision": result.capabilities.vision,
            },
            models=result.capabilities.models or [],
            error=result.error,
            model_info=result.model_info,
        )

    except Exception as e:
        return ConnectionTestResponse(
            success=False,
            capabilities={"text": False, "vision": False},
            error=str(e),
        )


@router.get("/models", response_model=List[str])
async def list_models():
    """List available models from current provider."""
    try:
        provider = get_ai_provider()
        return provider.list_models()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/presets", response_model=List[PresetInfo])
async def get_presets():
    """Get list of provider presets."""
    presets = list_presets()
    return [
        PresetInfo(
            id=preset_id,
            name=preset["name"],
            base_url=preset["base_url"],
            model=preset["model"],
            description=preset["description"],
        )
        for preset_id, preset in presets.items()
    ]


@router.get("/presets/{preset_id}")
async def get_preset_details(preset_id: str):
    """Get details for a specific preset."""
    preset = get_preset(preset_id)
    if not preset:
        raise HTTPException(status_code=404, detail=f"Preset '{preset_id}' not found")

    return {
        "id": preset_id,
        **preset,
    }


@router.post("/presets/{preset_id}/apply", response_model=AISettingsResponse)
async def apply_preset(preset_id: str):
    """Apply a preset configuration."""
    preset = get_preset(preset_id)
    if not preset:
        raise HTTPException(status_code=404, detail=f"Preset '{preset_id}' not found")

    # Create settings from preset
    settings = AISettings(
        provider_type="openai_compatible",
        base_url=preset["base_url"],
        api_key=preset.get("api_key", ""),
        model=preset["model"],
    )

    # Save settings
    if not save_ai_settings(settings):
        raise HTTPException(status_code=500, detail="Failed to save settings")

    clear_provider_cache()

    return await get_settings()


@router.get("/status")
async def get_status():
    """Get current AI provider status."""
    try:
        provider = get_ai_provider()
        result = provider.test_connection()

        return {
            "connected": result.success,
            "provider_type": "openai_compatible",
            "base_url": provider.server_url,
            "has_vision": provider.has_vision,
            "capabilities": {
                "text": result.capabilities.text,
                "vision": result.capabilities.vision,
            },
            "models": result.capabilities.models or [],
            "error": result.error,
        }
    except Exception as e:
        return {
            "connected": False,
            "error": str(e),
        }


# ============================================================================
# Match Quality Threshold Endpoints
# ============================================================================

class ThresholdSettingsResponse(BaseModel):
    """Response model for threshold settings."""
    excellent: int = Field(description="Score threshold for 'Excellent' rating")
    good: int = Field(description="Score threshold for 'Good' rating")
    fair: int = Field(description="Score threshold for 'Fair' rating")
    has_custom_settings: bool = False


class ThresholdSettingsUpdate(BaseModel):
    """Request model for updating threshold settings."""
    excellent: int = Field(ge=1, le=100, description="Score threshold for 'Excellent' rating")
    good: int = Field(ge=1, le=99, description="Score threshold for 'Good' rating")
    fair: int = Field(ge=0, le=98, description="Score threshold for 'Fair' rating")


@router.get("/thresholds", response_model=ThresholdSettingsResponse)
async def get_thresholds():
    """Get current match quality threshold settings."""
    settings = load_threshold_settings()
    return ThresholdSettingsResponse(
        excellent=settings.excellent,
        good=settings.good,
        fair=settings.fair,
        has_custom_settings=threshold_settings_file_exists(),
    )


@router.put("/thresholds", response_model=ThresholdSettingsResponse)
async def update_thresholds(update: ThresholdSettingsUpdate):
    """Update match quality threshold settings."""
    settings = MatchThresholdSettings(
        excellent=update.excellent,
        good=update.good,
        fair=update.fair,
    )

    error = settings.validate()
    if error:
        raise HTTPException(status_code=400, detail=error)

    if not save_threshold_settings(settings):
        raise HTTPException(status_code=500, detail="Failed to save threshold settings")

    return await get_thresholds()


@router.delete("/thresholds")
async def reset_thresholds():
    """Reset threshold settings to defaults."""
    deleted = delete_threshold_settings_file()
    return {
        "success": True,
        "message": "Thresholds reset to defaults" if deleted else "No custom thresholds to reset",
    }
