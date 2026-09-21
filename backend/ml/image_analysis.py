import random
import time

def analyze_food_image(image_path: str) -> dict:
    """
    Simulates AI Image Analysis for food spoilage and quality.
    In a production environment, this would call a custom ML model, OpenCV heuristics, or a Vision API like Gemini.
    """
    
    # Generate a plausible mock quality score (mostly good, occasionally borderline)
    # 0.0 is completely spoiled, 1.0 is perfect condition.
    base_quality = random.uniform(0.70, 0.99)
    
    is_spoiled = base_quality < 0.75
    
    issues = []
    if is_spoiled:
        issues.append("Potential discoloration or wilting detected.")
    
    if base_quality < 0.80:
        issues.append("Slight packaging irregularity or moisture detected.")
        
    analysis_result = {
        "isSpoiled": is_spoiled,
        "qualityScore": round(base_quality, 2),
        "detectedIssues": issues,
        "confidence": round(random.uniform(0.85, 0.99), 2),
        "notes": "Food appears safe for consumption." if not is_spoiled else "Manual inspection strongly recommended before pickup."
    }
    
    return analysis_result
