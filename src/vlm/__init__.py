"""
VLM (Vision Language Model) module for visual automation.

Provides screen capture, UI element detection via OmniParser,
and mouse/keyboard control for visual web scraping.
"""

from .config import config, VLMConfig
from .llm_client import LLMClient, Action, ActionType
from .screenshot import ScreenCapture, capture_screen
from .input_controller import InputController, execute_action
from .omniparser import OmniParser, ParsedImage, ParsedElement
from .agent import Agent, open_browser

__all__ = [
    "config",
    "VLMConfig",
    "LLMClient",
    "Action",
    "ActionType",
    "ScreenCapture",
    "capture_screen",
    "InputController",
    "execute_action",
    "OmniParser",
    "ParsedImage",
    "ParsedElement",
    "Agent",
    "open_browser",
]
