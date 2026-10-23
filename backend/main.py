import asyncio
import uuid
import os
import shutil
import math
import requests
import urllib.parse
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any, Literal

from geocoding import geocode_address, reverse_geocode, format_geojson_point
from geo_matching import (
    calculate_haversine_distance,
    calculate_match_metrics,
    get_directions_url,
)
from image_originality import (
    create_capture_session_token,
    verify_capture_session_token,
    evaluate_image_originality,
    compute_image_hashes,
)


def get_coordinates(location_str: str):
    """Backward-compatible geocode helper using geocoding module."""
    return geocode_address(location_str)

from bson import ObjectId
from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr, Field
from pymongo import DESCENDING, ReturnDocument
from pymongo.errors import DuplicateKeyError, PyMongoError

from database import (
    check_database_connection,
    donations_collection,
    initialise_database_indexes,
    users_collection,
    notifications_collection,
    claims_collection,
)
from image_analysis import analyse_food_image, check_packaging_image, FSSAI_DISCLAIMER
from prediction import predict_food_priority
from security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)

PriorityType = Literal["High", "Medium", "Low"]
DonationStatusType = Literal["Active", "Partially Accepted", "Accepted", "Collected"]
UserRoleType = Literal["donor", "ngo", "admin"]
RegistrationRoleType = Literal["donor", "ngo"]

FoodCategoryType = Literal[
    "Cooked Meal",
    "Packaged Food",
    "Bakery",
    "Fruits",
    "Vegetables",
    "Dairy",
    "Snacks",
]


class UserRegister(BaseModel):
    fullName: str = Field(min_length=2, max_length=100)
    email: EmailStr
    organisation: str = Field(min_length=2, max_length=150)
    role: RegistrationRoleType

    organizationType: str | None = None

    description: str | None = None

    capacity: int | None = None

    operatingHours: str | None = None

    acceptedFoodTypes: list[str] = []
    verificationStatus: str | None = "pending"

    registrationCertificate: str | None = None

    governmentId: str | None = None

    organizationLogo: str | None = None

    verifiedAt: datetime | None = None

    verifiedBy: str | None = None
    location: str = Field(min_length=2, max_length=200)
    contactNumber: str = Field(min_length=10, max_length=15)
    password: str = Field(min_length=6, max_length=100)

    safetyAgreement: bool


class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=100)
    role: UserRoleType


class UserPublic(BaseModel):
    id: str
    fullName: str
    email: EmailStr

    organisation: str
    role: UserRoleType

    # Receiver Profile
    organizationType: str | None = None
    description: str | None = None
    capacity: int | None = None
    operatingHours: str | None = None
    acceptedFoodTypes: list[str] = []

    # Verification
    verificationStatus: str = "verified"
    registrationCertificate: str | None = None
    governmentId: str | None = None
    organizationLogo: str |None = None
    verifiedAt: datetime | None = None
    verifiedBy: str | None = None
    rejectionReason: str | None = None

    # Trust & Status
    trustScore: int = 100
    accountStatus: str = "active"

    # Common
    location: str
    contactNumber: str
    createdAt: datetime


class AuthResponse(BaseModel):
    accessToken: str
    tokenType: str
    user: UserPublic


class UserLocationUpdate(BaseModel):
    location: str = Field(min_length=2, max_length=200)
    latitude: float | None = None
    longitude: float | None = None


class DonationCreate(BaseModel):
    foodName: str = Field(min_length=2, max_length=100)
    category: FoodCategoryType
    servings: int = Field(gt=0, le=10000)
    preparationTime: str = Field(min_length=2, max_length=150)
    pickupDeadline: datetime
    location: str = Field(min_length=2, max_length=200)
    packagingCondition: str = Field(min_length=2, max_length=300)
    foodImage: str = Field(min_length=1, description="Food image is required for AI-assisted safety screening.")
    packagingImage: str | None = None
    captureToken: str | None = None
    captureMethod: str | None = "live_camera"
    captureLat: float | None = None
    captureLng: float | None = None
    pickupLat: float | None = None
    pickupLng: float | None = None


class DonationFeedback(BaseModel):
    rating: int = Field(ge=1, le=5)
    comments: str | None = None


class ClaimItem(BaseModel):
    id: str
    donationId: str
    receiverUserId: str
    receiverName: str
    receiverOrganisation: str
    receiverLocation: str
    quantity: int
    status: Literal["Accepted", "Collected"]
    acceptedAt: datetime
    collectedAt: datetime | None = None


class ClaimAcceptRequest(BaseModel):
    quantity: int | None = Field(default=None, ge=1, le=10000)


class Donation(BaseModel):
    id: str
    foodName: str
    category: str
    servings: int
    remainingServings: int = 0
    claimedServings: int = 0
    preparationTime: str
    pickupDeadline: datetime
    location: str
    packagingCondition: str
    foodImage: str | None = None
    packagingImage: str | None = None
    donorName: str
    donorOrganisation: str
    priority: PriorityType
    status: DonationStatusType
    createdAt: datetime
    aiConfidence: float | None = None
    predictionMethod: str | None = None
    predictionFeatures: dict[str, Any] | None = None
    imageAnalysis: dict[str, Any] | None = None
    foodVerdict: str | None = None
    isFood: bool | None = None
    matchesDescription: bool | None = None
    detectedFood: str | None = None
    isSpoiled: bool | None = None
    freshnessIndicator: str | None = None
    visualCondition: str | None = None
    visionConfidence: float | None = None
    rejectionReason: str | None = None
    inspectedAt: datetime | None = None
    screeningDisclaimer: str | None = None
    acceptedByName: str | None = None
    acceptedByOrganisation: str | None = None
    acceptedByLocation: str | None = None
    acceptedAt: datetime | None = None
    collectedAt: datetime | None = None
    claims: list[ClaimItem] = []
    feedback: DonationFeedback | None = None
    matchScore: int | None = None
    distanceKm: float | None = None
    # Feature 1: Originality & anti-fraud fields
    imageOriginality: str | None = None
    originalityScore: int | None = None
    captureMethod: str | None = None
    imageSha256: str | None = None
    imagePerceptualHash: str | None = None
    originalityReasons: list[str] = []
    photoTakenAt: str | None = None
    # Feature 2: Geospatial & matching fields
    pickupCoordinates: dict[str, Any] | None = None
    match: dict[str, Any] | None = None


class PublicStats(BaseModel):
    donations: int
    mealsSaved: int
    ngoPartners: int


class Notification(BaseModel):
    id: str
    recipientUserId: str
    recipientRole: str = "ngo"
    type: str = "general"
    title: str
    message: str
    donationId: str | None = None
    read: bool = False
    createdAt: datetime
    # Backward compatibility with existing UI properties
    userId: str | None = None
    isRead: bool | None = None


class MyPickupItem(BaseModel):
    claimId: str
    donationId: str
    foodName: str
    category: str
    servings: int
    remainingServings: int
    claimedQuantity: int
    claimStatus: Literal["Accepted", "Collected"]
    donationStatus: DonationStatusType
    foodImage: str | None = None
    packagingImage: str | None = None
    packagingCondition: str
    location: str
    pickupDeadline: datetime
    priority: PriorityType
    donorName: str
    donorOrganisation: str
    acceptedAt: datetime
    collectedAt: datetime | None = None
    imageAnalysis: dict[str, Any] | None = None
    feedback: DonationFeedback | None = None
    distanceKm: float | None = None


class MonthlyDonation(BaseModel):
    month: str
    count: int

class CategoryCount(BaseModel):
    category: str
    count: int

class DonorStatistics(BaseModel):
    activeDonations: int
    acceptedPickups: int
    completedPickups: int
    highPriorityDonations: int
    mealsSaved: int
    monthlyDonations: list[MonthlyDonation] = []


class NgoStatistics(BaseModel):
    availableDonations: int
    acceptedPickups: int
    completedPickups: int
    highPriorityAvailable: int
    mealsCollected: int
    categoryBreakdown: list[CategoryCount] = []


class AdminStatistics(BaseModel):
    totalUsers: int
    totalDonors: int
    totalNgos: int
    totalDonations: int
    activeDonations: int
    acceptedPickups: int
    completedPickups: int
    totalMealsRecovered: int
    verifiedNgos: int = 0
    pendingNgos: int = 0
    suspendedDonors: int = 0
    monthlyDonations: list[MonthlyDonation] = []
    categoryBreakdown: list[CategoryCount] = []


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialise_database_indexes()
    yield


app = FastAPI(
    title="FoodBridge AI API",
    description="Backend API for surplus food recovery and distribution platform.",
    version="1.1.0",
    lifespan=lifespan,
)


# -----------------------------
# Upload folder setup
# -----------------------------
BASE_DIR = Path(__file__).resolve().parent

# Upload directories
UPLOAD_DIR = BASE_DIR / "uploads"

# Donation image folders
FOOD_UPLOAD_DIR = UPLOAD_DIR / "food"
PACKAGING_UPLOAD_DIR = UPLOAD_DIR / "packaging"

