from pathlib import Path

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder


BASE_DIR = Path(__file__).parent
DATASET_PATH = BASE_DIR / "food_priority_dataset.csv"
MODEL_PATH = BASE_DIR / "food_priority_model.pkl"


def train_priority_model() -> None:
    if not DATASET_PATH.exists():
        raise FileNotFoundError(
            "Dataset not found. Run generate_dataset.py before training the model."
        )

    dataset = pd.read_csv(DATASET_PATH)

    features = [
        "category",
        "servings",
        "preparation_age_minutes",
        "pickup_window_minutes",
        "packaging_score",
    ]

    target = "priority"

    x = dataset[features]
    y = dataset[target]

    categorical_features = ["category"]
    numeric_features = [
        "servings",
        "preparation_age_minutes",
        "pickup_window_minutes",
        "packaging_score",
    ]

    preprocessor = ColumnTransformer(
        transformers=[
            ("category_encoder", OneHotEncoder(handle_unknown="ignore"), categorical_features),
            ("numeric_features", "passthrough", numeric_features),
        ]
    )

    model = RandomForestClassifier(
        n_estimators=150,
        random_state=42,
        class_weight="balanced",
    )

    pipeline = Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            ("model", model),
        ]
    )

    x_train, x_test, y_train, y_test = train_test_split(
        x,
        y,
        test_size=0.2,
        random_state=42,
        stratify=y,
    )

    pipeline.fit(x_train, y_train)

    predictions = pipeline.predict(x_test)
    accuracy = accuracy_score(y_test, predictions)

    print("Food priority ML model trained successfully.")
    print(f"Accuracy: {accuracy:.2%}")
    print("\nClassification Report:")
    print(classification_report(y_test, predictions))

    model_package = {
        "model": pipeline,
        "features": features,
        "labels": ["High", "Medium", "Low"],
        "model_type": "RandomForestClassifier",
        "version": "1.0",
    }

    joblib.dump(model_package, MODEL_PATH)

    print(f"\nSaved trained model at: {MODEL_PATH}")


if __name__ == "__main__":
    train_priority_model()