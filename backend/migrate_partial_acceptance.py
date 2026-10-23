"""
One-off migration script for Partial Acceptance & Claims Architecture.
Idempotent: can be run safely multiple times.

Actions:
1. Backfills `remainingServings` and `claimedServings` on legacy donations.
2. Creates claim documents in `claims` collection for legacy Accepted / Collected donations.
3. Sets default food safety disclaimer and verdict for legacy donations lacking them.
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from database import donations_collection, claims_collection, users_collection


def migrate_partial_acceptance():
    print("[*] Starting Partial Acceptance & Claims migration...")

    total_donations = donations_collection.count_documents({})
    print(f"[*] Found {total_donations} total donations in database.")

    donations_updated = 0
    claims_created = 0

    for donation in donations_collection.find():
        donation_id = str(donation["_id"])
        servings = donation.get("servings", 1)
        status = donation.get("status", "Active")
        accepted_by = donation.get("acceptedByUserId")
        accepted_name = donation.get("acceptedByName", "Receiver Organization")

        updates = {}

        # 1. Backfill remainingServings & claimedServings if missing
        if "remainingServings" not in donation:
            if status == "Active":
                updates["remainingServings"] = servings
                updates["claimedServings"] = 0
            elif status in ("Accepted", "Collected"):
                updates["remainingServings"] = 0
                updates["claimedServings"] = servings
            elif status == "Partially Accepted":
                updates["remainingServings"] = donation.get("remainingServings", 0)
                updates["claimedServings"] = servings - updates["remainingServings"]

        # 2. Backfill food verdict fields if missing
        if "foodVerdict" not in donation:
            updates["foodVerdict"] = "Accepted"
            updates["foodConfidence"] = 0.95
            updates["detectedFood"] = donation.get("title", "Food Item")
            updates["isSpoiled"] = False
            updates["visualCondition"] = "Good"
            updates["freshnessIndicator"] = "Fresh"
            updates["fssaiDisclaimer"] = (
                "Visual screening only; not a laboratory safety certification."
            )

        if updates:
            donations_collection.update_one({"_id": donation["_id"]}, {"$set": updates})
            donations_updated += 1

        # 3. Create legacy claims if Accepted or Collected and acceptedByUserId exists
        if status in ("Accepted", "Collected") and accepted_by:
            existing_claim = claims_collection.find_one({
                "donationId": donation_id,
                "receiverUserId": accepted_by,
            })
            if not existing_claim:
                claim_doc = {
                    "donationId": donation_id,
                    "receiverUserId": accepted_by,
                    "receiverOrgName": accepted_name,
                    "quantity": servings,
                    "status": status,
                    "createdAt": donation.get("updatedAt", donation.get("createdAt", datetime.now(timezone.utc))),
                }
                if status == "Collected":
                    claim_doc["collectedAt"] = donation.get("collectedAt", datetime.now(timezone.utc))

                claims_collection.insert_one(claim_doc)
                claims_created += 1

    print(f"[✓] Migration completed successfully!")
    print(f"    - Donations updated: {donations_updated}")
    print(f"    - Legacy claims created: {claims_created}")


if __name__ == "__main__":
    migrate_partial_acceptance()