# Receiver organization verification folders
VERIFICATION_UPLOAD_DIR = UPLOAD_DIR / "verification"
CERTIFICATE_UPLOAD_DIR = VERIFICATION_UPLOAD_DIR / "certificates"
GOVERNMENT_ID_UPLOAD_DIR = VERIFICATION_UPLOAD_DIR / "government_ids"
LOGO_UPLOAD_DIR = VERIFICATION_UPLOAD_DIR / "logos"


# Create folders automatically if they don't exist
FOOD_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
PACKAGING_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

CERTIFICATE_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
GOVERNMENT_ID_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
LOGO_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


# Make uploaded files accessible (excluding verification documents)
app.mount(
    "/uploads/food",
    StaticFiles(directory=str(FOOD_UPLOAD_DIR)),
    name="uploads_food",
)
app.mount(
    "/uploads/packaging",
    StaticFiles(directory=str(PACKAGING_UPLOAD_DIR)),
    name="uploads_packaging",
)


# -----------------------------
# CORS setup for local + Render deployment
# -----------------------------
allowed_origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.options("/{full_path:path}")
async def preflight_handler(full_path: str):
    return {"message": "CORS preflight successful"}


bearer_scheme = HTTPBearer(auto_error=False)


def get_current_datetime_for(deadline: datetime) -> datetime:
    if deadline.tzinfo is not None and deadline.utcoffset() is not None:
        return datetime.now(deadline.tzinfo)

    return datetime.now()


def normalise_priority(priority: str | None) -> PriorityType:
    if priority == "High":
        return "High"

    if priority == "Medium":
        return "Medium"

    if priority == "Low":
        return "Low"

    return "Medium"


def document_to_user(document: dict[str, Any]) -> UserPublic:
    return UserPublic(
        id=str(document["_id"]),
        fullName=document["fullName"],
        email=document["email"],
        organisation=document["organisation"],
        role=document["role"],
        organizationType=document.get("organizationType"),
        description=document.get("description"),
        capacity=document.get("capacity"),
        operatingHours=document.get("operatingHours"),
        acceptedFoodTypes=document.get("acceptedFoodTypes", []),
        verificationStatus=document.get("verificationStatus", "verified"),
        registrationCertificate=document.get("registrationCertificate"),
        governmentId=document.get("governmentId"),
        organizationLogo=document.get("organizationLogo"),
        verifiedAt=document.get("verifiedAt"),
        verifiedBy=document.get("verifiedBy"),
        rejectionReason=document.get("rejectionReason"),
        trustScore=document.get("trustScore", 100),
        accountStatus=document.get("accountStatus", "active"),
        location=document["location"],
        contactNumber=document["contactNumber"],
        createdAt=document["createdAt"],
    )


def document_to_notification(document: dict[str, Any]) -> Notification:
    rec_id = document.get("recipientUserId") or document.get("userId") or ""
    is_read = document.get("read") if "read" in document else document.get("isRead", False)
    return Notification(
        id=str(document["_id"]),
        recipientUserId=rec_id,
        recipientRole=document.get("recipientRole", "ngo"),
        type=document.get("type", "general"),
        title=document.get("title", ""),
        message=document.get("message", ""),
        donationId=document.get("donationId"),
        read=bool(is_read),
        createdAt=document.get("createdAt", datetime.now()),
        userId=rec_id,
        isRead=bool(is_read),
    )


def get_eligible_receiver_user_ids() -> list[str]:
    """Single eligibility rule: role 'ngo' whose verificationStatus is not 'rejected'."""
    try:
        docs = users_collection.find(
            {"role": "ngo", "verificationStatus": {"$ne": "rejected"}},
            {"_id": 1}
        )
        return [str(d["_id"]) for d in docs]
    except Exception as e:
        print(f"[Eligibility] Failed to fetch eligible receivers: {e}")
        return []


def dispatch_notifications(notification_list: list[dict[str, Any]]) -> None:
    """Safely batch-inserts in-app notifications. Never raises or breaks the caller."""
    if not notification_list:
        return
    try:
        now = datetime.now()
        for item in notification_list:
            if "createdAt" not in item:
                item["createdAt"] = now
            if "read" not in item:
                item["read"] = False
            if "recipientUserId" in item and "userId" not in item:
                item["userId"] = item["recipientUserId"]
            if "read" in item and "isRead" not in item:
                item["isRead"] = item["read"]
        notifications_collection.insert_many(notification_list)
    except Exception as e:
        print(f"[Notifications] Error inserting notifications: {e}")


def create_notification(user_id: str, title: str, message: str, donation_id: str | None = None, notif_type: str = "general") -> None:
    dispatch_notifications([{
        "recipientUserId": user_id,
        "recipientRole": "user",
        "type": notif_type,
        "title": title,
        "message": message,
        "donationId": donation_id,
    }])


def document_to_donation(
    document: dict,
    include_claims: bool = True,
    is_admin: bool = False,
) -> Donation:
    doc_id = str(document["_id"])
    servings = document.get("servings", 0)
    claimed_servings = document.get("claimedServings", 0)
    remaining_servings = document.get("remainingServings")
    if remaining_servings is None:
        remaining_servings = max(0, servings - claimed_servings)

    claims_list: list[ClaimItem] = []
    if include_claims:
        try:
            claim_docs = claims_collection.find({"donationId": doc_id}).sort("acceptedAt", 1)
            for c in claim_docs:
                claims_list.append(ClaimItem(
                    id=str(c["_id"]),
                    donationId=str(c.get("donationId", doc_id)),
                    receiverUserId=str(c.get("receiverUserId", "")),
                    receiverName=c.get("receiverName", "Receiver"),
                    receiverOrganisation=c.get("receiverOrganisation", "Organization"),
                    receiverLocation=c.get("receiverLocation", ""),
                    quantity=c.get("quantity", 0),
                    status=c.get("status", "Accepted"),
                    acceptedAt=c.get("acceptedAt", datetime.now()),
                    collectedAt=c.get("collectedAt"),
                ))
        except Exception:
            pass

    # Privacy constraint (Feature 3): prediction details hidden from non-admin users
    ai_confidence = document.get("aiConfidence") if is_admin else None
    prediction_method = document.get("predictionMethod") if is_admin else None
    prediction_features = document.get("predictionFeatures") if is_admin else None

    return Donation(
        id=doc_id,
        foodName=document["foodName"],
        category=document["category"],
        servings=servings,
        remainingServings=remaining_servings,
        claimedServings=claimed_servings,
        preparationTime=document["preparationTime"],
        pickupDeadline=document["pickupDeadline"],
        location=document["location"],
        packagingCondition=document["packagingCondition"],
        foodImage=document.get("foodImage"),
        packagingImage=document.get("packagingImage"),
        donorName=document.get("donorName", "Food Donor"),
        donorOrganisation=document.get(
            "donorOrganisation",
            "Registered Food Donor",
        ),
        priority=document["priority"],
        status=document["status"],
        createdAt=document["createdAt"],
        aiConfidence=ai_confidence,
        predictionMethod=prediction_method,
        predictionFeatures=prediction_features,
        imageAnalysis=document.get("imageAnalysis"),
        foodVerdict=document.get("foodVerdict"),
        isFood=document.get("isFood"),
        matchesDescription=document.get("matchesDescription"),
        detectedFood=document.get("detectedFood"),
        isSpoiled=document.get("isSpoiled"),
        freshnessIndicator=document.get("freshnessIndicator"),
        visualCondition=document.get("visualCondition"),
        visionConfidence=document.get("visionConfidence"),
        rejectionReason=document.get("rejectionReason"),
        inspectedAt=document.get("inspectedAt"),
        screeningDisclaimer=document.get("screeningDisclaimer", FSSAI_DISCLAIMER),
        acceptedByName=document.get("acceptedByName"),
        acceptedByOrganisation=document.get("acceptedByOrganisation"),
        acceptedByLocation=document.get("acceptedByLocation"),
        acceptedAt=document.get("acceptedAt"),
        collectedAt=document.get("collectedAt"),
        claims=claims_list,
        feedback=document.get("feedback"),
        distanceKm=document.get("distanceKm"),
        imageOriginality=document.get("imageOriginality"),
        originalityScore=document.get("originalityScore"),
        captureMethod=document.get("captureMethod"),
        imageSha256=document.get("imageSha256"),
        imagePerceptualHash=document.get("imagePerceptualHash"),
        originalityReasons=document.get("originalityReasons", []),
        photoTakenAt=document.get("photoTakenAt"),
        pickupCoordinates=document.get("pickupCoordinates"),
        match=document.get("match"),
    )


def calculate_priority(category: str, pickup_deadline: datetime) -> PriorityType:
    minutes_remaining = (
        pickup_deadline - get_current_datetime_for(pickup_deadline)
    ).total_seconds() / 60

    if category == "Cooked Meal" or minutes_remaining <= 90:
        return "High"

    if category in ["Bakery", "Fruits", "Vegetables", "Dairy"] or minutes_remaining <= 240:
        return "Medium"

    return "Low"


