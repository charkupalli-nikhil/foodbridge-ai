import base64
from pathlib import Path
import sys

# Ensure parent directory is in sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from image_analysis import (
    analyse_food_image,
    check_packaging_image,
    CONFIDENCE_THRESHOLD,
    FSSAI_DISCLAIMER,
)


def analyze_food_image(image_data: str, food_name: str = "", category: str = "") -> dict:
    """
    Backwards-compatible wrapper that accepts base64 data URI or raw bytes,
    and forwards to the official analyse_food_image implementation.
    """
    if not image_data:
        return {
            "isSpoiled": False,
            "freshnessIndicator": "Invalid",
            "visualCondition": "No image provided",
            "foodVerdict": "Rejected",
            "verdict": "Rejected",
        }

    # If data URL with base64 prefix
    if "," in image_data:
        image_data = image_data.split(",")[1]

    try:
        image_bytes = base64.b64decode(image_data)
    except Exception:
        image_bytes = image_data.encode("utf-8")

    return analyse_food_image(
        image_bytes=image_bytes,
        mime_type="image/jpeg",
        food_name=food_name,
        category=category,
    )
