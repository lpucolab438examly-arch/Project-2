"""API schemas for request/response validation using Marshmallow."""

from marshmallow import Schema, fields, validate, post_load, ValidationError
from datetime import datetime
from typing import Dict, Any
import re

class TransactionRequestSchema(Schema):
    """Schema for transaction creation requests."""
    
    user_id = fields.Integer(required=True, validate=validate.Range(min=1))
    amount = fields.Decimal(required=True, validate=validate.Range(min=0.01), places=2)
    currency = fields.String(
        required=True, 
        validate=validate.Regexp(r'^[A-Z]{3}$', error='Currency must be 3 uppercase letters')
    )
    merchant_category = fields.String(required=True, validate=validate.Length(min=1, max=100))
    device_id = fields.String(required=False, allow_none=True, validate=validate.Length(max=255))
    ip_address = fields.IP(required=False, allow_none=True)
    timestamp = fields.DateTime(required=True)
    raw_payload = fields.Dict(required=True)
    
    @post_load
    def validate_timestamp(self, data, **kwargs):
        """Validate timestamp is not in the future."""
        if data['timestamp'] > datetime.utcnow():
            raise ValidationError('Transaction timestamp cannot be in the future')
        return data

class TransactionResponseSchema(Schema):
    """Schema for transaction response."""
    
    id = fields.Integer(required=True)
    user_id = fields.Integer(required=True)
    amount = fields.Decimal(required=True, places=2)
    currency = fields.String(required=True)
    merchant_category = fields.String(required=True)
    device_id = fields.String(required=False, allow_none=True)
    ip_address = fields.String(required=False, allow_none=True)
    timestamp = fields.DateTime(required=True)
    created_at = fields.DateTime(required=True)
    
    # Nested fraud prediction
    prediction = fields.Nested('PredictionResponseSchema', required=False)

class PredictionRequestSchema(Schema):
    """Schema for standalone prediction requests."""
    
    transaction_id = fields.Integer(required=True, validate=validate.Range(min=1))

class PredictionResponseSchema(Schema):
    """Schema for prediction response."""
    
    id = fields.Integer(required=True)
    transaction_id = fields.Integer(required=True)
    model_version = fields.String(required=True)
    fraud_probability = fields.Decimal(required=True, places=4)
    prediction_label = fields.Boolean(required=True)
    confidence_score = fields.Decimal(required=False, allow_none=True, places=4)
    inference_time_ms = fields.Integer(required=False, allow_none=True)
    created_at = fields.DateTime(required=True)

class ModelTrainingRequestSchema(Schema):
    """Schema for model training requests."""
    
    model_type = fields.String(
        required=True,
        validate=validate.OneOf(['logistic_regression', 'random_forest', 'gradient_boosting'])
    )
    train_start_date = fields.DateTime(required=False, allow_none=True)
    train_end_date = fields.DateTime(required=False, allow_none=True)
    hyperparameters = fields.Dict(required=False, allow_none=True)
    
    @post_load
    def validate_dates(self, data, **kwargs):
        """Validate date range."""
        start_date = data.get('train_start_date')
        end_date = data.get('train_end_date')
        
        if start_date and end_date and start_date >= end_date:
            raise ValidationError('train_start_date must be before train_end_date')
        
        return data

class ModelTrainingResponseSchema(Schema):
    """Schema for model training response."""
    
    model_id = fields.Integer(required=True)
    model_name = fields.String(required=True)
    model_version = fields.String(required=True)
    model_type = fields.String(required=True)
    metrics = fields.Dict(required=True)
    training_duration_seconds = fields.Float(required=True)
    training_samples = fields.Integer(required=True)
    created_at = fields.DateTime(required=True)

class ModelMetricsResponseSchema(Schema):
    """Schema for model metrics response."""
    
    model_version = fields.String(required=True)
    model_type = fields.String(required=True)
    metrics = fields.Dict(required=True)
    created_at = fields.DateTime(required=True)
    is_active = fields.Boolean(required=True)

class HealthCheckResponseSchema(Schema):
    """Schema for health check response."""
    
    status = fields.String(required=True, validate=validate.OneOf(['healthy', 'unhealthy']))
    timestamp = fields.DateTime(required=True)
    version = fields.String(required=True)
    database_connection = fields.Boolean(required=True)
    active_model_loaded = fields.Boolean(required=True)
    active_model_version = fields.String(required=False, allow_none=True)

class UserCreateSchema(Schema):
    """Schema for user creation."""
    
    name = fields.String(required=True, validate=validate.Length(min=1, max=255))
    email = fields.Email(required=True)

class UserResponseSchema(Schema):
    """Schema for user response."""
    
    id = fields.Integer(required=True)
    name = fields.String(required=True)
    email = fields.String(required=True)
    created_at = fields.DateTime(required=True)

class ErrorResponseSchema(Schema):
    """Schema for error responses."""
    
    error = fields.String(required=True)
    message = fields.String(required=True)
    status_code = fields.Integer(required=True)
    timestamp = fields.DateTime(required=True)
    path = fields.String(required=True)
    
class BulkTransactionRequestSchema(Schema):
    """Schema for bulk transaction processing."""
    
    transactions = fields.List(
        fields.Nested(TransactionRequestSchema),
        required=True,
        validate=validate.Length(min=1, max=100)  # Limit bulk size
    )

class BulkTransactionResponseSchema(Schema):
    """Schema for bulk transaction response."""
    
    processed_count = fields.Integer(required=True)
    successful_count = fields.Integer(required=True)
    failed_count = fields.Integer(required=True)
    results = fields.List(fields.Nested(TransactionResponseSchema), required=True)
    errors = fields.List(fields.Dict(), required=True)