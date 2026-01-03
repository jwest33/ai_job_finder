"""
Configuration for VLM visual automation module.

Uses vision-capable models for visual web automation.
Configuration can be set via ai_settings.json or environment variables.
"""

import os
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse


def _get_ai_settings_url() -> tuple[str, int]:
    """
    Get host and port from AI settings or environment.

    Returns:
        Tuple of (host, port)
    """
    try:
        from src.ai import load_ai_settings
        settings = load_ai_settings()
        # Parse base_url to get host and port
        parsed = urlparse(settings.base_url)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or 8080
        return host, port
    except Exception:
        # Fall back to environment
        host = os.getenv("LLAMA_HOST", "127.0.0.1")
        port = int(os.getenv("LLAMA_PORT", "8080"))
        return host, port


def _check_vision_available() -> bool:
    """
    Check if vision capabilities are available from AI provider.

    Returns:
        True if vision is available, False otherwise
    """
    try:
        from src.ai import get_ai_provider
        provider = get_ai_provider()
        return provider.has_vision
    except Exception:
        return False


@dataclass
class LlamaServerConfig:
    """Configuration for llama-server."""
    executable: str = "llama-server"
    model_path: str = r"D:\models\gemma-3-27b-it\gemma-3-27b-it-UD-Q6_K_XL.gguf"
    mmproj_path: str = r"D:\models\gemma-3-27b-it\mmproj-BF16.gguf"
    host: str = "127.0.0.1"
    port: int = 8080
    context_size: int = 65536
    gpu_layers: int = -1  # -1 = all layers on GPU

    def __post_init__(self):
        # Try to get host/port from AI settings
        try:
            self.host, self.port = _get_ai_settings_url()
        except Exception:
            pass

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    @property
    def completion_url(self) -> str:
        return f"{self.base_url}/v1/chat/completions"

    @property
    def health_url(self) -> str:
        return f"{self.base_url}/health"


@dataclass
class OmniParserConfig:
    """Configuration for OmniParser UI element detection."""
    # OmniParser v2.0 paths
    som_model_path: str = r"D:\models\OmniParser-v2.0\icon_detect\model.pt"
    caption_model_path: str = r"D:\models\OmniParser-v2.0\icon_caption"
    # Processor is downloaded from HuggingFace (model weights are local)
    caption_processor_name: str = "microsoft/Florence-2-base"
    device: Optional[str] = None  # Auto-detect cuda/cpu
    box_threshold: float = 0.05
    text_threshold: float = 0.9
    iou_threshold: float = 0.7


@dataclass
class AgentConfig:
    """Configuration for the visual agent."""
    max_actions: int = 100
    action_delay: float = 0.5  # Seconds between actions
    screenshot_delay: float = 0.3  # Delay before taking screenshot
    startup_timeout: float = 120.0  # Seconds to wait for llama-server


@dataclass
class VLMConfig:
    """Main configuration container."""
    llama: LlamaServerConfig = field(default_factory=LlamaServerConfig)
    omniparser: OmniParserConfig = field(default_factory=OmniParserConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)


# Default configuration instance
config = VLMConfig()

# Allow overrides from environment
if os.getenv("LLAMA_MODEL_PATH"):
    config.llama.model_path = os.getenv("LLAMA_MODEL_PATH")
if os.getenv("LLAMA_MMPROJ_PATH"):
    config.llama.mmproj_path = os.getenv("LLAMA_MMPROJ_PATH")
if os.getenv("LLAMA_HOST"):
    config.llama.host = os.getenv("LLAMA_HOST")
if os.getenv("LLAMA_PORT"):
    config.llama.port = int(os.getenv("LLAMA_PORT"))
if os.getenv("OMNIPARSER_SOM_MODEL"):
    config.omniparser.som_model_path = os.getenv("OMNIPARSER_SOM_MODEL")
if os.getenv("OMNIPARSER_CAPTION_MODEL"):
    config.omniparser.caption_model_path = os.getenv("OMNIPARSER_CAPTION_MODEL")
if os.getenv("OMNIPARSER_CAPTION_PROCESSOR"):
    config.omniparser.caption_processor_name = os.getenv("OMNIPARSER_CAPTION_PROCESSOR")


def is_vision_available() -> bool:
    """
    Check if vision capabilities are available.

    Checks the AI provider settings to determine if vision is enabled.

    Returns:
        True if vision is available, False otherwise
    """
    return _check_vision_available()
