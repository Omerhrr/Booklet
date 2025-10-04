# In: init_prod_db.py

import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from app.database import Base  # Import your SQLAlchemy Base
from app.models import *  # Import all your models to register them with Base

# --- IMPORTANT ---
# This script is for ONE-TIME use to initialize your production database.
# Do not run this regularly on a database that has data you want to keep,
# as future versions of SQLAlchemy might behave unexpectedly.
# It is safe for the very first setup.
# -----------------

def initialize_database():
    """
    Connects to the database specified in the .env file and creates all tables
    defined in the SQLAlchemy models.
    """
    print("Loading environment variables from .env file...")
    load_dotenv()
    
    DATABASE_URL = os.getenv("DATABASE_URL")
    
    if not DATABASE_URL:
        print("🔴 ERROR: DATABASE_URL not found in .env file. Aborting.")
        return

    if "sqlite" in DATABASE_URL:
        print("🟡 WARNING: Detected SQLite URL. This script is intended for production DBs like Postgres.")
        # return # You can uncomment this to prevent accidental runs on SQLite

    print(f"Connecting to database: {DATABASE_URL.split('@')[1]}...") # Hide password in log

    try:
        engine = create_engine(DATABASE_URL)
        
        print("Engine created. Creating all tables based on SQLAlchemy models...")
        # This is the command that builds the schema
        Base.metadata.create_all(bind=engine)
        
        print("✅ SUCCESS: All tables created successfully in the production database.")
        print("You can now proceed with deploying your application.")

    except Exception as e:
        print(f"🔴 ERROR: An error occurred during database initialization.")
        print(f"Error details: {e}")

if __name__ == "__main__":
    initialize_database()
