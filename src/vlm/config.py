"""
Configuration for VLM visual automation module.

Uses Gemma 3 12B IT vision model for both scraping and AI matching.
"""

import os
from dataclasses import dataclass, field
from typing import Optional


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
