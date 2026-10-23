import pytest
import os
import sys
from pathlib import Path
from PIL import Image
import io

backend_path = Path(__file__).resolve().parent.parent
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from image_originality import (
    create_capture_session_token,
    verify_capture_session_token,
    compute_image_hashes,
    hamming_distance,
    evaluate_image_originality,
    ORIGINALITY_LIKELY_ORIGINAL,
    ORIGINALITY_SUSPICIOUS,
    ORIGINALITY_LIKELY_INTERNET,
)


def create_test_image_bytes(color=(120, 200, 80)):
    image = Image.new("RGB", (120, 120), color=color)
    buf = io.BytesIO()
    image.save(buf, format="JPEG")
    return buf.getvalue()


def test_capture_session_token_lifecycle():
    token = create_capture_session_token(expiry_minutes=10)
    assert token is not None
    assert len(token) > 20

    # First verification should succeed
    is_valid, reason = verify_capture_session_token(token)
    assert is_valid is True
    assert "Valid" in reason

    # Second verification with same token should fail due to single-use nonce
    is_valid_reused, reuse_reason = verify_capture_session_token(token)
    assert is_valid_reused is False
    assert "already been used" in reuse_reason.lower()


def test_tampered_token():
    tampered_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.tampered.signature"
    is_valid, reason = verify_capture_session_token(tampered_token)
    assert is_valid is False


def test_compute_image_hashes():
    data = create_test_image_bytes()
    sha, phash, dhash = compute_image_hashes(data)
    assert len(sha) == 64
    assert phash is not None
    assert len(phash) == 16


def test_hamming_distance():
    assert hamming_distance("0000000000000000", "0000000000000000") == 0
    assert hamming_distance("0000000000000000", "0000000000000001") == 1
    assert hamming_distance("ffffffffffffffff", "0000000000000000") == 64


def test_evaluate_image_originality_live_camera_passes():
    img_bytes = create_test_image_bytes()
    token = create_capture_session_token(expiry_minutes=10)

    # Clean Gemini result without web/stock flags
    inspection_result = {
        "looksLikeStockOrWebImage": False,
        "hasWatermarkOrLogo": False,
        "looksLikeScreenPhoto": False,
        "looksProfessionallyStaged": False,
        "originalityReason": "Natural smartphone photo of home-cooked meal",
    }

    report = evaluate_image_originality(
        image_bytes=img_bytes,
        user_id="test_donor",
        capture_method="live_camera",
        capture_token=token,
        gemini_cues=inspection_result,
    )

    assert report["imageOriginality"] == ORIGINALITY_LIKELY_ORIGINAL
    assert report["originalityScore"] >= 70
    assert "imageSha256" in report
    assert "imagePerceptualHash" in report


def test_evaluate_image_originality_stock_flag_blocks():
    img_bytes = create_test_image_bytes()

    # Gemini detects commercial stock image / watermark
    inspection_result = {
        "looksLikeStockOrWebImage": True,
        "hasWatermarkOrLogo": True,
        "looksLikeScreenPhoto": False,
        "looksProfessionallyStaged": True,
        "originalityReason": "Visible Getty Images watermark and commercial studio lighting",
    }

    report = evaluate_image_originality(
        image_bytes=img_bytes,
        user_id="test_donor",
        capture_method="gallery_upload",
        capture_token=None,
        gemini_cues=inspection_result,
    )

    assert report["imageOriginality"] == ORIGINALITY_LIKELY_INTERNET
    assert report["originalityScore"] < 40
    assert any("watermark" in r.lower() or "stock" in r.lower() for r in report["originalityReasons"])
