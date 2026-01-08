"""Feature engineering pipeline for fraud detection."""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Any, List, Tuple, Optional
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler, LabelEncoder, OneHotEncoder
from sklearn.compose import ColumnTransformer
import joblib
import json
import hashlib
from contextlib import contextmanager

from app.utils.helpers import (
    normalize_currency_amount, extract_location_from_ip,
    get_business_hours_flag, get_weekend_flag, safe_float_conversion
)
from app.utils.logging import get_logger
from app.models.database import Transaction, User
from sqlalchemy.orm import Session

logger = get_logger(__name__)

class FeatureConfig:
    """Configuration for feature engineering."""
    
    VERSION = "1.0.0"
    
    # Feature categories
    TRANSACTION_FEATURES = [
        'amount_normalized', 'currency_risk_score', 'merchant_risk_score',
        'hour_of_day', 'day_of_week', 'is_weekend', 'is_business_hours'
    ]
    
    USER_FEATURES = [
        'user_transaction_count_24h', 'user_avg_transaction_24h',
        'user_transaction_frequency_1h', 'user_distinct_merchants_24h',
        'user_distinct_countries_24h', 'user_account_age_days'
    ]
    
    DEVICE_FEATURES = [
        'device_transaction_count_24h', 'device_distinct_users_24h',
        'device_risk_score'
    ]
    
    LOCATION_FEATURES = [
        'country_risk_score', 'is_vpn', 'location_velocity_flag',
        'unusual_location_flag'
    ]
    
    ALL_FEATURES = TRANSACTION_FEATURES + USER_FEATURES + DEVICE_FEATURES + LOCATION_FEATURES

class HistoricalFeatureExtractor:
    """Extract historical features for training data."""
    
    def __init__(self, db_session: Session):
        self.db_session = db_session
        self.logger = get_logger(__name__)
    
    def extract_user_features(self, user_id: int, current_timestamp: datetime,
                            window_hours: int = 24) -> Dict[str, float]:
        """Extract user-based features from historical data."""
        window_start = current_timestamp - timedelta(hours=window_hours)
        
        # Query user's historical transactions
        historical_transactions = self.db_session.query(Transaction).filter(
            Transaction.user_id == user_id,
            Transaction.timestamp >= window_start,
            Transaction.timestamp < current_timestamp
        ).all()
        
        if not historical_transactions:
            return {
                'user_transaction_count_24h': 0.0,
                'user_avg_transaction_24h': 0.0,
                'user_transaction_frequency_1h': 0.0,
                'user_distinct_merchants_24h': 0.0,
                'user_distinct_countries_24h': 0.0,
                'user_account_age_days': 0.0
            }
        
        # Calculate features
        amounts = [float(t.amount) for t in historical_transactions]
        merchants = [t.merchant_category for t in historical_transactions]
        
        # Get user creation date
        user = self.db_session.query(User).filter(User.id == user_id).first()
        account_age = (current_timestamp - user.created_at).days if user else 0
        
        # Location extraction (simplified)
        countries = []
        for t in historical_transactions:
            location = extract_location_from_ip(t.ip_address or '')
            countries.append(location.get('country', 'Unknown'))
        
        return {
            'user_transaction_count_24h': float(len(historical_transactions)),
            'user_avg_transaction_24h': np.mean(amounts) if amounts else 0.0,
            'user_transaction_frequency_1h': len(historical_transactions) / 24.0,
            'user_distinct_merchants_24h': float(len(set(merchants))),
            'user_distinct_countries_24h': float(len(set(countries))),
            'user_account_age_days': float(account_age)
        }
    
    def extract_device_features(self, device_id: str, current_timestamp: datetime,
                              window_hours: int = 24) -> Dict[str, float]:
        """Extract device-based features."""
        if not device_id:
            return {
                'device_transaction_count_24h': 0.0,
                'device_distinct_users_24h': 0.0,
                'device_risk_score': 0.5  # Neutral risk
            }
        
        window_start = current_timestamp - timedelta(hours=window_hours)
        
        # Query device's historical transactions
        device_transactions = self.db_session.query(Transaction).filter(
            Transaction.device_id == device_id,
            Transaction.timestamp >= window_start,
            Transaction.timestamp < current_timestamp
        ).all()
        
        user_ids = [t.user_id for t in device_transactions]
        
        # Simple risk scoring based on usage patterns
        device_risk = min(len(set(user_ids)) / 5.0, 1.0)  # Risk increases with multiple users
        
        return {
            'device_transaction_count_24h': float(len(device_transactions)),
            'device_distinct_users_24h': float(len(set(user_ids))),
            'device_risk_score': device_risk
        }

