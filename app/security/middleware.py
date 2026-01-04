"""
Security middleware for FraudNet.AI.
Implements authentication, rate limiting, input validation, and security headers.
"""

import json
import time
import hashlib
import hmac
from datetime import datetime, timedelta
from functools import wraps
from typing import Dict, Optional, Callable, Any
from flask import request, jsonify, g, current_app
from werkzeug.security import safe_str_cmp
import redis
import structlog

logger = structlog.get_logger(__name__)


class SecurityError(Exception):
    """Base exception for security-related errors."""
    pass


class AuthenticationError(SecurityError):
    """Authentication failed."""
    pass


class RateLimitError(SecurityError):
    """Rate limit exceeded."""
    pass


class ValidationError(SecurityError):
    """Input validation failed."""
    pass


class AuthenticationManager:
    """Manages API key authentication and JWT tokens."""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis_client = redis_client
        self.api_keys_prefix = "api_keys:"
        self.sessions_prefix = "sessions:"
        
    def generate_api_key(self, user_id: str, permissions: list = None) -> str:
        """Generate a new API key for a user."""
        import secrets
        
        api_key = secrets.token_urlsafe(32)
        key_data = {
            'user_id': user_id,
            'permissions': permissions or ['read', 'write'],
            'created_at': datetime.now().isoformat(),
            'last_used': None
        }
        
        # Store API key with expiration (30 days)
        self.redis_client.setex(
            f"{self.api_keys_prefix}{api_key}",
            2592000,  # 30 days
            json.dumps(key_data)
        )
        
        logger.info("API key generated", user_id=user_id, api_key_prefix=api_key[:8])
        return api_key
    
    def validate_api_key(self, api_key: str) -> Optional[Dict]:
        """Validate API key and return key data."""
        if not api_key:
            return None
            
        key_data_str = self.redis_client.get(f"{self.api_keys_prefix}{api_key}")
        if not key_data_str:
            return None
            
        try:
            key_data = json.loads(key_data_str)
            
            # Update last used timestamp
            key_data['last_used'] = datetime.now().isoformat()
            self.redis_client.setex(
                f"{self.api_keys_prefix}{api_key}",
                2592000,  # 30 days
                json.dumps(key_data)
            )
            
            return key_data
        except (json.JSONDecodeError, KeyError):
            return None
    
    def revoke_api_key(self, api_key: str) -> bool:
        """Revoke an API key."""
        deleted = self.redis_client.delete(f"{self.api_keys_prefix}{api_key}")
        if deleted:
            logger.info("API key revoked", api_key_prefix=api_key[:8])
        return bool(deleted)


class RateLimiter:
    """Token bucket rate limiter with Redis backend."""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis_client = redis_client
        self.rate_limit_prefix = "rate_limit:"
        
    def is_allowed(self, key: str, limit: int, window: int = 60, 
                  burst: int = None) -> tuple[bool, Dict]:
        """
        Check if request is within rate limits.
        
        Args:
            key: Unique identifier (IP, user_id, etc.)
            limit: Maximum requests per window
            window: Time window in seconds
            burst: Maximum burst requests (default: limit)
            
        Returns:
            (is_allowed, rate_limit_info)
        """
        if burst is None:
            burst = limit
        
        now = time.time()
        pipeline = self.redis_client.pipeline()
        
        # Use sliding window log approach
        bucket_key = f"{self.rate_limit_prefix}{key}"
        
        # Remove expired entries
        pipeline.zremrangebyscore(bucket_key, 0, now - window)
        
        # Count current requests
        pipeline.zcard(bucket_key)
        
        # Add current request
        pipeline.zadd(bucket_key, {str(now): now})
        
        # Set expiration
        pipeline.expire(bucket_key, window)
        
        results = pipeline.execute()
        current_count = results[1]
        
        rate_limit_info = {
            'limit': limit,
            'window': window,
            'remaining': max(0, limit - current_count - 1),
            'reset_time': int(now + window),
            'current_count': current_count + 1
        }
        
        if current_count >= limit:
            # Remove the request we just added
            self.redis_client.zrem(bucket_key, str(now))
            logger.warning("Rate limit exceeded", key=key, count=current_count, limit=limit)
            return False, rate_limit_info
            
        return True, rate_limit_info


