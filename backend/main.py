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

GEOCODE_CACHE = {}

def get_coordinates(location_str: str):
    if not location_str or len(location_str) < 3: return None
    loc_lower = location_str.lower().strip()
    if loc_lower in GEOCODE_CACHE: return GEOCODE_CACHE[loc_lower]
    
    try:
        url = f"https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(location_str)}&format=json&limit=1"
        res = requests.get(url, headers={'User-Agent': 'FoodBridgeAI/1.0'}, timeout=3)
        if res.status_code == 200 and len(res.json()) > 0:
            data = res.json()[0]
            coords = (float(data['lat']), float(data['lon']))
            GEOCODE_CACHE[loc_lower] = coords
            return coords
    except Exception:
        pass
    return None

def calculate_haversine_distance(lat1, lon1, lat2, lon2):
    R = 6371.0 # Earth radius in km
    dLat = math.radians(lat2 - lat1)
    dLon = math.radians(lon2 - lon1)
    a = math.sin(dLat/2)**2 + math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(dLon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c
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
)
from prediction import predict_food_priority
from security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)

PriorityType = Literal["High", "Medium", "Low"]
DonationStatusType = Literal["Active", "Accepted", "Collected"]
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


class DonationCreate(BaseModel):
    foodName: str = Field(min_length=2, max_length=100)
    category: FoodCategoryType
    servings: int = Field(gt=0, le=10000)
    preparationTime: str = Field(min_length=2, max_length=150)
    pickupDeadline: datetime
    location: str = Field(min_length=2, max_length=200)
    packagingCondition: str = Field(min_length=2, max_length=300)
    foodImage: str | None = None
    packagingImage: str | None = None


class DonationFeedback(BaseModel):
    rating: int = Field(ge=1, le=5)
    comments: str | None = None


class Donation(BaseModel):
    id: str
    foodName: str
    category: str
    servings: int
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
    acceptedByName: str | None = None
    acceptedByOrganisation: str | None = None
    acceptedByLocation: str | None = None
    acceptedAt: datetime | None = None
    collectedAt: datetime | None = None
    feedback: DonationFeedback | None = None
    matchScore: int | None = None
    distanceKm: float | None = None


class PublicStats(BaseModel):
    donations: int
    mealsSaved: int
    ngoPartners: int


class Notification(BaseModel):
    id: str
    userId: str
    title: str
    message: str
    isRead: bool = False
    createdAt: datetime


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
    return Notification(
        id=str(document["_id"]),
        userId=document["userId"],
        title=document["title"],
        message=document["message"],
        isRead=document.get("isRead", False),
        createdAt=document["createdAt"],
    )


def create_notification(user_id: str, title: str, message: str) -> None:
    try:
        notifications_collection.insert_one({
            "userId": user_id,
            "title": title,
            "message": message,
            "isRead": False,
            "createdAt": datetime.now()
        })
    except Exception as e:
        print(f"Failed to create notification: {e}")


