"""
OmniParser utility functions for UI element detection.

Uses YOLO for icon detection, EasyOCR for text extraction,
and Florence2 for icon captioning.
"""

import os
from typing import Tuple, List, Optional, Dict, Any
from dataclasses import dataclass

import numpy as np
from PIL import Image
import torch

# Lazy imports for heavy dependencies
_yolo_model = None
_caption_model = None
_caption_processor = None
_ocr_reader = None


@dataclass
class DetectedElement:
    """A detected UI element."""
    bbox: List[float]  # [x1, y1, x2, y2] normalized
    label: str
    element_type: str  # "icon" or "text"
    confidence: float


def get_device() -> str:
    """Get the best available device."""
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def get_yolo_model(model_path: str):
    """
    Load YOLO model for icon detection.

    Args:
        model_path: Path to the YOLO model weights

    Returns:
        YOLO model instance
    """
    global _yolo_model
    if _yolo_model is None:
        from ultralytics import YOLO
        _yolo_model = YOLO(model_path)
    return _yolo_model


def get_caption_model_processor(
    model_path: str,
    processor_name: str = "microsoft/Florence-2-base",
    device: str = None
):
    """
    Load Florence2 model for icon captioning.

    OmniParser v2.0 uses a hybrid approach:
    - Processor is downloaded from HuggingFace
    - Model weights are loaded from local directory

    Args:
        model_path: Path to local Florence2 model weights directory
        processor_name: HuggingFace model name for processor (default: microsoft/Florence-2-base)
        device: Device to load model on

    Returns:
        Tuple of (model, processor)
    """
    global _caption_model, _caption_processor

    if _caption_model is None:
        import os
        from transformers import AutoProcessor, AutoModelForCausalLM

        if device is None:
            device = get_device()

        # Processor comes from HuggingFace (includes tokenizer, image processor)
        _caption_processor = AutoProcessor.from_pretrained(
            processor_name,
            trust_remote_code=True
        )

        # Model weights from local directory
        # Use attn_implementation="eager" to avoid SDPA compatibility issues
        # with custom Florence2 code that lacks _supports_sdpa attribute
        _caption_model = AutoModelForCausalLM.from_pretrained(
            model_path,
            trust_remote_code=True,
            torch_dtype=torch.float16 if device == "cuda" else torch.float32,
            attn_implementation="eager",
        ).to(device)

    return _caption_model, _caption_processor


def get_ocr_reader():
    """Get EasyOCR reader instance."""
    global _ocr_reader
    if _ocr_reader is None:
        import easyocr
        _ocr_reader = easyocr.Reader(["en"], gpu=torch.cuda.is_available())
    return _ocr_reader


def check_ocr_box(
    image: Image.Image,
    box: List[float],
    ocr_reader=None,
    threshold: float = 0.5
) -> Tuple[bool, str]:
    """
    Run OCR on a specific region of an image.

    Args:
        image: PIL Image
        box: [x1, y1, x2, y2] normalized coordinates
        ocr_reader: EasyOCR reader instance
        threshold: Confidence threshold

    Returns:
        Tuple of (has_text, extracted_text)
    """
    if ocr_reader is None:
        ocr_reader = get_ocr_reader()

    width, height = image.size
    x1 = int(box[0] * width)
    y1 = int(box[1] * height)
    x2 = int(box[2] * width)
    y2 = int(box[3] * height)

    # Ensure valid crop
    x1, x2 = max(0, x1), min(width, x2)
    y1, y2 = max(0, y1), min(height, y2)

    if x2 <= x1 or y2 <= y1:
        return False, ""

    # Crop and run OCR
    crop = image.crop((x1, y1, x2, y2))
    crop_array = np.array(crop)

    results = ocr_reader.readtext(crop_array, detail=1)

    texts = []
    for result in results:
        if len(result) >= 2:
            text = result[1]
            conf = result[2] if len(result) > 2 else 1.0
            if conf >= threshold and text.strip():
                texts.append(text.strip())

    combined = " ".join(texts)
    return bool(combined), combined