def generate_ai_priority_payload(donation_data: DonationCreate) -> dict[str, Any]:
    try:
        prediction_result = predict_food_priority(
            category=donation_data.category,
            servings=donation_data.servings,
            preparation_time=donation_data.preparationTime,
            pickup_deadline=donation_data.pickupDeadline,
            packaging_condition=donation_data.packagingCondition,
        )

        predicted_priority = normalise_priority(
            str(prediction_result.get("priority"))
        )

        raw_confidence = float(prediction_result.get("confidence", 0))

        if raw_confidence <= 1:
            confidence_percentage = round(raw_confidence * 100, 2)
        else:
            confidence_percentage = round(raw_confidence, 2)

        return {
            "priority": predicted_priority,
            "aiConfidence": confidence_percentage,
            "predictionMethod": prediction_result.get("method", "ml_model"),
            "predictionFeatures": prediction_result.get("features", {}),
        }

    except Exception:
        fallback_priority = calculate_priority(
            donation_data.category,
            donation_data.pickupDeadline,
        )

        return {
            "priority": fallback_priority,
            "aiConfidence": None,
            "predictionMethod": "rule_fallback_after_ml_error",
            "predictionFeatures": {
                "category": donation_data.category,
                "servings": donation_data.servings,
                "preparationTime": donation_data.preparationTime,
                "pickupDeadline": donation_data.pickupDeadline.isoformat(),
                "packagingCondition": donation_data.packagingCondition,
            },
        }


def validate_donation_id(donation_id: str) -> ObjectId:
    if not ObjectId.is_valid(donation_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid donation ID.",
        )

    return ObjectId(donation_id)


def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
) -> UserPublic:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )

    try:
        token_payload = decode_access_token(credentials.credentials)
        user_id = token_payload.get("sub")

        if not user_id or not ObjectId.is_valid(user_id):
            raise ValueError("Invalid user ID.")

    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token.",
        ) from error

    try:
        user_document = users_collection.find_one(
            {"_id": ObjectId(user_id)}
        )

        if user_document is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account not found.",
            )

        return document_to_user(user_document)

    except PyMongoError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to verify the signed-in user.",
        ) from error


def require_role(
    current_user: UserPublic,
    required_role: Literal["donor", "ngo", "admin"],
) -> None:
    if current_user.role != required_role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"This action requires a {required_role} account.",
        )


def require_verified_ngo(current_user: UserPublic) -> None:
    require_role(current_user, "ngo")
    if current_user.verificationStatus != "verified":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your organization is currently under verification. Please wait for administrator approval.",
        )


@app.get("/")
def read_root():
    return {
        "application": "FoodBridge AI API",
        "message": "Backend server is running successfully.",
        "version": "1.1.0",
        "aiPriorityPrediction": "enabled",
        "imageUpload": "enabled",
    }


@app.get("/api/public/stats", response_model=PublicStats)
def get_public_stats():
    total_donations = donations_collection.count_documents({})
    # Calculate meals saved from Collected claims
    claim_aggregation = list(claims_collection.aggregate([
        {"$match": {"status": "Collected"}},
        {"$group": {"_id": None, "total": {"$sum": "$quantity"}}}
    ]))
    if claim_aggregation and claim_aggregation[0]["total"] > 0:
        meals_saved = claim_aggregation[0]["total"]
    else:
        completed = donations_collection.find({"status": "Collected"})
        meals_saved = sum(doc.get("servings", 0) for doc in completed)

    ngo_partners = users_collection.count_documents({"role": "ngo", "verificationStatus": "verified"})
    
    return PublicStats(
        donations=total_donations,
        mealsSaved=meals_saved,
        ngoPartners=ngo_partners,
    )


@app.get("/api/health")
def health_check():
    database_connected = check_database_connection()

    return {
        "status": "healthy" if database_connected else "database disconnected",
        "service": "FoodBridge AI Backend",
        "database": "connected" if database_connected else "not connected",
        "aiPriorityPrediction": "enabled",
        "imageUpload": "enabled",
    }


@app.post("/api/upload-image")
async def upload_image(
    file: UploadFile = File(...),
    image_type: str = Form("food"),
):
    if image_type not in ["food", "packaging"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid image type. Use food or packaging.",
        )

    allowed_content_types = {
        "image/jpeg",
        "image/jpg",
        "image/png",
        "image/webp",
    }

    if file.content_type not in allowed_content_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only JPG, JPEG, PNG and WEBP image files are allowed.",
        )

    original_filename = file.filename or ""
    extension = original_filename.split(".")[-1].lower()

    if extension not in ["jpg", "jpeg", "png", "webp"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid image extension. Use jpg, jpeg, png or webp.",
        )

    file_content = await file.read()

    max_file_size = 5 * 1024 * 1024

    if len(file_content) > max_file_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Image size must be less than 5 MB.",
        )

    filename = f"{uuid.uuid4()}.{extension}"

    if image_type == "food":
        save_path = FOOD_UPLOAD_DIR / filename
        image_url = f"/uploads/food/{filename}"
    else:
        save_path = PACKAGING_UPLOAD_DIR / filename
        image_url = f"/uploads/packaging/{filename}"

    with open(save_path, "wb") as buffer:
        buffer.write(file_content)

    return {
        "message": "Image uploaded successfully.",
        "imageUrl": image_url,
    }


@app.post("/api/donations/capture-session")
def get_camera_capture_session(
    current_user: Annotated[UserPublic, Depends(get_current_user)],
):
    require_role(current_user, "donor")
    token = create_capture_session_token(current_user.id)
    return {
        "captureToken": token,
        "expiresInMinutes": 10,
        "issuedAt": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/api/donations/verify-image")
async def verify_donation_image(
    current_user: Annotated[UserPublic, Depends(get_current_user)],
    file: UploadFile = File(...),
    foodName: str = Form(""),
    category: str = Form(""),
    captureToken: str | None = Form(None),
    captureMethod: str | None = Form("live_camera"),
    captureLat: float | None = Form(None),
    captureLng: float | None = Form(None),
):
    require_role(current_user, "donor")

    allowed_content_types = {
        "image/jpeg",
        "image/jpg",
        "image/png",
        "image/webp",
    }
    if file.content_type not in allowed_content_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only JPG, JPEG, PNG and WEBP image files are allowed.",
        )

    file_content = await file.read()
    if len(file_content) > 5 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Image size must be less than 5 MB.",
        )

    # Run inspection in worker thread so event loop is never blocked
    analysis = await asyncio.to_thread(
        analyse_food_image,
        image_bytes=file_content,
        mime_type=file.content_type or "image/jpeg",
        food_name=foodName,
        category=category,
    )

    return analysis


@app.post("/api/users/me/verification-documents")
async def upload_verification_document(
    current_user: Annotated[UserPublic, Depends(get_current_user)],
    file: UploadFile = File(...),
    document_type: str = Form(...),
):
    require_role(current_user, "ngo")

    if document_type not in ["registrationCertificate", "governmentId", "organizationLogo"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid document type.",
        )

    # Validate file type
    allowed_content_types = {
        "image/jpeg",
        "image/jpg",
        "image/png",
        "image/webp",
        "application/pdf",
    }
    
    if document_type == "organizationLogo" and file.content_type == "application/pdf":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Logo cannot be a PDF.",
        )

    if file.content_type not in allowed_content_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF, JPG, JPEG, PNG and WEBP files are allowed.",
        )

    original_filename = file.filename or ""
    extension = original_filename.split(".")[-1].lower()

    if extension not in ["jpg", "jpeg", "png", "webp", "pdf"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file extension.",
        )

    file_content = await file.read()
    max_file_size = 5 * 1024 * 1024

    if len(file_content) > max_file_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size must be less than 5 MB.",
        )

    filename = f"{uuid.uuid4()}.{extension}"

    if document_type == "registrationCertificate":
        save_path = CERTIFICATE_UPLOAD_DIR / filename
        db_path = f"certificates/{filename}"
    elif document_type == "governmentId":
        save_path = GOVERNMENT_ID_UPLOAD_DIR / filename
        db_path = f"government_ids/{filename}"
    else:
        save_path = LOGO_UPLOAD_DIR / filename
        db_path = f"logos/{filename}"

    with open(save_path, "wb") as buffer:
        buffer.write(file_content)

    # Update database
    try:
        users_collection.update_one(
            {"_id": ObjectId(current_user.id)},
            {"$set": {document_type: db_path}}
        )
    except PyMongoError as error:
        # Cleanup file if DB update fails
        if save_path.exists():
            save_path.unlink()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update database.",
        ) from error

    return {
        "message": "Document uploaded successfully.",
        "documentPath": db_path,
    }


@app.get("/api/verification-documents/{document_type}/{filename}")
def get_verification_document(
    document_type: str,
    filename: str,
    current_user: Annotated[UserPublic, Depends(get_current_user)],
):
    if document_type not in ["certificates", "government_ids", "logos"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid document type.",
        )

    db_path = f"{document_type}/{filename}"

    # Allow access if admin
    is_authorized = False
    if current_user.role == "admin":
        is_authorized = True
    else:
        # Check if the file belongs to the current user
        if document_type == "certificates":
            field_name = "registrationCertificate"
        elif document_type == "government_ids":
            field_name = "governmentId"
        else:
            field_name = "organizationLogo"
        
        user_doc_path = getattr(current_user, field_name, None)
        if user_doc_path == db_path:
            is_authorized = True

    if not is_authorized:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view this document.",
        )

    if document_type == "certificates":
        file_path = CERTIFICATE_UPLOAD_DIR / filename
    elif document_type == "government_ids":
        file_path = GOVERNMENT_ID_UPLOAD_DIR / filename
    else:
        file_path = LOGO_UPLOAD_DIR / filename

    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    return FileResponse(path=file_path)


