import os

from dotenv import load_dotenv
from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.errors import PyMongoError

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")
MONGODB_DATABASE = os.getenv("MONGODB_DATABASE", "foodbridge_ai")

if not MONGODB_URI:
    raise RuntimeError(
        "MONGODB_URI is missing. Add your MongoDB Atlas connection string to backend/.env."
    )

client = MongoClient(
    MONGODB_URI,
    serverSelectionTimeoutMS=30000,
    connectTimeoutMS=30000,
    socketTimeoutMS=30000,
    tz_aware=True,
)
client.admin.command("ping")

print("MongoDB Connected Successfully")
database = client[MONGODB_DATABASE]

users_collection = database["users"]
donations_collection = database["donations"]
notifications_collection = database["notifications"]
claims_collection = database["claims"]
geocode_cache_collection = database["geocode_cache"]


def check_database_connection() -> bool:
    try:
        client.admin.command("ping")
        return True
    except PyMongoError:
        return False


def initialise_database_indexes() -> None:
    client.admin.command("ping")

    users_collection.create_index(
        [("email", ASCENDING)],
        unique=True,
        name="unique_user_email",
    )

    donations_collection.create_index(
        [("createdAt", DESCENDING)],
        name="donations_created_at",
    )

    donations_collection.create_index(
        [("status", ASCENDING), ("createdAt", DESCENDING)],
        name="donations_status_created_at",
    )

    donations_collection.create_index(
        [("donorUserId", ASCENDING), ("createdAt", DESCENDING)],
        name="donations_donor_created_at",
    )

    donations_collection.create_index(
        [("acceptedByUserId", ASCENDING), ("createdAt", DESCENDING)],
        name="donations_ngo_created_at",
    )

    # Note: partialFilterExpression ensures donations with claims ("Partially Accepted", "Accepted")
    # are never deleted by the TTL index.
    donations_collection.create_index(
        [("pickupDeadline", ASCENDING)],
        expireAfterSeconds=0,
        partialFilterExpression={"status": "Active"},
        name="delete_expired_active_donations",
    )

    # Notifications indexes (Feature 2)
    notifications_collection.create_index(
        [("recipientUserId", ASCENDING), ("read", ASCENDING), ("createdAt", DESCENDING)],
        name="recipient_notifications_read_created_at",
    )

    notifications_collection.create_index(
        [("createdAt", ASCENDING)],
        expireAfterSeconds=30 * 86400,
        name="notifications_ttl_30d",
    )

    # Claims indexes (Feature 3)
    claims_collection.create_index(
        [("donationId", ASCENDING), ("receiverUserId", ASCENDING)],
        name="claims_donation_receiver",
    )

    claims_collection.create_index(
        [("receiverUserId", ASCENDING), ("createdAt", DESCENDING)],
        name="claims_receiver_created_at",
    )

    claims_collection.create_index(
        [("status", ASCENDING)],
        name="claims_status",
    )

    # GeoJSON 2dsphere indexes for location matching
    try:
        donations_collection.create_index(
            [("pickupCoordinates", "2dsphere")],
            name="donations_pickup_2dsphere",
        )
    except Exception as e:
        print(f"[Index] Note on donations 2dsphere index: {e}")

    try:
        users_collection.create_index(
            [("locationCoordinates", "2dsphere")],
            name="users_location_2dsphere",
        )
    except Exception as e:
        print(f"[Index] Note on users 2dsphere index: {e}")

    # Image originality and deduplication indexes
    donations_collection.create_index(
        [("imagePerceptualHash", ASCENDING)],
        name="donations_image_phash",
    )
    donations_collection.create_index(
        [("imageSha256", ASCENDING)],
        name="donations_image_sha256",
    )

    # Geocode cache indexes
    geocode_cache_collection.create_index(
        [("normalizedKey", ASCENDING)],
        unique=True,
        name="unique_geocode_key",
    )
    geocode_cache_collection.create_index(
        [("createdAt", ASCENDING)],
        expireAfterSeconds=90 * 86400,
        name="geocode_cache_ttl_90d",
    )