"""Flask application factory and configuration."""

import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime
import uuid
from typing import Dict, Any

from app.config.config import config
from app.core.database_manager import DatabaseManager
from app.utils.logging import setup_logging, RequestLogger
from app.inference.fraud_detector import FraudDetectionInference
from app.training.model_trainer import ModelTrainer
from app.security import configure_security, generate_default_api_keys

# Global instances
db_manager = None
fraud_detector = None
model_trainer = None
security_manager = None
request_logger = RequestLogger()

def create_app(config_name: str = None) -> Flask:
    """Create Flask application with configuration."""
    
    # Determine configuration
    config_name = config_name or os.environ.get('FLASK_ENV', 'development')
    app_config = config[config_name]
    
    # Setup logging
    setup_logging(app_config.LOG_LEVEL, app_config.LOG_FORMAT)
    
    # Create Flask app
    app = Flask(__name__)
    app.config.from_object(app_config)
    
    # Configure security first
    global security_manager
    security_manager = configure_security(app)
    
    # Enable CORS (if configured)
    if app.config.get('CORS_ENABLED', False):
        CORS(app, origins=app.config.get('CORS_ORIGINS', '*'))
    
    # Initialize global components
    global db_manager, fraud_detector, model_trainer
    
    # Database manager
    db_manager = DatabaseManager(
        app_config.SQLALCHEMY_DATABASE_URI,
        **app_config.SQLALCHEMY_ENGINE_OPTIONS
    )
    
    # Fraud detector
    fraud_detector = FraudDetectionInference(
        db_manager, app_config.MODEL_ARTIFACTS_PATH
    )
    
    # Model trainer
    model_trainer = ModelTrainer(
        db_manager, app_config.MODEL_ARTIFACTS_PATH
    )
    
    # Register blueprints
    from app.api.transactions import transactions_bp
    from app.api.models import models_bp
    from app.api.health import health_bp
    from app.api.users import users_bp
    from app.api.auth import init_auth_routes
    
    app.register_blueprint(transactions_bp, url_prefix='/api/v1')
    app.register_blueprint(models_bp, url_prefix='/api/v1')
    app.register_blueprint(health_bp, url_prefix='/api/v1')
    app.register_blueprint(users_bp, url_prefix='/api/v1')
    
    # Initialize JWT authentication routes
    init_auth_routes(app)
    
    # Global error handlers
    @app.errorhandler(400)
    def bad_request(error):
        return jsonify({
            'error': 'Bad Request',
            'message': str(error),
            'status_code': 400,
            'timestamp': datetime.utcnow().isoformat()
        }), 400
    
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({
            'error': 'Not Found',
            'message': 'The requested resource was not found',
            'status_code': 404,
            'timestamp': datetime.utcnow().isoformat()
        }), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({
            'error': 'Internal Server Error',
            'message': 'An internal server error occurred',
            'status_code': 500,
            'timestamp': datetime.utcnow().isoformat()
        }), 500
    
    @app.before_request
    def before_request():
        """Log incoming requests."""
        request.start_time = datetime.utcnow()
        request.correlation_id = str(uuid.uuid4())
        
        # Skip logging for health checks
        if request.path != '/api/v1/health':
            request_logger.log_request(
                request.correlation_id,
                request.method,
                request.path,
                request.get_json(silent=True)
            )
    
    @app.after_request
    def after_request(response):
        """Log outgoing responses."""
        if hasattr(request, 'start_time') and request.path != '/api/v1/health':
            duration = (datetime.utcnow() - request.start_time).total_seconds() * 1000
            request_logger.log_response(
                getattr(request, 'correlation_id', 'unknown'),
                response.status_code,
                len(response.get_data()),
                duration
            )
        
        # Add correlation ID to response headers
        if hasattr(request, 'correlation_id'):
            response.headers['X-Correlation-ID'] = request.correlation_id
        
        return response
    
    # Initialize components on first request
    @app.before_first_request
    def initialize_components():
        """Initialize fraud detector and other components.""" 
        try:
            # Initialize fraud detector
            if not fraud_detector.initialize():
                app.logger.error("Failed to initialize fraud detector")
            else:
                app.logger.info("Fraud detector initialized successfully")
            
            # Generate default API keys for development
            if app.config.get('FLASK_ENV') == 'development':
                api_keys = generate_default_api_keys(security_manager, app)
                if api_keys:
                    app.logger.info(f"Development API keys: {api_keys}")
                
        except Exception as e:
            app.logger.error(f"Error initializing components: {e}")
    
    return app