@app.post(
    "/api/auth/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_user(registration_data: UserRegister):
    if not registration_data.safetyAgreement:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You must accept the food safety responsibility statement.",
        )

    user_document = {
    "fullName": registration_data.fullName.strip(),
    "email": str(registration_data.email).lower(),
    "organisation": registration_data.organisation.strip(),
    "role": registration_data.role,

    # Receiver profile
    "organizationType": registration_data.organizationType,
    "description": registration_data.description,
    "capacity": registration_data.capacity,
    "operatingHours": registration_data.operatingHours,
    "acceptedFoodTypes": registration_data.acceptedFoodTypes,

    # Verification fields
    "verificationStatus": (
        "verified"
        if registration_data.role == "donor"
        else "pending"
    ),

    "registrationCertificate": None,

    "governmentId": None,

    "organizationLogo": None,

        "verifiedAt": None,

        "verifiedBy": None,

        # Common fields
        "location": registration_data.location.strip(),
        "locationCoordinates": (
            format_geojson_point(loc_coords[0], loc_coords[1])
            if (loc_coords := geocode_address(registration_data.location.strip()))
            else None
        ),
        "contactNumber": registration_data.contactNumber.strip(),
        "passwordHash": hash_password(registration_data.password),
        "createdAt": datetime.now(),
    }

    try:
        insert_result = users_collection.insert_one(user_document)

        created_document = users_collection.find_one(
            {"_id": insert_result.inserted_id}
        )

        if created_document is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Account was created but could not be retrieved.",
            )

        public_user = document_to_user(created_document)

        if registration_data.role == "ngo":
            admins = users_collection.find({"role": "admin"}, {"_id": 1})
            for admin in admins:
                create_notification(str(admin["_id"]), "New NGO Registration", f"{registration_data.organisation} has registered and is pending verification.")

        return AuthResponse(
            accessToken=create_access_token(
                public_user.id,
                public_user.role,
            ),
            tokenType="bearer",
            user=public_user,
        )

    except DuplicateKeyError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email address already exists.",
        ) from error

    except PyMongoError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to create account in MongoDB.",
        ) from error


@app.post("/api/auth/login", response_model=AuthResponse)
def login_user(login_data: UserLogin):
    try:
        user_document = users_collection.find_one(
            {"email": str(login_data.email).lower()}
        )

        if user_document is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password.",
            )

        if not verify_password(
            login_data.password,
            user_document["passwordHash"],
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password.",
            )
            
        if user_document.get("accountStatus") == "suspended":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your account has been suspended.",
            )

        if user_document["role"] != login_data.role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="The selected account role is incorrect.",
            )

        public_user = document_to_user(user_document)

        return AuthResponse(
            accessToken=create_access_token(
                public_user.id,
                public_user.role,
            ),
            tokenType="bearer",
            user=public_user,
        )

    except HTTPException:
        raise

    except PyMongoError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to login using MongoDB.",
        ) from error


@app.get("/api/auth/me", response_model=UserPublic)
def get_logged_in_user(
    current_user: Annotated[UserPublic, Depends(get_current_user)],
):
    return current_user


@app.patch("/api/users/me/location", response_model=UserPublic)
def update_user_location(
    loc_data: UserLocationUpdate,
    current_user: Annotated[UserPublic, Depends(get_current_user)],
):
    coords = None
    if loc_data.latitude is not None and loc_data.longitude is not None:
        coords = (float(loc_data.latitude), float(loc_data.longitude))
    else:
        coords = geocode_address(loc_data.location)

    update_fields: dict[str, Any] = {"location": loc_data.location.strip()}
    if coords:
        update_fields["locationCoordinates"] = format_geojson_point(coords[0], coords[1])

    users_collection.update_one(
        {"_id": ObjectId(current_user.id)},
        {"$set": update_fields},
    )
    updated_user = users_collection.find_one({"_id": ObjectId(current_user.id)})
    if not updated_user:
        raise HTTPException(status_code=404, detail="User not found.")
    return document_to_user(updated_user)



@app.get("/api/donations/my", response_model=list[Donation])
def get_my_donations(
    current_user: Annotated[UserPublic, Depends(get_current_user)],
):
    require_role(current_user, "donor")

    try:
        documents = donations_collection.find(
            {"donorUserId": current_user.id}
        ).sort("createdAt", DESCENDING)

        return [document_to_donation(document) for document in documents]

    except PyMongoError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to load your donations from MongoDB.",
        ) from error


@app.get("/api/donations/available", response_model=list[Donation])
def get_available_donations(
    current_user: Annotated[UserPublic, Depends(get_current_user)],
    sort: str = "match",
):
    require_verified_ngo(current_user)

    try:
        user_doc = users_collection.find_one({"_id": ObjectId(current_user.id)})
        ngo_coords = None
        if user_doc and "locationCoordinates" in user_doc and user_doc["locationCoordinates"]:
            c_arr = user_doc["locationCoordinates"].get("coordinates")
            if c_arr and len(c_arr) >= 2:
                ngo_coords = (float(c_arr[1]), float(c_arr[0]))  # (lat, lng)
        if not ngo_coords and user_doc and user_doc.get("location"):
            ngo_coords = geocode_address(user_doc["location"])

        documents = list(donations_collection.find(
            {
                "status": {"$in": ["Active", "Partially Accepted"]},
                "$or": [
                    {"remainingServings": {"$gt": 0}},
                    {"remainingServings": {"$exists": False}},
                ],
            }
        ).sort("createdAt", DESCENDING))

        donations: list[Donation] = []
        for document in documents:
            don_obj = document_to_donation(document)

            don_coords = None
            if "pickupCoordinates" in document and document["pickupCoordinates"]:
                p_arr = document["pickupCoordinates"].get("coordinates")
                if p_arr and len(p_arr) >= 2:
                    don_coords = (float(p_arr[1]), float(p_arr[0]))  # (lat, lng)
            if not don_coords and document.get("location"):
                don_coords = geocode_address(document["location"])

            if ngo_coords and don_coords:
                match_metrics = calculate_match_metrics(
                    receiver_lat=ngo_coords[0],
                    receiver_lng=ngo_coords[1],
                    donation_lat=don_coords[0],
                    donation_lng=don_coords[1],
                    pickup_deadline=document.get("pickupDeadline"),
                )
                don_obj.match = match_metrics
                don_obj.matchScore = match_metrics["matchPercent"]
                don_obj.distanceKm = match_metrics["distanceKm"]
            else:
                don_obj.match = None
                don_obj.distanceKm = None

            donations.append(don_obj)

        priority_ranks = {"High": 3, "Medium": 2, "Low": 1}

        if sort == "match":
            donations.sort(
                key=lambda d: (
                    1 if (d.match and d.match.get("feasible", True)) else 0,
                    d.match.get("matchPercent", 0) if d.match else 0,
                    priority_ranks.get(d.priority, 0),
                ),
                reverse=True,
            )
        elif sort == "distance":
            donations.sort(
                key=lambda d: d.distanceKm if d.distanceKm is not None else float("inf")
            )
        elif sort == "priority":
            donations.sort(
                key=lambda d: priority_ranks.get(d.priority, 0),
                reverse=True,
            )
        elif sort == "newest":
            donations.sort(
                key=lambda d: d.createdAt,
                reverse=True,
            )

        return donations

    except PyMongoError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to load available donations from MongoDB.",
        ) from error


@app.get("/api/donations/recommended", response_model=list[Donation])
def get_recommended_donations(
    current_user: Annotated[UserPublic, Depends(get_current_user)],
):
    require_verified_ngo(current_user)

    try:
        user_doc = users_collection.find_one({"_id": ObjectId(current_user.id)})
        if not user_doc:
            return []

        ngo_capacity = user_doc.get("capacity")
        accepted_food_types = user_doc.get("acceptedFoodTypes", [])
        ngo_location = user_doc.get("location", "")
        ngo_coords = get_coordinates(ngo_location)

        documents = list(donations_collection.find({
            "status": {"$in": ["Active", "Partially Accepted"]},
            "$or": [
                {"remainingServings": {"$gt": 0}},
                {"remainingServings": {"$exists": False}},
            ],
        }))
        scored_donations = []

        for doc in documents:
            remaining = doc.get("remainingServings", doc.get("servings", 0))
            if ngo_capacity and remaining > ngo_capacity:
                continue

            score = 0
            
            # Food Type Match (+40)
            if doc.get("category") in accepted_food_types:
                score += 40

            # Priority (+30 for High, +15 for Medium, +5 for Low)
            priority = doc.get("priority", "Medium")
            if priority == "High":
                score += 30
            elif priority == "Medium":
                score += 15
            else:
                score += 5

            # Location (+20) - Real Geospatial matching using OpenStreetMap API
            donor_location = doc.get("location", "")
            donor_coords = get_coordinates(donor_location)
            
            if ngo_coords and donor_coords:
                distance_km = calculate_haversine_distance(ngo_coords[0], ngo_coords[1], donor_coords[0], donor_coords[1])
                doc["distanceKm"] = round(distance_km, 1)
                
                # Assign points based on physical distance (closer = better)
                if distance_km <= 5.0:
                    score += 20
                elif distance_km <= 15.0:
                    score += 15
                elif distance_km <= 30.0:
                    score += 10
                else:
                    score += 5
            else:
                # Fallback to legacy text matching if geocoding fails
                donor_loc_lower = donor_location.lower()
                ngo_loc_lower = ngo_location.lower()
                if ngo_loc_lower and (ngo_loc_lower in donor_loc_lower or donor_loc_lower in ngo_loc_lower):
                    score += 20
                else:
                    ngo_words = set(ngo_loc_lower.replace(",", " ").split())
                    donor_words = set(donor_loc_lower.replace(",", " ").split())
                    if ngo_words & donor_words:
                        score += 10

            # Urgency (+10)
            deadline = doc.get("pickupDeadline")
            if deadline:
                if deadline.tzinfo is None:
                    deadline = deadline.replace(tzinfo=timezone.utc)
                now = datetime.now(timezone.utc)
                hours_remaining = (deadline - now).total_seconds() / 3600
                if hours_remaining <= 2:
                    score += 10
                elif hours_remaining <= 6:
                    score += 5

            donation = document_to_donation(doc)
            donation.matchScore = score
            scored_donations.append((score, donation))

        scored_donations.sort(key=lambda x: x[0], reverse=True)
        return [donation for _, donation in scored_donations[:3]]

    except PyMongoError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to load recommended donations.",
        ) from error


