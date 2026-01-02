"""
LLM Client for communicating with llama-server.
"""

import atexit
import base64
import io
import json
import re
import subprocess
import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional, List

import requests
from PIL import Image

from .config import LlamaServerConfig, config as default_config
from .prompts import SYSTEM_PROMPT


class ActionType(Enum):
    CLICK = "click"
    DOUBLE_CLICK = "double_click"
    RIGHT_CLICK = "right_click"
    TYPE = "type"
    PRESS_KEY = "press_key"
    SCROLL = "scroll"
    WAIT = "wait"
    DONE = "done"
    EXTRACT_JOBS = "extract_jobs"
    EXTRACT_DETAIL = "extract_detail"


@dataclass
class Action:
    """An action to perform."""
    type: ActionType
    element_id: Optional[int] = None
    x: Optional[float] = None  # Normalized coordinates
    y: Optional[float] = None
    text: Optional[str] = None
    key: Optional[str] = None
    direction: Optional[str] = None  # "up" or "down"
    amount: Optional[int] = None
    reason: Optional[str] = None


class LlamaServer:
    """Manages llama-server subprocess."""

    def __init__(self, config: LlamaServerConfig):
        self.config = config
        self.process: Optional[subprocess.Popen] = None
        self._started = False

    def start(self, timeout: float = 120.0) -> bool:
        """Start the llama-server process."""
        if self._started:
            return True

        # First check if server is already running
        if self._check_health():
            print(f"llama-server already running at {self.config.base_url}")
            self._started = True
            return True

        cmd = [
            self.config.executable,
            "--model", self.config.model_path,
            "--mmproj", self.config.mmproj_path,
            "--host", self.config.host,
            "--port", str(self.config.port),
            "--ctx-size", str(self.config.context_size),
        ]

        print(f"Starting llama-server...")
        print(f"Model: {self.config.model_path}")

        try:
            self.process = subprocess.Popen(cmd)
        except FileNotFoundError:
            print(f"Error: '{self.config.executable}' not found. Is llama.cpp installed?")
            return False

        atexit.register(self.stop)

        # Wait for server to be ready
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.process.poll() is not None:
                print("Error: llama-server exited unexpectedly")
                return False

            if self._check_health():
                print(f"llama-server ready at {self.config.base_url}")
                self._started = True
                return True

            time.sleep(0.5)

        print(f"Timeout waiting for llama-server after {timeout}s")
        self.stop()
        return False

    def _check_health(self) -> bool:
        """Check if server is healthy."""
        try:
            resp = requests.get(self.config.health_url, timeout=2)
            return resp.status_code == 200
        except requests.RequestException:
            return False

    def stop(self):
        """Stop the llama-server process."""
        if self.process is not None:
            print("Stopping llama-server...")
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self.process = None
            self._started = False

    def is_running(self) -> bool:
        """Check if server is running."""
        return self._started and self._check_health()


