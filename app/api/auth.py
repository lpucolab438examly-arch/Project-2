"""
JWT Authentication endpoints for the FraudNet.AI API.
Provides token-based authentication with refresh capability.
"""

from datetime import datetime, timedelta
from functools import wraps
import jwt
from flask import Blueprint, request, jsonify, current_app
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.security import check_password_hash, generate_password_hash
from app.models.database import User, AuditLog
from app.core.database_manager import db_manager
from app.utils.logging import get_logger

# Initialize logger
logger = get_logger(__name__)

def log_audit_event(user_id, entity_type, metadata, description):
    """Simple audit event logging function."""
    try:
        with db_manager.get_session() as session:
            audit_log = AuditLog(
                entity_type=entity_type,
                entity_id=user_id or 0,
                action_type='AUTH_EVENT',
                metadata={
                    'description': description,
                    'ip_address': metadata.get('ip_address'),
                    'user_agent': request.user_agent.string if request.user_agent else None,
                    **metadata
                }
            )
            session.add(audit_log)
            session.commit()
            logger.info(f"Audit event logged: {description}", user_id=user_id, metadata=metadata)
    except Exception as e:
        logger.error(f"Failed to log audit event: {str(e)}")

# Initialize rate limiter
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri="redis://localhost:6379"  # Configure Redis connection
)

# Create blueprint
auth_bp = Blueprint('auth', __name__, url_prefix='/auth')
logger = setup_logger(__name__)

# JWT Configuration
JWT_SECRET_KEY = 'your-super-secret-jwt-key-change-in-production'
JWT_ALGORITHM = 'HS256'
JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)

