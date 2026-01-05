"""Transaction API endpoints."""

from flask import Blueprint, request, jsonify, g
from marshmallow import ValidationError
from datetime import datetime
import time

from app.schemas.api_schemas import (
    TransactionRequestSchema, TransactionResponseSchema, 
    PredictionResponseSchema, BulkTransactionRequestSchema,
    BulkTransactionResponseSchema
)
from app.models.database import Transaction, User
from app.utils.logging import get_logger
from app.security.middleware import require_api_key, rate_limit, InputValidator
from app import db_manager, fraud_detector, request_logger

transactions_bp = Blueprint('transactions', __name__)
logger = get_logger(__name__)

# Schema instances
transaction_request_schema = TransactionRequestSchema()
transaction_response_schema = TransactionResponseSchema()
prediction_response_schema = PredictionResponseSchema()
bulk_request_schema = BulkTransactionRequestSchema()
bulk_response_schema = BulkTransactionResponseSchema()

@transactions_bp.route('/transactions', methods=['POST'])
@require_api_key(['write'])
@rate_limit(50, window=60, per='user')  # 50 requests per minute per user
@InputValidator.validate_json_payload({
    'user_id': {'required': True, 'type': str},
    'amount': {'required': True, 'type': (int, float), 'min': 0, 'max': 1000000},
    'merchant': {'required': True, 'type': str},
    'merchant_category': {'required': True, 'type': str}
})
def create_transaction():
    """Create a new transaction and perform fraud detection."""
    
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
            validated_data = transaction_request_schema.load(json_data)
        except ValidationError as e:
            return jsonify({
                'error': 'Validation Error',
                'message': e.messages,
                'status_code': 400,
                'timestamp': datetime.utcnow().isoformat()
            }), 400
        
        with db_manager.get_session() as session:
            # Check if user exists
            user = session.query(User).filter(User.id == validated_data['user_id']).first()
            if not user:
                return jsonify({
                    'error': 'Not Found',
                    'message': f"User with ID {validated_data['user_id']} not found",
                    'status_code': 404,
                    'timestamp': datetime.utcnow().isoformat()
                }), 404
            
            # Create transaction
            transaction = Transaction(
                user_id=validated_data['user_id'],
                amount=validated_data['amount'],
                currency=validated_data['currency'],
                merchant_category=validated_data['merchant_category'],
                device_id=validated_data.get('device_id'),
                ip_address=validated_data.get('ip_address'),
                timestamp=validated_data['timestamp'],
                raw_payload=validated_data['raw_payload']
            )
            
            session.add(transaction)
            session.flush()  # Get transaction ID
            transaction_id = transaction.id
            session.commit()
            
            logger.info(f"Created transaction {transaction_id}")
        
        # Perform fraud detection
        try:
            # Prepare transaction data for inference
            transaction_data = {
                'id': transaction_id,
                'user_id': validated_data['user_id'],
                'amount': validated_data['amount'],
                'currency': validated_data['currency'],
                'merchant_category': validated_data['merchant_category'],
                'device_id': validated_data.get('device_id'),
                'ip_address': validated_data.get('ip_address'),
                'timestamp': validated_data['timestamp'],
                'raw_payload': validated_data['raw_payload']
            }
            
            # Predict fraud
            prediction_result = fraud_detector.predict_fraud(transaction_data)
            
            # Save prediction to database
            prediction_id = fraud_detector.save_prediction(transaction_id, prediction_result)
            
            logger.info(f"Fraud prediction completed for transaction {transaction_id}: {prediction_result['prediction_label']}")
            
        except Exception as e:
            logger.error(f"Error in fraud detection for transaction {transaction_id}: {e}")
            # Return transaction even if fraud detection fails
            prediction_result = {
                'fraud_probability': None,
                'prediction_label': None,
                'error': str(e)
            }
        
        # Prepare response
        response_data = transaction_response_schema.dump({
            'id': transaction_id,
            'user_id': validated_data['user_id'],
            'amount': validated_data['amount'],
            'currency': validated_data['currency'],
            'merchant_category': validated_data['merchant_category'],
            'device_id': validated_data.get('device_id'),
            'ip_address': validated_data.get('ip_address'),
            'timestamp': validated_data['timestamp'],
            'created_at': datetime.utcnow(),
            'prediction': {
                'id': prediction_id if 'error' not in prediction_result else None,
                'transaction_id': transaction_id,
                'model_version': prediction_result.get('model_version'),
                'fraud_probability': prediction_result.get('fraud_probability'),
                'prediction_label': prediction_result.get('prediction_label'),
                'confidence_score': prediction_result.get('confidence_score'),
                'inference_time_ms': prediction_result.get('inference_time_ms'),
                'created_at': datetime.utcnow()
            } if 'error' not in prediction_result else None
        })
        
        return jsonify(response_data), 201
        
    except Exception as e:
        logger.error(f"Error creating transaction: {e}")
        return jsonify({
            'error': 'Internal Server Error',
            'message': str(e),
            'status_code': 500,
            'timestamp': datetime.utcnow().isoformat()
        }), 500

