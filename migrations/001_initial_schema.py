"""Database initialization migration script."""

from sqlalchemy import create_engine, text
import sys
import os

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

from models.database import Base
from config.config import config

def create_database(config_name='development'):
    """Create the database and all tables."""
    app_config = config[config_name]
    
    # Create database if not exists
    base_url = app_config.SQLALCHEMY_DATABASE_URI.rsplit('/', 1)[0]
    db_name = app_config.DB_NAME
    
    engine = create_engine(base_url, echo=True)
    
    with engine.connect() as connection:
        # Create database
        connection.execute(text(f"CREATE DATABASE IF NOT EXISTS {db_name}"))
        connection.commit()
    
    # Connect to the specific database
    db_engine = create_engine(app_config.SQLALCHEMY_DATABASE_URI, echo=True)
    
    # Create all tables
    Base.metadata.create_all(db_engine)
    
    print(f"Database '{db_name}' and all tables created successfully!")

if __name__ == "__main__":
    config_name = sys.argv[1] if len(sys.argv) > 1 else 'development'
    create_database(config_name)