class TokenManager:
    """Manages JWT token creation, validation, and refresh."""
    
    @staticmethod
    def create_tokens(user_id, user_role):
        """Create access and refresh tokens for a user."""
        now = datetime.utcnow()
        
        # Access token payload
        access_payload = {
            'user_id': user_id,
            'role': user_role,
            'type': 'access',
            'iat': now,
            'exp': now + JWT_ACCESS_TOKEN_EXPIRES
        }
        
        # Refresh token payload  
        refresh_payload = {
            'user_id': user_id,
            'type': 'refresh',
            'iat': now,
            'exp': now + JWT_REFRESH_TOKEN_EXPIRES
        }
        
        try:
            access_token = jwt.encode(access_payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
            refresh_token = jwt.encode(refresh_payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
            
            return access_token, refresh_token
        except Exception as e:
            logger.error(f"Error creating tokens: {str(e)}")
            raise
    
    @staticmethod
    def decode_token(token, token_type='access'):
        """Decode and validate a JWT token."""
        try:
            payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
            
            # Verify token type
            if payload.get('type') != token_type:
                raise jwt.InvalidTokenError(f"Invalid token type: expected {token_type}")
            
            return payload
        except jwt.ExpiredSignatureError:
            raise jwt.ExpiredSignatureError("Token has expired")
        except jwt.InvalidTokenError as e:
            raise jwt.InvalidTokenError(f"Invalid token: {str(e)}")
    
    @staticmethod
    def refresh_access_token(refresh_token):
        """Create a new access token using a valid refresh token."""
        try:
            # Decode refresh token
            payload = TokenManager.decode_token(refresh_token, 'refresh')
            user_id = payload['user_id']
            
            # Get user info
            with db_manager.get_session() as session:
                user = session.query(User).filter_by(id=user_id).first()
                if not user or not user.is_active:
                    raise jwt.InvalidTokenError("User not found or inactive")
                
                # Create new access token
                access_token, _ = TokenManager.create_tokens(user_id, user.role)
                return access_token
            
        except Exception as e:
            logger.error(f"Error refreshing token: {str(e)}")
            raise

def jwt_required(roles=None):
    """Decorator to protect routes with JWT authentication."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            token = None
            
            # Get token from Authorization header
            auth_header = request.headers.get('Authorization')
            if auth_header and auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
            
            if not token:
                return jsonify({'error': 'Access token is missing'}), 401
            
            try:
                # Decode token
                payload = TokenManager.decode_token(token, 'access')
                current_user_id = payload['user_id']
                current_user_role = payload['role']
                
                # Check role permissions
                if roles and current_user_role not in roles:
                    return jsonify({'error': 'Insufficient permissions'}), 403
                
                # Add user info to request context
                request.current_user_id = current_user_id
                request.current_user_role = current_user_role
                
                return f(*args, **kwargs)
                
            except jwt.ExpiredSignatureError:
                return jsonify({'error': 'Token has expired'}), 401
            except jwt.InvalidTokenError as e:
                return jsonify({'error': f'Invalid token: {str(e)}'}), 401
            except Exception as e:
                logger.error(f"JWT authentication error: {str(e)}")
                return jsonify({'error': 'Authentication failed'}), 401
        
        return decorated_function
    return decorator

@auth_bp.route('/login', methods=['POST'])
@limiter.limit("5 per minute")  # Rate limit login attempts
def login():
    """Authenticate user and return JWT tokens."""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        email = data.get('email')
        password = data.get('password')
        
        if not email or not password:
            return jsonify({'error': 'Email and password are required'}), 400
        
        # Find user
        with db_manager.get_session() as session:
            user = session.query(User).filter_by(email=email).first()
            
            if not user or not check_password_hash(user.password_hash, password):
                # Log failed login attempt
                log_audit_event(
                    None,  # No user_id for failed attempts
                    'auth.login_failed',
                    {'email': email, 'ip_address': get_remote_address()},
                    'Authentication failed for email: ' + email
                )
                return jsonify({'error': 'Invalid email or password'}), 401
            
            if not user.is_active:
                log_audit_event(
                    user.id,
                    'auth.login_inactive',
                    {'email': email},
                    'Login attempt by inactive user'
                )
                return jsonify({'error': 'Account is deactivated'}), 401
            
            # Create tokens
            access_token, refresh_token = TokenManager.create_tokens(user.id, user.role)
            
            # Update last login
            user.last_login_at = datetime.utcnow()
            user.login_count = (user.login_count or 0) + 1
            session.commit()
            
            # Log successful login
            log_audit_event(
                user.id,
                'auth.login_success',
                {'email': email, 'ip_address': get_remote_address()},
                'User logged in successfully'
            )
            
            # Return user data and tokens
            return jsonify({
                'access_token': access_token,
                'refresh_token': refresh_token,
                'token_type': 'Bearer',
                'expires_in': int(JWT_ACCESS_TOKEN_EXPIRES.total_seconds()),
                'user': user.to_dict()
            }), 200
        
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@auth_bp.route('/refresh', methods=['POST'])
@limiter.limit("10 per minute")
def refresh_token():
    """Refresh an access token using a valid refresh token."""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        refresh_token = data.get('refresh_token')
        
        if not refresh_token:
            return jsonify({'error': 'Refresh token is required'}), 400
        
        # Generate new access token
        new_access_token = TokenManager.refresh_access_token(refresh_token)
        
        return jsonify({
            'access_token': new_access_token,
            'token_type': 'Bearer',
            'expires_in': int(JWT_ACCESS_TOKEN_EXPIRES.total_seconds())
        }), 200
        
    except jwt.ExpiredSignatureError:
        return jsonify({'error': 'Refresh token has expired'}), 401
    except jwt.InvalidTokenError as e:
        return jsonify({'error': f'Invalid refresh token: {str(e)}'}), 401
    except Exception as e:
        logger.error(f"Token refresh error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    """Logout user and invalidate tokens."""
    try:
        user_id = request.current_user_id
        
        # In a production system, you'd want to blacklist the tokens
        # For now, we'll just log the logout event
        log_audit_event(
            user_id,
            'auth.logout',
            {'ip_address': get_remote_address()},
            'User logged out'
        )
        
        return jsonify({'message': 'Logged out successfully'}), 200
        
    except Exception as e:
        logger.error(f"Logout error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def get_current_user():
    """Get current authenticated user information."""
    try:
        user_id = request.current_user_id
        
        with db_manager.get_session() as session:
            user = session.query(User).filter_by(id=user_id).first()
            if not user:
                return jsonify({'error': 'User not found'}), 404
            
            return jsonify(user.to_dict()), 200
        
    except Exception as e:
        logger.error(f"Get current user error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@auth_bp.route('/change-password', methods=['POST'])
@jwt_required()
def change_password():
    """Change user password."""
    try:
        user_id = request.current_user_id
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        current_password = data.get('current_password')
        new_password = data.get('new_password')
        
        if not current_password or not new_password:
            return jsonify({'error': 'Current and new passwords are required'}), 400
        
        if len(new_password) < 6:
            return jsonify({'error': 'New password must be at least 6 characters long'}), 400
        
        # Get user and update password
        with db_manager.get_session() as session:
            user = session.query(User).filter_by(id=user_id).first()
            if not user:
                return jsonify({'error': 'User not found'}), 404
            
            # Verify current password
            if not check_password_hash(user.password_hash, current_password):
                return jsonify({'error': 'Current password is incorrect'}), 400
            
            # Update password
            user.password_hash = generate_password_hash(new_password)
            user.password_changed_at = datetime.utcnow()
            session.commit()
            
            # Log password change
            log_audit_event(
                user_id,
                'auth.password_changed',
                {},
                'User changed password'
            )
            
            return jsonify({'message': 'Password changed successfully'}), 200
        
    except Exception as e:
        logger.error(f"Change password error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

# Register the blueprint with the Flask app
def init_auth_routes(app):
    """Initialize authentication routes with the Flask app."""
    app.register_blueprint(auth_bp)
    
    # Initialize rate limiter
    limiter.init_app(app)
    
    logger.info("JWT authentication routes initialized")