@app.get("/api/donations/my-pickups", response_model=list[Donation])
def get_my_pickups(
    current_user: Annotated[UserPublic, Depends(get_current_user)],
):
    require_role(current_user, "ngo")

    try:
        results: list[Donation] = []
        user_claims = list(claims_collection.find(
            {"receiverUserId": current_user.id}
        ).sort("acceptedAt", DESCENDING))

        claimed_donation_ids = set()

        for claim in user_claims:
            don_id = claim.get("donationId")
            if not don_id or not ObjectId.is_valid(don_id):
                continue
            claimed_donation_ids.add(don_id)
            don_doc = donations_collection.find_one({"_id": ObjectId(don_id)})
            if don_doc:
                donation_obj = document_to_donation(don_doc)
                donation_obj.status = claim.get("status", "Accepted")
                donation_obj.claimedServings = claim.get("quantity", 0)
                if claim.get("acceptedAt"):
                    donation_obj.acceptedAt = claim["acceptedAt"]
                if claim.get("collectedAt"):
                    donation_obj.collectedAt = claim["collectedAt"]
                results.append(donation_obj)

        # Include legacy donations if any where acceptedByUserId == current_user.id without claim doc
        valid_oids = [ObjectId(did) for did in claimed_donation_ids if ObjectId.is_valid(did)]
        legacy_donations = donations_collection.find(
            {
                "acceptedByUserId": current_user.id,
                "_id": {"$nin": valid_oids}
            }
        ).sort("createdAt", DESCENDING)

        for leg in legacy_donations:
            results.append(document_to_donation(leg))

        return results

    except PyMongoError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to load your pickup requests from MongoDB.",
        ) from error


@app.post(
    "/api/donations",
    response_model=Donation,
    status_code=status.HTTP_201_CREATED,
)
def create_donation(
    donation_data: DonationCreate,
    current_user: Annotated[UserPublic, Depends(get_current_user)],
):
    require_role(current_user, "donor")

    if current_user.accountStatus == "suspended":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been suspended due to low trust score. You cannot create new donations.",
        )

    if donation_data.pickupDeadline <= get_current_datetime_for(
        donation_data.pickupDeadline
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Pickup deadline must be later than the current time.",
        )

    # Food image is required
    if not donation_data.foodImage:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Food image is required for AI-assisted safety screening.",
        )

    # 1. Server-side validation of the stored image bytes
    food_img_path = donation_data.foodImage
    if food_img_path.startswith("/uploads/food/"):
        filename = food_img_path.replace("/uploads/food/", "")
        local_image_path = FOOD_UPLOAD_DIR / filename
    else:
        filename = Path(food_img_path).name
        local_image_path = FOOD_UPLOAD_DIR / filename

    if not local_image_path.exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded food image file could not be found on server. Please upload again.",
        )

    with open(local_image_path, "rb") as f:
        food_image_bytes = f.read()

    # Run AI inspection
    image_analysis_result = analyse_food_image(
        image_bytes=food_image_bytes,
        mime_type="image/jpeg",
        food_name=donation_data.foodName,
        category=donation_data.category,
    )

    # Fail closed: block if Rejected or Unverified
    if image_analysis_result.get("verdict") in ["Rejected", "Unverified"]:
        rejection_reason = (
            image_analysis_result.get("rejectionReason")
            or f"AI food screening verdict: {image_analysis_result.get('verdict')}"
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=rejection_reason,
        )

    # Geocode pickup coordinates
    pickup_lat: float | None = None
    pickup_lng: float | None = None
    if donation_data.pickupLat is not None and donation_data.pickupLng is not None:
        pickup_lat = float(donation_data.pickupLat)
        pickup_lng = float(donation_data.pickupLng)
    else:
        coords = geocode_address(donation_data.location)
        if coords:
            pickup_lat, pickup_lng = coords

    # Evaluate image originality & anti-fraud cues
    gemini_cues = {
        "hasWatermarkOrLogo": image_analysis_result.get("hasWatermarkOrLogo", False),
        "looksLikeStockOrWebImage": image_analysis_result.get("looksLikeStockOrWebImage", False),
        "looksLikeScreenPhoto": image_analysis_result.get("looksLikeScreenPhoto", False),
        "looksProfessionallyStaged": image_analysis_result.get("looksProfessionallyStaged", False),
    }

    originality_result = evaluate_image_originality(
        image_bytes=food_image_bytes,
        user_id=current_user.id,
        capture_method=donation_data.captureMethod or "live_camera",
        capture_token=donation_data.captureToken,
        capture_lat=donation_data.captureLat,
        capture_lng=donation_data.captureLng,
        pickup_lat=pickup_lat,
        pickup_lng=pickup_lng,
        gemini_cues=gemini_cues,
    )

    if originality_result.get("imageOriginality") == "Likely Internet Image":
        reasons_str = "; ".join(originality_result.get("originalityReasons", []))
        new_score = max(0, current_user.trustScore - 10)
        new_status = "suspended" if new_score < 40 else "active"
        users_collection.update_one(
            {"_id": ObjectId(current_user.id)},
            {"$set": {"trustScore": new_score, "accountStatus": new_status}},
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Image rejected by authenticity screening: This image appears to be sourced from the internet, "
                "a stock photo library, another screen, or a duplicate upload. "
                f"Reasons: {reasons_str}. "
                "Please capture a live, original photograph of the actual food."
            ),
        )

    # Packaging image check (optional, lighter check, does not block)
    packaging_analysis = None
    if donation_data.packagingImage:
        pkg_path_str = donation_data.packagingImage
        pkg_filename = (
            pkg_path_str.replace("/uploads/packaging/", "")
            if pkg_path_str.startswith("/uploads/packaging/")
            else Path(pkg_path_str).name
        )
        local_pkg_path = PACKAGING_UPLOAD_DIR / pkg_filename
        if local_pkg_path.exists():
            with open(local_pkg_path, "rb") as pf:
                packaging_analysis = check_packaging_image(pf.read(), "image/jpeg")

    prediction_payload = generate_ai_priority_payload(donation_data)

    donation_document = {
        **donation_data.model_dump(),
        "donorUserId": current_user.id,
        "donorName": current_user.fullName,
        "donorOrganisation": current_user.organisation,
        "priority": prediction_payload["priority"],
        "aiConfidence": prediction_payload["aiConfidence"],
        "predictionMethod": prediction_payload["predictionMethod"],
        "predictionFeatures": prediction_payload["predictionFeatures"],
        "servings": donation_data.servings,
        "remainingServings": donation_data.servings,
        "claimedServings": 0,
        "foodVerdict": image_analysis_result.get("verdict", "Accepted"),
        "isFood": image_analysis_result.get("isFood", True),
        "matchesDescription": image_analysis_result.get("matchesDescription", True),
        "detectedFood": image_analysis_result.get("detectedFood", donation_data.foodName),
        "isSpoiled": image_analysis_result.get("isSpoiled", False),
        "freshnessIndicator": image_analysis_result.get("freshness", "Acceptable"),
        "visualCondition": image_analysis_result.get("visualCondition", "Good"),
        "visionConfidence": image_analysis_result.get("confidence", 1.0),
        "rejectionReason": image_analysis_result.get("rejectionReason"),
        "inspectedAt": datetime.now(),
        "screeningDisclaimer": image_analysis_result.get("screeningDisclaimer", FSSAI_DISCLAIMER),
        "imageAnalysis": image_analysis_result,
        "packagingAnalysis": packaging_analysis,
        "imageOriginality": originality_result.get("imageOriginality", "Likely Original"),
        "originalityScore": originality_result.get("originalityScore"),
        "captureMethod": donation_data.captureMethod or "live_camera",
        "imageSha256": originality_result.get("imageSha256"),
        "imagePerceptualHash": originality_result.get("imagePerceptualHash"),
        "originalityReasons": originality_result.get("originalityReasons", []),
        "photoTakenAt": originality_result.get("photoTakenAt"),
        "pickupCoordinates": (
            format_geojson_point(pickup_lat, pickup_lng)
            if (pickup_lat is not None and pickup_lng is not None)
            else None
        ),
        "status": "Active",
        "createdAt": datetime.now(),
        "acceptedByUserId": None,
        "acceptedByName": None,
        "acceptedByOrganisation": None,
        "acceptedByLocation": None,
        "acceptedAt": None,
        "collectedAt": None,
    }

    try:
        insert_result = donations_collection.insert_one(donation_document)

        created_document = donations_collection.find_one(
            {"_id": insert_result.inserted_id}
        )

        if created_document is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Donation was created but could not be retrieved.",
            )

        # Notify eligible receiver organizations with physical distance
        notify_radius_km = float(os.getenv("NOTIFY_RADIUS_KM", "25.0"))
        pickup_time_str = donation_data.pickupDeadline.strftime("%d %b, %I:%M %p")
        eligible_receivers = list(users_collection.find(
            {"role": "ngo", "verificationStatus": {"$ne": "rejected"}}
        ))

        notification_items = []
        for receiver in eligible_receivers:
            rec_id = str(receiver["_id"])
            rec_coords = None
            if "locationCoordinates" in receiver and receiver["locationCoordinates"]:
                c_arr = receiver["locationCoordinates"].get("coordinates")
                if c_arr and len(c_arr) >= 2:
                    rec_coords = (float(c_arr[1]), float(c_arr[0]))
            if not rec_coords and receiver.get("location"):
                rec_coords = geocode_address(receiver["location"])

            dist_km = None
            if rec_coords and pickup_lat is not None and pickup_lng is not None:
                dist_km = calculate_haversine_distance(
                    rec_coords[0], rec_coords[1], pickup_lat, pickup_lng
                )
                if notify_radius_km > 0 and dist_km > notify_radius_km:
                    continue

            dist_text = f" ({round(dist_km, 1)} km away)" if dist_km is not None else ""
            notification_items.append({
                "recipientUserId": rec_id,
                "recipientRole": "ngo",
                "type": "new_donation",
                "title": "New Food Available",
                "message": (
                    f"New food available: {donation_data.servings} servings of {donation_data.foodName} "
                    f"({prediction_payload['priority']} priority) at {donation_data.location}{dist_text}. "
                    f"Pickup before {pickup_time_str}."
                ),
                "donationId": str(insert_result.inserted_id),
            })

        dispatch_notifications(notification_items)

        return document_to_donation(created_document)

    except HTTPException:
        raise
    except PyMongoError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to save donation in MongoDB.",
        ) from error


