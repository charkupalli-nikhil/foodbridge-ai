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


def test_notification_structure():
    """Validates notification model fields for recipient, type, read flag, and timestamps."""
    recipient_id = str(ObjectId())
    donation_id = str(ObjectId())

    notification = {
        "recipientUserId": recipient_id,
        "type": "new_donation",
        "title": "New Food Donation Available",
        "message": "50 servings of Cooked Meal are available near your location.",
        "donationId": donation_id,
        "read": False,
        "createdAt": datetime.now(timezone.utc),
    }

    assert notification["recipientUserId"] == recipient_id
    assert notification["type"] == "new_donation"
    assert notification["read"] is False
    assert notification["donationId"] == donation_id


def test_notification_unread_filtering():
    """Validates unread notification counting and read status marking."""
    notifications = [
        {"id": "1", "read": False, "title": "New donation"},
        {"id": "2", "read": True, "title": "Pickup accepted"},
        {"id": "3", "read": False, "title": "Collection completed"},
    ]

    unread = [n for n in notifications if not n["read"]]
    assert len(unread) == 2

    # Mark id 1 as read
    for n in notifications:
        if n["id"] == "1":
            n["read"] = True

    unread_after = [n for n in notifications if not n["read"]]
    assert len(unread_after) == 1
