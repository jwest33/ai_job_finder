"""
Box annotation utilities for OmniParser.
Draws bounding boxes with labels on images.
"""

from dataclasses import dataclass
from typing import List, Tuple, Optional
import numpy as np
from PIL import Image, ImageDraw, ImageFont


@dataclass
class BoxAnnotator:
    """Annotates images with bounding boxes and labels."""

    color: Tuple[int, int, int] = (255, 0, 0)  # Red
    thickness: int = 2
    text_color: Tuple[int, int, int] = (255, 255, 255)
    text_background: Tuple[int, int, int] = (255, 0, 0)
    text_padding: int = 2
    font_size: int = 12

    def annotate(
        self,
        image: Image.Image,
        boxes: List[List[float]],
        labels: Optional[List[str]] = None,
    ) -> Image.Image:
        """
        Draw bounding boxes on an image.

        Args:
            image: PIL Image to annotate
            boxes: List of [x1, y1, x2, y2] normalized coordinates (0-1)
            labels: Optional list of labels for each box

        Returns:
            Annotated PIL Image
        """
        img = image.copy()
        draw = ImageDraw.Draw(img)
        width, height = img.size

        # Try to load a font, fall back to default
        try:
            font = ImageFont.truetype("arial.ttf", self.font_size)
        except (OSError, IOError):
            font = ImageFont.load_default()

        for i, box in enumerate(boxes):
            # Convert normalized coords to absolute
            x1 = int(box[0] * width)
            y1 = int(box[1] * height)
            x2 = int(box[2] * width)
            y2 = int(box[3] * height)

            # Draw rectangle
            draw.rectangle([x1, y1, x2, y2], outline=self.color, width=self.thickness)

            # Draw label if provided
            if labels and i < len(labels):
                label = labels[i]

                # Get text size
                bbox = draw.textbbox((0, 0), label, font=font)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]

                # Draw background rectangle for text
                padding = self.text_padding
                text_x = x1
                text_y = y1 - text_height - 2 * padding
                if text_y < 0:
                    text_y = y2 + padding

                draw.rectangle(
                    [text_x, text_y, text_x + text_width + 2 * padding, text_y + text_height + 2 * padding],
                    fill=self.text_background
                )

                # Draw text
                draw.text((text_x + padding, text_y + padding), label, fill=self.text_color, font=font)

        return img

    def annotate_with_ids(
        self,
        image: Image.Image,
        boxes: List[List[float]],
        start_id: int = 0,
    ) -> Image.Image:
        """
        Draw bounding boxes with numeric IDs.

        Args:
            image: PIL Image to annotate
            boxes: List of [x1, y1, x2, y2] normalized coordinates
            start_id: Starting ID number

        Returns:
            Annotated PIL Image
        """
        labels = [str(i + start_id) for i in range(len(boxes))]
        return self.annotate(image, boxes, labels)
