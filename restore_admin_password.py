#!/usr/bin/env python3
"""
Restore admin password to 12345 in MongoDB
This is needed because the test changed it to TempPass987 but cannot change it back
due to validation requiring min 6 characters (12345 is only 5 characters)
"""
import bcrypt
from pymongo import MongoClient

MONGO_URL = "mongodb://localhost:27017"
DB_NAME = "test_database"
ADMIN_EMAIL = "patrik.degerstam@yp.se"
ADMIN_PASSWORD = "12345"

def hash_pw(password: str) -> str:
    """Hash password using bcrypt"""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def main():
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    
    # Hash the password
    password_hash = hash_pw(ADMIN_PASSWORD)
    
    # Update the admin user
    result = db.users.update_one(
        {"email": ADMIN_EMAIL},
        {"$set": {"password_hash": password_hash}}
    )
    
    if result.modified_count > 0:
        print(f"✅ Successfully restored password for {ADMIN_EMAIL} to '{ADMIN_PASSWORD}'")
    else:
        print(f"⚠️  No user found with email {ADMIN_EMAIL} or password was already correct")
    
    client.close()

if __name__ == "__main__":
    main()
