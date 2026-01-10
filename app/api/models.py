"""Model management API endpoints."""

from flask import Blueprint, request, jsonify
from marshmallow import ValidationError
from datetime import datetime
import threading
import time

from app.schemas.api_schemas import (
    ModelTrainingRequestSchema, ModelTrainingResponseSchema,
    ModelMetricsResponseSchema
)
from app.models.database import ModelRegistry
from app.utils.logging import get_logger
from app import db_manager, model_trainer, fraud_detector

models_bp = Blueprint('models', __name__)
logger = get_logger(__name__)

# Schema instances
training_request_schema = ModelTrainingRequestSchema()
training_response_schema = ModelTrainingResponseSchema()
metrics_response_schema = ModelMetricsResponseSchema()

# Background training tracking
training_status = {
    'is_training': False,
    'current_model': None,
    'start_time': None,
    'progress': None
}

@models_bp.route('/train', methods=['POST'])
def train_model():
    """Train a new fraud detection model."""
    
    # Check if training is already in progress
    if training_status['is_training']:
        return jsonify({
            'error': 'Conflict',
            'message': 'Model training is already in progress',
            'status_code': 409,
            'current_training': {
                'model_type': training_status['current_model'],
                'start_time': training_status['start_time'],
                'progress': training_status['progress']
            },
            'timestamp': datetime.utcnow().isoformat()
        }), 409
    
    try:
        # Validate request data
        json_data = request.get_json()
        if not json_data:
            return jsonify({
                'error': 'Bad Request',
                'message': 'No JSON data provided',
                'status_code': 400,
                'timestamp': datetime.utcnow().isoformat()
            }), 400
        
        # Parse and validate input
        try:
            validated_data = training_request_schema.load(json_data)
        except ValidationError as e:
            return jsonify({
                'error': 'Validation Error',
                'message': e.messages,
                'status_code': 400,
                'timestamp': datetime.utcnow().isoformat()
            }), 400
        
        model_type = validated_data['model_type']
        train_start_date = validated_data.get('train_start_date')
        train_end_date = validated_data.get('train_end_date')
        hyperparameters = validated_data.get('hyperparameters')
        
        # Start training in background thread
        def train_background():
            global training_status
            training_start_time = time.time()
            
            try:
                training_status.update({
                    'is_training': True,
                    'current_model': model_type,
                    'start_time': datetime.utcnow().isoformat(),
                    'progress': 'Preparing training data'
                })
                
                logger.info(f"Starting training for model type: {model_type}")
                
                # Prepare training data
                training_status['progress'] = 'Preparing training data'
                X, y = model_trainer.prepare_training_data(train_start_date, train_end_date)
                
                # Train model
                training_status['progress'] = f'Training {model_type} model'
                result = model_trainer.train_model(model_type, X, y, hyperparameters)
                
                # Refresh fraud detector to use new model if it's the best
                training_status['progress'] = 'Finalizing model'
                fraud_detector.refresh_model()
                
                training_duration = time.time() - training_start_time
                
                logger.info(f"Training completed for {model_type} in {training_duration:.2f} seconds")
                
                # Store result for retrieval
                training_status.update({
                    'is_training': False,
                    'current_model': None,
                    'start_time': None,
                    'progress': None,
                    'last_result': {
                        'model_id': None,  # We don't store model ID in our registry
                        'model_name': result['model_type'],
                        'model_version': result['model_version'],
                        'model_type': result['model_type'],
                        'metrics': result['metrics'],
                        'training_duration_seconds': training_duration,
                        'training_samples': len(X),
                        'created_at': datetime.utcnow().isoformat()
                    }
                })
                
            except Exception as e:
                logger.error(f"Error in background training: {e}")
                training_status.update({
                    'is_training': False,
                    'current_model': None,
                    'start_time': None,
                    'progress': None,
                    'error': str(e)
                })
        
        # Start background training
        training_thread = threading.Thread(target=train_background)
        training_thread.daemon = True
        training_thread.start()
        
        return jsonify({
            'message': f'Training started for {model_type} model',
            'model_type': model_type,
            'status': 'training_started',
            'estimated_duration_minutes': 10,  # Rough estimate
            'check_status_url': '/api/v1/train/status',
            'timestamp': datetime.utcnow().isoformat()
        }), 202
        
    except Exception as e:
        logger.error(f"Error starting model training: {e}")
        return jsonify({
            'error': 'Internal Server Error',
            'message': str(e),
            'status_code': 500,
            'timestamp': datetime.utcnow().isoformat()
        }), 500

