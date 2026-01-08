"""Unit tests for feature engineering pipeline."""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from app.preprocessing.feature_engineering import (
    FeatureEngineeringPipeline, FeatureConfig,
    HistoricalFeatureExtractor, RealTimeFeatureExtractor
)
from app.validation.feature_validation import FeatureValidator

class TestFeatureConfig:
    """Test FeatureConfig class."""
    
    def test_feature_config_constants(self):
        """Test that feature config has expected constants."""
        config = FeatureConfig()
        
        assert hasattr(config, 'VERSION')
        assert hasattr(config, 'ALL_FEATURES')
        assert len(config.ALL_FEATURES) > 0
        
        # Check that all feature categories are included
        assert all(f in config.ALL_FEATURES for f in config.TRANSACTION_FEATURES)
        assert all(f in config.ALL_FEATURES for f in config.USER_FEATURES)
        assert all(f in config.ALL_FEATURES for f in config.DEVICE_FEATURES)
        assert all(f in config.ALL_FEATURES for f in config.LOCATION_FEATURES)

class TestRealTimeFeatureExtractor:
    """Test RealTimeFeatureExtractor class."""
    
    def test_extract_transaction_features(self, db_session):
        """Test transaction feature extraction."""
        extractor = RealTimeFeatureExtractor(db_session)
        
        transaction_data = {
            'timestamp': datetime.utcnow(),
            'amount': 100.0,
            'currency': 'USD',
            'merchant_category': 'retail'
        }
        
        features = extractor.extract_transaction_features(transaction_data)
        
        # Check that all expected features are present
        expected_features = [
            'amount_normalized', 'currency_risk_score', 'merchant_risk_score',
            'hour_of_day', 'day_of_week', 'is_weekend', 'is_business_hours'
        ]
        
        for feature in expected_features:
            assert feature in features
            assert isinstance(features[feature], (int, float))
    
    def test_extract_location_features(self, db_session):
        """Test location feature extraction."""
        extractor = RealTimeFeatureExtractor(db_session)
        
        features = extractor.extract_location_features(
            ip_address='192.168.1.1',
            user_id=1,
            current_timestamp=datetime.utcnow()
        )
        
        expected_features = [
            'country_risk_score', 'is_vpn', 'location_velocity_flag', 'unusual_location_flag'
        ]
        
        for feature in expected_features:
            assert feature in features
            assert isinstance(features[feature], (int, float))
    
    def test_currency_risk_score(self, db_session):
        """Test currency risk scoring."""
        extractor = RealTimeFeatureExtractor(db_session)
        
        # Test different currencies
        assert extractor._get_currency_risk_score('USD') < extractor._get_currency_risk_score('BTC')
        assert extractor._get_currency_risk_score('EUR') < extractor._get_currency_risk_score('XMR')
    
    def test_merchant_risk_score(self, db_session):
        """Test merchant category risk scoring."""
        extractor = RealTimeFeatureExtractor(db_session)
        
        # Test different merchant categories
        assert extractor._get_merchant_risk_score('grocery') < extractor._get_merchant_risk_score('gambling')
        assert extractor._get_merchant_risk_score('retail') < extractor._get_merchant_risk_score('crypto')

class TestHistoricalFeatureExtractor:
    """Test HistoricalFeatureExtractor class."""
    
    def test_extract_user_features_no_history(self, db_session, sample_user):
        """Test user feature extraction with no historical data."""
        extractor = HistoricalFeatureExtractor(db_session)
        
        features = extractor.extract_user_features(
            sample_user.id, 
            datetime.utcnow()
        )
        
        # Should return zero values for all features
        expected_features = [
            'user_transaction_count_24h', 'user_avg_transaction_24h',
            'user_transaction_frequency_1h', 'user_distinct_merchants_24h',
            'user_distinct_countries_24h', 'user_account_age_days'
        ]
        
        for feature in expected_features:
            assert feature in features
            assert features[feature] == 0.0 or feature == 'user_account_age_days'
    
    def test_extract_device_features_no_device(self, db_session):
        """Test device feature extraction with no device ID."""
        extractor = HistoricalFeatureExtractor(db_session)
        
        features = extractor.extract_device_features(
            None, datetime.utcnow()
        )
        
        expected_features = [
            'device_transaction_count_24h', 'device_distinct_users_24h', 'device_risk_score'
        ]
        
        for feature in expected_features:
            assert feature in features
            # Risk score should be neutral (0.5) for unknown device
            if feature == 'device_risk_score':
                assert features[feature] == 0.5
            else:
                assert features[feature] == 0.0

