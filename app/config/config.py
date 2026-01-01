"""Application configuration."""

import os
from datetime import timedelta
from typing import Optional

class Config:
    """Base configuration class."""
    
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    
    # Database Configuration
    DB_USER = os.environ.get('DB_USER', 'fraudnet')
    DB_PASSWORD = os.environ.get('DB_PASSWORD', 'fraudnet123')
    DB_HOST = os.environ.get('DB_HOST', 'localhost')
    DB_PORT = os.environ.get('DB_PORT', '3306')
    DB_NAME = os.environ.get('DB_NAME', 'fraudnet')
    
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
        'pool_size': int(os.environ.get('DATABASE_POOL_SIZE', '20')),
        'max_overflow': 10
    }
    
    # Redis Configuration
    REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0') 
    REDIS_TIMEOUT = int(os.environ.get('REDIS_TIMEOUT', '5'))
    
    # Model Artifacts
    MODEL_ARTIFACTS_PATH = os.environ.get('MODEL_ARTIFACT_PATH', './artifacts')
    MODELS_PATH = f"{MODEL_ARTIFACTS_PATH}/models"
    METRICS_PATH = f"{MODEL_ARTIFACTS_PATH}/metrics"
    PREPROCESSING_PATH = f"{MODEL_ARTIFACTS_PATH}/preprocessing"
    
    # Security Configuration
    API_KEY_HEADER = os.environ.get('API_KEY_HEADER', 'X-API-Key')
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or SECRET_KEY
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(seconds=int(os.environ.get('JWT_ACCESS_TOKEN_EXPIRES', '3600')))
    
    # Rate Limiting
    RATE_LIMIT_ENABLED = os.environ.get('RATE_LIMIT_ENABLED', 'true').lower() == 'true'
    RATE_LIMIT_PER_MINUTE = int(os.environ.get('RATE_LIMIT_PER_MINUTE', '100'))
    RATE_LIMIT_BURST = int(os.environ.get('RATE_LIMIT_BURST', '20'))
    
    # CORS Configuration
    CORS_ENABLED = os.environ.get('CORS_ENABLED', 'true').lower() == 'true'
    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', '*')
    
    # Content Validation
    VALIDATE_CONTENT_TYPE = os.environ.get('VALIDATE_CONTENT_TYPE', 'true').lower() == 'true'
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH', '1048576'))  # 1MB
    
    # Logging
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_FORMAT = os.environ.get('LOG_FORMAT', 'json')
    LOG_FILE = os.environ.get('LOG_FILE')
    
    # Feature Engineering
    FEATURE_WINDOW_HOURS = int(os.environ.get('FEATURE_WINDOW_HOURS', '24'))
    FEATURE_CACHE_TTL = int(os.environ.get('FEATURE_CACHE_TTL', '300'))
    FEATURE_VALIDATION_ENABLED = os.environ.get('FEATURE_VALIDATION_ENABLED', 'true').lower() == 'true'
    
    # Model Configuration
    MODEL_RETRAIN_THRESHOLD_DAYS = int(os.environ.get('MODEL_RETRAIN_THRESHOLD_DAYS', '7'))
    MODEL_CACHE_TTL = int(os.environ.get('MODEL_CACHE_TTL', '3600'))
    MODEL_RETRAIN_THRESHOLD = float(os.environ.get('MODEL_RETRAIN_THRESHOLD', '0.05'))
    
    # Monitoring
    PROMETHEUS_ENABLED = os.environ.get('PROMETHEUS_ENABLED', 'false').lower() == 'true'
    PROMETHEUS_PORT = int(os.environ.get('PROMETHEUS_PORT', '8000'))
    HEALTH_CHECK_TIMEOUT = int(os.environ.get('HEALTH_CHECK_TIMEOUT', '30'))
    
class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    TESTING = False
    
    # Development security settings
    RATE_LIMIT_ENABLED = False  # Disable for easier development
    CORS_ENABLED = True
    CORS_ORIGINS = 'http://localhost:3000,http://localhost:8080'
    
class TestingConfig(Config):
    """Testing configuration."""
    TESTING = True
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    
    # Testing security settings
    RATE_LIMIT_ENABLED = False
    CORS_ENABLED = False
    SECRET_KEY = 'test-secret-key'
    
class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    TESTING = False
    
    # Production security settings (stricter)
    RATE_LIMIT_ENABLED = True
    RATE_LIMIT_PER_MINUTE = 1000
    RATE_LIMIT_BURST = 50
    CORS_ENABLED = False  # Disable CORS in production unless needed
    
    # Require environment variables in production
    SECRET_KEY = os.environ.get('SECRET_KEY')
    if not SECRET_KEY:
        raise ValueError("SECRET_KEY environment variable must be set in production")
    
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY')
    if not JWT_SECRET_KEY:
        raise ValueError("JWT_SECRET_KEY environment variable must be set in production")

config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}