#!/usr/bin/env python3
"""
Initialize authentication system for FraudNet.AI.
Creates User table and seeds with default users.
"""

import sys
import os

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

from app import create_app
from app.models.database import User
from app.core.database_manager import DatabaseManager

def init_auth_system():
    """Initialize authentication system."""
    print("Initializing FraudNet.AI authentication system...")
    
    # Create Flask app and application context
    app = create_app()
    
    with app.app_context():
        try:
            # Get database manager from app globals
            from app import db_manager
            
            # Create tables if they don't exist
            print("Creating database tables...")
            db_manager.create_tables()
            
            # Create default users
            print("Creating default users...")
            with db_manager.get_session() as session:
                User.create_default_users(session)
            
            print("✅ Authentication system initialized successfully!")
            print()
            print("Default user credentials:")
            print("👤 Admin:      admin@fraudnet.ai / admin123")
            print("👤 Analyst:    analyst@fraudnet.ai / analyst123") 
            print("👤 Viewer:     viewer@fraudnet.ai / viewer123")
            print("👤 John Smith: john.smith@fraudnet.ai / demo123")
            print("👤 Sarah J.:   sarah.johnson@fraudnet.ai / demo123")
            print()
            print("🚀 Ready to start the application!")
            
        except Exception as e:
            print(f"❌ Error initializing authentication: {str(e)}")
            sys.exit(1)

if __name__ == "__main__":
    init_auth_system()