class TestFeatureEngineeringPipeline:
    """Test FeatureEngineeringPipeline class."""
    
    def test_pipeline_initialization(self, db_session):
        """Test pipeline initialization."""
        pipeline = FeatureEngineeringPipeline(db_session)
        
        assert pipeline.db_session is not None
        assert pipeline.preprocessing_pipeline is not None
        assert pipeline.config is not None
        assert isinstance(pipeline.config, FeatureConfig)
    
    def test_extract_features_for_inference(self, db_session, sample_user):
        """Test feature extraction for inference."""
        pipeline = FeatureEngineeringPipeline(db_session)
        
        transaction_data = {
            'id': 1,
            'user_id': sample_user.id,
            'amount': 100.0,
            'currency': 'USD',
            'merchant_category': 'retail',
            'device_id': 'test_device',
            'ip_address': '192.168.1.1',
            'timestamp': datetime.utcnow(),
            'raw_payload': {}
        }
        
        features = pipeline.extract_features_for_inference(transaction_data)
        
        # Should return numpy array with correct shape
        assert isinstance(features, np.ndarray)
        assert features.shape[1] == len(pipeline.config.ALL_FEATURES)
    
    def test_get_feature_schema_hash(self, db_session):
        """Test feature schema hash generation."""
        pipeline = FeatureEngineeringPipeline(db_session)
        
        hash1 = pipeline.get_feature_schema_hash()
        hash2 = pipeline.get_feature_schema_hash()
        
        # Hash should be consistent
        assert hash1 == hash2
        assert len(hash1) == 32  # MD5 hash length

class TestFeatureValidator:
    """Test FeatureValidator class."""
    
    @pytest.fixture
    def validator(self, db_session):
        """Create feature validator for testing."""
        pipeline = FeatureEngineeringPipeline(db_session)
        return FeatureValidator(pipeline)
    
    def test_validate_feature_ranges_valid_data(self, validator, mock_training_data):
        """Test feature range validation with valid data."""
        features_df, _ = mock_training_data
        
        validation_results = validator.validate_feature_ranges(features_df)
        
        assert validation_results['valid'] is True
        assert len(validation_results['issues']) == 0
        assert 'feature_stats' in validation_results
    
    def test_validate_feature_ranges_with_nulls(self, validator):
        """Test feature range validation with null values."""
        # Create data with null values
        features_df = pd.DataFrame({
            'transaction_id': [1, 2, 3],
            'amount_normalized': [100.0, np.nan, 200.0],
            'fraud_probability': [0.5, 0.8, 0.3]
        })
        
        validation_results = validator.validate_feature_ranges(features_df)
        
        assert validation_results['valid'] is False
        assert any('null values' in issue for issue in validation_results['issues'])
    
    def test_validate_feature_ranges_out_of_bounds(self, validator):
        """Test feature range validation with out-of-bounds values."""
        # Create data with invalid probability values
        features_df = pd.DataFrame({
            'transaction_id': [1, 2, 3],
            'fraud_probability': [0.5, 1.5, -0.1],  # Invalid: > 1 and < 0
            'risk_score': [0.3, 0.7, 0.9]
        })
        
        validation_results = validator.validate_feature_ranges(features_df)
        
        assert validation_results['valid'] is False
        assert any('outside [0,1] range' in issue for issue in validation_results['issues'])
    
    def test_generate_feature_report(self, validator, mock_training_data):
        """Test feature report generation."""
        features_df, _ = mock_training_data
        
        report = validator.generate_feature_report(features_df)
        
        assert 'summary' in report
        assert 'features' in report
        assert 'validation_results' in report
        
        # Check summary
        assert report['summary']['total_samples'] == len(features_df)
        assert report['summary']['total_features'] > 0
        
        # Check feature analysis
        feature_name = 'amount_normalized'
        if feature_name in report['features']:
            feature_stats = report['features'][feature_name]
            assert 'mean' in feature_stats
            assert 'std' in feature_stats
            assert 'min' in feature_stats
            assert 'max' in feature_stats
            assert 'percentiles' in feature_stats

class TestFeatureParity:
    """Test feature parity between training and inference."""
    
    def test_feature_consistency(self, db_session, mock_training_data):
        """Test that features are consistent between training and inference."""
        pipeline = FeatureEngineeringPipeline(db_session)
        validator = FeatureValidator(pipeline)
        
        # Create mock transaction data
        transaction_data = [{
            'id': 1,
            'user_id': 1,
            'amount': 100.0,
            'currency': 'USD',
            'merchant_category': 'retail',
            'device_id': 'test_device',
            'ip_address': '192.168.1.1',
            'timestamp': datetime.utcnow(),
            'raw_payload': {}
        }]
        
        # Note: This test would need more setup to work properly
        # as it requires actual database data for historical features
        # In a real scenario, you'd populate the database with test data first
    
    def test_feature_schema_consistency(self, db_session):
        """Test that feature schema is consistent."""
        pipeline1 = FeatureEngineeringPipeline(db_session)
        pipeline2 = FeatureEngineeringPipeline(db_session)
        
        hash1 = pipeline1.get_feature_schema_hash()
        hash2 = pipeline2.get_feature_schema_hash()
        
        assert hash1 == hash2