class InputValidator:
    """Input validation and sanitization."""
    
    @staticmethod
    def validate_json_payload(schema: Dict) -> Callable:
        """Decorator to validate JSON payload against schema."""
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                if not request.is_json:
                    raise ValidationError("Content-Type must be application/json")
                
                try:
                    data = request.get_json()
                except Exception:
                    raise ValidationError("Invalid JSON payload")
                
                # Basic schema validation
                for field, rules in schema.items():
                    if rules.get('required', False) and field not in data:
                        raise ValidationError(f"Missing required field: {field}")
                    
                    if field in data:
                        value = data[field]
                        field_type = rules.get('type')
                        
                        if field_type and not isinstance(value, field_type):
                            raise ValidationError(f"Invalid type for field {field}")
                        
                        min_val = rules.get('min')
                        max_val = rules.get('max')
                        
                        if min_val is not None and value < min_val:
                            raise ValidationError(f"Field {field} below minimum value")
                        
                        if max_val is not None and value > max_val:
                            raise ValidationError(f"Field {field} above maximum value")
                
                return func(*args, **kwargs)
            return wrapper
        return decorator
    
    @staticmethod
    def sanitize_string(value: str, max_length: int = 255) -> str:
        """Sanitize string input."""
        if not isinstance(value, str):
            raise ValidationError("Value must be a string")
        
        # Remove null bytes and control characters
        value = ''.join(char for char in value if ord(char) >= 32 or char in '\n\r\t')
        
        # Trim to max length
        if len(value) > max_length:
            value = value[:max_length]
        
        return value.strip()
    
    @staticmethod
    def validate_amount(amount: float) -> float:
        """Validate transaction amount."""
        if not isinstance(amount, (int, float)):
            raise ValidationError("Amount must be a number")
        
        if amount < 0:
            raise ValidationError("Amount cannot be negative")
        
        if amount > 1000000:  # $1M limit
            raise ValidationError("Amount exceeds maximum limit")
        
        return round(float(amount), 2)


class SecurityHeadersManager:
    """Manages security headers."""
    
    @staticmethod
    def add_security_headers(response):
        """Add security headers to response."""
        # CORS headers
        if current_app.config.get('CORS_ENABLED', False):
            origins = current_app.config.get('CORS_ORIGINS', '*')
            response.headers['Access-Control-Allow-Origin'] = origins
            response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
            response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-API-Key'
        
        # Security headers
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Content-Security-Policy'] = "default-src 'self'"
        
        return response


# Authentication decorators
def require_api_key(permissions: list = None):
    """Decorator to require valid API key."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            auth_manager = getattr(g, 'auth_manager', None)
            if not auth_manager:
                raise AuthenticationError("Authentication system not initialized")
            
            api_key_header = current_app.config.get('API_KEY_HEADER', 'X-API-Key')
            api_key = request.headers.get(api_key_header)
            
            key_data = auth_manager.validate_api_key(api_key)
            if not key_data:
                raise AuthenticationError("Invalid or expired API key")
            
            # Check permissions
            if permissions:
                key_permissions = key_data.get('permissions', [])
                if not any(perm in key_permissions for perm in permissions):
                    raise AuthenticationError("Insufficient permissions")
            
            # Store key data in request context
            g.current_user = key_data['user_id']
            g.api_key_data = key_data
            
            return func(*args, **kwargs)
        return wrapper
    return decorator


def rate_limit(limit: int, window: int = 60, per: str = 'ip'):
    """Decorator to apply rate limiting."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not current_app.config.get('RATE_LIMIT_ENABLED', False):
                return func(*args, **kwargs)
            
            rate_limiter = getattr(g, 'rate_limiter', None)
            if not rate_limiter:
                raise RateLimitError("Rate limiter not initialized")
            
            # Determine rate limit key
            if per == 'ip':
                key = request.remote_addr
            elif per == 'user':
                key = getattr(g, 'current_user', request.remote_addr)
            else:
                key = f"{per}:{request.remote_addr}"
            
            allowed, info = rate_limiter.is_allowed(key, limit, window)
            
            # Add rate limit headers
            @current_app.after_request
            def add_rate_limit_headers(response):
                response.headers['X-RateLimit-Limit'] = str(info['limit'])
                response.headers['X-RateLimit-Remaining'] = str(info['remaining'])
                response.headers['X-RateLimit-Reset'] = str(info['reset_time'])
                return response
            
            if not allowed:
                raise RateLimitError("Rate limit exceeded")
            
            return func(*args, **kwargs)
        return wrapper
    return decorator


# HMAC signature validation for webhook endpoints
def verify_webhook_signature(secret_key: str):
    """Decorator to verify HMAC signature for webhook endpoints."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            signature = request.headers.get('X-Signature-256', '')
            if not signature.startswith('sha256='):
                raise AuthenticationError("Invalid signature format")
            
            expected_signature = signature[7:]  # Remove 'sha256=' prefix
            
            payload = request.get_data()
            computed_signature = hmac.new(
                secret_key.encode(),
                payload,
                hashlib.sha256
            ).hexdigest()
            
            if not hmac.compare_digest(expected_signature, computed_signature):
                raise AuthenticationError("Invalid signature")
            
            return func(*args, **kwargs)
        return wrapper
    return decorator