@models_bp.route('/train/status', methods=['GET'])
def get_training_status():
    """Get current training status."""
    
    try:
        if training_status['is_training']:
            return jsonify({
                'status': 'training',
                'model_type': training_status['current_model'],
                'start_time': training_status['start_time'],
                'progress': training_status['progress'],
                'timestamp': datetime.utcnow().isoformat()
            }), 200
        
        elif 'last_result' in training_status:
            result = training_status.pop('last_result')  # Remove after retrieval
            return jsonify({
                'status': 'completed',
                'result': result,
                'timestamp': datetime.utcnow().isoformat()
            }), 200
        
        elif 'error' in training_status:
            error = training_status.pop('error')  # Remove after retrieval
            return jsonify({
                'status': 'error',
                'error': error,
                'timestamp': datetime.utcnow().isoformat()
            }), 500
        
        else:
            return jsonify({
                'status': 'idle',
                'message': 'No training in progress',
                'timestamp': datetime.utcnow().isoformat()
            }), 200
            
    except Exception as e:
        logger.error(f"Error getting training status: {e}")
        return jsonify({
            'error': 'Internal Server Error',
            'message': str(e),
            'status_code': 500,
            'timestamp': datetime.utcnow().isoformat()
        }), 500

@models_bp.route('/train/all', methods=['POST'])
def train_all_models():
    """Train all available model types."""
    
    # Check if training is already in progress
    if training_status['is_training']:
        return jsonify({
            'error': 'Conflict',
            'message': 'Model training is already in progress',
            'status_code': 409,
            'timestamp': datetime.utcnow().isoformat()
        }), 409
    
    try:
        # Get optional date range from request
        json_data = request.get_json() or {}
        train_start_date = json_data.get('train_start_date')
        train_end_date = json_data.get('train_end_date')
        
        if train_start_date:
            train_start_date = datetime.fromisoformat(train_start_date)
        if train_end_date:
            train_end_date = datetime.fromisoformat(train_end_date)
        
        # Start training in background
        def train_all_background():
            global training_status
            training_start_time = time.time()
            
            try:
                training_status.update({
                    'is_training': True,
                    'current_model': 'all_models',
                    'start_time': datetime.utcnow().isoformat(),
                    'progress': 'Preparing training data'
                })
                
                # Prepare training data once for all models
                X, y = model_trainer.prepare_training_data(train_start_date, train_end_date)
                
                # Train all models
                training_status['progress'] = 'Training all models'
                results = model_trainer.train_all_models(X, y)
                
                # Refresh fraud detector
                training_status['progress'] = 'Finalizing models'
                fraud_detector.refresh_model()
                
                training_duration = time.time() - training_start_time
                
                # Store results
                training_status.update({
                    'is_training': False,
                    'current_model': None,
                    'start_time': None,
                    'progress': None,
                    'last_result': {
                        'total_models_trained': len(results),
                        'models': results,
                        'training_duration_seconds': training_duration,
                        'training_samples': len(X),
                        'created_at': datetime.utcnow().isoformat()
                    }
                })
                
            except Exception as e:
                logger.error(f"Error in background training (all models): {e}")
                training_status.update({
                    'is_training': False,
                    'current_model': None,
                    'start_time': None,
                    'progress': None,
                    'error': str(e)
                })
        
        # Start background training
        training_thread = threading.Thread(target=train_all_background)
        training_thread.daemon = True
        training_thread.start()
        
        return jsonify({
            'message': 'Training started for all model types',
            'model_types': ['logistic_regression', 'random_forest', 'gradient_boosting'],
            'status': 'training_started',
            'estimated_duration_minutes': 30,  # Rough estimate for all models
            'check_status_url': '/api/v1/train/status',
            'timestamp': datetime.utcnow().isoformat()
        }), 202
        
    except Exception as e:
        logger.error(f"Error starting training for all models: {e}")
        return jsonify({
            'error': 'Internal Server Error',
            'message': str(e),
            'status_code': 500,
            'timestamp': datetime.utcnow().isoformat()
        }), 500

