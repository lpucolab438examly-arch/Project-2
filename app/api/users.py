"""Users API endpoints."""

from flask import Blueprint, request, jsonify
from marshmallow import ValidationError
from datetime import datetime
from sqlalchemy.exc import IntegrityError

from app.schemas.api_schemas import UserCreateSchema, UserResponseSchema
from app.models.database import User
from app.utils.logging import get_logger
from app import db_manager

users_bp = Blueprint('users', __name__)
logger = get_logger(__name__)

# Schema instances
user_create_schema = UserCreateSchema()
user_response_schema = UserResponseSchema()

@users_bp.route('/users', methods=['POST'])
def create_user():
    """Create a new user."""
    
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
            validated_data = user_create_schema.load(json_data)
        except ValidationError as e:
            return jsonify({
                'error': 'Validation Error',
                'message': e.messages,
                'status_code': 400,
                'timestamp': datetime.utcnow().isoformat()
            }), 400
        
        # Create user
        with db_manager.get_session() as session:
            user = User(
                name=validated_data['name'],
                email=validated_data['email']
            )
            
            try:
                session.add(user)
                session.flush()  # Get user ID
                user_id = user.id
                session.commit()
                
                logger.info(f"Created user {user_id} with email {validated_data['email']}")
                
            except IntegrityError as e:
                session.rollback()
                if 'email' in str(e.orig):
                    return jsonify({
                        'error': 'Conflict',
                        'message': f"User with email {validated_data['email']} already exists",
                        'status_code': 409,
                        'timestamp': datetime.utcnow().isoformat()
                    }), 409
                else:
                    raise
        
        # Prepare response
        response_data = user_response_schema.dump({
            'id': user_id,
            'name': validated_data['name'],
            'email': validated_data['email'],
            'created_at': datetime.utcnow()
        })
        
        return jsonify(response_data), 201
        
    except Exception as e:
        logger.error(f"Error creating user: {e}")
        return jsonify({
            'error': 'Internal Server Error',
            'message': str(e),
            'status_code': 500,
            'timestamp': datetime.utcnow().isoformat()
        }), 500

@users_bp.route('/users/<int:user_id>', methods=['GET'])
def get_user(user_id):
    """Get a specific user."""
    
    try:
        with db_manager.get_session() as session:
            user = session.query(User).filter(User.id == user_id).first()
            
            if not user:
                return jsonify({
                    'error': 'Not Found',
                    'message': f'User with ID {user_id} not found',
                    'status_code': 404,
                    'timestamp': datetime.utcnow().isoformat()
                }), 404
            
            # Prepare response
            response_data = user_response_schema.dump({
                'id': user.id,
                'name': user.name,
                'email': user.email,
                'created_at': user.created_at
            })
            
            return jsonify(response_data), 200
            
    except Exception as e:
        logger.error(f"Error retrieving user {user_id}: {e}")
        return jsonify({
            'error': 'Internal Server Error',
            'message': str(e),
            'status_code': 500,
            'timestamp': datetime.utcnow().isoformat()
        }), 500

@users_bp.route('/users', methods=['GET'])
def list_users():
    """List all users with pagination."""
    
    try:
        # Get query parameters
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 50, type=int), 100)  # Max 100 per page
        
        with db_manager.get_session() as session:
            # Query users with pagination
            users_query = session.query(User).order_by(User.created_at.desc())
            
            # Calculate total count
            total_users = users_query.count()
            
            # Apply pagination
            offset = (page - 1) * per_page
            users = users_query.offset(offset).limit(per_page).all()
            
            # Prepare response
            users_data = []
            for user in users:
                users_data.append(user_response_schema.dump({
                    'id': user.id,
                    'name': user.name,
                    'email': user.email,
                    'created_at': user.created_at
                }))
            
            # Pagination metadata
            total_pages = (total_users + per_page - 1) // per_page
            has_next = page < total_pages
            has_prev = page > 1
            
            return jsonify({
                'users': users_data,
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total_users': total_users,
                    'total_pages': total_pages,
                    'has_next': has_next,
                    'has_prev': has_prev
                },
                'timestamp': datetime.utcnow().isoformat()
            }), 200
            
    except Exception as e:
        logger.error(f"Error listing users: {e}")
        return jsonify({
            'error': 'Internal Server Error',
            'message': str(e),
            'status_code': 500,
            'timestamp': datetime.utcnow().isoformat()
        }), 500

