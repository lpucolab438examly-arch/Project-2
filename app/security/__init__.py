"""
Security configuration and initialization for FraudNet.AI.
"""

import os
import redis
import structlog
from flask import Flask, g, request, jsonify
from app.security.middleware import (
    AuthenticationManager, RateLimiter, SecurityHeadersManager,
    SecurityError, AuthenticationError, RateLimitError, ValidationError
)

logger = structlog.get_logger(__name__)


class SecurityManager:
    """Central security manager for the application."""
    
    def __init__(self):
        self.auth_manager = None
        self.rate_limiter = None
        self.redis_client = None
        
    def init_app(self, app: Flask):
        """Initialize security components with Flask app."""
        # Initialize Redis connection
        redis_url = app.config.get('REDIS_URL', 'redis://localhost:6379/0')
        self.redis_client = redis.from_url(redis_url, decode_responses=True)
        
        # Test Redis connection
        try:
            self.redis_client.ping()
            logger.info("Redis connection established")
        except Exception as e:
            logger.error("Redis connection failed", error=str(e))
            raise
        
        # Initialize security components
        self.auth_manager = AuthenticationManager(self.redis_client)
        self.rate_limiter = RateLimiter(self.redis_client)
        
        # Register before_request handler
        app.before_request(self._before_request)
        
        # Register after_request handler for security headers
        app.after_request(SecurityHeadersManager.add_security_headers)
        
        # Register error handlers
        self._register_error_handlers(app)
        
        logger.info("Security manager initialized")
        
    def _before_request(self):
        """Set up request context with security components."""
        g.auth_manager = self.auth_manager
        g.rate_limiter = self.rate_limiter
        g.request_start_time = request.start_time if hasattr(request, 'start_time') else None
        
        # Log request for audit trail
        logger.info(
            "Request started",
            method=request.method,
            path=request.path,
            remote_addr=request.remote_addr,
            user_agent=request.user_agent.string if request.user_agent else None
        )
        
        # Validate content type for POST/PUT requests
        if request.method in ['POST', 'PUT']:
            if not request.is_json:
                # Only require JSON for API endpoints
                if request.path.startswith('/api/'):
                    return jsonify({
                        'error': 'Invalid content type',
                        'message': 'Content-Type must be application/json'
                    }), 400
        
        # Validate content length
        max_content_length = 1024 * 1024  # 1MB
        if request.content_length and request.content_length > max_content_length:
            return jsonify({
                'error': 'Payload too large',
                'message': f'Maximum content length is {max_content_length} bytes'
            }), 413
    
    def _register_error_handlers(self, app: Flask):
        """Register security-related error handlers."""
        
        @app.errorhandler(AuthenticationError)
        def handle_auth_error(error: AuthenticationError):
            logger.warning("Authentication error", error=str(error))
            return jsonify({
                'error': 'Authentication failed',
                'message': str(error)
            }), 401
        
        @app.errorhandler(RateLimitError)
        def handle_rate_limit_error(error: RateLimitError):
            logger.warning("Rate limit exceeded", error=str(error))
            return jsonify({
                'error': 'Rate limit exceeded',
                'message': 'Too many requests. Please try again later.'
            }), 429
        
        @app.errorhandler(ValidationError)
        def handle_validation_error(error: ValidationError):
            logger.warning("Validation error", error=str(error))
            return jsonify({
                'error': 'Validation failed',
                'message': str(error)
            }), 400
        
        @app.errorhandler(SecurityError)
        def handle_security_error(error: SecurityError):
            logger.error("Security error", error=str(error))
            return jsonify({
                'error': 'Security violation',
                'message': 'Request blocked for security reasons'
            }), 403
        
        @app.errorhandler(403)
        def handle_forbidden(error):
            return jsonify({
                'error': 'Forbidden',
                'message': 'Access denied'
            }), 403
        
        @app.errorhandler(413)
        def handle_payload_too_large(error):
            return jsonify({
                'error': 'Payload too large',
                'message': 'Request payload exceeds maximum size limit'
            }), 413


def configure_security(app: Flask) -> SecurityManager:
    """Configure security for the Flask application."""
    
    # Validate security configuration
    required_configs = ['SECRET_KEY']
    for config in required_configs:
        if not app.config.get(config):
            raise ValueError(f"Missing required security configuration: {config}")
    
    # Initialize security manager
    security_manager = SecurityManager()
    security_manager.init_app(app)
    
    # Store in app context for access in other modules
    app.security_manager = security_manager
    
    return security_manager


def generate_default_api_keys(security_manager: SecurityManager, app: Flask):
    """Generate default API keys for development/testing."""
    if app.config.get('FLASK_ENV') == 'development':
        # Create admin API key
        admin_key = security_manager.auth_manager.generate_api_key(
            'admin',
            ['read', 'write', 'admin']
        )
        
        # Create read-only API key
        readonly_key = security_manager.auth_manager.generate_api_key(
            'readonly_user',
            ['read']
        )
        
        logger.info(
            "Development API keys generated",
            admin_key=admin_key[:8] + "...",
            readonly_key=readonly_key[:8] + "..."
        )
        
        return {
            'admin': admin_key,
            'readonly': readonly_key
        }
    
    return None