def caption_icons_batch(
    image: Image.Image,
    boxes: List[List[float]],
    model,
    processor,
    device: str = None,
    batch_size: int = 64,
) -> List[str]:
    """
    Generate captions for multiple icon regions in batches.

    Args:
        image: PIL Image
        boxes: List of [x1, y1, x2, y2] normalized coordinates
        model: Florence2 model
        processor: Florence2 processor
        device: Device to use
        batch_size: Number of icons to process at once

    Returns:
        List of caption strings
    """
    import cv2
    from torchvision.transforms import ToPILImage

    if device is None:
        device = get_device()

    if not boxes:
        return []

    width, height = image.size
    image_np = np.array(image)

    # Ensure image has 3 channels (RGB)
    if len(image_np.shape) == 2:
        # Grayscale - convert to RGB
        image_np = np.stack([image_np] * 3, axis=-1)
    elif len(image_np.shape) == 3 and image_np.shape[2] == 4:
        # RGBA - drop alpha channel
        image_np = image_np[:, :, :3]

    # Crop and resize all icons
    bbox_images = []
    for box in boxes:
        x1 = int(box[0] * width)
        y1 = int(box[1] * height)
        x2 = int(box[2] * width)
        y2 = int(box[3] * height)

        # Ensure valid crop (with minimum size of 1 pixel)
        x1, x2 = max(0, x1), min(width, x2)
        y1, y2 = max(0, y1), min(height, y2)

        # Need at least 1 pixel in each dimension
        if x2 - x1 < 1 or y2 - y1 < 1:
            bbox_images.append(None)
            continue

        try:
            cropped = image_np[y1:y2, x1:x2]
            # Validate cropped array
            if cropped is None or cropped.size == 0 or cropped.shape[0] == 0 or cropped.shape[1] == 0:
                bbox_images.append(None)
                continue
            # Ensure 3 channels
            if len(cropped.shape) == 2:
                cropped = np.stack([cropped] * 3, axis=-1)
            cropped = cv2.resize(cropped, (64, 64))
            bbox_images.append(ToPILImage()(cropped))
        except Exception:
            bbox_images.append(None)

    # Process in batches
    prompt = "<CAPTION>"
    captions = []

    valid_images = [img for img in bbox_images if img is not None]
    valid_indices = [i for i, img in enumerate(bbox_images) if img is not None]

    if not valid_images:
        return ["icon"] * len(boxes)

    for idx in range(0, len(valid_images), batch_size):
        batch = valid_images[idx:idx + batch_size]

        try:
            inputs = processor(
                images=batch,
                text=[prompt] * len(batch),
                return_tensors="pt",
                do_resize=False,
            )

            # Move to device with correct dtype
            if device in ("cuda", "mps"):
                inputs = inputs.to(device=device, dtype=torch.float16)
            else:
                inputs = inputs.to(device=device)

            with torch.inference_mode():
                generated_ids = model.generate(
                    input_ids=inputs["input_ids"],
                    pixel_values=inputs["pixel_values"],
                    max_new_tokens=20,
                    num_beams=1,
                    do_sample=False,
                    early_stopping=False,
                )

            generated_texts = processor.batch_decode(generated_ids, skip_special_tokens=True)
            captions.extend([text.strip() for text in generated_texts])

        except Exception as e:
            print(f"Error in batch captioning: {e}")
            # Fill with default captions for this batch
            captions.extend(["icon"] * len(batch))

    # Map back to original order, filling in "icon" for failed crops
    result = ["icon"] * len(boxes)
    for i, caption_idx in enumerate(valid_indices):
        if i < len(captions):
            result[caption_idx] = captions[i] if captions[i] else "icon"

    return result


def caption_icon(
    image: Image.Image,
    box: List[float],
    model,
    processor,
    device: str = None
) -> str:
    """
    Generate a caption for a single icon region.

    Args:
        image: PIL Image
        box: [x1, y1, x2, y2] normalized coordinates
        model: Florence2 model
        processor: Florence2 processor
        device: Device to use

    Returns:
        Caption string
    """
    captions = caption_icons_batch(image, [box], model, processor, device)
    return captions[0] if captions else "icon"


def run_yolo_detection(
    image: Image.Image,
    model,
    box_threshold: float = 0.05,
    iou_threshold: float = 0.7
) -> List[Dict[str, Any]]:
    """
    Run YOLO detection on image.

    Args:
        image: PIL Image
        model: YOLO model
        box_threshold: Confidence threshold
        iou_threshold: IOU threshold for NMS

    Returns:
        List of detected boxes with confidence
    """
    results = model.predict(
        source=image,
        conf=box_threshold,
        iou=iou_threshold,
        verbose=False
    )

    detections = []
    if results and len(results) > 0:
        result = results[0]
        boxes = result.boxes

        width, height = image.size

        for i in range(len(boxes)):
            xyxy = boxes.xyxy[i].cpu().numpy()
            conf = float(boxes.conf[i].cpu().numpy())

            # Normalize coordinates
            x1 = xyxy[0] / width
            y1 = xyxy[1] / height
            x2 = xyxy[2] / width
            y2 = xyxy[3] / height

            detections.append({
                "bbox": [x1, y1, x2, y2],
                "confidence": conf
            })

    return detections