class RealTimeFeatureExtractor:
    """Extract features for real-time inference."""
    
    def __init__(self, db_session: Session):
        self.db_session = db_session
        self.logger = get_logger(__name__)
    
    def extract_transaction_features(self, transaction_data: Dict[str, Any]) -> Dict[str, float]:
        """Extract transaction-specific features."""
        timestamp = transaction_data['timestamp']
        amount = float(transaction_data['amount'])
        currency = transaction_data['currency']
        
        # Normalize amount to USD
        amount_normalized = normalize_currency_amount(amount, currency)
        
        # Time-based features
        hour_of_day = timestamp.hour
        day_of_week = timestamp.weekday()
        is_weekend = get_weekend_flag(timestamp)
        is_business_hours = get_business_hours_flag(timestamp)
        
        # Risk scores (simplified)
        currency_risk = self._get_currency_risk_score(currency)
        merchant_risk = self._get_merchant_risk_score(transaction_data['merchant_category'])
        
        return {
            'amount_normalized': amount_normalized,
            'currency_risk_score': currency_risk,
            'merchant_risk_score': merchant_risk,
            'hour_of_day': float(hour_of_day),
            'day_of_week': float(day_of_week),
            'is_weekend': float(is_weekend),
            'is_business_hours': float(is_business_hours)
        }
    
    def extract_location_features(self, ip_address: str, user_id: int,
                                current_timestamp: datetime) -> Dict[str, float]:
        """Extract location-based features."""
        location_info = extract_location_from_ip(ip_address or '')
        
        # Get user's typical locations
        typical_countries = self._get_user_typical_locations(user_id, current_timestamp)
        
        country_risk = self._get_country_risk_score(location_info.get('country', 'Unknown'))
        unusual_location = location_info.get('country') not in typical_countries
        
        return {
            'country_risk_score': country_risk,
            'is_vpn': float(location_info.get('is_vpn', False)),
            'location_velocity_flag': 0.0,  # Simplified implementation
            'unusual_location_flag': float(unusual_location)
        }
    
    def _get_currency_risk_score(self, currency: str) -> float:
        """Get risk score for currency (simplified)."""
        high_risk_currencies = ['BTC', 'ETH', 'XMR']  # Crypto
        medium_risk_currencies = ['RUB', 'CHF', 'SEK']
        
        if currency in high_risk_currencies:
            return 1.0
        elif currency in medium_risk_currencies:
            return 0.7
        else:
            return 0.3
    
    def _get_merchant_risk_score(self, merchant_category: str) -> float:
        """Get risk score for merchant category."""
        high_risk_categories = ['gambling', 'crypto', 'adult', 'pharmacy']
        medium_risk_categories = ['electronics', 'jewelry', 'travel']
        
        merchant_lower = merchant_category.lower()
        
        if any(risk_cat in merchant_lower for risk_cat in high_risk_categories):
            return 1.0
        elif any(risk_cat in merchant_lower for risk_cat in medium_risk_categories):
            return 0.6
        else:
            return 0.2
    
    def _get_country_risk_score(self, country: str) -> float:
        """Get risk score for country."""
        high_risk_countries = ['Unknown', 'CN', 'RU', 'IR', 'KP']
        medium_risk_countries = ['BR', 'IN', 'PK', 'BD']
        
        if country in high_risk_countries:
            return 1.0
        elif country in medium_risk_countries:
            return 0.6
        else:
            return 0.2
    
    def _get_user_typical_locations(self, user_id: int, current_timestamp: datetime,
                                  lookback_days: int = 30) -> List[str]:
        """Get user's typical countries."""
        lookback_start = current_timestamp - timedelta(days=lookback_days)
        
        historical_transactions = self.db_session.query(Transaction).filter(
            Transaction.user_id == user_id,
            Transaction.timestamp >= lookback_start,
            Transaction.timestamp < current_timestamp
        ).limit(100).all()  # Limit for performance
        
        countries = []
        for t in historical_transactions:
            location = extract_location_from_ip(t.ip_address or '')
            countries.append(location.get('country', 'Unknown'))
        
        from collections import Counter
        # Return countries that appear in >10% of transactions
        country_counts = Counter(countries)
        total_transactions = len(countries)
        return [country for country, count in country_counts.items() 
                if count / total_transactions > 0.1]

