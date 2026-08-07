import uuid
import os
import shutil
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any, Literal


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
    acceptedByName: str | None = None
    acceptedByOrganisation: str | None = None
    acceptedByLocation: str | None = None
    acceptedAt: datetime | None = None
    collectedAt: datetime | None = None


class DonorStatistics(BaseModel):
    activeDonations: int
    acceptedPickups: int
    completedPickups: int
    highPriorityDonations: int
    mealsSaved: int


class NgoStatistics(BaseModel):
    availableDonations: int
    acceptedPickups: int
    completedPickups: int
    highPriorityAvailable: int
    mealsCollected: int


class AdminStatistics(BaseModel):
    totalUsers: int
    totalDonors: int
    totalNgos: int
    totalDonations: int
    activeDonations: int
    acceptedPickups: int
    completedPickups: int
    totalMealsRecovered: int


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

UPLOAD_DIR = BASE_DIR / "uploads"
FOOD_UPLOAD_DIR = UPLOAD_DIR / "food"
PACKAGING_UPLOAD_DIR = UPLOAD_DIR / "packaging"
CERTIFICATE_UPLOAD_DIR = UPLOAD_DIR / "certificates"
GOVERNMENT_ID_UPLOAD_DIR = UPLOAD_DIR / "government_ids"
LOGO_UPLOAD_DIR = UPLOAD_DIR / "logos"

CERTIFICATE_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
GOVERNMENT_ID_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
LOGO_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

FOOD_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
PACKAGING_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app.mount(
    "/uploads",
    StaticFiles(directory=str(UPLOAD_DIR)),
    name="uploads",
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


def document_to_user(document: dict) -> UserPublic:
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

        location=document["location"],
        contactNumber=document["contactNumber"],
        createdAt=document["createdAt"],
    )


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
        acceptedByName=document.get("acceptedByName"),
        acceptedByOrganisation=document.get("acceptedByOrganisation"),
        acceptedByLocation=document.get("acceptedByLocation"),
        acceptedAt=document.get("acceptedAt"),
        collectedAt=document.get("collectedAt"),
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


@app.get("/")
def read_root():
    return {
        "application": "FoodBridge AI API",
        "message": "Backend server is running successfully.",
        "version": "1.1.0",
        "aiPriorityPrediction": "enabled",
        "imageUpload": "enabled",
    }


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
    require_role(current_user, "ngo")

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

    if donation_data.pickupDeadline <= get_current_datetime_for(
        donation_data.pickupDeadline
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Pickup deadline must be later than the current time.",
        )

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
    require_role(current_user, "ngo")
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
    require_role(current_user, "ngo")
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

        return DonorStatistics(
            activeDonations=active_donations,
            acceptedPickups=accepted_pickups,
            completedPickups=completed_pickups,
            highPriorityDonations=high_priority_donations,
            mealsSaved=meals_saved,
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

        return NgoStatistics(
            availableDonations=available_donations,
            acceptedPickups=accepted_pickups,
            completedPickups=completed_pickups,
            highPriorityAvailable=high_priority_available,
            mealsCollected=meals_collected,
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

        return AdminStatistics(
            totalUsers=total_users,
            totalDonors=total_donors,
            totalNgos=total_ngos,
            totalDonations=total_donations,
            activeDonations=active_donations,
            acceptedPickups=accepted_pickups,
            completedPickups=completed_pickups,
            totalMealsRecovered=total_meals_recovered,
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