@app.patch(
    "/api/donations/{donation_id}/accept",
    response_model=Donation,
)
def accept_donation(
    donation_id: str,
    current_user: Annotated[UserPublic, Depends(get_current_user)],
    claim_request: ClaimAcceptRequest | None = None,
):
    require_verified_ngo(current_user)
    object_id = validate_donation_id(donation_id)

    try:
        existing_doc = donations_collection.find_one({"_id": object_id})
        if existing_doc is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Donation not found.",
            )

        if existing_doc.get("status") not in ["Active", "Partially Accepted"]:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This donation is no longer available for acceptance.",
            )

        servings = existing_doc.get("servings", 0)
        claimed_servings = existing_doc.get("claimedServings", 0)
        remaining_servings = existing_doc.get("remainingServings")
        if remaining_servings is None:
            remaining_servings = max(0, servings - claimed_servings)

        if remaining_servings <= 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This donation has already been fully claimed.",
            )

        # Quantity requested
        if claim_request and claim_request.quantity is not None:
            quantity = claim_request.quantity
        else:
            quantity = remaining_servings

        if quantity < 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Quantity to accept must be at least 1 serving.",
            )

        if quantity > remaining_servings:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Requested {quantity} servings exceeds remaining available {remaining_servings} servings.",
            )

        if current_user.capacity and quantity > current_user.capacity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Requested {quantity} servings exceeds your organization's daily handling capacity of {current_user.capacity} meals.",
            )

        # Atomic find_one_and_update with concurrency guard
        updated_document = donations_collection.find_one_and_update(
            {
                "_id": object_id,
                "status": {"$in": ["Active", "Partially Accepted"]},
                "$or": [
                    {"remainingServings": {"$gte": quantity}},
                    {"remainingServings": {"$exists": False}},
                ],
            },
            {
                "$inc": {
                    "remainingServings": -quantity,
                    "claimedServings": quantity,
                },
                "$set": {
                    "acceptedAt": datetime.now(),
                    "acceptedByUserId": current_user.id,
                    "acceptedByName": current_user.fullName,
                    "acceptedByOrganisation": current_user.organisation,
                    "acceptedByLocation": current_user.location,
                },
            },
            return_document=ReturnDocument.AFTER,
        )

        if updated_document is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This donation is no longer available in the requested quantity. Another organization may have claimed it.",
            )

        new_remaining = updated_document.get("remainingServings", 0)
        new_status: DonationStatusType = "Accepted" if new_remaining == 0 else "Partially Accepted"
        donations_collection.update_one(
            {"_id": object_id},
            {"$set": {"status": new_status}},
        )
        updated_document["status"] = new_status

        # Insert claim record
        claim_doc = {
            "donationId": str(object_id),
            "receiverUserId": current_user.id,
            "receiverName": current_user.fullName,
            "receiverOrganisation": current_user.organisation,
            "receiverLocation": current_user.location,
            "quantity": quantity,
            "status": "Accepted",
            "acceptedAt": datetime.now(),
            "collectedAt": None,
            "createdAt": datetime.now(),
        }

        try:
            claims_collection.insert_one(claim_doc)
        except Exception as claim_err:
            # Compensate / rollback atomic counter
            donations_collection.update_one(
                {"_id": object_id},
                {
                    "$inc": {"remainingServings": quantity, "claimedServings": -quantity},
                    "$set": {"status": existing_doc.get("status", "Active")},
                },
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to record pickup claim.",
            ) from claim_err

        # Notifications
        # 1. Notify donor
        dispatch_notifications([{
            "recipientUserId": updated_document["donorUserId"],
            "recipientRole": "donor",
            "type": "donation_accepted",
            "title": "Donation Accepted",
            "message": f"Your donation '{updated_document['foodName']}' was accepted for {quantity} servings by {current_user.organisation}.",
            "donationId": str(object_id),
        }])

        # 2. If partially accepted with remaining servings, notify other eligible NGOs
        if new_status == "Partially Accepted" and new_remaining > 0:
            other_ngos = [nid for nid in get_eligible_receiver_user_ids() if nid != current_user.id]
            if other_ngos:
                dispatch_notifications([
                    {
                        "recipientUserId": ngo_id,
                        "recipientRole": "ngo",
                        "type": "partial_remaining",
                        "title": "Food Remaining Available",
                        "message": (
                            f"Update: {new_remaining} servings of '{updated_document['foodName']}' "
                            f"remain available for pickup at {updated_document['location']}."
                        ),
                        "donationId": str(object_id),
                    }
                    for ngo_id in other_ngos
                ])

        return document_to_donation(updated_document)

    except HTTPException:
        raise
    except PyMongoError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to accept donation in MongoDB.",
        ) from error


@app.patch("/api/claims/{claim_id}/collect")
def collect_claim(
    claim_id: str,
    current_user: Annotated[UserPublic, Depends(get_current_user)],
):
    require_verified_ngo(current_user)
    if not ObjectId.is_valid(claim_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid claim ID.",
        )

    try:
        updated_claim = claims_collection.find_one_and_update(
            {
                "_id": ObjectId(claim_id),
                "receiverUserId": current_user.id,
                "status": "Accepted",
            },
            {
                "$set": {
                    "status": "Collected",
                    "collectedAt": datetime.now(),
                }
            },
            return_document=ReturnDocument.AFTER,
        )

        if updated_claim is None:
            existing = claims_collection.find_one({"_id": ObjectId(claim_id)})
            if existing is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Claim record not found.",
                )
            if existing.get("receiverUserId") != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only collect claims assigned to your organization.",
                )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This claim has already been marked as collected.",
            )

        donation_id = updated_claim.get("donationId")
        if donation_id and ObjectId.is_valid(donation_id):
            donation_oid = ObjectId(donation_id)
            donation_doc = donations_collection.find_one({"_id": donation_oid})
            if donation_doc:
                # Check if all claims are collected and remainingServings == 0
                pending_claims = claims_collection.count_documents({
                    "donationId": donation_id,
                    "status": {"$ne": "Collected"},
                })
                rem = donation_doc.get("remainingServings", 0)
                if pending_claims == 0 and rem == 0:
                    donations_collection.update_one(
                        {"_id": donation_oid},
                        {"$set": {"status": "Collected", "collectedAt": datetime.now()}},
                    )

                # Notify donor
                dispatch_notifications([{
                    "recipientUserId": donation_doc["donorUserId"],
                    "recipientRole": "donor",
                    "type": "donation_collected",
                    "title": "Collection Completed",
                    "message": (
                        f"{current_user.organisation} has collected {updated_claim['quantity']} "
                        f"servings of '{donation_doc['foodName']}'! Thank you."
                    ),
                    "donationId": donation_id,
                }])

        return {
            "message": "Pickup marked as collected successfully.",
            "claimId": str(updated_claim["_id"]),
            "status": "Collected",
            "quantity": updated_claim["quantity"],
        }

    except HTTPException:
        raise
    except PyMongoError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to update claim status in MongoDB.",
        ) from error


