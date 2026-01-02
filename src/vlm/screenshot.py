"""
Screenshot capture module for VLM agent.
"""

from typing import Optional, Tuple
import numpy as np
from PIL import Image
import mss
import mss.tools


def compare_images(img1: Image.Image, img2: Image.Image, resize_to: int = 256) -> float:
    """
    Compare two images and return a difference score.

    Args:
        img1: First image
        img2: Second image
        resize_to: Resize images to this size for faster comparison

    Returns:
        Difference score from 0.0 (identical) to 1.0 (completely different)
    """
    img1_small = img1.resize((resize_to, resize_to), Image.Resampling.LANCZOS)
    img2_small = img2.resize((resize_to, resize_to), Image.Resampling.LANCZOS)

    arr1 = np.array(img1_small, dtype=np.float32)
    arr2 = np.array(img2_small, dtype=np.float32)

    diff = np.abs(arr1 - arr2).mean() / 255.0
    return diff


class ScreenCapture:
    """Captures screenshots using mss library."""

    def __init__(self):
        self._sct = None

    @property
    def sct(self) -> mss.mss:
        """Lazy initialization of mss instance."""
        if self._sct is None:
            self._sct = mss.mss()
        return self._sct

    def get_screen_size(self, monitor: int = 0) -> Tuple[int, int]:
        """
        Get the size of a monitor.

        Args:
            monitor: Monitor index (0 = all monitors, 1+ = specific monitor)

        Returns:
            Tuple of (width, height)
        """
        mon = self.sct.monitors[monitor]
        return mon["width"], mon["height"]

    def capture(
        self,
        monitor: int = 1,
        region: Optional[Tuple[int, int, int, int]] = None
    ) -> Image.Image:
        """
        Capture a screenshot.

        Args:
            monitor: Monitor index (1 = primary, 2+ = additional monitors)
            region: Optional (left, top, right, bottom) region to capture

        Returns:
            PIL Image of the captured screen
        """
        if region:
            capture_area = {
                "left": region[0],
                "top": region[1],
                "width": region[2] - region[0],
                "height": region[3] - region[1],
            }
            sct_img = self.sct.grab(capture_area)
        else:
            mon = self.sct.monitors[monitor]
            sct_img = self.sct.grab(mon)

        img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
        return img

    def capture_primary(self) -> Image.Image:
        """Capture the primary monitor."""
        return self.capture(monitor=1)

    def close(self):
        """Clean up resources."""
        if self._sct is not None:
            self._sct.close()
            self._sct = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def capture_screen(monitor: int = 1) -> Image.Image:
    """
    Quick screenshot capture.

    Args:
        monitor: Monitor index (1 = primary)

    Returns:
        PIL Image of the screen
    """
    with mss.mss() as sct:
        mon = sct.monitors[monitor]
        sct_img = sct.grab(mon)
        return Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