class LLMClient:
    """Client for communicating with llama-server."""

    def __init__(self, config: LlamaServerConfig = None):
        self.config = config or default_config.llama
        self.server = LlamaServer(self.config)
        self.session = requests.Session()

    def start(self, timeout: float = 120.0) -> bool:
        """Start the llama-server."""
        return self.server.start(timeout)

    def stop(self):
        """Stop the llama-server."""
        self.server.stop()

    def is_available(self) -> bool:
        """Check if LLM is available."""
        return self.server._check_health()

    def _encode_image(self, image: Image.Image) -> str:
        """Encode PIL Image to base64."""
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue()).decode("utf-8")

    def get_action(
        self,
        task: str,
        parsed_elements: str,
        screenshot: Optional[Image.Image] = None,
        annotated_image: Optional[Image.Image] = None,
        history: Optional[List[str]] = None,
        system_prompt: Optional[str] = None,
    ) -> List[Action]:
        """
        Get the next action(s) from the VLM.

        Args:
            task: The task description
            parsed_elements: Text description of UI elements
            screenshot: Optional raw screenshot
            annotated_image: Optional annotated image
            history: Optional list of previous actions
            system_prompt: Optional custom system prompt

        Returns:
            List of actions to perform
        """
        content = []

        # Add images if provided
        if screenshot:
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{self._encode_image(screenshot)}"
                }
            })

        if annotated_image:
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{self._encode_image(annotated_image)}"
                }
            })

        # Build text prompt
        text_parts = [f"Task: {task}", "", "Current screen state:", parsed_elements]

        if history:
            text_parts.extend(["", "Previous actions:", *history[-5:]])

        text_parts.extend(["", "What action should be taken next? Respond with JSON only."])

        content.append({
            "type": "text",
            "text": "\n".join(text_parts)
        })

        payload = {
            "model": "gemma-3-12b-it",
            "messages": [
                {"role": "system", "content": system_prompt or SYSTEM_PROMPT},
                {"role": "user", "content": content}
            ],
            "temperature": 0.1,
            "max_tokens": 512,
            "cache_prompt": False,
        }

        try:
            response = self.session.post(
                self.config.completion_url,
                json=payload,
                timeout=60,
            )
            response.raise_for_status()
            result = response.json()

            message = result["choices"][0]["message"]["content"]
            return self._parse_action(message)

        except requests.RequestException as e:
            print(f"API request failed: {e}")
            return [Action(type=ActionType.WAIT, amount=2, reason="API error, waiting")]

    def get_completion(
        self,
        prompt: str,
        image: Optional[Image.Image] = None,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1024,
    ) -> str:
        """
        Get a text completion from the VLM.

        Args:
            prompt: The user prompt
            image: Optional image to analyze
            system_prompt: Optional system prompt
            max_tokens: Maximum tokens to generate

        Returns:
            Generated text response
        """
        content = []

        if image:
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{self._encode_image(image)}"
                }
            })

        content.append({"type": "text", "text": prompt})

        messages = [{"role": "user", "content": content}]
        if system_prompt:
            messages.insert(0, {"role": "system", "content": system_prompt})

        payload = {
            "model": "gemma-3-12b-it",
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": max_tokens,
            "cache_prompt": False,
        }

        try:
            response = self.session.post(
                self.config.completion_url,
                json=payload,
                timeout=120,
            )
            response.raise_for_status()
            result = response.json()
            return result["choices"][0]["message"]["content"]

        except requests.RequestException as e:
            print(f"API request failed: {e}")
            return ""

    def _parse_action(self, response: str) -> List[Action]:
        """Parse the LLM response into a list of Actions."""
        try:
            # Handle markdown code blocks
            if "```" in response:
                match = re.search(r"```(?:json)?\s*(\[.*?\]|\{.*?\})\s*```", response, re.DOTALL)
                if match:
                    response = match.group(1)

            data = json.loads(response.strip())

            if isinstance(data, list):
                action_list = [data[0]] if data else []
            else:
                action_list = [data]

            actions = []
            for action_data in action_list:
                action_str = action_data.get("action", "wait")
                try:
                    action_type = ActionType(action_str)
                except ValueError:
                    action_type = ActionType.WAIT

                actions.append(Action(
                    type=action_type,
                    element_id=action_data.get("element_id"),
                    x=action_data.get("x"),
                    y=action_data.get("y"),
                    text=action_data.get("text"),
                    key=action_data.get("key"),
                    direction=action_data.get("direction"),
                    amount=action_data.get("amount"),
                    reason=action_data.get("reason", ""),
                ))

            return actions

        except (json.JSONDecodeError, ValueError) as e:
            print(f"Failed to parse action: {e}")
            print(f"Response was: {response[:200]}")
            return [Action(type=ActionType.WAIT, amount=1, reason="Failed to parse response")]

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args):
        self.stop()
