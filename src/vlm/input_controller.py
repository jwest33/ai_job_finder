"""
Input controller for mouse and keyboard automation.
"""

import time
from typing import Optional, Tuple, List

from pynput.keyboard import Key, Controller as KeyboardController
from pynput.mouse import Button, Controller as MouseController

from .screenshot import ScreenCapture


# Map of special key names to pynput Key objects
SPECIAL_KEYS = {
    "enter": Key.enter,
    "return": Key.enter,
    "tab": Key.tab,
    "escape": Key.esc,
    "esc": Key.esc,
    "backspace": Key.backspace,
    "delete": Key.delete,
    "space": Key.space,
    "up": Key.up,
    "down": Key.down,
    "left": Key.left,
    "right": Key.right,
    "home": Key.home,
    "end": Key.end,
    "pageup": Key.page_up,
    "pagedown": Key.page_down,
    "f1": Key.f1,
    "f2": Key.f2,
    "f3": Key.f3,
    "f4": Key.f4,
    "f5": Key.f5,
    "f6": Key.f6,
    "f7": Key.f7,
    "f8": Key.f8,
    "f9": Key.f9,
    "f10": Key.f10,
    "f11": Key.f11,
    "f12": Key.f12,
    "ctrl": Key.ctrl,
    "alt": Key.alt,
    "shift": Key.shift,
    "win": Key.cmd,
    "cmd": Key.cmd,
}


class InputController:
    """Controls mouse and keyboard input."""

    def __init__(self, action_delay: float = 0.1):
        """
        Initialize input controller.

        Args:
            action_delay: Delay in seconds between sub-actions
        """
        self.mouse = MouseController()
        self.keyboard = KeyboardController()
        self.action_delay = action_delay
        self._screen_capture = None

    @property
    def screen_capture(self) -> ScreenCapture:
        """Lazy initialization of screen capture."""
        if self._screen_capture is None:
            self._screen_capture = ScreenCapture()
        return self._screen_capture

    def get_screen_size(self) -> Tuple[int, int]:
        """Get the primary monitor size."""
        return self.screen_capture.get_screen_size(monitor=1)

    def normalized_to_absolute(
        self,
        x: float,
        y: float,
        screen_size: Optional[Tuple[int, int]] = None
    ) -> Tuple[int, int]:
        """
        Convert normalized coordinates (0-1) to absolute screen coordinates.

        Args:
            x: Normalized x coordinate (0-1)
            y: Normalized y coordinate (0-1)
            screen_size: Optional (width, height) tuple

        Returns:
            Tuple of (absolute_x, absolute_y)
        """
        if screen_size is None:
            screen_size = self.get_screen_size()

        abs_x = int(x * screen_size[0])
        abs_y = int(y * screen_size[1])
        return abs_x, abs_y

    def bbox_center(self, bbox: List[float]) -> Tuple[float, float]:
        """
        Get the center of a bounding box.

        Args:
            bbox: [x1, y1, x2, y2] normalized coordinates

        Returns:
            (center_x, center_y) normalized coordinates
        """
        x1, y1, x2, y2 = bbox
        return (x1 + x2) / 2, (y1 + y2) / 2

    def move_to(self, x: int, y: int):
        """Move mouse to absolute coordinates."""
        self.mouse.position = (x, y)
        time.sleep(self.action_delay)

    def click(
        self,
        x: Optional[float] = None,
        y: Optional[float] = None,
        button: Button = Button.left,
        count: int = 1,
    ):
        """
        Click at coordinates.

        Args:
            x: Normalized x coordinate (0-1), or None for current position
            y: Normalized y coordinate (0-1), or None for current position
            button: Mouse button to click
            count: Number of clicks
        """
        if x is not None and y is not None:
            abs_x, abs_y = self.normalized_to_absolute(x, y)
            self.move_to(abs_x, abs_y)

        self.mouse.click(button, count)
        time.sleep(self.action_delay)

    def click_element(self, bbox: List[float], button: Button = Button.left, count: int = 1):
        """
        Click the center of an element's bounding box.

        Args:
            bbox: [x1, y1, x2, y2] normalized coordinates
            button: Mouse button to click
            count: Number of clicks
        """
        cx, cy = self.bbox_center(bbox)
        self.click(cx, cy, button, count)

    def double_click(self, x: Optional[float] = None, y: Optional[float] = None):
        """Double click at coordinates."""
        self.click(x, y, count=2)

    def right_click(self, x: Optional[float] = None, y: Optional[float] = None):
        """Right click at coordinates."""
        self.click(x, y, button=Button.right)

    def scroll(self, direction: str = "down", amount: int = 3):
        """
        Scroll the mouse wheel.

        Args:
            direction: "up" or "down"
            amount: Number of scroll steps
        """
        dy = amount if direction == "up" else -amount
        self.mouse.scroll(0, dy)
        time.sleep(self.action_delay)

    def type_text(self, text: str, interval: float = 0.02):
        """
        Type text using the keyboard.

        Args:
            text: Text to type
            interval: Delay between keystrokes
        """
        for char in text:
            self.keyboard.type(char)
            time.sleep(interval)
        time.sleep(self.action_delay)

    def press_key(self, key: str):
        """
        Press a special key.

        Args:
            key: Key name (e.g., "enter", "tab", "escape")
        """
        key_lower = key.lower()
        if key_lower in SPECIAL_KEYS:
            self.keyboard.press(SPECIAL_KEYS[key_lower])
            self.keyboard.release(SPECIAL_KEYS[key_lower])
        else:
            self.keyboard.press(key)
            self.keyboard.release(key)
        time.sleep(self.action_delay)

    def key_combo(self, *keys: str):
        """
        Press a key combination.

        Args:
            keys: Key names to press together (e.g., "ctrl", "c")
        """
        # Press all keys
        for key in keys:
            key_lower = key.lower()
            if key_lower in SPECIAL_KEYS:
                self.keyboard.press(SPECIAL_KEYS[key_lower])
            else:
                self.keyboard.press(key)

        time.sleep(0.05)

        # Release in reverse order
        for key in reversed(keys):
            key_lower = key.lower()
            if key_lower in SPECIAL_KEYS:
                self.keyboard.release(SPECIAL_KEYS[key_lower])
            else:
                self.keyboard.release(key)

        time.sleep(self.action_delay)


def execute_action(controller: InputController, action, elements: list = None):
    """
    Execute an action using the input controller.

    Args:
        controller: InputController instance
        action: Action object from llm_client
        elements: List of ParsedElement objects for looking up element_id
    """
    from .llm_client import ActionType

    # Get coordinates from element_id if provided
    x, y = action.x, action.y
    if action.element_id is not None and elements:
        for elem in elements:
            if elem.id == action.element_id:
                x, y = controller.bbox_center(elem.bbox)
                break

    if action.type == ActionType.CLICK:
        controller.click(x, y)

    elif action.type == ActionType.DOUBLE_CLICK:
        controller.double_click(x, y)

    elif action.type == ActionType.RIGHT_CLICK:
        controller.right_click(x, y)

    elif action.type == ActionType.TYPE:
        if x is not None and y is not None:
            controller.click(x, y)
            time.sleep(0.3)
        if action.text:
            controller.type_text(action.text)

    elif action.type == ActionType.PRESS_KEY:
        if action.key:
            controller.press_key(action.key)

    elif action.type == ActionType.SCROLL:
        controller.scroll(
            direction=action.direction or "down",
            amount=action.amount or 3
        )

    elif action.type == ActionType.WAIT:
        time.sleep(action.amount or 1)

    elif action.type == ActionType.DONE:
        pass  # No action needed
