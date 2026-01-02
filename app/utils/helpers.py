"""Common utilities and helper functions."""

import uuid
import hashlib
import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
import time
from functools import wraps
from contextlib import contextmanager

def generate_correlation_id() -> str:
    """Generate unique correlation ID for request tracking."""
    return str(uuid.uuid4())

def generate_model_version() -> str:
    """Generate unique model version identifier."""
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    unique_id = str(uuid.uuid4())[:8]
    return f"model_{timestamp}_{unique_id}"

def generate_hash(data: Dict[str, Any], algorithm: str = 'sha256') -> str:
    """Generate hash for data integrity verification."""
    json_str = json.dumps(data, sort_keys=True, separators=(',', ':'))
    hash_obj = hashlib.new(algorithm)
    hash_obj.update(json_str.encode('utf-8'))
    return hash_obj.hexdigest()

def safe_float_conversion(value: Any, default: float = 0.0) -> float:
    """Safely convert value to float with fallback."""
    try:
        return float(value)
    except (ValueError, TypeError):
        return default

def safe_int_conversion(value: Any, default: int = 0) -> int:
    """Safely convert value to int with fallback."""
    try:
        return int(value)
    except (ValueError, TypeError):
        return default

def validate_json_schema(data: Dict[str, Any], required_keys: List[str]) -> bool:
    """Validate if JSON data contains required keys."""
    return all(key in data for key in required_keys)

def measure_execution_time(func):
    """Decorator to measure function execution time."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        execution_time = (end_time - start_time) * 1000  # Convert to milliseconds
        
        # Add execution time to result if it's a dict
        if isinstance(result, dict):
            result['execution_time_ms'] = execution_time
        
        return result
    return wrapper

@contextmanager
def timing_context(operation_name: str):
    """Context manager for timing operations."""
    start_time = time.time()
    try:
        yield
    finally:
        end_time = time.time()
        duration_ms = (end_time - start_time) * 1000
        print(f"{operation_name} completed in {duration_ms:.2f}ms")

class RateLimiter:
    """Simple in-memory rate limiter."""
    
    def __init__(self, max_requests: int, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = {}
    
    def is_allowed(self, identifier: str) -> bool:
        """Check if request is allowed for given identifier."""
        current_time = time.time()
        
        if identifier not in self.requests:
            self.requests[identifier] = []
        
        # Remove old requests outside the window
        self.requests[identifier] = [
            req_time for req_time in self.requests[identifier]
            if current_time - req_time < self.window_seconds
        ]
        
        # Check if under limit
        if len(self.requests[identifier]) < self.max_requests:
            self.requests[identifier].append(current_time)
            return True
        
        return False

def normalize_currency_amount(amount: float, from_currency: str, to_currency: str = 'USD') -> float:
    """Normalize currency amount to base currency (simplified version)."""
    # In production, this would use real exchange rates
    exchange_rates = {
        'USD': 1.0,
        'EUR': 1.1,
        'GBP': 1.3,
        'JPY': 0.007,
        'CAD': 0.8,
        'AUD': 0.7
    }
    
    if from_currency == to_currency:
        return amount
    
    # Convert to USD first, then to target currency
    usd_amount = amount / exchange_rates.get(from_currency, 1.0)
    return usd_amount * exchange_rates.get(to_currency, 1.0)

def extract_location_from_ip(ip_address: str) -> Dict[str, Any]:
    """Extract location information from IP address (simplified version)."""
    # In production, this would use a real GeoIP service
    # This is a simplified mock implementation
    if not ip_address:
        return {'country': 'US', 'region': 'Unknown', 'is_vpn': False}
    
    # Simple heuristic based on IP ranges (not accurate)
    ip_parts = ip_address.split('.')
    if len(ip_parts) == 4:
        first_octet = safe_int_conversion(ip_parts[0])
        if first_octet in range(192, 224):
            return {'country': 'US', 'region': 'North America', 'is_vpn': False}
        elif first_octet in range(80, 128):
            return {'country': 'EU', 'region': 'Europe', 'is_vpn': False}
        else:
            return {'country': 'Unknown', 'region': 'Unknown', 'is_vpn': True}
    
    return {'country': 'Unknown', 'region': 'Unknown', 'is_vpn': False}

def chunk_list(data: List[Any], chunk_size: int) -> List[List[Any]]:
    """Split list into chunks of specified size."""
    for i in range(0, len(data), chunk_size):
        yield data[i:i + chunk_size]

def get_business_hours_flag(timestamp: datetime) -> bool:
    """Determine if timestamp falls within business hours (9 AM - 5 PM UTC)."""
    return 9 <= timestamp.hour < 17

def get_weekend_flag(timestamp: datetime) -> bool:
    """Determine if timestamp falls on weekend."""
    return timestamp.weekday() >= 5  # Saturday=5, Sunday=6