@models_bp.route('/metrics/<string:model_version>', methods=['GET'])
def get_model_metrics(model_version):
    """Get metrics for a specific model version."""
    
    try:
        # Get metrics from model trainer
        metrics_data = model_trainer.get_model_metrics(model_version)
        
        if not metrics_data:
            return jsonify({
                'error': 'Not Found',
                'message': f'Model version {model_version} not found',
                'status_code': 404,
                'timestamp': datetime.utcnow().isoformat()
            }), 404
        
        # Format response
        response_data = metrics_response_schema.dump({
            'model_version': metrics_data['model_version'],
            'model_type': metrics_data['model_type'],
            'metrics': metrics_data['metrics'],
            'created_at': metrics_data['created_at'],
            'is_active': metrics_data['is_active']
        })
        
        return jsonify(response_data), 200
        
    except Exception as e:
        logger.error(f"Error retrieving metrics for model {model_version}: {e}")
        return jsonify({
            'error': 'Internal Server Error',
            'message': str(e),
            'status_code': 500,
            'timestamp': datetime.utcnow().isoformat()
        }), 500

@models_bp.route('/models', methods=['GET'])
def list_models():
    """List all trained models with their metrics."""
    
    try:
        with db_manager.get_session() as session:
            models = session.query(ModelRegistry).order_by(
                ModelRegistry.created_at.desc()
            ).all()
            
            models_data = []
            for model in models:
                models_data.append({
                    'model_name': model.model_name,
                    'model_version': model.model_version,
                    'model_type': model.model_type,
                    'metrics': model.metrics,
                    'is_active': model.is_active,
                    'created_at': model.created_at.isoformat(),
                    'feature_schema_version': model.feature_schema_version
                })
        
        return jsonify({
            'total_models': len(models_data),
            'models': models_data,
            'timestamp': datetime.utcnow().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Error listing models: {e}")
        return jsonify({
            'error': 'Internal Server Error',
            'message': str(e),
            'status_code': 500,
            'timestamp': datetime.utcnow().isoformat()
        }), 500

@models_bp.route('/models/<string:model_version>/activate', methods=['POST'])
def activate_model(model_version):
    """Activate a specific model version."""
    
    try:
        with db_manager.get_session() as session:
            # Check if model exists
            model = session.query(ModelRegistry).filter(
                ModelRegistry.model_version == model_version
            ).first()
            
            if not model:
                return jsonify({
                    'error': 'Not Found',
                    'message': f'Model version {model_version} not found',
                    'status_code': 404,
                    'timestamp': datetime.utcnow().isoformat()
                }), 404
            
            # Deactivate all models
            session.query(ModelRegistry).update({'is_active': False})
            
            # Activate specified model
            model.is_active = True
            session.commit()
            
            # Refresh fraud detector
            fraud_detector.refresh_model()
            
        return jsonify({
            'message': f'Model {model_version} activated successfully',
            'model_version': model_version,
            'model_type': model.model_type,
            'timestamp': datetime.utcnow().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Error activating model {model_version}: {e}")
        return jsonify({
            'error': 'Internal Server Error',
            'message': str(e),
            'status_code': 500,
            'timestamp': datetime.utcnow().isoformat()
        }), 500

@models_bp.route('/models/active', methods=['GET'])
def get_active_model():
    """Get information about the currently active model."""
    
    try:
        # Get model status from fraud detector
        model_status = fraud_detector.get_model_status()
        
        return jsonify({
            'is_model_loaded': model_status['model_loaded'],
            'active_model': model_status['model_info'],
            'fraud_threshold': model_status['fraud_threshold'],
            'high_risk_threshold': model_status['high_risk_threshold'],
            'status': model_status['status'],
            'timestamp': datetime.utcnow().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting active model info: {e}")
        return jsonify({
            'error': 'Internal Server Error',
            'message': str(e),
            'status_code': 500,
            'timestamp': datetime.utcnow().isoformat()
        }), 500