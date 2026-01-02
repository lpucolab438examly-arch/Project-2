"""Logging configuration and utilities."""

import logging
import structlog
import sys
from datetime import datetime
from typing import Dict, Any

def setup_logging(log_level: str = "INFO", log_format: str = "json") -> None:
    """Setup structured logging configuration."""
    
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer() if log_format == "json" else structlog.dev.ConsoleRenderer()
        ],
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, log_level.upper())),
        logger_factory=structlog.WriteLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )
    
    # Configure standard logging
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)]
    )

def get_logger(name: str) -> structlog.BoundLogger:
    """Get a structured logger instance."""
    return structlog.get_logger(name)

class RequestLogger:
    """Request/response logging utility."""
    
    def __init__(self):
        self.logger = get_logger(__name__)
    
    def log_request(self, request_id: str, method: str, path: str, 
                   payload: Dict[str, Any] = None, user_id: int = None) -> None:
        """Log incoming request."""
        self.logger.info(
            "request_received",
            request_id=request_id,
            method=method,
            path=path,
            payload_size=len(str(payload)) if payload else 0,
            user_id=user_id,
            timestamp=datetime.utcnow().isoformat()
        )
    
    def log_response(self, request_id: str, status_code: int, 
                    response_size: int = None, duration_ms: float = None) -> None:
        """Log outgoing response."""
        self.logger.info(
            "response_sent",
            request_id=request_id,
            status_code=status_code,
            response_size=response_size,
            duration_ms=duration_ms,
            timestamp=datetime.utcnow().isoformat()
        )
    
    def log_error(self, request_id: str, error: Exception, 
                  context: Dict[str, Any] = None) -> None:
        """Log error with context."""
        self.logger.error(
            "request_error",
            request_id=request_id,
            error_type=type(error).__name__,
            error_message=str(error),
            context=context or {},
            timestamp=datetime.utcnow().isoformat()
        )

class ModelLogger:
    """Model training and inference logging utility."""
    
    def __init__(self):
        self.logger = get_logger(__name__)
    
    def log_training_start(self, model_type: str, training_data_size: int,
                          hyperparameters: Dict[str, Any] = None) -> None:
        """Log model training start."""
        self.logger.info(
            "model_training_start",
            model_type=model_type,
            training_data_size=training_data_size,
            hyperparameters=hyperparameters or {},
            timestamp=datetime.utcnow().isoformat()
        )
    
    def log_training_complete(self, model_version: str, model_type: str,
                             metrics: Dict[str, float], duration_seconds: float) -> None:
        """Log model training completion."""
        self.logger.info(
            "model_training_complete",
            model_version=model_version,
            model_type=model_type,
            metrics=metrics,
            duration_seconds=duration_seconds,
            timestamp=datetime.utcnow().isoformat()
        )
    
    def log_prediction(self, transaction_id: int, model_version: str,
                      fraud_probability: float, prediction_label: bool,
                      inference_time_ms: float) -> None:
        """Log fraud prediction."""
        self.logger.info(
            "fraud_prediction",
            transaction_id=transaction_id,
            model_version=model_version,
            fraud_probability=fraud_probability,
            prediction_label=prediction_label,
            inference_time_ms=inference_time_ms,
            timestamp=datetime.utcnow().isoformat()
        )
    
    def log_feature_extraction(self, transaction_id: int, feature_count: int,
                              extraction_time_ms: float) -> None:
        """Log feature extraction."""
        self.logger.info(
            "feature_extraction",
            transaction_id=transaction_id,
            feature_count=feature_count,
            extraction_time_ms=extraction_time_ms,
            timestamp=datetime.utcnow().isoformat()
        )