from datetime import datetime
from getpass import getpass

from pymongo.errors import DuplicateKeyError, PyMongoError

from database import initialise_database_indexes, users_collection
from security import hash_password


def read_required_value(label: str) -> str:
    while True:
        value = input(f"{label}: ").strip()

        if value:
            return value

        print(f"{label} cannot be empty.")


def main() -> None:
    print("\nFoodBridge AI - Create Administrator Account")
    print("--------------------------------------------")
    print("This creates a private admin account in MongoDB.\n")

    full_name = read_required_value("Full name")
    email = read_required_value("Email address").lower()
    organisation = read_required_value("Organisation name")
    location = read_required_value("Location")
    contact_number = read_required_value("Contact number")

    while True:
        password = getpass("Password: ")
        confirm_password = getpass("Confirm password: ")

        if password != confirm_password:
            print("Passwords do not match. Try again.\n")
            continue

        if len(password) < 8:
            print("Password must contain at least 8 characters.\n")
            continue

        break

    admin_document = {
        "fullName": full_name,
        "email": email,
        "organisation": organisation,
        "role": "admin",
        "location": location,
        "contactNumber": contact_number,
        "passwordHash": hash_password(password),
        "createdAt": datetime.now(),
    }

    try:
        initialise_database_indexes()
        users_collection.insert_one(admin_document)

        print("\nAdministrator account created successfully.")
        print(f"Login email: {email}")
        print("Login role: Administrator")

    except DuplicateKeyError:
        print("\nAn account with this email address already exists.")

    except PyMongoError as error:
        print("\nUnable to create administrator account in MongoDB.")
        print(f"Error: {error}")


if __name__ == "__main__":
    main()