@app.patch(
    "/api/donations/{donation_id}/collect",
    response_model=Donation,
)
def mark_donation_as_collected(
    donation_id: str,
    current_user: Annotated[UserPublic, Depends(get_current_user)],
):
    require_verified_ngo(current_user)
    object_id = validate_donation_id(donation_id)

    try:
        # Check if caller has an Accepted claim on this donation
        claim = claims_collection.find_one({
            "donationId": str(object_id),
            "receiverUserId": current_user.id,
            "status": "Accepted",
        })

        if claim:
            collect_claim(str(claim["_id"]), current_user)
            updated_doc = donations_collection.find_one({"_id": object_id})
            return document_to_donation(updated_doc)

        # Fallback for legacy donation
        updated_document = donations_collection.find_one_and_update(
            {
                "_id": object_id,
                "status": {"$in": ["Accepted", "Partially Accepted"]},
                "acceptedByUserId": current_user.id,
            },
            {
                "$set": {
                    "status": "Collected",
                    "collectedAt": datetime.now(),
                }
            },
            return_document=ReturnDocument.AFTER,
        )

        if updated_document is not None:
            dispatch_notifications([{
                "recipientUserId": updated_document["donorUserId"],
                "recipientRole": "donor",
                "type": "donation_collected",
                "title": "Collection Completed",
                "message": f"{current_user.organisation} has collected '{updated_document['foodName']}'! Thank you.",
                "donationId": str(object_id),
            }])
            return document_to_donation(updated_document)

        existing_document = donations_collection.find_one({"_id": object_id})
        if existing_document is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Donation not found.",
            )

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only the NGO assigned to this pickup can mark it as collected.",
        )

    except HTTPException:
        raise
    except PyMongoError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to update donation in MongoDB.",
        ) from error


@app.get("/api/statistics/donor", response_model=DonorStatistics)
def get_donor_statistics(
    current_user: Annotated[UserPublic, Depends(get_current_user)],
):
    require_role(current_user, "donor")

    base_filter = {"donorUserId": current_user.id}

    try:
        active_donations = donations_collection.count_documents(
            {**base_filter, "status": {"$in": ["Active", "Partially Accepted"]}}
        )

        donor_donations = list(donations_collection.find(base_filter, {"_id": 1}))
        donor_donation_ids = [str(d["_id"]) for d in donor_donations]

        claim_accepted = claims_collection.count_documents(
            {"donationId": {"$in": donor_donation_ids}, "status": "Accepted"}
        )
        legacy_accepted = donations_collection.count_documents(
            {**base_filter, "status": "Accepted", "claims": {"$exists": False}}
        )
        accepted_pickups = claim_accepted if claim_accepted > 0 else legacy_accepted

        claim_collected = claims_collection.count_documents(
            {"donationId": {"$in": donor_donation_ids}, "status": "Collected"}
        )
        legacy_collected = donations_collection.count_documents(
            {**base_filter, "status": "Collected"}
        )
        completed_pickups = claim_collected if claim_collected > 0 else legacy_collected

        high_priority_donations = donations_collection.count_documents(
            {
                **base_filter,
                "status": {"$in": ["Active", "Partially Accepted"]},
                "priority": "High",
            }
        )

        claim_agg = list(
            claims_collection.aggregate(
                [
                    {"$match": {"donationId": {"$in": donor_donation_ids}, "status": "Collected"}},
                    {"$group": {"_id": None, "totalServings": {"$sum": "$quantity"}}},
                ]
            )
        )
        if claim_agg and claim_agg[0].get("totalServings", 0) > 0:
            meals_saved = claim_agg[0]["totalServings"]
        else:
            legacy_agg = list(
                donations_collection.aggregate(
                    [
                        {"$match": {**base_filter, "status": "Collected"}},
                        {"$group": {"_id": None, "totalServings": {"$sum": "$servings"}}},
                    ]
                )
            )
            meals_saved = legacy_agg[0]["totalServings"] if legacy_agg else 0

        monthly_pipeline = [
            {"$match": base_filter},
            {"$group": {
                "_id": {"$dateToString": {"format": "%Y-%m", "date": "$createdAt"}},
                "count": {"$sum": 1}
            }},
            {"$sort": {"_id": 1}}
        ]
        monthly_results = list(donations_collection.aggregate(monthly_pipeline))
        monthly_donations = [{"month": res["_id"] or "Unknown", "count": res["count"]} for res in monthly_results]

        return DonorStatistics(
            activeDonations=active_donations,
            acceptedPickups=accepted_pickups,
            completedPickups=completed_pickups,
            highPriorityDonations=high_priority_donations,
            mealsSaved=meals_saved,
            monthlyDonations=monthly_donations,
        )

    except PyMongoError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to calculate donor statistics.",
        ) from error


@app.get("/api/statistics/ngo", response_model=NgoStatistics)
def get_ngo_statistics(
    current_user: Annotated[UserPublic, Depends(get_current_user)],
):
    require_role(current_user, "ngo")

    try:
        available_donations = donations_collection.count_documents(
            {
                "status": {"$in": ["Active", "Partially Accepted"]},
                "$or": [{"remainingServings": {"$gt": 0}}, {"remainingServings": {"$exists": False}}],
            }
        )

        high_priority_available = donations_collection.count_documents(
            {
                "status": {"$in": ["Active", "Partially Accepted"]},
                "priority": "High",
                "$or": [{"remainingServings": {"$gt": 0}}, {"remainingServings": {"$exists": False}}],
            }
        )

        claim_accepted = claims_collection.count_documents(
            {"receiverUserId": current_user.id, "status": "Accepted"}
        )
        legacy_accepted = donations_collection.count_documents(
            {"acceptedByUserId": current_user.id, "status": "Accepted"}
        )
        accepted_pickups = max(claim_accepted, legacy_accepted)

        claim_collected = claims_collection.count_documents(
            {"receiverUserId": current_user.id, "status": "Collected"}
        )
        legacy_collected = donations_collection.count_documents(
            {"acceptedByUserId": current_user.id, "status": "Collected"}
        )
        completed_pickups = max(claim_collected, legacy_collected)

        claim_agg = list(
            claims_collection.aggregate(
                [
                    {"$match": {"receiverUserId": current_user.id, "status": "Collected"}},
                    {"$group": {"_id": None, "totalServings": {"$sum": "$quantity"}}},
                ]
            )
        )
        if claim_agg and claim_agg[0].get("totalServings", 0) > 0:
            meals_collected = claim_agg[0]["totalServings"]
        else:
            legacy_agg = list(
                donations_collection.aggregate(
                    [
                        {"$match": {"acceptedByUserId": current_user.id, "status": "Collected"}},
                        {"$group": {"_id": None, "totalServings": {"$sum": "$servings"}}},
                    ]
                )
            )
            meals_collected = legacy_agg[0]["totalServings"] if legacy_agg else 0

        category_pipeline = [
            {"$match": {"$or": [{"acceptedByUserId": current_user.id}]}},
            {"$group": {
                "_id": "$category",
                "count": {"$sum": 1}
            }}
        ]
        category_results = list(donations_collection.aggregate(category_pipeline))
        category_breakdown = [{"category": res["_id"] or "Other", "count": res["count"]} for res in category_results]

        return NgoStatistics(
            availableDonations=available_donations,
            acceptedPickups=accepted_pickups,
            completedPickups=completed_pickups,
            highPriorityAvailable=high_priority_available,
            mealsCollected=meals_collected,
            categoryBreakdown=category_breakdown,
        )

    except PyMongoError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to calculate NGO statistics.",
        ) from error


