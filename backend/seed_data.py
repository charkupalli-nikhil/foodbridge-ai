import os
from datetime import datetime, timedelta, timezone
import random
from pymongo import MongoClient
from dotenv import load_dotenv
import sys

# Load environment variables
load_dotenv()
MONGODB_URI = os.getenv("MONGODB_URI")
if not MONGODB_URI:
    print("MONGODB_URI missing.")
    sys.exit(1)

client = MongoClient(MONGODB_URI)
db = client[os.getenv("MONGODB_DATABASE", "foodbridge_ai")]
users_collection = db["users"]
donations_collection = db["donations"]

# Reference lists
FOOD_CATEGORIES = ["Cooked Meal", "Packaged Food", "Bakery", "Fruits", "Vegetables", "Dairy", "Snacks"]
LOCATIONS = [
    "Solapur, Maharashtra", 
    "Pune, Maharashtra", 
    "Mumbai, Maharashtra", 
    "Thane, Maharashtra",
    "Nagpur, Maharashtra",
    "Nashik, Maharashtra"
]

DONOR_ORGS = [
    ("Taj Hotel", "Mumbai, Maharashtra"),
    ("Mainland China", "Pune, Maharashtra"),
    ("Solapur Central Canteen", "Solapur, Maharashtra"),
    ("Sagar Ratna", "Thane, Maharashtra"),
    ("JW Marriott", "Pune, Maharashtra"),
    ("Shivaji Nagar Wedding Hall", "Solapur, Maharashtra"),
    ("Grand Banquet", "Nagpur, Maharashtra")
]

NGO_ORGS = [
    ("Robin Hood Army", "Solapur, Maharashtra"),
    ("Feeding India", "Pune, Maharashtra"),
    ("Sambhaji Foundation", "Mumbai, Maharashtra"),
    ("Annamrita", "Thane, Maharashtra"),
    ("Goonj", "Nashik, Maharashtra"),
]

def seed_database():
    print("Starting database seeding...")
    
    # 1. Clear OLD seeded data to avoid infinite growth (identified by a specific flag)
    users_collection.delete_many({"isSeeded": True})
    donations_collection.delete_many({"isSeeded": True})
    
    # 2. Create Donors
    print("Creating Donor accounts...")
    donor_ids = []
    default_password = "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjIQG8.6k6" # Demo@123
    
    for org_name, loc in DONOR_ORGS:
        user_doc = {
            "fullName": f"Admin {org_name}",
            "email": f"donor_{org_name.lower().replace(' ', '')}@example.com",
            "organisation": org_name,
            "role": "donor",
            "location": loc,
            "contactNumber": "9876543210",
            "password": default_password,
            "safetyAgreement": True,
            "trustScore": random.randint(80, 100),
            "createdAt": datetime.now(timezone.utc) - timedelta(days=random.randint(60, 180)),
            "isSeeded": True
        }
        res = users_collection.insert_one(user_doc)
        donor_ids.append((str(res.inserted_id), org_name, loc, f"Admin {org_name}"))

    # 3. Create NGOs
    print("Creating NGO accounts...")
    ngo_ids = []
    for org_name, loc in NGO_ORGS:
        user_doc = {
            "fullName": f"Coordinator {org_name}",
            "email": f"ngo_{org_name.lower().replace(' ', '')}@example.com",
            "organisation": org_name,
            "role": "ngo",
            "location": loc,
            "contactNumber": "9876543210",
            "password": default_password,
            "safetyAgreement": True,
            "verificationStatus": "verified",
            "verifiedAt": datetime.now(timezone.utc) - timedelta(days=60),
            "capacity": random.randint(200, 1000),
            "acceptedFoodTypes": ["Cooked Meal", "Packaged Food", "Bakery", "Fruits", "Vegetables"],
            "createdAt": datetime.now(timezone.utc) - timedelta(days=random.randint(60, 180)),
            "isSeeded": True
        }
        res = users_collection.insert_one(user_doc)
        ngo_ids.append((str(res.inserted_id), org_name, loc, f"Coordinator {org_name}"))

    # 4. Generate Historical Donations (to populate charts)
    print("Generating Historical Donations for analytics...")
    
    now = datetime.now(timezone.utc)
    for _ in range(150): # 150 historical donations
        donor = random.choice(donor_ids)
        ngo = random.choice(ngo_ids)
        
        # Pick a random date in the last 180 days
        days_ago = random.randint(2, 180)
        created_at = now - timedelta(days=days_ago)
        
        cat = random.choice(FOOD_CATEGORIES)
        food_names = {
            "Cooked Meal": ["Veg Biryani", "Dal Makhani & Roti", "Mixed Sabzi", "Pulao"],
            "Packaged Food": ["Biscuits", "Instant Noodles", "Canned Beans"],
            "Bakery": ["Fresh Bread", "Muffins", "Leftover Cakes"],
            "Fruits": ["Bananas", "Apples", "Mixed Fruits"],
            "Vegetables": ["Tomatoes & Onions", "Potatoes", "Mixed Veggies"],
            "Dairy": ["Milk Packets", "Paneer"],
            "Snacks": ["Samosas", "Poha"]
        }
        
        status_choice = random.choices(["Collected", "Active", "Accepted"], weights=[80, 10, 10])[0]
        priority = random.choices(["High", "Medium", "Low"], weights=[50, 40, 10])[0]
        
        donation = {
            "foodName": random.choice(food_names[cat]),
            "category": cat,
            "servings": random.randint(20, 250),
            "preparationTime": "Prepared 2 hours ago",
            "pickupDeadline": created_at + timedelta(hours=random.randint(2, 6)),
            "location": donor[2],
            "packagingCondition": "Packed in food-grade containers",
            "donorUserId": donor[0],
            "donorName": donor[3],
            "donorOrganisation": donor[1],
            "priority": priority,
            "status": status_choice,
            "createdAt": created_at,
            "aiConfidence": round(random.uniform(85.0, 99.9), 1),
            "predictionMethod": "ml_model",
            "predictionFeatures": {
                "preparation_age_minutes": random.randint(30, 120),
                "pickup_window_minutes": random.randint(120, 360),
                "packaging_score": round(random.uniform(0.7, 1.0), 2)
            },
            "isSeeded": True
        }
        
        if status_choice in ["Accepted", "Collected"]:
            donation["acceptedByUserId"] = ngo[0]
            donation["acceptedByName"] = ngo[3]
            donation["acceptedByOrganisation"] = ngo[1]
            donation["acceptedAt"] = created_at + timedelta(minutes=random.randint(15, 60))
            donation["matchScore"] = random.randint(70, 100)
            donation["distanceKm"] = round(random.uniform(1.5, 12.0), 1)
            
        if status_choice == "Collected":
            donation["collectedAt"] = donation["acceptedAt"] + timedelta(hours=random.randint(1, 3))
            
        donations_collection.insert_one(donation)

    print("✅ Database successfully seeded with production data!")
    print("Check your Admin, Donor, and NGO dashboards to see the charts!")

if __name__ == "__main__":
    seed_database()