@transactions_bp.route('/transactions/<int:transaction_id>', methods=['GET'])
@require_api_key(['read'])
@rate_limit(100, window=60, per='user')  # 100 reads per minute per user
def get_transaction(transaction_id):
    """Get a specific transaction with its prediction."""
    
    try:
        with db_manager.get_session() as session:
            # Query transaction with its prediction
            transaction = session.query(Transaction).filter(
                Transaction.id == transaction_id
            ).first()
            
            if not transaction:
                return jsonify({
                    'error': 'Not Found',
                    'message': f'Transaction with ID {transaction_id} not found',
                    'status_code': 404,
                    'timestamp': datetime.utcnow().isoformat()
                }), 404
            
            # Get the most recent prediction for this transaction
            from app.models.database import Prediction
            prediction = session.query(Prediction).filter(
                Prediction.transaction_id == transaction_id
            ).order_by(Prediction.created_at.desc()).first()
            
            # Prepare response
            response_data = {
                'id': transaction.id,
                'user_id': transaction.user_id,
                'amount': float(transaction.amount),
                'currency': transaction.currency,
                'merchant_category': transaction.merchant_category,
                'device_id': transaction.device_id,
                'ip_address': transaction.ip_address,
                'timestamp': transaction.timestamp.isoformat(),
                'created_at': transaction.created_at.isoformat(),
                'prediction': {
                    'id': prediction.id,
                    'transaction_id': prediction.transaction_id,
                    'model_version': prediction.model_version,
                    'fraud_probability': float(prediction.fraud_probability),
                    'prediction_label': prediction.prediction_label,
                    'confidence_score': float(prediction.confidence_score) if prediction.confidence_score else None,
                    'inference_time_ms': prediction.inference_time_ms,
                    'created_at': prediction.created_at.isoformat()
                } if prediction else None
            }
            
            return jsonify(response_data), 200
            
    except Exception as e:
        logger.error(f"Error retrieving transaction {transaction_id}: {e}")
        return jsonify({
            'error': 'Internal Server Error',
            'message': str(e),
            'status_code': 500,
            'timestamp': datetime.utcnow().isoformat()
        }), 500

