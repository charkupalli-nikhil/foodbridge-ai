"""
Image Originality & Anti-Fraud Detection Engine for FoodBridge AI.

Detects photos sourced from the internet, stock galleries, duplicate uploads,
or taken of other screens.

Features:
1. Server-issued 10-minute signed capture session tokens for live camera captures.
2. EXIF recency validation (DateTimeOriginal <= ALLOWED_PHOTO_AGE_MINUTES).
3. Exact (SHA-256) and Perceptual (pHash / dHash) duplicate detection against past donations.
4. Geolocation proximity verification (capture coordinates vs declared pickup coordinates).
5. Gemini visual cue scoring (stock photo, watermarks, screen photos, staged studio lighting).
6. Fail-open error handling (never crashes donation creation if originality check fails).
"""

import io
import os
import uuid
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any, Tuple

import jwt
from jwt.exceptions import InvalidTokenError
from PIL import Image, ExifTags
import imagehash

try:
    from database import donations_collection
except ImportError:
    donations_collection = None

from security import JWT_SECRET, JWT_ALGORITHM
from geo_matching import calculate_haversine_distance

# Configurable thresholds via environment
DEFAULT_CAPTURE_TOKEN_EXPIRE_MINUTES = 10
DEFAULT_ALLOWED_PHOTO_AGE_MINUTES = 30
DEFAULT_ALLOWED_CAPTURE_DISTANCE_KM = 1.0
DEFAULT_DUPLICATE_HAMMING_THRESHOLD = 6

ORIGINALITY_LIKELY_ORIGINAL = "Likely Original"
ORIGINALITY_SUSPICIOUS = "Suspicious"
ORIGINALITY_LIKELY_INTERNET = "Likely Internet Image"

# Single-use consumed nonces in-memory set with auto-expiry cleanup
_consumed_capture_nonces: set[str] = set()


def hamming_distance(hash1: str, hash2: str) -> int:
    """Calculates Hamming distance between two hex-encoded perceptual hashes."""
    try:
        h1 = imagehash.hex_to_hash(hash1)
        h2 = imagehash.hex_to_hash(hash2)
        return h1 - h2
    except Exception:
        # Fallback bitwise calculation if plain hex strings
        val1 = int(hash1, 16)
        val2 = int(hash2, 16)
        return bin(val1 ^ val2).count("1")


# ---------------------------------------------------------------------------
# 1. Capture Session Tokens (10-minute validity, single use)
# ---------------------------------------------------------------------------