def document_to_donation(document: dict) -> Donation:
    return Donation(
        id=str(document["_id"]),
        foodName=document["foodName"],
        category=document["category"],
        servings=document["servings"],
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
        aiConfidence=document.get("aiConfidence"),
        predictionMethod=document.get("predictionMethod"),
        predictionFeatures=document.get("predictionFeatures"),
        imageAnalysis=document.get("imageAnalysis"),
        acceptedByName=document.get("acceptedByName"),
        acceptedByOrganisation=document.get("acceptedByOrganisation"),
        acceptedByLocation=document.get("acceptedByLocation"),
        acceptedAt=document.get("acceptedAt"),
        collectedAt=document.get("collectedAt"),
        feedback=document.get("feedback"),
        distanceKm=document.get("distanceKm"),
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
):
    require_verified_ngo(current_user)

    try:
        documents = donations_collection.find(
            {"status": "Active"}
        ).sort("createdAt", DESCENDING)

        return [document_to_donation(document) for document in documents]

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

        documents = list(donations_collection.find({"status": "Active"}))
        scored_donations = []

        for doc in documents:
            if ngo_capacity and doc.get("servings", 0) > ngo_capacity:
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
        documents = donations_collection.find(
            {"acceptedByUserId": current_user.id}
        ).sort("createdAt", DESCENDING)

        return [document_to_donation(document) for document in documents]

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

    prediction_payload = generate_ai_priority_payload(donation_data)

    image_analysis_result = None
    if donation_data.foodImage:
        from ml.image_analysis import analyze_food_image
        image_analysis_result = analyze_food_image(donation_data.foodImage)
        
        # Phase 3: Duplicate image detection
        if image_analysis_result.get("imageHash"):
            existing_duplicate = donations_collection.find_one({
                "imageAnalysis.imageHash": image_analysis_result["imageHash"],
                "status": {"$ne": "Cancelled"}
            })
            if existing_duplicate:
                # Deduct trust score for duplicates
                new_score = max(0, current_user.trustScore - 10)
                new_status = "suspended" if new_score < 40 else "active"
                users_collection.update_one(
                    {"_id": ObjectId(current_user.id)},
                    {"$set": {"trustScore": new_score, "accountStatus": new_status}}
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Duplicate image detected. This exact image has been used in a previous donation.",
                )

    donation_document = {
        **donation_data.model_dump(),
        "donorUserId": current_user.id,
        "donorName": current_user.fullName,
        "donorOrganisation": current_user.organisation,
        "priority": prediction_payload["priority"],
        "aiConfidence": prediction_payload["aiConfidence"],
        "predictionMethod": prediction_payload["predictionMethod"],
        "predictionFeatures": prediction_payload["predictionFeatures"],
        "imageAnalysis": image_analysis_result,
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

        if prediction_payload["priority"] == "High":
            ngos = users_collection.find({"role": "ngo", "verificationStatus": "verified"}, {"_id": 1})
            for ngo in ngos:
                create_notification(str(ngo["_id"]), "High Priority Donation", f"New urgent donation available: {donation_data.foodName}")

        return document_to_donation(created_document)

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
):
    require_verified_ngo(current_user)
    object_id = validate_donation_id(donation_id)

    try:
        accepted_document = donations_collection.find_one_and_update(
            {
                "_id": object_id,
                "status": "Active",
            },
            {
                "$set": {
                    "status": "Accepted",
                    "acceptedByUserId": current_user.id,
                    "acceptedByName": current_user.fullName,
                    "acceptedByOrganisation": current_user.organisation,
                    "acceptedByLocation": current_user.location,
                    "acceptedAt": datetime.now(),
                }
            },
            return_document=ReturnDocument.AFTER,
        )

        if accepted_document is not None:
            create_notification(accepted_document["donorUserId"], "Donation Accepted", f"Your donation '{accepted_document['foodName']}' was accepted by {current_user.organisation}.")
            return document_to_donation(accepted_document)

        existing_document = donations_collection.find_one(
            {"_id": object_id}
        )

        if existing_document is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Donation not found.",
            )

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This donation is no longer available for acceptance.",
        )

    except HTTPException:
        raise

    except PyMongoError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to accept donation in MongoDB.",
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
        updated_document = donations_collection.find_one_and_update(
            {
                "_id": object_id,
                "status": "Accepted",
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
            create_notification(updated_document["donorUserId"], "Collection Completed", f"{current_user.organisation} has collected '{updated_document['foodName']}'! Thank you.")
            return document_to_donation(updated_document)

        existing_document = donations_collection.find_one(
            {"_id": object_id}
        )

        if existing_document is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Donation not found.",
            )

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only the NGO assigned to an accepted pickup can mark it as collected.",
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
            {**base_filter, "status": "Active"}
        )

        accepted_pickups = donations_collection.count_documents(
            {**base_filter, "status": "Accepted"}
        )

        completed_pickups = donations_collection.count_documents(
            {**base_filter, "status": "Collected"}
        )

        high_priority_donations = donations_collection.count_documents(
            {
                **base_filter,
                "status": "Active",
                "priority": "High",
            }
        )

        aggregation_result = list(
            donations_collection.aggregate(
                [
                    {
                        "$match": {
                            **base_filter,
                            "status": "Collected",
                        }
                    },
                    {
                        "$group": {
                            "_id": None,
                            "totalServings": {"$sum": "$servings"},
                        }
                    },
                ]
            )
        )

        meals_saved = (
            aggregation_result[0]["totalServings"]
            if aggregation_result
            else 0
        )

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

    assigned_filter = {"acceptedByUserId": current_user.id}

    try:
        available_donations = donations_collection.count_documents(
            {"status": "Active"}
        )

        high_priority_available = donations_collection.count_documents(
            {
                "status": "Active",
                "priority": "High",
            }
        )

        accepted_pickups = donations_collection.count_documents(
            {
                **assigned_filter,
                "status": "Accepted",
            }
        )

        completed_pickups = donations_collection.count_documents(
            {
                **assigned_filter,
                "status": "Collected",
            }
        )

        aggregation_result = list(
            donations_collection.aggregate(
                [
                    {
                        "$match": {
                            **assigned_filter,
                            "status": "Collected",
                        }
                    },
                    {
                        "$group": {
                            "_id": None,
                            "totalServings": {"$sum": "$servings"},
                        }
                    },
                ]
            )
        )

        meals_collected = (
            aggregation_result[0]["totalServings"]
            if aggregation_result
            else 0
        )

        category_pipeline = [
            {"$match": assigned_filter},
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
            {"status": "Active"}
        )
        accepted_pickups = donations_collection.count_documents(
            {"status": "Accepted"}
        )
        completed_pickups = donations_collection.count_documents(
            {"status": "Collected"}
        )

        aggregation_result = list(
            donations_collection.aggregate(
                [
                    {"$match": {"status": "Collected"}},
                    {
                        "$group": {
                            "_id": None,
                            "totalServings": {"$sum": "$servings"},
                        }
                    },
                ]
            )
        )

        total_meals_recovered = (
            aggregation_result[0]["totalServings"]
            if aggregation_result
            else 0
        )

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
            document_to_donation(document)
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
):
    try:
        documents = notifications_collection.find(
            {"userId": current_user.id, "isRead": False}
        ).sort("createdAt", DESCENDING)
        
        return [document_to_notification(doc) for doc in documents]
    except PyMongoError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to load notifications.",
        ) from error


@app.put("/api/notifications/{notification_id}/read")
def mark_notification_read(
    notification_id: str,
    current_user: Annotated[UserPublic, Depends(get_current_user)],
):
    if not ObjectId.is_valid(notification_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid ID.")
    try:
        result = notifications_collection.update_one(
            {"_id": ObjectId(notification_id), "userId": current_user.id},
            {"$set": {"isRead": True}}
        )
        if result.matched_count == 0:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found.")
        return {"message": "Marked as read."}
    except PyMongoError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Error marking read.") from error