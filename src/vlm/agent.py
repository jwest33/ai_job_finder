"""
Visual automation agent that combines all VLM components.

Provides a high-level interface for visual web automation.
"""

import subprocess
import time
import webbrowser
from typing import Optional, List
from PIL import Image

from .config import VLMConfig, config as default_config
from .llm_client import LLMClient, Action, ActionType
from .screenshot import ScreenCapture
from .input_controller import InputController, execute_action
from .omniparser import OmniParser, ParsedImage


def open_browser(url: str, browser: str = None, wait: float = 3.0) -> bool:
    """
    Open a URL in the default or specified browser.

    Args:
        url: URL to open
        browser: Optional browser name ('chrome', 'firefox', 'edge')
        wait: Seconds to wait for browser to open

    Returns:
        True if browser opened successfully
    """
    try:
        if browser:
            # Try to open specific browser
            browser_paths = {
                "chrome": [
                    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                ],
                "edge": [
                    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
                ],
                "firefox": [
                    r"C:\Program Files\Mozilla Firefox\firefox.exe",
                    r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe",
                ],
            }

            paths = browser_paths.get(browser.lower(), [])
            for path in paths:
                try:
                    subprocess.Popen([path, url])
                    time.sleep(wait)
                    return True
                except FileNotFoundError:
                    continue

        # Fall back to default browser
        webbrowser.open(url)
        time.sleep(wait)
        return True

    except Exception as e:
        print(f"Failed to open browser: {e}")
        return False


class Agent:
    """
    High-level visual automation agent.

    Combines screen capture, UI parsing, LLM reasoning,
    and input control into a unified interface.
    """

    def __init__(self, config: VLMConfig = None):
        """
        Initialize the agent.

        Args:
            config: Configuration for all components
        """
        self.config = config or default_config

        # Components (lazy initialization)
        self._screen_capture = None
        self._omniparser = None
        self._llm_client = None
        self._input_controller = None

        self._initialized = False

    @property
    def screen_capture(self) -> ScreenCapture:
        """Get screen capture component."""
        if self._screen_capture is None:
            self._screen_capture = ScreenCapture()
        return self._screen_capture

    @property
    def omniparser(self) -> OmniParser:
        """Get OmniParser component."""
        if self._omniparser is None:
            self._omniparser = OmniParser(self.config.omniparser)
        return self._omniparser

    @property
    def llm_client(self) -> LLMClient:
        """Get LLM client component."""
        if self._llm_client is None:
            self._llm_client = LLMClient(self.config.llama)
        return self._llm_client

    @property
    def input_controller(self) -> InputController:
        """Get input controller component."""
        if self._input_controller is None:
            self._input_controller = InputController(
                action_delay=self.config.agent.action_delay
            )
        return self._input_controller

    def initialize(self) -> bool:
        """
        Initialize all components.

        Returns:
            True if initialization successful
        """
        if self._initialized:
            return True

        try:
            # Start LLM server if needed
            if not self.llm_client.start(timeout=self.config.agent.startup_timeout):
                print("Failed to start LLM server")
                return False

            # Initialize OmniParser (loads models)
            self.omniparser.initialize()

            self._initialized = True
            print("Agent initialized successfully")
            return True

        except Exception as e:
            print(f"Agent initialization failed: {e}")
            return False

    def shutdown(self):
        """Shutdown agent and cleanup resources."""
        if self._screen_capture:
            self._screen_capture.close()
            self._screen_capture = None

        if self._llm_client:
            self._llm_client.stop()
            self._llm_client = None

        self._initialized = False
        print("Agent shutdown complete")

    def capture_and_parse(self) -> ParsedImage:
        """
        Capture screen and parse UI elements.

        Returns:
            ParsedImage with detected elements
        """
        screenshot = self.screen_capture.capture_primary()
        time.sleep(self.config.agent.screenshot_delay)
        return self.omniparser.parse(screenshot)

    def run(
        self,
        task: str,
        max_actions: Optional[int] = None,
        history: Optional[List[str]] = None
    ) -> str:
        """
        Run the agent on a task.

        The agent will:
        1. Capture and parse the screen
        2. Ask the VLM what action to take
        3. Execute the action
        4. Repeat until task is complete or max_actions reached

        Args:
            task: Task description for the agent
            max_actions: Maximum number of actions (default from config)
            history: Previous action history

        Returns:
            Result description
        """
        if not self._initialized:
            if not self.initialize():
                return "Failed to initialize agent"

        if max_actions is None:
            max_actions = self.config.agent.max_actions

        if history is None:
            history = []

        action_count = 0
        result = ""

        while action_count < max_actions:
            # Capture and parse screen
            parsed = self.capture_and_parse()

            # Get next action from VLM
            actions = self.llm_client.get_action(
                task=task,
                parsed_elements=parsed.get_elements_text(),
                screenshot=parsed.original,
                annotated_image=parsed.annotated,
                history=history,
            )

            if not actions:
                result = "No action returned"
                break

            action = actions[0]
            action_count += 1

            # Log the action
            action_desc = f"{action.type.value}"
            if action.element_id is not None:
                action_desc += f" element {action.element_id}"
            if action.text:
                action_desc += f" text='{action.text[:30]}...'" if len(action.text) > 30 else f" text='{action.text}'"
            if action.reason:
                action_desc += f" ({action.reason})"

            print(f"Action {action_count}: {action_desc}")
            history.append(action_desc)

            # Check if task is done
            if action.type == ActionType.DONE:
                result = action.reason or "Task completed"
                break

            # Check for extraction actions
            if action.type in (ActionType.EXTRACT_JOBS, ActionType.EXTRACT_DETAIL):
                result = action.reason or "Extraction complete"
                break

            # Execute the action
            execute_action(
                self.input_controller,
                action,
                elements=[e for e in parsed.elements]
            )

            # Wait for screen to update
            time.sleep(self.config.agent.action_delay)

        if action_count >= max_actions:
            result = f"Reached max actions ({max_actions})"

        return result

    def get_completion(
        self,
        prompt: str,
        image: Optional[Image.Image] = None,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1024,
    ) -> str:
        """
        Get a text completion from the VLM.

        Useful for extracting data from screenshots without
        performing actions.

        Args:
            prompt: The prompt to send
            image: Optional image for analysis
            system_prompt: Optional system prompt override
            max_tokens: Maximum tokens to generate

        Returns:
            Generated text response
        """
        if not self._initialized:
            if not self.initialize():
                return ""

        # If no image provided, capture screen
        if image is None:
            image = self.screen_capture.capture_primary()

        return self.llm_client.get_completion(
            prompt=prompt,
            image=image,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
        )

    def __enter__(self):
        self.initialize()
        return self

    def __exit__(self, *args):
        self.shutdown()