@transactions_bp.route('/transactions/bulk', methods=['POST'])
@require_api_key(['write', 'bulk'])
@rate_limit(10, window=60, per='user')  # 10 bulk requests per minute per user
@InputValidator.validate_json_payload({
    'transactions': {'required': True, 'type': list}
})
def bulk_create_transactions():
    """Create multiple transactions and perform fraud detection."""
    
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
            validated_data = bulk_request_schema.load(json_data)
        except ValidationError as e:
            return jsonify({
                'error': 'Validation Error',
                'message': e.messages,
                'status_code': 400,
                'timestamp': datetime.utcnow().isoformat()
            }), 400
        
        transactions_data = validated_data['transactions']
        results = []
        successful_count = 0
        failed_count = 0
        errors = []
        
        for idx, transaction_data in enumerate(transactions_data):
            try:
                with db_manager.get_session() as session:
                    # Check if user exists
                    user = session.query(User).filter(User.id == transaction_data['user_id']).first()
                    if not user:
                        errors.append({
                            'index': idx,
                            'error': f"User with ID {transaction_data['user_id']} not found"
                        })
                        failed_count += 1
                        continue
                    
                    # Create transaction
                    transaction = Transaction(
                        user_id=transaction_data['user_id'],
                        amount=transaction_data['amount'],
                        currency=transaction_data['currency'],
                        merchant_category=transaction_data['merchant_category'],
                        device_id=transaction_data.get('device_id'),
                        ip_address=transaction_data.get('ip_address'),
                        timestamp=transaction_data['timestamp'],
                        raw_payload=transaction_data['raw_payload']
                    )
                    
                    session.add(transaction)
                    session.flush()
                    transaction_id = transaction.id
                    session.commit()
                
                # Perform fraud detection
                try:
                    inference_data = {
                        'id': transaction_id,
                        **transaction_data
                    }
                    prediction_result = fraud_detector.predict_fraud(inference_data)
                    prediction_id = fraud_detector.save_prediction(transaction_id, prediction_result)
                    
                    # Add to results
                    results.append({
                        'id': transaction_id,
                        'user_id': transaction_data['user_id'],
                        'amount': float(transaction_data['amount']),
                        'currency': transaction_data['currency'],
                        'merchant_category': transaction_data['merchant_category'],
                        'device_id': transaction_data.get('device_id'),
                        'ip_address': transaction_data.get('ip_address'),
                        'timestamp': transaction_data['timestamp'].isoformat(),
                        'created_at': datetime.utcnow().isoformat(),
                        'prediction': {
                            'id': prediction_id,
                            'transaction_id': transaction_id,
                            'model_version': prediction_result.get('model_version'),
                            'fraud_probability': prediction_result.get('fraud_probability'),
                            'prediction_label': prediction_result.get('prediction_label'),
                            'confidence_score': prediction_result.get('confidence_score'),
                            'inference_time_ms': prediction_result.get('inference_time_ms'),
                            'created_at': datetime.utcnow().isoformat()
                        }
                    })
                    
                    successful_count += 1
                    
                except Exception as e:
                    logger.error(f"Error in fraud detection for bulk transaction {idx}: {e}")
                    errors.append({
                        'index': idx,
                        'transaction_id': transaction_id,
                        'error': f"Fraud detection failed: {str(e)}"
                    })
                    failed_count += 1
                    
            except Exception as e:
                logger.error(f"Error creating bulk transaction {idx}: {e}")
                errors.append({
                    'index': idx,
                    'error': str(e)
                })
                failed_count += 1
        
        # Prepare response
        response_data = {
            'processed_count': len(transactions_data),
            'successful_count': successful_count,
            'failed_count': failed_count,
            'results': results,
            'errors': errors
        }
        
        status_code = 200 if failed_count == 0 else 207  # 207 Multi-Status for partial success
        return jsonify(response_data), status_code
        
    except Exception as e:
        logger.error(f"Error in bulk transaction creation: {e}")
        return jsonify({
            'error': 'Internal Server Error',
            'message': str(e),
            'status_code': 500,
            'timestamp': datetime.utcnow().isoformat()
        }), 500

@transactions_bp.route('/transactions/<int:transaction_id>/predict', methods=['POST'])
@require_api_key(['write'])
@rate_limit(50, window=60, per='user')  # 50 predictions per minute per user
def rerun_prediction(transaction_id):
    """Rerun fraud prediction for an existing transaction."""
    
    try:
        with db_manager.get_session() as session:
            # Get existing transaction
            transaction = session.query(Transaction).filter(
                Transaction.id == transaction_id
            ).first()
            
            if not transaction:
                return jsonify({
                    'error': 'Not Found',
                    'message': f'Transaction with ID {transaction_id} not found',
                    'status_code': 404,
                    'timestamp': datetime.utcnow().isoformat()
                }), 404
            
            # Prepare transaction data for inference
            transaction_data = {
                'id': transaction.id,
                'user_id': transaction.user_id,
                'amount': float(transaction.amount),
                'currency': transaction.currency,
                'merchant_category': transaction.merchant_category,
                'device_id': transaction.device_id,
                'ip_address': transaction.ip_address,
                'timestamp': transaction.timestamp,
                'raw_payload': transaction.raw_payload
            }
        
        # Perform fraud detection
        prediction_result = fraud_detector.predict_fraud(transaction_data)
        prediction_id = fraud_detector.save_prediction(transaction_id, prediction_result)
        
        # Prepare response
        response_data = prediction_response_schema.dump({
            'id': prediction_id,
            'transaction_id': transaction_id,
            'model_version': prediction_result['model_version'],
            'fraud_probability': prediction_result['fraud_probability'],
            'prediction_label': prediction_result['prediction_label'],
            'confidence_score': prediction_result.get('confidence_score'),
            'inference_time_ms': prediction_result.get('inference_time_ms'),
            'created_at': datetime.utcnow()
        })
        
        return jsonify(response_data), 200
        
    except Exception as e:
        logger.error(f"Error rerunning prediction for transaction {transaction_id}: {e}")
        return jsonify({
            'error': 'Internal Server Error',
            'message': str(e),
            'status_code': 500,
            'timestamp': datetime.utcnow().isoformat()
        }), 500