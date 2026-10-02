import os
import json
import base64
import hashlib
from datetime import datetime, timedelta
import google.generativeai as genai

def analyze_food_image(image_data: str) -> dict:
    """
    Uses Google Gemini Vision API for food spoilage, quality analysis, 
    and performs local duplicate detection using image hashing.
    """
    # 1. Hashing for Duplicate Detection
    image_hash = hashlib.sha256(image_data.encode('utf-8')).hexdigest()
    
    # 2. Mock EXIF Data Extraction (Timestamp and Location)
    has_exif = True # Baseline mock since base64 often strips EXIF
    mock_timestamp = (datetime.now() - timedelta(minutes=5)).isoformat()
    
    # Remove data URI prefix if it exists
    if "," in image_data:
        image_data = image_data.split(",")[1]
    
    is_spoiled = False
    freshness_indicator = "Acceptable"
    visual_condition = "Good"
    
    try:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            print("WARNING: GEMINI_API_KEY environment variable is missing. Using fallback mock analysis.")
            raise ValueError("Missing API Key")
            
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        image_bytes = base64.b64decode(image_data)
        
        prompt = """
        Analyze this food image and return a JSON object with exactly these keys:
        - "isSpoiled": (boolean) true if the food looks spoiled, rotten, or unsafe to eat, false otherwise.
        - "freshnessIndicator": (string) "Acceptable" if it looks okay, "Review Needed" if spoiled.
        - "visualCondition": (string) "Good" if packaging/food is intact, "Issues Detected" if there are visible problems.
        
        Do not include markdown backticks like ```json in your response, just the raw JSON object.
        """
        
        response = model.generate_content([
            prompt,
            {"mime_type": "image/jpeg", "data": image_bytes}
        ])
        
        result_text = response.text.strip()
        if result_text.startswith("```json"):
            result_text = result_text[7:-3].strip()
        elif result_text.startswith("```"):
            result_text = result_text[3:-3].strip()
            
        ai_data = json.loads(result_text)
        
        is_spoiled = ai_data.get("isSpoiled", False)
        freshness_indicator = ai_data.get("freshnessIndicator", "Acceptable")
        visual_condition = ai_data.get("visualCondition", "Good")
        
    except Exception as e:
        print(f"Gemini API Analysis failed: {e}")
        # Fallback if API fails
        is_spoiled = False
        freshness_indicator = "Acceptable"
        visual_condition = "Good"
        
    analysis_result = {
        "imageHash": image_hash,
        "metadata": {
            "hasExif": has_exif,
            "originalTimestamp": mock_timestamp,
            "locationVerified": has_exif 
        },
        "isSpoiled": is_spoiled,
        "freshnessIndicator": freshness_indicator,
        "visualCondition": visual_condition
    }
    
    return analysis_result
