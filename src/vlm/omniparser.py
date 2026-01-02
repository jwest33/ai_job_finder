"""
OmniParser for UI element detection.

Uses YOLO for icon detection, EasyOCR for text extraction,
and Florence2 for icon captioning.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from PIL import Image

from .config import OmniParserConfig, config as default_config
from .util.utils import (
    get_yolo_model,
    get_caption_model_processor,
    get_ocr_reader,
    get_som_labeled_img,
    get_device,
    DetectedElement,
)


@dataclass
class ParsedElement:
    """A parsed UI element with ID."""
    id: int
    bbox: List[float]  # [x1, y1, x2, y2] normalized
    label: str
    element_type: str  # "icon" or "text"
    confidence: float

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "bbox": self.bbox,
            "label": self.label,
            "type": self.element_type,
            "confidence": self.confidence
        }


@dataclass
class ParsedImage:
    """Result of parsing an image."""
    original: Image.Image
    annotated: Image.Image
    elements: List[ParsedElement]

    def get_elements_text(self) -> str:
        """Get a text description of all elements."""
        lines = []
        for elem in self.elements:
            lines.append(
                f"[{elem.id}] {elem.element_type}: \"{elem.label}\" "
                f"at ({elem.bbox[0]:.2f}, {elem.bbox[1]:.2f}) - "
                f"({elem.bbox[2]:.2f}, {elem.bbox[3]:.2f})"
            )
        return "\n".join(lines)

    def get_element_by_id(self, element_id: int) -> Optional[ParsedElement]:
        """Get element by ID."""
        for elem in self.elements:
            if elem.id == element_id:
                return elem
        return None


class OmniParser:
    """
    UI element detection using YOLO + OCR + Florence2.

    Analyzes screenshots to detect interactive elements
    (icons, buttons, text fields, etc.) and provides
    structured data for VLM agents.
    """

    def __init__(self, config: OmniParserConfig = None):
        """
        Initialize OmniParser.

        Args:
            config: Configuration for model paths and thresholds
        """
        self.config = config or default_config.omniparser
        self.device = self.config.device or get_device()

        # Lazy-loaded models
        self._yolo_model = None
        self._caption_model = None
        self._caption_processor = None
        self._ocr_reader = None
        self._initialized = False

    def initialize(self):
        """Load all models. Called automatically on first parse."""
        if self._initialized:
            return

        print(f"Initializing OmniParser on {self.device}...")

        # Load YOLO model
        print(f"Loading YOLO model from {self.config.som_model_path}")
        self._yolo_model = get_yolo_model(self.config.som_model_path)

        # Load caption model (processor from HuggingFace, weights from local)
        print(f"Loading caption model from {self.config.caption_model_path}")
        print(f"Using processor: {self.config.caption_processor_name}")
        self._caption_model, self._caption_processor = get_caption_model_processor(
            self.config.caption_model_path,
            self.config.caption_processor_name,
            self.device
        )

        # Initialize OCR
        print("Initializing EasyOCR...")
        self._ocr_reader = get_ocr_reader()

        self._initialized = True
        print("OmniParser initialized")

    def parse(self, image: Image.Image, use_caption: bool = True) -> ParsedImage:
        """
        Parse an image to detect UI elements.

        Args:
            image: PIL Image to analyze
            use_caption: Whether to generate captions for icons

        Returns:
            ParsedImage with annotated image and detected elements
        """
        if not self._initialized:
            self.initialize()

        annotated, detected = get_som_labeled_img(
            image=image,
            yolo_model=self._yolo_model,
            caption_model=self._caption_model if use_caption else None,
            caption_processor=self._caption_processor if use_caption else None,
            ocr_reader=self._ocr_reader,
            box_threshold=self.config.box_threshold,
            text_threshold=self.config.text_threshold,
            iou_threshold=self.config.iou_threshold,
            use_caption=use_caption,
            device=self.device
        )

        # Convert to ParsedElements with IDs
        elements = [
            ParsedElement(
                id=i,
                bbox=elem.bbox,
                label=elem.label,
                element_type=elem.element_type,
                confidence=elem.confidence
            )
            for i, elem in enumerate(detected)
        ]

        return ParsedImage(
            original=image,
            annotated=annotated,
            elements=elements
        )

    def parse_for_text(self, image: Image.Image) -> str:
        """
        Parse image and return text description of elements.

        Convenient method for passing to VLM prompts.

        Args:
            image: PIL Image to analyze

        Returns:
            Text description of all detected elements
        """
        parsed = self.parse(image)
        return parsed.get_elements_text()


# Convenience function for quick parsing
def parse_screen(image: Image.Image) -> ParsedImage:
    """
    Quick screen parsing with default settings.

    Args:
        image: PIL Image to analyze

    Returns:
        ParsedImage with annotated image and elements
    """
    parser = OmniParser()
    return parser.parse(image)
