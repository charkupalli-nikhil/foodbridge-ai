import random
from pathlib import Path

import pandas as pd


DATASET_PATH = Path(__file__).parent / "food_priority_dataset.csv"


FOOD_CATEGORIES = [
    "Cooked Meal",
    "Packaged Food",
    "Bakery",
    "Fruits",
    "Vegetables",
    "Dairy",
    "Snacks",
]

PACKAGING_CONDITIONS = [
    "Packed in clean covered containers",
    "Sealed and hygienic packaging",
    "Freshly packed in food-grade boxes",
    "Open container but clean",
    "Needs quick handling",
    "Loose packaging",
    "Refrigerated and sealed",
]


def calculate_priority_label(
    category: str,
    servings: int,
    preparation_age_minutes: int,
    pickup_window_minutes: int,
    packaging_score: int,
) -> str:
    """
    This hidden function creates realistic labels for training data.
    Later, the ML model will learn this pattern instead of using direct rules.
    """

    urgency_score = 0

    if category in ["Cooked Meal", "Dairy"]:
        urgency_score += 3
    elif category in ["Fruits", "Vegetables", "Bakery"]:
        urgency_score += 2
    else:
        urgency_score += 1

    if servings >= 100:
        urgency_score += 3
    elif servings >= 50:
        urgency_score += 2
    else:
        urgency_score += 1

    if preparation_age_minutes <= 60:
        urgency_score += 1
    elif preparation_age_minutes <= 180:
        urgency_score += 2
    else:
        urgency_score += 3

    if pickup_window_minutes <= 90:
        urgency_score += 4
    elif pickup_window_minutes <= 240:
        urgency_score += 2
    else:
        urgency_score += 1

    if packaging_score <= 2:
        urgency_score += 2
    elif packaging_score == 3:
        urgency_score += 1

    if urgency_score >= 11:
        return "High"
    if urgency_score >= 7:
        return "Medium"
    return "Low"


def create_dataset(total_rows: int = 1500) -> pd.DataFrame:
    rows = []

    for _ in range(total_rows):
        category = random.choice(FOOD_CATEGORIES)
        servings = random.randint(10, 250)
        preparation_age_minutes = random.randint(5, 480)
        pickup_window_minutes = random.randint(30, 720)
        packaging_condition = random.choice(PACKAGING_CONDITIONS)

        if "sealed" in packaging_condition.lower() or "food-grade" in packaging_condition.lower():
            packaging_score = 5
        elif "clean" in packaging_condition.lower() or "covered" in packaging_condition.lower():
            packaging_score = 4
        elif "open" in packaging_condition.lower():
            packaging_score = 3
        elif "quick" in packaging_condition.lower():
            packaging_score = 2
        else:
            packaging_score = 1

        priority = calculate_priority_label(
            category=category,
            servings=servings,
            preparation_age_minutes=preparation_age_minutes,
            pickup_window_minutes=pickup_window_minutes,
            packaging_score=packaging_score,
        )

        rows.append(
            {
                "category": category,
                "servings": servings,
                "preparation_age_minutes": preparation_age_minutes,
                "pickup_window_minutes": pickup_window_minutes,
                "packaging_score": packaging_score,
                "priority": priority,
            }
        )

    return pd.DataFrame(rows)


def main() -> None:
    dataset = create_dataset()
    dataset.to_csv(DATASET_PATH, index=False)

    print("Food priority dataset generated successfully.")
    print(f"Saved at: {DATASET_PATH}")
    print(f"Rows: {len(dataset)}")
    print("\nPriority distribution:")
    print(dataset["priority"].value_counts())


if __name__ == "__main__":
    main()