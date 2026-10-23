import pytest
from unittest.mock import MagicMock, patch
from PIL import Image
import io
import json
import os
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_path = Path(__file__).resolve().parent.parent
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from image_analysis import (
    analyse_food_image,
    CONFIDENCE_THRESHOLD,
    FSSAI_DISCLAIMER,
)


def create_dummy_image_bytes():
    """Generates a simple 100x100 JPEG image in memory for testing."""
    image = Image.new("RGB", (100, 100), color=(200, 100, 50))
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    return buffer.getvalue()


@pytest.fixture(autouse=True)
def mock_env():
    with patch.dict(os.environ, {"GEMINI_API_KEY": "AIzaSyFakeKeyForUnitTests12345"}):
        yield


def test_analyse_food_image_rejects_non_food():
    """AI must reject images that do not depict edible food (e.g. laptop, wall, meme)."""
    ai_response = {
        "isFood": False,
        "detectedFood": "Laptop computer and keyboard",
        "matchesDescription": False,
        "isSpoiled": False,
        "freshness": "Invalid",
        "visualCondition": "Electronic device on wooden desk.",
        "confidence": 0.95,
        "reason": "The uploaded photo is of a laptop, not edible food.",
    }

    mock_resp = MagicMock()
    mock_resp.text = json.dumps(ai_response)

    with patch("google.genai.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        result = analyse_food_image(
            create_dummy_image_bytes(),
            mime_type="image/jpeg",
            food_name="Fresh Cooked Rice",
        )

        assert result["verdict"] == "Rejected"
        assert result["isFood"] is False
        assert "not edible food" in result["rejectionReason"].lower()
        assert result["screeningDisclaimer"] == FSSAI_DISCLAIMER


def test_analyse_food_image_rejects_description_mismatch():
    """AI must reject images where food doesn't match the donor's description."""
    ai_response = {
        "isFood": True,
        "detectedFood": "Fresh apples and oranges",
        "matchesDescription": False,
        "isSpoiled": False,
        "freshness": "Fresh",
        "visualCondition": "Whole fresh fruits.",
        "confidence": 0.92,
        "reason": "Image shows whole fruits, but donor declared Biryani.",
    }

    mock_resp = MagicMock()
    mock_resp.text = json.dumps(ai_response)

    with patch("google.genai.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        result = analyse_food_image(
            create_dummy_image_bytes(),
            mime_type="image/jpeg",
            food_name="Chicken Biryani",
        )

        assert result["verdict"] == "Rejected"
        assert result["matchesDescription"] is False
        assert "does not match" in result["rejectionReason"].lower()


def test_analyse_food_image_unverified_on_low_confidence():
    """AI must fail-closed with 'Unverified' if confidence is below threshold (< 0.60)."""
    ai_response = {
        "isFood": True,
        "detectedFood": "Unidentifiable stew",
        "matchesDescription": True,
        "isSpoiled": False,
        "freshness": "Acceptable",
        "visualCondition": "Very blurry and dark photo.",
        "confidence": 0.45,  # Below 0.60 threshold
        "reason": "Poor lighting and extreme motion blur prevent visual quality check.",
    }

    mock_resp = MagicMock()
    mock_resp.text = json.dumps(ai_response)

    with patch("google.genai.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        result = analyse_food_image(
            create_dummy_image_bytes(),
            mime_type="image/jpeg",
            food_name="Veg Curry",
        )

        assert result["verdict"] == "Unverified"
        assert result["confidence"] < CONFIDENCE_THRESHOLD
        assert "below the safety threshold" in result["rejectionReason"].lower()


def test_analyse_food_image_rejects_spoiled_food():
    """AI must reject visually spoiled or moldy food."""
    ai_response = {
        "isFood": True,
        "detectedFood": "Curry with white mold patches",
        "matchesDescription": True,
        "isSpoiled": True,
        "freshness": "Spoiled",
        "visualCondition": "Extensive mold growth and discoloration.",
        "confidence": 0.96,
        "reason": "Visible bacterial or fungal contamination.",
    }

    mock_resp = MagicMock()
    mock_resp.text = json.dumps(ai_response)

    with patch("google.genai.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        result = analyse_food_image(
            create_dummy_image_bytes(),
            mime_type="image/jpeg",
            food_name="Vegetable Curry",
        )

        assert result["verdict"] == "Rejected"
        assert result["isSpoiled"] is True
        assert "signs of spoilage" in result["rejectionReason"].lower()


def test_analyse_food_image_accepts_good_food():
    """AI accepts edible, wholesome food matching description with high confidence."""
    ai_response = {
        "isFood": True,
        "detectedFood": "Freshly cooked yellow dal and steamed white rice",
        "matchesDescription": True,
        "isSpoiled": False,
        "freshness": "Fresh",
        "visualCondition": "Freshly prepared in clean stainless container, good steam and texture.",
        "confidence": 0.94,
        "reason": "Wholesome freshly prepared meal in clean condition.",
    }

    mock_resp = MagicMock()
    mock_resp.text = json.dumps(ai_response)

    with patch("google.genai.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        result = analyse_food_image(
            create_dummy_image_bytes(),
            mime_type="image/jpeg",
            food_name="Dal Rice",
        )

        assert result["verdict"] == "Accepted"
        assert result["isFood"] is True
        assert result["isSpoiled"] is False
        assert result["matchesDescription"] is True
        assert result["freshness"] == "Fresh"
        assert result["screeningDisclaimer"] == FSSAI_DISCLAIMER