@app.get("/api/admin/statistics", response_model=AdminStatistics)
def get_admin_statistics(
    current_user: Annotated[UserPublic, Depends(get_current_user)],
):
    require_role(current_user, "admin")

    try:
        total_users = users_collection.count_documents({})
        total_donors = users_collection.count_documents({"role": "donor"})
        total_ngos = users_collection.count_documents({"role": "ngo"})
        total_donations = donations_collection.count_documents({})

        active_donations = donations_collection.count_documents(
            {"status": {"$in": ["Active", "Partially Accepted"]}}
        )
        
        claim_accepted = claims_collection.count_documents({"status": "Accepted"})
        legacy_accepted = donations_collection.count_documents({"status": "Accepted"})
        accepted_pickups = max(claim_accepted, legacy_accepted)

        claim_collected = claims_collection.count_documents({"status": "Collected"})
        legacy_collected = donations_collection.count_documents({"status": "Collected"})
        completed_pickups = max(claim_collected, legacy_collected)

        claim_agg = list(
            claims_collection.aggregate(
                [
                    {"$match": {"status": "Collected"}},
                    {"$group": {"_id": None, "totalServings": {"$sum": "$quantity"}}},
                ]
            )
        )
        if claim_agg and claim_agg[0].get("totalServings", 0) > 0:
            total_meals_recovered = claim_agg[0]["totalServings"]
        else:
            legacy_agg = list(
                donations_collection.aggregate(
                    [
                        {"$match": {"status": "Collected"}},
                        {"$group": {"_id": None, "totalServings": {"$sum": "$servings"}}},
                    ]
                )
            )
            total_meals_recovered = legacy_agg[0]["totalServings"] if legacy_agg else 0

        verified_ngos = users_collection.count_documents({"role": "ngo", "verificationStatus": "verified"})
        pending_ngos = users_collection.count_documents({"role": "ngo", "verificationStatus": "pending"})
        suspended_donors = users_collection.count_documents({"role": "donor", "accountStatus": "suspended"})
        
        monthly_pipeline = [
            {"$group": {
                "_id": {"$dateToString": {"format": "%Y-%m", "date": "$createdAt"}},
                "count": {"$sum": 1}
            }},
            {"$sort": {"_id": 1}}
        ]
        monthly_results = list(donations_collection.aggregate(monthly_pipeline))
        monthly_donations = [{"month": res["_id"] or "Unknown", "count": res["count"]} for res in monthly_results]
        
        category_pipeline = [
            {"$group": {
                "_id": "$category",
                "count": {"$sum": 1}
            }}
        ]
        category_results = list(donations_collection.aggregate(category_pipeline))
        category_breakdown = [{"category": res["_id"] or "Other", "count": res["count"]} for res in category_results]

        return AdminStatistics(
            totalUsers=total_users,
            totalDonors=total_donors,
            totalNgos=total_ngos,
            totalDonations=total_donations,
            activeDonations=active_donations,
            acceptedPickups=accepted_pickups,
            completedPickups=completed_pickups,
            totalMealsRecovered=total_meals_recovered,
            verifiedNgos=verified_ngos,
            pendingNgos=pending_ngos,
            suspendedDonors=suspended_donors,
            monthlyDonations=monthly_donations,
            categoryBreakdown=category_breakdown,
        )

    except PyMongoError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to calculate admin statistics.",
        ) from error


@app.get("/api/admin/users", response_model=list[UserPublic])
def get_all_users_for_admin(
    current_user: Annotated[UserPublic, Depends(get_current_user)],
):
    require_role(current_user, "admin")

    try:
        user_documents = users_collection.find().sort(
            "createdAt",
            DESCENDING,
        )

        return [document_to_user(document) for document in user_documents]

    except PyMongoError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to load platform users.",
        ) from error


@app.get("/api/admin/donations", response_model=list[Donation])
def get_all_donations_for_admin(
    current_user: Annotated[UserPublic, Depends(get_current_user)],
):
    require_role(current_user, "admin")

    try:
        donation_documents = donations_collection.find().sort(
            "createdAt",
            DESCENDING,
        )

        return [
            document_to_donation(document, is_admin=True)
            for document in donation_documents
        ]

    except PyMongoError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to load platform donations.",
        ) from error


class RejectionRequest(BaseModel):
    rejectionReason: str = Field(min_length=1, max_length=500)


@app.get("/api/admin/verification/pending", response_model=list[UserPublic])
def get_pending_verifications(
    current_user: Annotated[UserPublic, Depends(get_current_user)],
):
    require_role(current_user, "admin")

    try:
        user_documents = users_collection.find(
            {"role": "ngo", "verificationStatus": "pending"}
        ).sort("createdAt", DESCENDING)

        return [document_to_user(document) for document in user_documents]
    except PyMongoError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to load pending verifications.",
        ) from error


@app.put("/api/admin/verification/{user_id}/approve")
def approve_verification(
    user_id: str,
    current_user: Annotated[UserPublic, Depends(get_current_user)],
):
    require_role(current_user, "admin")

    if not ObjectId.is_valid(user_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format.",
        )

    try:
        result = users_collection.update_one(
            {"_id": ObjectId(user_id), "role": "ngo"},
            {
                "$set": {
                    "verificationStatus": "verified",
                    "verifiedAt": datetime.now(),
                    "verifiedBy": current_user.id,
                },
                "$unset": {"rejectionReason": ""}
            }
        )

        if result.matched_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found or is not an NGO.",
            )

        return {"message": "Organization verified successfully."}
    except PyMongoError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to approve verification.",
        ) from error


@app.put("/api/admin/verification/{user_id}/reject")
def reject_verification(
    user_id: str,
    rejection_data: RejectionRequest,
    current_user: Annotated[UserPublic, Depends(get_current_user)],
):
    require_role(current_user, "admin")

    if not ObjectId.is_valid(user_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format.",
        )

    try:
        result = users_collection.update_one(
            {"_id": ObjectId(user_id), "role": "ngo"},
            {
                "$set": {
                    "verificationStatus": "rejected",
                    "rejectionReason": rejection_data.rejectionReason,
                }
            }
        )

        if result.matched_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found or is not an NGO.",
            )

        return {"message": "Organization verification rejected."}
    except PyMongoError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to reject verification.",
        ) from error


@app.post(
    "/api/donations/{donation_id}/feedback",
    response_model=Donation,
)
def submit_donation_feedback(
    donation_id: str,
    feedback_data: DonationFeedback,
    current_user: Annotated[UserPublic, Depends(get_current_user)],
):
    require_verified_ngo(current_user)
    object_id = validate_donation_id(donation_id)

    try:
        donation = donations_collection.find_one({
            "_id": object_id,
            "status": "Collected",
            "acceptedByUserId": current_user.id
        })
        
        if not donation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Donation not found, not collected by you, or not in Collected status."
            )
            
        if donation.get("feedback"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Feedback has already been submitted for this donation."
            )

        updated_document = donations_collection.find_one_and_update(
            {"_id": object_id},
            {"$set": {"feedback": feedback_data.model_dump()}},
            return_document=ReturnDocument.AFTER,
        )

        # Trust Score Adjustment
        donor_id = donation["donorUserId"]
        score_change = 0
        if feedback_data.rating == 5:
            score_change = 2
        elif feedback_data.rating <= 2:
            score_change = -5
            
        if score_change != 0:
            donor = users_collection.find_one({"_id": ObjectId(donor_id)})
            if donor:
                new_score = max(0, min(100, donor.get("trustScore", 100) + score_change))
                new_status = "suspended" if new_score < 40 else donor.get("accountStatus", "active")
                users_collection.update_one(
                    {"_id": ObjectId(donor_id)},
                    {"$set": {"trustScore": new_score, "accountStatus": new_status}}
                )

        if updated_document is not None:
            return document_to_donation(updated_document)
        raise HTTPException(status_code=404, detail="Donation not found.")

    except PyMongoError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to submit feedback.",
        ) from error


@app.get("/api/notifications", response_model=list[Notification])
def get_notifications(
    current_user: Annotated[UserPublic, Depends(get_current_user)],
    unreadOnly: bool = False,
    limit: int = 30,
):
    try:
        user_filter = {"$or": [{"recipientUserId": current_user.id}, {"userId": current_user.id}]}
        if unreadOnly:
            query = {
                "$and": [
                    user_filter,
                    {"$or": [{"read": False}, {"isRead": False}]}
                ]
            }
        else:
            query = user_filter

        documents = (
            notifications_collection.find(query)
            .sort("createdAt", DESCENDING)
            .limit(min(limit, 100))
        )
        
        return [document_to_notification(doc) for doc in documents]
    except PyMongoError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to load notifications.",
        ) from error


@app.get("/api/notifications/unread-count")
def get_unread_notification_count(
    current_user: Annotated[UserPublic, Depends(get_current_user)],
):
    try:
        query = {
            "$and": [
                {"$or": [{"recipientUserId": current_user.id}, {"userId": current_user.id}]},
                {"$or": [{"read": False}, {"isRead": False}]}
            ]
        }
        count = notifications_collection.count_documents(query)
        return {"unreadCount": count}
    except PyMongoError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to count unread notifications.",
        ) from error


@app.patch("/api/notifications/{notification_id}/read")
@app.put("/api/notifications/{notification_id}/read")
def mark_notification_read(
    notification_id: str,
    current_user: Annotated[UserPublic, Depends(get_current_user)],
):
    if not ObjectId.is_valid(notification_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid ID.")
    try:
        result = notifications_collection.update_one(
            {
                "_id": ObjectId(notification_id),
                "$or": [{"recipientUserId": current_user.id}, {"userId": current_user.id}]
            },
            {"$set": {"read": True, "isRead": True}}
        )
        if result.matched_count == 0:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found.")
        return {"message": "Marked as read."}
    except PyMongoError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Error marking read.") from error


@app.patch("/api/notifications/read-all")
def mark_all_notifications_read(
    current_user: Annotated[UserPublic, Depends(get_current_user)],
):
    try:
        query = {"$or": [{"recipientUserId": current_user.id}, {"userId": current_user.id}]}
        notifications_collection.update_many(
            query,
            {"$set": {"read": True, "isRead": True}}
        )
        return {"message": "All notifications marked as read."}
    except PyMongoError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Error marking all read.") from error