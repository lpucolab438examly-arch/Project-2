"""Health check API endpoints."""

from flask import Blueprint, jsonify
from datetime import datetime
import os

from app.schemas.api_schemas import HealthCheckResponseSchema
from app.utils.logging import get_logger
from app import db_manager, fraud_detector

health_bp = Blueprint('health', __name__)
logger = get_logger(__name__)

health_response_schema = HealthCheckResponseSchema()

@health_bp.route('/health', methods=['GET'])
def health_check():
    """Comprehensive health check endpoint."""
    
    try:
        health_status = 'healthy'
        checks = {}
        
        # Database connection check
        try:
            with db_manager.get_session() as session:
                # Simple query to test connection
                session.execute('SELECT 1')
                checks['database_connection'] = True
        except Exception as e:
            checks['database_connection'] = False
            health_status = 'unhealthy'
            logger.error(f"Database health check failed: {e}")
        
        # Model loading check
        try:
            model_status = fraud_detector.get_model_status()
            checks['active_model_loaded'] = model_status['model_loaded']
            checks['active_model_version'] = model_status.get('model_info', {}).get('model_version')
            
            if not model_status['model_loaded']:
                health_status = 'unhealthy'
        except Exception as e:
            checks['active_model_loaded'] = False
            checks['active_model_version'] = None
            health_status = 'unhealthy'
            logger.error(f"Model health check failed: {e}")
        
        # Application version
        app_version = os.environ.get('APP_VERSION', '1.0.0')
        
        # Prepare response
        response_data = health_response_schema.dump({
            'status': health_status,
            'timestamp': datetime.utcnow(),
            'version': app_version,
            'database_connection': checks['database_connection'],
            'active_model_loaded': checks['active_model_loaded'],
            'active_model_version': checks['active_model_version']
        })
        
        status_code = 200 if health_status == 'healthy' else 503
        return jsonify(response_data), status_code
        
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return jsonify({
            'status': 'unhealthy',
            'timestamp': datetime.utcnow().isoformat(),
            'version': os.environ.get('APP_VERSION', '1.0.0'),
            'database_connection': False,
            'active_model_loaded': False,
            'active_model_version': None,
            'error': str(e)
        }), 503

@health_bp.route('/health/detailed', methods=['GET'])
def detailed_health_check():
    """Detailed health check with performance metrics."""
    
    try:
        health_status = 'healthy'
        checks = {}
        performance_metrics = {}
        
        # Database connection and performance
        try:
            import time
            start_time = time.time()
            
            with db_manager.get_session() as session:
                session.execute('SELECT 1')
                # Count total transactions
                from app.models.database import Transaction
                transaction_count = session.query(Transaction).count()
                
            db_response_time = (time.time() - start_time) * 1000
            
            checks['database_connection'] = True
            performance_metrics['database_response_time_ms'] = round(db_response_time, 2)
            performance_metrics['total_transactions'] = transaction_count
            
        except Exception as e:
            checks['database_connection'] = False
            health_status = 'unhealthy'
            logger.error(f"Database health check failed: {e}")
        
        # Model status and performance
        try:
            model_status = fraud_detector.get_model_status()
            checks['active_model_loaded'] = model_status['model_loaded']
            checks['active_model_version'] = model_status.get('model_info', {}).get('model_version')
            
            if model_status['model_info']:
                performance_metrics.update({
                    'model_inference_count': model_status['model_info'].get('inference_count', 0),
                    'model_avg_inference_time_ms': model_status['model_info'].get('average_inference_time_ms', 0)
                })
            
            if not model_status['model_loaded']:
                health_status = 'unhealthy'
                
        except Exception as e:
            checks['active_model_loaded'] = False
            checks['active_model_version'] = None
            health_status = 'unhealthy'
            logger.error(f"Model health check failed: {e}")
        
        # Memory usage
        try:
            import psutil
            process = psutil.Process()
            memory_info = process.memory_info()
            performance_metrics.update({
                'memory_usage_mb': round(memory_info.rss / 1024 / 1024, 2),
                'cpu_percent': process.cpu_percent()
            })
        except Exception as e:
            logger.warning(f"Could not get system metrics: {e}")
        
        # System uptime
        try:
            with open('/proc/uptime', 'r') as f:
                uptime_seconds = float(f.readline().split()[0])
                performance_metrics['system_uptime_hours'] = round(uptime_seconds / 3600, 2)
        except Exception:
            pass  # Not critical
        
        return jsonify({
            'status': health_status,
            'timestamp': datetime.utcnow().isoformat(),
            'version': os.environ.get('APP_VERSION', '1.0.0'),
            'checks': checks,
            'performance_metrics': performance_metrics
        }), 200 if health_status == 'healthy' else 503
        
    except Exception as e:
        logger.error(f"Detailed health check error: {e}")
        return jsonify({
            'status': 'unhealthy',
            'timestamp': datetime.utcnow().isoformat(),
            'error': str(e)
        }), 503

@health_bp.route('/health/ready', methods=['GET'])
def readiness_check():
    """Kubernetes readiness probe endpoint."""
    
    try:
        # Check critical dependencies
        with db_manager.get_session() as session:
            session.execute('SELECT 1')
        
        # Check if fraud detector is initialized
        model_status = fraud_detector.get_model_status()
        if not model_status['is_initialized']:
            return jsonify({'status': 'not_ready', 'reason': 'fraud_detector_not_initialized'}), 503
        
        return jsonify({'status': 'ready', 'timestamp': datetime.utcnow().isoformat()}), 200
        
    except Exception as e:
        return jsonify({
            'status': 'not_ready',
            'reason': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 503

@health_bp.route('/health/live', methods=['GET']) 
def liveness_check():
    """Kubernetes liveness probe endpoint."""
    
    # Simple check that the application is running
    return jsonify({
        'status': 'alive',
        'timestamp': datetime.utcnow().isoformat()
    }), 200