def create_capture_session_token(
    user_id: str = "anonymous", expiry_minutes: int = DEFAULT_CAPTURE_TOKEN_EXPIRE_MINUTES
) -> str:
    """Creates a signed capture session token for live camera photo capture."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "purpose": "camera_capture",
        "nonce": uuid.uuid4().hex,
        "iat": now,
        "exp": now + timedelta(minutes=expiry_minutes),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_capture_session_token(
    token: str, expected_user_id: Optional[str] = None
) -> Tuple[bool, str]:
    """
    Verifies a capture session token.
    Enforces expiration, user matching (if expected_user_id provided), purpose, and single-use nonces.
    Returns (is_valid, reason).
    """
    if not token or not token.strip():
        return False, "Missing capture session token."

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except InvalidTokenError as exc:
        return False, f"Invalid or expired capture token: {exc}"

    if payload.get("purpose") != "camera_capture":
        return False, "Token is not a valid camera capture token."

    if expected_user_id is not None and payload.get("sub") != expected_user_id:
        return False, "Token was issued to a different user."

    nonce = payload.get("nonce")
    if not nonce:
        return False, "Token is missing nonce identifier."

    if nonce in _consumed_capture_nonces:
        return False, "Capture session token has already been used."

    # Mark consumed
    _consumed_capture_nonces.add(nonce)
    return True, "Valid capture token."


# ---------------------------------------------------------------------------
# 2. Perceptual Hashing & SHA-256
# ---------------------------------------------------------------------------

def compute_image_hashes(image_bytes: bytes) -> Tuple[str, str, str]:
    """
    Computes exact SHA-256, perceptual hash (pHash), and difference hash (dHash).
    Returns (sha256_hex, phash_hex, dhash_hex).
    """
    sha256_hash = hashlib.sha256(image_bytes).hexdigest()

    with Image.open(io.BytesIO(image_bytes)) as img:
        # Convert to RGB to ensure uniform perceptual hashing
        if img.mode != "RGB":
            rgb_img = img.convert("RGB")
        else:
            rgb_img = img
        phash_val = str(imagehash.phash(rgb_img))
        dhash_val = str(imagehash.dhash(rgb_img))

    return sha256_hash, phash_val, dhash_val


def check_for_duplicate_donations(
    current_sha256: str,
    current_phash: str,
    exclude_donation_id: Optional[str] = None,
    hamming_threshold: int = DEFAULT_DUPLICATE_HAMMING_THRESHOLD,
) -> Tuple[bool, bool, Optional[str]]:
    """
    Checks database for exact SHA-256 duplicate or near-duplicate perceptual hash.
    Returns (is_exact_dup, is_perceptual_dup, matching_donation_id).
    """
    if donations_collection is None:
        return False, False, None

    try:
        # 1. Exact SHA-256 match
        query: Dict[str, Any] = {"imageSha256": current_sha256}
        if exclude_donation_id:
            query["_id"] = {"$ne": exclude_donation_id}

        exact_match = donations_collection.find_one(query, {"_id": 1})
        if exact_match:
            return True, True, str(exact_match["_id"])

        # 2. Perceptual hash near-match
        curr_hash_obj = imagehash.hex_to_hash(current_phash)
        # Scan recent donations with perceptual hash (limit to recent 200 for fast query)
        recent_donations = donations_collection.find(
            {"imagePerceptualHash": {"$exists": True, "$ne": None}},
            {"_id": 1, "imagePerceptualHash": 1},
        ).sort("createdAt", -1).limit(200)

        for don in recent_donations:
            don_id = str(don["_id"])
            if exclude_donation_id and don_id == exclude_donation_id:
                continue
            past_phash_str = don.get("imagePerceptualHash")
            if not past_phash_str:
                continue
            try:
                past_hash_obj = imagehash.hex_to_hash(past_phash_str)
                hamming_dist = curr_hash_obj - past_hash_obj
                if hamming_dist <= hamming_threshold:
                    return False, True, don_id
            except Exception:
                continue

    except Exception as exc:
        print(f"[Originality] Duplicate check failed: {exc}")

    return False, False, None


# ---------------------------------------------------------------------------
# 3. EXIF Metadata Extraction
# ---------------------------------------------------------------------------

def extract_exif_metadata(image_bytes: bytes) -> Dict[str, Any]:
    """
    Extracts camera metadata and timestamp from EXIF tags.
    """
    metadata: Dict[str, Any] = {
        "hasExif": False,
        "photoTakenAt": None,
        "cameraMake": None,
        "cameraModel": None,
        "photoAgeMinutes": None,
    }

    try:
        with Image.open(io.BytesIO(image_bytes)) as img:
            raw_exif = img.getexif()
            if not raw_exif:
                return metadata

            metadata["hasExif"] = True

            # Extract basic tags
            for tag_id, val in raw_exif.items():
                tag_name = ExifTags.TAGS.get(tag_id, str(tag_id))
                if tag_name == "Make":
                    metadata["cameraMake"] = str(val).strip()
                elif tag_name == "Model":
                    metadata["cameraModel"] = str(val).strip()
                elif tag_name in ("DateTime", "DateTimeOriginal"):
                    if not metadata["photoTakenAt"]:
                        metadata["photoTakenAt"] = str(val).strip()

            # Inspect sub-IFD (often contains 36867 DateTimeOriginal)
            for ifd_id in (ExifTags.IFD.Exif, ExifTags.IFD.GPSInfo):
                try:
                    ifd_data = raw_exif.get_ifd(ifd_id)
                    for sub_tag, val in ifd_data.items():
                        sub_name = ExifTags.TAGS.get(sub_tag, str(sub_tag))
                        if sub_name == "DateTimeOriginal" and not metadata["photoTakenAt"]:
                            metadata["photoTakenAt"] = str(val).strip()
                except Exception:
                    pass

            # Parse timestamp if found (Standard EXIF: 'YYYY:MM:DD HH:MM:SS')
            if metadata["photoTakenAt"]:
                try:
                    parsed_dt = datetime.strptime(
                        metadata["photoTakenAt"], "%Y:%m:%d %H:%M:%S"
                    ).replace(tzinfo=timezone.utc)
                    age_seconds = (datetime.now(timezone.utc) - parsed_dt).total_seconds()
                    metadata["photoAgeMinutes"] = round(age_seconds / 60.0, 1)
                except Exception:
                    pass

    except Exception as exc:
        print(f"[Originality] EXIF extraction note: {exc}")

    return metadata


# ---------------------------------------------------------------------------
# 4. Layered Scoring & Verdict
# ---------------------------------------------------------------------------

def evaluate_image_originality(
    image_bytes: bytes,
    user_id: str = "system",
    capture_method: str = "live_camera",
    capture_token: Optional[str] = None,
    capture_lat: Optional[float] = None,
    capture_lng: Optional[float] = None,
    pickup_lat: Optional[float] = None,
    pickup_lng: Optional[float] = None,
    gemini_cues: Optional[Dict[str, Any]] = None,
    exclude_donation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Evaluates image authenticity across all verification layers.
    Returns a comprehensive originality dictionary.
    
    Fail-open design: Unexpected exceptions fall back gracefully
    to 'Not Checked' to avoid blocking valid donations on server errors.
    """
    reasons: List[str] = []
    cues = gemini_cues or {}

    try:
        # 1. Compute perceptual & SHA-256 hashes
        sha256_hash, phash_hex, dhash_hex = compute_image_hashes(image_bytes)

        # 2. Check for duplicates in database
        hamming_limit = int(
            os.getenv("DUPLICATE_HAMMING_THRESHOLD", DEFAULT_DUPLICATE_HAMMING_THRESHOLD)
        )
        is_exact_dup, is_perceptual_dup, dup_don_id = check_for_duplicate_donations(
            current_sha256=sha256_hash,
            current_phash=phash_hex,
            exclude_donation_id=exclude_donation_id,
            hamming_threshold=hamming_limit,
        )

        if is_exact_dup:
            return {
                "imageOriginality": "Likely Internet Image",
                "originalityScore": 0,
                "captureMethod": capture_method,
                "imageSha256": sha256_hash,
                "imagePerceptualHash": phash_hex,
                "originalityReasons": [
                    f"Identical duplicate of an existing donation photo in the system (Donation #{dup_don_id})."
                ],
                "photoTakenAt": None,
                "tokenVerified": False,
            }

        # 3. Base Score starts at 100 (Authentic)
        score = 100

        # Duplicate perceptual match penalty
        if is_perceptual_dup:
            score -= 60
            reasons.append(
                f"Visually identical/near-duplicate to an existing donation photo (Donation #{dup_don_id})."
            )

        # 4. Token validation for live camera
        token_valid = False
        if capture_method == "live_camera":
            if capture_token:
                is_valid, token_msg = verify_capture_session_token(capture_token, user_id)
                token_valid = is_valid
                if not is_valid:
                    score -= 20
                    reasons.append(f"Camera session token error: {token_msg}")
            else:
                score -= 15
                reasons.append("Photo submitted as live camera but missing session token.")
        else:
            # Gallery upload
            allow_gallery = os.getenv("ALLOW_GALLERY_UPLOAD", "false").lower() == "true"
            if not allow_gallery:
                score -= 25
                reasons.append("Uploaded from local gallery instead of live camera capture.")

        # 5. Geolocation proximity check
        max_dist_km = float(
            os.getenv("ALLOWED_CAPTURE_DISTANCE_KM", DEFAULT_ALLOWED_CAPTURE_DISTANCE_KM)
        )
        if (
            capture_lat is not None
            and capture_lng is not None
            and pickup_lat is not None
            and pickup_lng is not None
        ):
            loc_dist_km = calculate_haversine_distance(
                capture_lat, capture_lng, pickup_lat, pickup_lng
            )
            if loc_dist_km > max_dist_km:
                score -= 25
                reasons.append(
                    f"Capture location is {round(loc_dist_km, 1)} km away from declared pickup address "
                    f"(allowed radius: {max_dist_km} km)."
                )

        # 6. EXIF analysis
        exif = extract_exif_metadata(image_bytes)
        max_photo_age = float(
            os.getenv("ALLOWED_PHOTO_AGE_MINUTES", DEFAULT_ALLOWED_PHOTO_AGE_MINUTES)
        )
        photo_age = exif.get("photoAgeMinutes")
        if photo_age is not None and photo_age > max_photo_age and capture_method != "live_camera":
            score -= 30
            reasons.append(
                f"Photo was taken {round(photo_age)} minutes ago according to EXIF timestamp "
                f"(allowed age: {max_photo_age} min)."
            )

        # 7. Gemini visual cues penalties
        if cues.get("hasWatermarkOrLogo"):
            score -= 60
            reasons.append("Visible stock agency watermark or commercial branding detected.")

        if cues.get("looksLikeScreenPhoto"):
            score -= 50
            reasons.append("Image appears to be a photograph of a computer or phone screen.")

        if cues.get("looksLikeStockOrWebImage"):
            score -= 45
            reasons.append("Visual style matches commercial stock photography or downloaded web image.")

        if cues.get("looksProfessionallyStaged"):
            score -= 20
            reasons.append("Professional studio lighting or staged commercial culinary presentation.")

        # Clamp score 0 to 100
        score = max(0, min(100, score))

        # Classification
        if score >= 70:
            classification = "Likely Original"
        elif score >= 40:
            classification = "Suspicious"
        else:
            classification = "Likely Internet Image"

        if not reasons:
            reasons.append("Passed all originality and camera authenticity checks.")

        return {
            "imageOriginality": classification,
            "originalityScore": score,
            "captureMethod": capture_method,
            "imageSha256": sha256_hash,
            "imagePerceptualHash": phash_hex,
            "originalityReasons": reasons,
            "photoTakenAt": exif.get("photoTakenAt"),
            "tokenVerified": token_valid,
        }

    except Exception as exc:
        # FAIL-OPEN for originality system errors
        print(f"[FAIL-OPEN] Image originality evaluation error: {exc}")
        return {
            "imageOriginality": "Not Checked",
            "originalityScore": None,
            "captureMethod": capture_method,
            "imageSha256": None,
            "imagePerceptualHash": None,
            "originalityReasons": [f"Originality verification unavailable: {str(exc)}"],
            "photoTakenAt": None,
            "tokenVerified": False,
        }
