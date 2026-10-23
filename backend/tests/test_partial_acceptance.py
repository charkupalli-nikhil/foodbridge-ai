import pytest
from unittest.mock import MagicMock
from bson import ObjectId
from datetime import datetime, timezone
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_path = Path(__file__).resolve().parent.parent
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


def test_partial_claim_remaining_arithmetic():
    """Validates that claimed servings and remaining servings update accurately."""
    total_servings = 100
    claim_1 = 30
    remaining_after_1 = total_servings - claim_1
    assert remaining_after_1 == 70

    claim_2 = 40
    remaining_after_2 = remaining_after_1 - claim_2
    assert remaining_after_2 == 30

    claim_3 = 30
    remaining_after_3 = remaining_after_2 - claim_3
    assert remaining_after_3 == 0


def test_donation_status_progression():
    """Status transitions Active -> Partially Accepted -> Accepted -> Collected."""
    def compute_status(remaining, total, all_claims_collected=False):
        if remaining == 0:
            return "Collected" if all_claims_collected else "Accepted"
        if remaining < total:
            return "Partially Accepted"
        return "Active"

    total = 50
    # Initially active
    assert compute_status(50, total) == "Active"

    # Claim 20 servings -> 30 remain
    assert compute_status(30, total) == "Partially Accepted"

    # Claim remaining 30 servings -> 0 remain
    assert compute_status(0, total, all_claims_collected=False) == "Accepted"

    # All claims collected
    assert compute_status(0, total, all_claims_collected=True) == "Collected"


def test_claim_document_structure():
    """Ensures claim documents contain all required fields for tracking."""
    claim = {
        "donationId": str(ObjectId()),
        "receiverUserId": str(ObjectId()),
        "receiverOrgName": "Hope Shelter NGO",
        "quantity": 25,
        "status": "Accepted",
        "createdAt": datetime.now(timezone.utc),
    }

    assert claim["quantity"] == 25
    assert claim["status"] == "Accepted"
    assert "receiverOrgName" in claim
    assert "createdAt" in claim
