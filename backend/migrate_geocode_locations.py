"""
Migration script to backfill GeoJSON coordinates and image hashes
for existing donations and users in FoodBridge AI.

Safe and idempotent:
- Only updates documents missing GeoJSON coordinates or image hashes.
- Respects OpenStreetMap Nominatim 1 req/sec rate limit.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Ensure backend root is on sys.path
backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))
load_dotenv(backend_dir / ".env")

from database import users_collection, donations_collection
from geocoding import geocode_address, format_geojson_point
from image_originality import compute_image_hashes

FOOD_UPLOAD_DIR = backend_dir / "uploads" / "food"


def migrate_users():
    print("[Migration] Checking users for missing location coordinates...")
    users_cursor = users_collection.find({
        "$or": [
            {"locationCoordinates": {"$exists": False}},
            {"locationCoordinates": None},
        ],
        "location": {"$exists": True, "$ne": ""},
    })

    count = 0
    for user in users_cursor:
        location_str = user.get("location", "").strip()
        if not location_str:
            continue

        coords = geocode_address(location_str)
        if coords:
            geo_point = format_geojson_point(coords[0], coords[1])
            users_collection.update_one(
                {"_id": user["_id"]},
                {"$set": {"locationCoordinates": geo_point}},
            )
            count += 1
            print(f"  -> Updated user '{user.get('email')}' at '{location_str}': ({coords[0]}, {coords[1]})")
        else:
            print(f"  -> Could not geocode user location: '{location_str}'")

    print(f"[Migration] Completed user location backfill. Updated {count} users.")


def migrate_donations():
    print("\n[Migration] Checking donations for missing coordinates and image hashes...")
    donations_cursor = donations_collection.find({})

    coords_count = 0
    hashes_count = 0

    for donation in donations_cursor:
        don_id = donation["_id"]
        update_fields = {}

        # 1. Backfill GeoJSON pickup coordinates
        if not donation.get("pickupCoordinates") and donation.get("location"):
            location_str = donation["location"].strip()
            coords = geocode_address(location_str)
            if coords:
                update_fields["pickupCoordinates"] = format_geojson_point(coords[0], coords[1])
                coords_count += 1
                print(f"  -> Geocoded donation #{don_id} at '{location_str}': ({coords[0]}, {coords[1]})")

        # 2. Backfill SHA-256 and Perceptual Hash from local image file if missing
        if (not donation.get("imageSha256") or not donation.get("imagePerceptualHash")) and donation.get("foodImage"):
            img_path_str = donation["foodImage"]
            filename = Path(img_path_str).name
            local_path = FOOD_UPLOAD_DIR / filename
            if local_path.exists():
                try:
                    with open(local_path, "rb") as f:
                        img_bytes = f.read()
                    sha256, phash, _ = compute_image_hashes(img_bytes)
                    update_fields["imageSha256"] = sha256
                    update_fields["imagePerceptualHash"] = phash
                    if not donation.get("imageOriginality"):
                        update_fields["imageOriginality"] = "Likely Original"
                        update_fields["originalityScore"] = 100
                    hashes_count += 1
                    print(f"  -> Hashed image for donation #{don_id} (pHash: {phash})")
                except Exception as e:
                    print(f"  -> Could not hash image for donation #{don_id}: {e}")

        if update_fields:
            donations_collection.update_one({"_id": don_id}, {"$set": update_fields})

    print(f"[Migration] Completed donation backfill. Updated {coords_count} coordinates, {hashes_count} image hashes.")


if __name__ == "__main__":
    print("=== FoodBridge AI Database Geolocation & Hash Migration ===")
    try:
        migrate_users()
        migrate_donations()
        print("\n=== Migration finished successfully ===")
    except Exception as exc:
        print(f"\n[Migration Error] {exc}")
        sys.exit(1)
