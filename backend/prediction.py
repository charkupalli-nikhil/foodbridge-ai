from datetime import datetime
from pathlib import Path
from typing import Any

import joblib
import pandas as pd


MODEL_PATH = Path(__file__).parent / "ml" / "food_priority_model.pkl"


def parse_preparation_age_minutes(preparation_time: str) -> int:
    """
    Converts donor-entered preparation text into approximate minutes.
    Examples:
    - "Prepared 20 minutes ago" -> 20
    - "Prepared 2 hours ago" -> 120
    - unknown text -> 180
    """

    if not preparation_time:
        return 180

    text = preparation_time.lower()

    numbers = [int(word) for word in text.split() if word.isdigit()]

    if not numbers:
        return 180

    value = numbers[0]

    if "hour" in text:
        return value * 60

    if "minute" in text or "min" in text:
        return value

    return 180


def calculate_pickup_window_minutes(pickup_deadline: Any) -> int:
    """
    Calculates how many minutes are left before pickup deadline.
    """

    try:
        if isinstance(pickup_deadline, str):
            deadline = datetime.fromisoformat(pickup_deadline.replace("Z", "+00:00"))
        else:
            deadline = pickup_deadline

        now = datetime.now(deadline.tzinfo) if deadline.tzinfo else datetime.now()
        remaining_minutes = int((deadline - now).total_seconds() / 60)

        return max(remaining_minutes, 0)
    except Exception:
        return 240


def calculate_packaging_score(packaging_condition: str) -> int:
    """
    Converts packaging text into a numerical hygiene score.
    Higher score means better packaging condition.
    """

    if not packaging_condition:
        return 3

    text = packaging_condition.lower()

    if "sealed" in text or "food-grade" in text or "refrigerated" in text:
        return 5

    if "clean" in text or "covered" in text or "packed" in text:
        return 4

    if "open" in text:
        return 3

    if "quick" in text or "loose" in text:
        return 2

    return 3


def fallback_priority_prediction(
    category: str,
    servings: int,
    preparation_age_minutes: int,
    pickup_window_minutes: int,
    packaging_score: int,
) -> dict[str, Any]:
    """
    Safe fallback used only if the ML model file is missing.
    """

    score = 0

    if category in ["Cooked Meal", "Dairy"]:
        score += 3
    elif category in ["Fruits", "Vegetables", "Bakery"]:
        score += 2
    else:
        score += 1

    if servings >= 100:
        score += 3
    elif servings >= 50:
        score += 2
    else:
        score += 1

    if preparation_age_minutes > 180:
        score += 3
    elif preparation_age_minutes > 60:
        score += 2
    else:
        score += 1

    if pickup_window_minutes <= 90:
        score += 4
    elif pickup_window_minutes <= 240:
        score += 2
    else:
        score += 1

    if packaging_score <= 2:
        score += 2

    if score >= 11:
        priority = "High"
        confidence = 0.75
    elif score >= 7:
        priority = "Medium"
        confidence = 0.7
    else:
        priority = "Low"
        confidence = 0.65

    return {
        "priority": priority,
        "confidence": confidence,
        "method": "rule_fallback",
    }


def predict_food_priority(
    category: str,
    servings: int,
    preparation_time: str,
    pickup_deadline: Any,
    packaging_condition: str,
) -> dict[str, Any]:
    """
    Predicts donation priority using the trained ML model.

    Returns:
    {
        "priority": "High",
        "confidence": 0.91,
        "method": "ml_model",
        "features": {...}
    }
    """

    preparation_age_minutes = parse_preparation_age_minutes(preparation_time)
    pickup_window_minutes = calculate_pickup_window_minutes(pickup_deadline)
    packaging_score = calculate_packaging_score(packaging_condition)

    input_features = {
        "category": category,
        "servings": int(servings),
        "preparation_age_minutes": preparation_age_minutes,
        "pickup_window_minutes": pickup_window_minutes,
        "packaging_score": packaging_score,
    }

    if not MODEL_PATH.exists():
        fallback_result = fallback_priority_prediction(
            category=category,
            servings=int(servings),
            preparation_age_minutes=preparation_age_minutes,
            pickup_window_minutes=pickup_window_minutes,
            packaging_score=packaging_score,
        )

        fallback_result["features"] = input_features
        return fallback_result

    model_package = joblib.load(MODEL_PATH)
    model = model_package["model"]

    input_dataframe = pd.DataFrame([input_features])

    predicted_priority = model.predict(input_dataframe)[0]

    confidence = 0.0

    if hasattr(model, "predict_proba"):
        probabilities = model.predict_proba(input_dataframe)[0]
        confidence = float(max(probabilities))

    return {
        "priority": predicted_priority,
        "confidence": round(confidence, 4),
        "method": "ml_model",
        "features": input_features,
    }