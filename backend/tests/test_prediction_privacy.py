import pytest
import sys
from datetime import datetime, timezone
from pathlib import Path
from bson import ObjectId

backend_path = Path(__file__).resolve().parent.parent
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from main import document_to_donation


def create_sample_donation_document():
    return {
        "_id": ObjectId(),
        "foodName": "Fresh Dal Tadka & Rice",
        "category": "Cooked Meal",
        "servings": 60,
        "remainingServings": 60,
        "claimedServings": 0,
        "preparationTime": "2:00 PM today",
        "pickupDeadline": datetime.now(timezone.utc),
        "location": "Ashok Chowk, Solapur",
        "packagingCondition": "Sealed Stainless Steel Containers",
        "donorId": str(ObjectId()),
        "donorName": "Solapur Banquet Hall",
        "donorOrganisation": "Solapur Caterers",
        "donorLocation": "Solapur",
        "contactNumber": "9876543210",
        "status": "Active",
        "priority": "High",
        # ML Prediction Model fields that must be kept private
        "aiConfidence": 94.5,
        "predictionMethod": "ml_model",
        "predictionFeatures": {"freshnessScore": 0.95, "perishability": 0.8},
        # Originality fields
        "imageOriginality": "Likely Original",
        "originalityScore": 85,
        "captureMethod": "live_camera",
        "imageSha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "imagePerceptualHash": "0f0f0f0f0f0f0f0f",
        "createdAt": datetime.now(timezone.utc),
        "updatedAt": datetime.now(timezone.utc),
    }


def test_donor_ngo_cannot_see_prediction_details():
    """Non-admin callers (donors and NGOs) must receive None for prediction details."""
    doc = create_sample_donation_document()

    donation = document_to_donation(doc, include_claims=False, is_admin=False)
    donation_dict = donation.model_dump()

    assert donation_dict["aiConfidence"] is None
    assert donation_dict["predictionMethod"] is None
    assert donation_dict["predictionFeatures"] is None

    # Priority level itself should still be present
    assert donation_dict["priority"] == "High"
    # Originality verdict should be present
    assert donation_dict["imageOriginality"] == "Likely Original"


def test_admin_can_see_prediction_details():
    """Administrators must have full visibility of confidence, prediction method, and features."""
    doc = create_sample_donation_document()

    admin_donation = document_to_donation(doc, include_claims=False, is_admin=True)
    admin_dict = admin_donation.model_dump()

    assert admin_dict["aiConfidence"] == 94.5
    assert admin_dict["predictionMethod"] == "ml_model"
    assert admin_dict["predictionFeatures"] == {"freshnessScore": 0.95, "perishability": 0.8}
    assert admin_dict["imageOriginality"] == "Likely Original"
    assert admin_dict["originalityScore"] == 85
    assert admin_dict["imageSha256"] is not None
    assert admin_dict["imagePerceptualHash"] is not None