def run_ocr_detection(
    image: Image.Image,
    ocr_reader=None,
    text_threshold: float = 0.9
) -> List[Dict[str, Any]]:
    """
    Run OCR on entire image.

    Args:
        image: PIL Image
        ocr_reader: EasyOCR reader
        text_threshold: Confidence threshold

    Returns:
        List of detected text regions
    """
    if ocr_reader is None:
        ocr_reader = get_ocr_reader()

    img_array = np.array(image)
    width, height = image.size

    results = ocr_reader.readtext(img_array, detail=1)

    detections = []
    for result in results:
        if len(result) >= 2:
            box_points = result[0]  # [[x1,y1], [x2,y1], [x2,y2], [x1,y2]]
            text = result[1]
            conf = result[2] if len(result) > 2 else 1.0

            if conf >= text_threshold and text.strip():
                # Convert polygon to bbox
                xs = [p[0] for p in box_points]
                ys = [p[1] for p in box_points]

                x1 = min(xs) / width
                y1 = min(ys) / height
                x2 = max(xs) / width
                y2 = max(ys) / height

                detections.append({
                    "bbox": [x1, y1, x2, y2],
                    "text": text.strip(),
                    "confidence": conf
                })

    return detections


def get_som_labeled_img(
    image: Image.Image,
    yolo_model,
    caption_model=None,
    caption_processor=None,
    ocr_reader=None,
    box_threshold: float = 0.05,
    text_threshold: float = 0.9,
    iou_threshold: float = 0.7,
    use_caption: bool = True,
    device: str = None
) -> Tuple[Image.Image, List[DetectedElement]]:
    """
    Get image with labeled UI elements (Set-of-Mark).

    Combines YOLO icon detection with OCR text detection,
    optionally uses Florence2 for icon captioning.

    Args:
        image: PIL Image to analyze
        yolo_model: YOLO model for icon detection
        caption_model: Optional Florence2 model
        caption_processor: Optional Florence2 processor
        ocr_reader: Optional EasyOCR reader
        box_threshold: YOLO confidence threshold
        text_threshold: OCR confidence threshold
        iou_threshold: NMS IOU threshold
        use_caption: Whether to generate icon captions
        device: Device to use

    Returns:
        Tuple of (annotated_image, list of DetectedElement)
    """
    from .box_annotator import BoxAnnotator

    if device is None:
        device = get_device()

    elements = []

    # Run YOLO detection for icons
    icon_detections = run_yolo_detection(
        image, yolo_model, box_threshold, iou_threshold
    )

    # Batch caption all icons at once for efficiency
    icon_boxes = [det["bbox"] for det in icon_detections]
    if use_caption and caption_model and caption_processor and icon_boxes:
        try:
            captions = caption_icons_batch(
                image, icon_boxes, caption_model, caption_processor, device
            )
        except Exception as e:
            print(f"Error in icon captioning: {e}")
            captions = ["icon"] * len(icon_detections)
    else:
        captions = ["icon"] * len(icon_detections)

    for det, label in zip(icon_detections, captions):
        elements.append(DetectedElement(
            bbox=det["bbox"],
            label=label,
            element_type="icon",
            confidence=det["confidence"]
        ))

    # Run OCR detection for text
    if ocr_reader is None:
        ocr_reader = get_ocr_reader()

    text_detections = run_ocr_detection(image, ocr_reader, text_threshold)

    for det in text_detections:
        elements.append(DetectedElement(
            bbox=det["bbox"],
            label=det["text"],
            element_type="text",
            confidence=det["confidence"]
        ))

    # Remove overlapping text/icon boxes (prefer text)
    elements = _remove_overlaps(elements)

    # Sort by position (top to bottom, left to right)
    elements.sort(key=lambda e: (e.bbox[1], e.bbox[0]))

    # Create annotated image
    annotator = BoxAnnotator()
    boxes = [e.bbox for e in elements]
    labels = [f"{i}: {e.label[:20]}" for i, e in enumerate(elements)]

    annotated = annotator.annotate(image, boxes, labels)

    return annotated, elements


def _remove_overlaps(
    elements: List[DetectedElement],
    iou_threshold: float = 0.5
) -> List[DetectedElement]:
    """Remove overlapping elements, preferring text over icons."""

    def iou(box1, box2):
        x1 = max(box1[0], box2[0])
        y1 = max(box1[1], box2[1])
        x2 = min(box1[2], box2[2])
        y2 = min(box1[3], box2[3])

        if x2 <= x1 or y2 <= y1:
            return 0.0

        intersection = (x2 - x1) * (y2 - y1)
        area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
        area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
        union = area1 + area2 - intersection

        return intersection / union if union > 0 else 0.0

    # Separate text and icons
    text_elements = [e for e in elements if e.element_type == "text"]
    icon_elements = [e for e in elements if e.element_type == "icon"]

    # Keep all text elements
    keep = list(text_elements)

    # Only keep icons that don't overlap with text
    for icon in icon_elements:
        overlaps = False
        for text in text_elements:
            if iou(icon.bbox, text.bbox) > iou_threshold:
                overlaps = True
                break
        if not overlaps:
            keep.append(icon)

    return keep
