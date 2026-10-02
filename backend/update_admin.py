from getpass import getpass
from database import users_collection
from security import hash_password
import sys

def main():
    print("\nFoodBridge AI - Update Administrator Account")
    print("--------------------------------------------")
    
    # First, let's fix the seeded data bug (rename 'password' to 'passwordHash') silently
    users_collection.update_many(
        {"password": {"$exists": True}, "isSeeded": True},
        {"$rename": {"password": "passwordHash"}}
    )
    
    # Check if an admin exists
    admin = users_collection.find_one({"role": "admin"})
    if not admin:
        print("No admin account found. Please run create_admin.py instead.")
        sys.exit(1)
        
    print(f"Current Admin Email: {admin.get('email')}")
    
    new_email = input("Enter new real Email address: ").strip().lower()
    if not new_email:
        print("Email cannot be empty.")
        sys.exit(1)
        
    while True:
        password = getpass("Enter new Password: ")
        confirm_password = getpass("Confirm new Password: ")

        if password != confirm_password:
            print("Passwords do not match. Try again.\n")
            continue

        if len(password) < 8:
            print("Password must contain at least 8 characters.\n")
            continue
        break

    # Update the admin document
    result = users_collection.update_one(
        {"_id": admin["_id"]},
        {"$set": {
            "email": new_email,
            "passwordHash": hash_password(password)
        }}
    )
    
    print("\n✅ Administrator account successfully updated!")
    print(f"New Login email: {new_email}")

if __name__ == "__main__":
    main()
