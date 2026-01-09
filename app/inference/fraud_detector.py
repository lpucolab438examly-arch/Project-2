"""Real-time fraud detection inference engine."""

import joblib
import numpy as np
import time
import json
import os
from datetime import datetime
from typing import Dict, Any, Optional, Tuple
from threading import Lock
import pickle

from app.utils.logging import get_logger, ModelLogger
from app.utils.helpers import measure_execution_time, safe_float_conversion
from app.preprocessing.feature_engineering import FeatureEngineeringPipeline
from app.models.database import ModelRegistry, Prediction, AuditLog
from app.utils.database import DatabaseManager

logger = get_logger(__name__)

class ModelLoadError(Exception):
    """Exception raised when model loading fails."""
    pass

class InferenceError(Exception):
    """Exception raised during inference."""
    pass

class ModelManager:
    """Manages loading, caching, and switching of ML models."""
    
    def __init__(self, db_manager: DatabaseManager, artifacts_path: str):
        self.db_manager = db_manager
        self.artifacts_path = artifacts_path
        self.logger = get_logger(__name__)
        
        # Model cache
        self._current_model = None
        self._current_model_version = None
        self._current_preprocessing_pipeline = None
        self._model_metadata = None
        self._load_lock = Lock()
        
        # Performance tracking
        self._inference_count = 0
        self._total_inference_time = 0.0
        self._last_model_check = None
    
    def initialize(self) -> bool:
        """Initialize the model manager by loading the active model."""
        try:
            self.logger.info("Initializing model manager...")
            success = self.load_active_model()
            if success:
                self.logger.info(f"Model manager initialized with model: {self._current_model_version}")
            else:
                self.logger.error("Failed to initialize model manager - no active model found")
            return success
        except Exception as e:
            self.logger.error(f"Error initializing model manager: {e}")
            return False
    
    def load_active_model(self) -> bool:
        """Load the currently active model from the database."""
        with self._load_lock:
            try:
                with self.db_manager.get_session() as session:
                    # Find active model
                    active_model = session.query(ModelRegistry).filter(
                        ModelRegistry.is_active == True
                    ).first()
                    
                    if not active_model:
                        self.logger.warning("No active model found in registry")
                        return False
                    
                    # Check if this is the same model already loaded
                    if self._current_model_version == active_model.model_version:
                        self.logger.debug(f"Model {active_model.model_version} already loaded")
                        return True
                    
                    # Load new model
                    self.logger.info(f"Loading model: {active_model.model_version}")
                    
                    # Load the trained model
                    if not os.path.exists(active_model.model_path):
                        raise ModelLoadError(f"Model file not found: {active_model.model_path}")
                    
                    model = joblib.load(active_model.model_path)
                    
                    # Load preprocessing pipeline
                    if not os.path.exists(active_model.preprocessing_path):
                        raise ModelLoadError(f"Preprocessing file not found: {active_model.preprocessing_path}")
                    
                    preprocessing_data = joblib.load(active_model.preprocessing_path)
                    preprocessing_pipeline = preprocessing_data['pipeline']
                    
                    # Validate model
                    self._validate_model(model, preprocessing_pipeline)
                    
                    # Update current model
                    self._current_model = model
                    self._current_model_version = active_model.model_version
                    self._current_preprocessing_pipeline = preprocessing_pipeline
                    self._model_metadata = {
                        'model_type': active_model.model_type,
                        'model_version': active_model.model_version,
                        'created_at': active_model.created_at.isoformat(),
                        'metrics': active_model.metrics,
                        'feature_schema_version': active_model.feature_schema_version
                    }
                    
                    self.logger.info(f"Successfully loaded model: {active_model.model_version}")
                    return True
                    
            except Exception as e:
                self.logger.error(f"Error loading active model: {e}")
                return False
    
    def _validate_model(self, model, preprocessing_pipeline):
        """Validate that a model is properly loaded and functional."""
        try:
            # Check if model has required methods
            if not hasattr(model, 'predict_proba'):
                raise ModelLoadError("Model does not have predict_proba method")
            
            # Test with dummy data
            dummy_features = np.zeros((1, len(preprocessing_pipeline.feature_names_in_)))
            dummy_prediction = model.predict_proba(dummy_features)
            
            if dummy_prediction.shape[1] != 2:
                raise ModelLoadError("Model should output probability for binary classification")
                
        except Exception as e:
            raise ModelLoadError(f"Model validation failed: {e}")
    
    def get_current_model_info(self) -> Optional[Dict[str, Any]]:
        """Get information about the currently loaded model."""
        if self._model_metadata:
            return {
                **self._model_metadata,
                'inference_count': self._inference_count,
                'average_inference_time_ms': (
                    self._total_inference_time / self._inference_count * 1000
                    if self._inference_count > 0 else 0
                ),
                'is_loaded': self._current_model is not None
            }
        return None
    
    def is_model_loaded(self) -> bool:
        """Check if a model is currently loaded."""
        return self._current_model is not None
    
    def predict_fraud_probability(self, features: np.ndarray) -> Tuple[float, bool]:
        """Predict fraud probability for given features."""
        if not self.is_model_loaded():
            raise InferenceError("No model loaded")
        
        start_time = time.time()
        
        try:
            # Get prediction probabilities
            probabilities = self._current_model.predict_proba(features)
            fraud_probability = float(probabilities[0, 1])  # Probability of fraud (class 1)
            
            # Binary prediction (threshold at 0.5)
            prediction_label = fraud_probability > 0.5
            
            # Update performance metrics
            inference_time = time.time() - start_time
            self._inference_count += 1
            self._total_inference_time += inference_time
            
            return fraud_probability, prediction_label
            
        except Exception as e:
            raise InferenceError(f"Prediction failed: {e}")
    
    def refresh_model_if_needed(self, check_interval_minutes: int = 5) -> bool:
        """Check and reload model if a new active model is available."""
        current_time = datetime.utcnow()
        
        # Check if enough time has passed since last check
        if (self._last_model_check and 
            (current_time - self._last_model_check).total_seconds() < check_interval_minutes * 60):
            return False
        
        self._last_model_check = current_time
        
        try:
            with self.db_manager.get_session() as session:
                # Check for new active model
                active_model = session.query(ModelRegistry).filter(
                    ModelRegistry.is_active == True
                ).first()
                
                if (active_model and 
                    active_model.model_version != self._current_model_version):
                    self.logger.info(f"New active model detected: {active_model.model_version}")
                    return self.load_active_model()
                    
        except Exception as e:
            self.logger.error(f"Error checking for model updates: {e}")
            
        return False

