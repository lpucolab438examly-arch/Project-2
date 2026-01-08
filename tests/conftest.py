"""Test configuration and fixtures."""

import os
import pytest
import tempfile
import shutil
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import create_app
from app.models.database import Base, User, Transaction, Prediction, ModelRegistry
from app.utils.database import DatabaseManager
from app.config.config import TestingConfig

# Test configuration
TEST_DB_URL = 'sqlite:///:memory:'

@pytest.fixture(scope='session')
def app():
    """Create Flask app for testing."""
    # Use in-memory SQLite for tests
    TestingConfig.SQLALCHEMY_DATABASE_URI = TEST_DB_URL
    
    app = create_app('testing')
    app.config['TESTING'] = True
    
    with app.app_context():
        yield app

@pytest.fixture(scope='session')
def client(app):
    """Create test client."""
    return app.test_client()

@pytest.fixture(scope='function')
def db_session():
    """Create database session for testing."""
    engine = create_engine(TEST_DB_URL, echo=False)
    Session = sessionmaker(bind=engine)
    
    # Create tables
    Base.metadata.create_all(engine)
    
    session = Session()
    
    yield session
    
    session.close()
    Base.metadata.drop_all(engine)

@pytest.fixture(scope='function')
def db_manager():
    """Create database manager for testing."""
    manager = DatabaseManager(TEST_DB_URL)
    manager.create_tables()
    
    yield manager
    
    manager.drop_tables()

@pytest.fixture(scope='function')
def temp_artifacts_dir():
    """Create temporary directory for model artifacts."""
    temp_dir = tempfile.mkdtemp()
    
    # Create subdirectories
    os.makedirs(os.path.join(temp_dir, 'models'), exist_ok=True)
    os.makedirs(os.path.join(temp_dir, 'metrics'), exist_ok=True)
    os.makedirs(os.path.join(temp_dir, 'preprocessing'), exist_ok=True)
    
    yield temp_dir
    
    shutil.rmtree(temp_dir)

@pytest.fixture
def sample_user(db_session):
    """Create sample user for testing."""
    user = User(
        name='Test User',
        email='test@example.com'
    )
    db_session.add(user)
    db_session.commit()
    
    return user

@pytest.fixture
def sample_transaction(db_session, sample_user):
    """Create sample transaction for testing."""
    transaction = Transaction(
        user_id=sample_user.id,
        amount=100.50,
        currency='USD',
        merchant_category='retail',
        device_id='device123',
        ip_address='192.168.1.1',
        timestamp=datetime.utcnow(),
        raw_payload={'test': 'data'}
    )
    db_session.add(transaction)
    db_session.commit()
    
    return transaction

@pytest.fixture
def sample_prediction(db_session, sample_transaction):
    """Create sample prediction for testing."""
    prediction = Prediction(
        transaction_id=sample_transaction.id,
        model_version='test_model_v1',
        fraud_probability=0.25,
        prediction_label=False,
        confidence_score=0.75,
        inference_time_ms=50
    )
    db_session.add(prediction)
    db_session.commit()
    
    return prediction

@pytest.fixture
def sample_model_registry(db_session):
    """Create sample model registry entry."""
    model = ModelRegistry(
        model_name='test_fraud_detector',
        model_version='test_v1.0.0',
        model_type='logistic_regression',
        model_path='/tmp/test_model.joblib',
        preprocessing_path='/tmp/test_preprocessing.joblib',
        metrics={'auc': 0.85, 'precision': 0.80, 'recall': 0.75},
        is_active=True,
        training_data_hash='test_hash_123',
        feature_schema_version='1.0.0'
    )
    db_session.add(model)
    db_session.commit()
    
    return model

@pytest.fixture
def mock_training_data():
    """Generate mock training data."""
    np.random.seed(42)
    n_samples = 1000
    
    # Generate features
    feature_names = [
        'amount_normalized', 'currency_risk_score', 'merchant_risk_score',
        'hour_of_day', 'day_of_week', 'is_weekend', 'is_business_hours',
        'user_transaction_count_24h', 'user_avg_transaction_24h',
        'user_transaction_frequency_1h', 'user_distinct_merchants_24h',
        'user_distinct_countries_24h', 'user_account_age_days',
        'device_transaction_count_24h', 'device_distinct_users_24h',
        'device_risk_score', 'country_risk_score', 'is_vpn',
        'location_velocity_flag', 'unusual_location_flag'
    ]
    
    # Generate realistic feature data
    data = {
        'transaction_id': list(range(1, n_samples + 1)),
        'amount_normalized': np.random.lognormal(4, 1, n_samples),
        'currency_risk_score': np.random.beta(2, 5, n_samples),
        'merchant_risk_score': np.random.beta(2, 5, n_samples),
        'hour_of_day': np.random.randint(0, 24, n_samples),
        'day_of_week': np.random.randint(0, 7, n_samples),
        'is_weekend': np.random.binomial(1, 0.3, n_samples),
        'is_business_hours': np.random.binomial(1, 0.4, n_samples),
        'user_transaction_count_24h': np.random.poisson(3, n_samples),
        'user_avg_transaction_24h': np.random.lognormal(4, 0.5, n_samples),
        'user_transaction_frequency_1h': np.random.exponential(0.5, n_samples),
        'user_distinct_merchants_24h': np.random.poisson(2, n_samples),
        'user_distinct_countries_24h': np.random.poisson(1, n_samples),
        'user_account_age_days': np.random.exponential(365, n_samples),
        'device_transaction_count_24h': np.random.poisson(2, n_samples),
        'device_distinct_users_24h': np.random.poisson(1, n_samples),
        'device_risk_score': np.random.beta(2, 5, n_samples),
        'country_risk_score': np.random.beta(2, 8, n_samples),
        'is_vpn': np.random.binomial(1, 0.1, n_samples),
        'location_velocity_flag': np.random.binomial(1, 0.05, n_samples),
        'unusual_location_flag': np.random.binomial(1, 0.15, n_samples)
    }
    
    features_df = pd.DataFrame(data)
    
    # Generate labels with some correlation to features
    fraud_probability = (
        0.1 * features_df['merchant_risk_score'] +
        0.1 * features_df['device_risk_score'] +
        0.05 * features_df['is_vpn'] +
        0.05 * np.random.beta(1, 10, n_samples)
    )
    
    labels = pd.Series(np.random.binomial(1, fraud_probability, n_samples), name='is_fraud')
    
    return features_df, labels

@pytest.fixture
def mock_transaction_data():
    """Generate mock transaction data for API testing."""
    return {
        'user_id': 1,
        'amount': 150.75,
        'currency': 'USD',
        'merchant_category': 'electronics',
        'device_id': 'device_456',
        'ip_address': '10.0.0.1',
        'timestamp': datetime.utcnow().isoformat(),
        'raw_payload': {
            'merchant_name': 'Electronics Store',
            'payment_method': 'credit_card',
            'card_last_four': '1234'
        }
    }