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
    serverSelectionTimeoutMS=8000,
    tz_aware=True,
)

database = client[MONGODB_DATABASE]

users_collection = database["users"]
donations_collection = database["donations"]


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

    donations_collection.create_index(
        [("pickupDeadline", ASCENDING)],
        expireAfterSeconds=0,
        partialFilterExpression={"status": "Active"},
        name="delete_expired_active_donations",
    )