import random
import time
import hashlib
from datetime import datetime, timedelta

def analyze_food_image(image_data: str) -> dict:
    """
    Simulates AI Image Analysis for food spoilage, quality, duplicate detection, and EXIF extraction.
    image_data is typically a base64 encoded string from the frontend.
    """
    # 1. Hashing for Duplicate Detection
    image_hash = hashlib.sha256(image_data.encode('utf-8')).hexdigest()
    
    # 2. Mock EXIF Data Extraction (Timestamp and Location)
    # In production, we would use Pillow (PIL.ExifTags) to parse standard JPEG EXIF.
    # Since mobile browsers often strip EXIF in base64 uploads, we simulate it here.
    has_exif = random.random() > 0.3 # 70% chance EXIF is preserved
    
    mock_timestamp = None
    if has_exif:
        # Simulate the photo being taken within the last 2 hours
        mock_timestamp = (datetime.now() - timedelta(minutes=random.randint(1, 120))).isoformat()
    
    # 3. AI Quality and Spoilage Analysis
    base_quality = random.uniform(0.70, 0.99)
    is_spoiled = base_quality < 0.75
    
    issues = []
    if is_spoiled:
        issues.append("Potential discoloration or wilting detected.")
    if base_quality < 0.80:
        issues.append("Slight packaging irregularity or moisture detected.")
        
    analysis_result = {
        "imageHash": image_hash,
        "metadata": {
            "hasExif": has_exif,
            "originalTimestamp": mock_timestamp,
            "locationVerified": has_exif 
        },
        "isSpoiled": is_spoiled,
        "freshnessIndicator": "Review Needed" if is_spoiled else "Acceptable",
        "visualCondition": "Issues Detected" if is_spoiled else "Good"
    }
    
    return analysis_result