@users_bp.route('/users/<int:user_id>/transactions', methods=['GET'])
def get_user_transactions(user_id):
    """Get transactions for a specific user."""
    
    try:
        # Get query parameters
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 50, type=int), 100)
        include_predictions = request.args.get('include_predictions', 'false').lower() == 'true'
        
        with db_manager.get_session() as session:
            # Check if user exists
            user = session.query(User).filter(User.id == user_id).first()
            if not user:
                return jsonify({
                    'error': 'Not Found',
                    'message': f'User with ID {user_id} not found',
                    'status_code': 404,
                    'timestamp': datetime.utcnow().isoformat()
                }), 404
            
            # Query user's transactions
            from app.models.database import Transaction, Prediction
            
            transactions_query = session.query(Transaction).filter(
                Transaction.user_id == user_id
            ).order_by(Transaction.timestamp.desc())
            
            # Calculate total count
            total_transactions = transactions_query.count()
            
            # Apply pagination
            offset = (page - 1) * per_page
            transactions = transactions_query.offset(offset).limit(per_page).all()
            
            # Prepare response
            transactions_data = []
            for transaction in transactions:
                transaction_data = {
                    'id': transaction.id,
                    'amount': float(transaction.amount),
                    'currency': transaction.currency,
                    'merchant_category': transaction.merchant_category,
                    'device_id': transaction.device_id,
                    'ip_address': transaction.ip_address,
                    'timestamp': transaction.timestamp.isoformat(),
                    'created_at': transaction.created_at.isoformat()
                }
                
                # Include predictions if requested
                if include_predictions:
                    prediction = session.query(Prediction).filter(
                        Prediction.transaction_id == transaction.id
                    ).order_by(Prediction.created_at.desc()).first()
                    
                    if prediction:
                        transaction_data['prediction'] = {
                            'id': prediction.id,
                            'model_version': prediction.model_version,
                            'fraud_probability': float(prediction.fraud_probability),
                            'prediction_label': prediction.prediction_label,
                            'confidence_score': float(prediction.confidence_score) if prediction.confidence_score else None,
                            'inference_time_ms': prediction.inference_time_ms,
                            'created_at': prediction.created_at.isoformat()
                        }
                
                transactions_data.append(transaction_data)
            
            # Pagination metadata
            total_pages = (total_transactions + per_page - 1) // per_page
            has_next = page < total_pages
            has_prev = page > 1
            
            return jsonify({
                'user_id': user_id,
                'transactions': transactions_data,
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total_transactions': total_transactions,
                    'total_pages': total_pages,
                    'has_next': has_next,
                    'has_prev': has_prev
                },
                'include_predictions': include_predictions,
                'timestamp': datetime.utcnow().isoformat()
            }), 200
            
    except Exception as e:
        logger.error(f"Error getting transactions for user {user_id}: {e}")
        return jsonify({
            'error': 'Internal Server Error',
            'message': str(e),
            'status_code': 500,
            'timestamp': datetime.utcnow().isoformat()
        }), 500

@users_bp.route('/users/<int:user_id>', methods=['PUT'])
def update_user(user_id):
    """Update a user's information."""
    
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
            validated_data = user_create_schema.load(json_data)
        except ValidationError as e:
            return jsonify({
                'error': 'Validation Error',
                'message': e.messages,
                'status_code': 400,
                'timestamp': datetime.utcnow().isoformat()
            }), 400
        
        with db_manager.get_session() as session:
            # Check if user exists
            user = session.query(User).filter(User.id == user_id).first()
            if not user:
                return jsonify({
                    'error': 'Not Found',
                    'message': f'User with ID {user_id} not found',
                    'status_code': 404,
                    'timestamp': datetime.utcnow().isoformat()
                }), 404
            
            # Update user
            try:
                user.name = validated_data['name']
                user.email = validated_data['email']
                session.commit()
                
                logger.info(f"Updated user {user_id}")
                
            except IntegrityError as e:
                session.rollback()
                if 'email' in str(e.orig):
                    return jsonify({
                        'error': 'Conflict',
                        'message': f"User with email {validated_data['email']} already exists",
                        'status_code': 409,
                        'timestamp': datetime.utcnow().isoformat()
                    }), 409
                else:
                    raise
            
            # Prepare response
            response_data = user_response_schema.dump({
                'id': user.id,
                'name': user.name,
                'email': user.email,
                'created_at': user.created_at
            })
            
            return jsonify(response_data), 200
            
    except Exception as e:
        logger.error(f"Error updating user {user_id}: {e}")
        return jsonify({
            'error': 'Internal Server Error',
            'message': str(e),
            'status_code': 500,
            'timestamp': datetime.utcnow().isoformat()
        }), 500