class FraudDetectionInference:
    """High-level fraud detection inference service."""
    
    def __init__(self, db_manager: DatabaseManager, artifacts_path: str):
        self.db_manager = db_manager
        self.model_manager = ModelManager(db_manager, artifacts_path)
        self.feature_pipeline = None
        self.logger = get_logger(__name__)
        self.model_logger = ModelLogger()
        
        # Configuration
        self.fraud_threshold = 0.5
        self.high_risk_threshold = 0.8
        
    def initialize(self) -> bool:
        """Initialize the inference engine."""
        self.logger.info("Initializing fraud detection inference engine...")
        
        # Initialize model manager
        if not self.model_manager.initialize():
            self.logger.error("Failed to initialize model manager")
            return False
        
        # Initialize feature pipeline
        try:
            with self.db_manager.get_session() as session:
                self.feature_pipeline = FeatureEngineeringPipeline(session)
        except Exception as e:
            self.logger.error(f"Failed to initialize feature pipeline: {e}")
            return False
        
        self.logger.info("Fraud detection inference engine initialized successfully")
        return True
    
    @measure_execution_time
    def predict_fraud(self, transaction_data: Dict[str, Any]) -> Dict[str, Any]:
        """Perform fraud detection on a transaction."""
        
        if not self.model_manager.is_model_loaded():
            raise InferenceError("Inference engine not properly initialized")
        
        start_time = time.time()
        
        try:
            # Extract features
            feature_start = time.time()
            
            # Create a new DB session for feature extraction
            with self.db_manager.get_session() as session:
                feature_pipeline = FeatureEngineeringPipeline(session)
                features = feature_pipeline.extract_features_for_inference(transaction_data)
            
            feature_time = (time.time() - feature_start) * 1000
            
            # Validate features
            if features is None or len(features) == 0:
                raise InferenceError("Feature extraction failed")
            
            # Log feature extraction
            self.model_logger.log_feature_extraction(
                transaction_data.get('id', 0),
                features.shape[1] if len(features.shape) > 1 else len(features),
                feature_time
            )
            
            # Predict fraud probability
            prediction_start = time.time()
            fraud_probability, prediction_label = self.model_manager.predict_fraud_probability(features)
            prediction_time = (time.time() - prediction_start) * 1000
            
            # Calculate confidence score
            confidence_score = abs(fraud_probability - 0.5) * 2  # Range 0-1
            
            # Determine risk level
            risk_level = self._determine_risk_level(fraud_probability)
            
            # Total inference time
            total_time = (time.time() - start_time) * 1000
            
            # Log prediction
            self.model_logger.log_prediction(
                transaction_data.get('id', 0),
                self.model_manager._current_model_version,
                fraud_probability,
                prediction_label,
                total_time
            )
            
            # Prepare result
            result = {
                'fraud_probability': round(fraud_probability, 4),
                'prediction_label': prediction_label,
                'confidence_score': round(confidence_score, 4),
                'risk_level': risk_level,
                'model_version': self.model_manager._current_model_version,
                'inference_time_ms': round(total_time, 2),
                'feature_extraction_time_ms': round(feature_time, 2),
                'model_prediction_time_ms': round(prediction_time, 2),
                'timestamp': datetime.utcnow().isoformat()
            }
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error in fraud prediction: {e}")
            raise InferenceError(f"Fraud prediction failed: {e}")
    
    def _determine_risk_level(self, fraud_probability: float) -> str:
        """Determine risk level based on fraud probability."""
        if fraud_probability >= self.high_risk_threshold:
            return 'HIGH'
        elif fraud_probability >= self.fraud_threshold:
            return 'MEDIUM'
        elif fraud_probability >= 0.25:
            return 'LOW'
        else:
            return 'MINIMAL'
    
    def save_prediction(self, transaction_id: int, prediction_result: Dict[str, Any]) -> int:
        """Save prediction result to database."""
        try:
            with self.db_manager.get_session() as session:
                prediction = Prediction(
                    transaction_id=transaction_id,
                    model_version=prediction_result['model_version'],
                    fraud_probability=prediction_result['fraud_probability'],
                    prediction_label=prediction_result['prediction_label'],
                    confidence_score=prediction_result.get('confidence_score'),
                    inference_time_ms=int(prediction_result.get('inference_time_ms', 0))
                )
                
                session.add(prediction)
                session.flush()  # Get the ID
                prediction_id = prediction.id
                session.commit()
                
                self.logger.info(f"Prediction saved with ID: {prediction_id}")
                return prediction_id
                
        except Exception as e:
            self.logger.error(f"Error saving prediction: {e}")
            raise
    
    def batch_predict(self, transactions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Perform batch fraud detection on multiple transactions."""
        results = []
        
        for transaction in transactions:
            try:
                result = self.predict_fraud(transaction)
                result['transaction_id'] = transaction.get('id')
                results.append(result)
            except Exception as e:
                self.logger.error(f"Error predicting fraud for transaction {transaction.get('id')}: {e}")
                results.append({
                    'transaction_id': transaction.get('id'),
                    'error': str(e),
                    'fraud_probability': None,
                    'prediction_label': None
                })
        
        return results
    
    def get_model_status(self) -> Dict[str, Any]:
        """Get current model status and performance metrics."""
        model_info = self.model_manager.get_current_model_info()
        
        return {
            'is_initialized': self.feature_pipeline is not None,
            'model_loaded': self.model_manager.is_model_loaded(),
            'model_info': model_info,
            'fraud_threshold': self.fraud_threshold,
            'high_risk_threshold': self.high_risk_threshold,
            'status': 'healthy' if model_info and model_info['is_loaded'] else 'unhealthy'
        }
    
    def refresh_model(self) -> bool:
        """Manually refresh the model if a new version is available."""
        return self.model_manager.refresh_model_if_needed(check_interval_minutes=0)

class InferencePerformanceMonitor:
    """Monitor inference performance and detect issues."""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self.recent_predictions = []
        self.max_history = 1000
        
    def record_prediction(self, inference_time_ms: float, fraud_probability: float):
        """Record a prediction for performance monitoring."""
        self.recent_predictions.append({
            'timestamp': datetime.utcnow(),
            'inference_time_ms': inference_time_ms,
            'fraud_probability': fraud_probability
        })
        
        # Keep only recent predictions
        if len(self.recent_predictions) > self.max_history:
            self.recent_predictions = self.recent_predictions[-self.max_history:]
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics."""
        if not self.recent_predictions:
            return {'status': 'no_data'}
        
        inference_times = [p['inference_time_ms'] for p in self.recent_predictions]
        fraud_probabilities = [p['fraud_probability'] for p in self.recent_predictions]
        
        return {
            'total_predictions': len(self.recent_predictions),
            'avg_inference_time_ms': np.mean(inference_times),
            'p95_inference_time_ms': np.percentile(inference_times, 95),
            'max_inference_time_ms': np.max(inference_times),
            'avg_fraud_probability': np.mean(fraud_probabilities),
            'fraud_rate': np.mean([p > 0.5 for p in fraud_probabilities]),
            'time_window_hours': (
                (datetime.utcnow() - self.recent_predictions[0]['timestamp']).total_seconds() / 3600
                if self.recent_predictions else 0
            )
        }