class FeatureEngineeringPipeline:
    """Complete feature engineering pipeline ensuring training-inference parity."""
    
    def __init__(self, db_session: Session):
        self.db_session = db_session
        self.historical_extractor = HistoricalFeatureExtractor(db_session)
        self.realtime_extractor = RealTimeFeatureExtractor(db_session)
        self.config = FeatureConfig()
        self.logger = get_logger(__name__)
        
        # Preprocessing pipeline
        self.preprocessing_pipeline = None
        self._build_preprocessing_pipeline()
    
    def _build_preprocessing_pipeline(self):
        """Build sklearn preprocessing pipeline."""
        # Categorical features that need encoding
        categorical_features = []
        
        # Numerical features that need scaling
        numerical_features = self.config.ALL_FEATURES
        
        # Create preprocessing pipeline
        preprocessor = ColumnTransformer(
            transformers=[
                ('num', StandardScaler(), numerical_features),
                # Add categorical preprocessing if needed
            ],
            remainder='passthrough'
        )
        
        self.preprocessing_pipeline = Pipeline([
            ('preprocessor', preprocessor)
        ])
    
    def extract_features_for_training(self, transactions: List[Transaction]) -> pd.DataFrame:
        """Extract features for training data with historical context."""
        feature_rows = []
        
        for transaction in transactions:
            try:
                # Extract all feature types
                transaction_features = self.realtime_extractor.extract_transaction_features({
                    'timestamp': transaction.timestamp,
                    'amount': transaction.amount,
                    'currency': transaction.currency,
                    'merchant_category': transaction.merchant_category
                })
                
                user_features = self.historical_extractor.extract_user_features(
                    transaction.user_id, transaction.timestamp
                )
                
                device_features = self.historical_extractor.extract_device_features(
                    transaction.device_id, transaction.timestamp
                )
                
                location_features = self.realtime_extractor.extract_location_features(
                    transaction.ip_address, transaction.user_id, transaction.timestamp
                )
                
                # Combine features
                all_features = {
                    'transaction_id': transaction.id,
                    **transaction_features,
                    **user_features,
                    **device_features,
                    **location_features
                }
                
                feature_rows.append(all_features)
                
            except Exception as e:
                self.logger.error(f"Error extracting features for transaction {transaction.id}: {e}")
                continue
        
        return pd.DataFrame(feature_rows)
    
    def extract_features_for_inference(self, transaction_data: Dict[str, Any]) -> np.ndarray:
        """Extract features for single transaction inference."""
        try:
            # Extract all feature types
            transaction_features = self.realtime_extractor.extract_transaction_features(transaction_data)
            
            user_features = self.historical_extractor.extract_user_features(
                transaction_data['user_id'], transaction_data['timestamp']
            )
            
            device_features = self.historical_extractor.extract_device_features(
                transaction_data.get('device_id'), transaction_data['timestamp']
            )
            
            location_features = self.realtime_extractor.extract_location_features(
                transaction_data.get('ip_address'), 
                transaction_data['user_id'], 
                transaction_data['timestamp']
            )
            
            # Combine features in correct order
            all_features = {
                **transaction_features,
                **user_features,
                **device_features,
                **location_features
            }
            
            # Convert to DataFrame for pipeline compatibility
            feature_df = pd.DataFrame([all_features])
            feature_df = feature_df[self.config.ALL_FEATURES]  # Ensure correct order
            
            # Apply preprocessing if pipeline is fitted
            if self.preprocessing_pipeline and hasattr(self.preprocessing_pipeline, 'named_steps'):
                return self.preprocessing_pipeline.transform(feature_df)
            else:
                return feature_df.values
                
        except Exception as e:
            self.logger.error(f"Error in feature extraction for inference: {e}")
            # Return zero vector as fallback
            return np.zeros((1, len(self.config.ALL_FEATURES)))
    
    def fit_preprocessing_pipeline(self, training_features: pd.DataFrame) -> None:
        """Fit the preprocessing pipeline on training data."""
        feature_columns = [col for col in training_features.columns if col in self.config.ALL_FEATURES]
        X = training_features[feature_columns]
        
        self.preprocessing_pipeline.fit(X)
        self.logger.info("Preprocessing pipeline fitted successfully")
    
    def save_pipeline(self, filepath: str) -> None:
        """Save the fitted preprocessing pipeline."""
        pipeline_data = {
            'pipeline': self.preprocessing_pipeline,
            'feature_config': self.config.__dict__,
            'version': self.config.VERSION
        }
        joblib.dump(pipeline_data, filepath)
        self.logger.info(f"Feature pipeline saved to {filepath}")
    
    def load_pipeline(self, filepath: str) -> None:
        """Load a fitted preprocessing pipeline."""
        pipeline_data = joblib.load(filepath)
        self.preprocessing_pipeline = pipeline_data['pipeline']
        
        # Verify version compatibility
        if pipeline_data.get('version') != self.config.VERSION:
            self.logger.warning(f"Pipeline version mismatch: {pipeline_data.get('version')} vs {self.config.VERSION}")
        
        self.logger.info(f"Feature pipeline loaded from {filepath}")
    
    def get_feature_schema_hash(self) -> str:
        """Get hash of current feature schema for version tracking."""
        schema_data = {
            'version': self.config.VERSION,
            'features': sorted(self.config.ALL_FEATURES)
        }
        return hashlib.md5(json.dumps(schema_data, sort_keys=True).encode()).hexdigest()