"""Integration tests for API endpoints."""

import pytest
import json
from datetime import datetime
from unittest.mock import patch, Mock

class TestHealthAPI:
    """Test health check endpoints."""
    
    def test_health_check_success(self, client):
        """Test successful health check."""
        with patch('app.fraud_detector.get_model_status') as mock_status, \
             patch('app.db_manager.get_session') as mock_session:
            
            # Mock successful database connection
            mock_session.return_value.__enter__ = Mock()
            mock_session.return_value.__exit__ = Mock(return_value=None)
            mock_session.return_value.execute = Mock()
            
            # Mock successful model status
            mock_status.return_value = {
                'model_loaded': True,
                'model_info': {'model_version': 'test_v1.0.0'}
            }
            
            response = client.get('/api/v1/health')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['status'] == 'healthy'
            assert data['database_connection'] is True
            assert data['active_model_loaded'] is True
    
    def test_health_check_database_failure(self, client):
        """Test health check with database failure."""
        with patch('app.fraud_detector.get_model_status') as mock_status, \
             patch('app.db_manager.get_session') as mock_session:
            
            # Mock database connection failure
            mock_session.return_value.__enter__.side_effect = Exception("DB Error")
            
            # Mock successful model status
            mock_status.return_value = {
                'model_loaded': True,
                'model_info': {'model_version': 'test_v1.0.0'}
            }
            
            response = client.get('/api/v1/health')
            
            assert response.status_code == 503
            data = json.loads(response.data)
            assert data['status'] == 'unhealthy'
            assert data['database_connection'] is False
    
    def test_liveness_check(self, client):
        """Test liveness probe."""
        response = client.get('/api/v1/health/live')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'alive'

class TestUsersAPI:
    """Test user management endpoints."""
    
    def test_create_user_success(self, client):
        """Test successful user creation."""
        user_data = {
            'name': 'Test User',
            'email': 'test@example.com'
        }
        
        with patch('app.db_manager.get_session') as mock_session:
            # Mock session
            mock_session_obj = Mock()
            mock_session_obj.__enter__ = Mock(return_value=mock_session_obj)
            mock_session_obj.__exit__ = Mock(return_value=None)
            mock_session_obj.add = Mock()
            mock_session_obj.flush = Mock()
            mock_session_obj.commit = Mock()
            
            # Mock user object
            mock_user = Mock()
            mock_user.id = 1
            mock_session_obj.add.side_effect = lambda user: setattr(user, 'id', 1)
            
            mock_session.return_value = mock_session_obj
            
            response = client.post('/api/v1/users', 
                                 data=json.dumps(user_data),
                                 content_type='application/json')
            
            assert response.status_code == 201
            data = json.loads(response.data)
            assert data['name'] == user_data['name']
            assert data['email'] == user_data['email']
            assert 'id' in data
    
    def test_create_user_invalid_data(self, client):
        """Test user creation with invalid data."""
        user_data = {
            'name': '',  # Invalid: empty name
            'email': 'invalid-email'  # Invalid: not a proper email
        }
        
        response = client.post('/api/v1/users',
                             data=json.dumps(user_data),
                             content_type='application/json')
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['error'] == 'Validation Error'
    
    def test_create_user_no_data(self, client):
        """Test user creation with no JSON data."""
        response = client.post('/api/v1/users',
                             content_type='application/json')
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['error'] == 'Bad Request'
    
    def test_get_user_success(self, client):
        """Test successful user retrieval.""" 
        with patch('app.db_manager.get_session') as mock_session:
            # Mock session and user
            mock_session_obj = Mock()
            mock_session_obj.__enter__ = Mock(return_value=mock_session_obj)
            mock_session_obj.__exit__ = Mock(return_value=None)
            
            mock_user = Mock()
            mock_user.id = 1
            mock_user.name = 'Test User'
            mock_user.email = 'test@example.com'
            mock_user.created_at = datetime.utcnow()
            
            mock_session_obj.query.return_value.filter.return_value.first.return_value = mock_user
            mock_session.return_value = mock_session_obj
            
            response = client.get('/api/v1/users/1')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['id'] == 1
            assert data['name'] == 'Test User'
            assert data['email'] == 'test@example.com'
    
    def test_get_user_not_found(self, client):
        """Test user retrieval when user doesn't exist."""
        with patch('app.db_manager.get_session') as mock_session:
            # Mock session returning no user
            mock_session_obj = Mock()
            mock_session_obj.__enter__ = Mock(return_value=mock_session_obj)
            mock_session_obj.__exit__ = Mock(return_value=None)
            mock_session_obj.query.return_value.filter.return_value.first.return_value = None
            mock_session.return_value = mock_session_obj
            
            response = client.get('/api/v1/users/999')
            
            assert response.status_code == 404
            data = json.loads(response.data)
            assert data['error'] == 'Not Found'

class TestTransactionsAPI:
    """Test transaction endpoints."""
    
    def test_create_transaction_success(self, client, mock_transaction_data):
        """Test successful transaction creation."""
        with patch('app.db_manager.get_session') as mock_session, \
             patch('app.fraud_detector.predict_fraud') as mock_predict, \
             patch('app.fraud_detector.save_prediction') as mock_save_pred:
            
            # Mock session and user
            mock_session_obj = Mock()
            mock_session_obj.__enter__ = Mock(return_value=mock_session_obj)
            mock_session_obj.__exit__ = Mock(return_value=None)
            mock_session_obj.add = Mock()
            mock_session_obj.flush = Mock()
            mock_session_obj.commit = Mock()
            
            # Mock user exists
            mock_user = Mock()
            mock_user.id = 1
            mock_session_obj.query.return_value.filter.return_value.first.return_value = mock_user
            
            # Mock transaction ID
            mock_session_obj.flush.side_effect = lambda: setattr(
                mock_session_obj.add.call_args[0][0], 'id', 1
            )
            
            # Mock fraud prediction
            mock_predict.return_value = {
                'fraud_probability': 0.25,
                'prediction_label': False,
                'confidence_score': 0.75,
                'model_version': 'test_v1.0.0',
                'inference_time_ms': 50.0
            }
            
            mock_save_pred.return_value = 1
            mock_session.return_value = mock_session_obj
            
            response = client.post('/api/v1/transactions',
                                 data=json.dumps(mock_transaction_data),
                                 content_type='application/json')
            
            assert response.status_code == 201
            data = json.loads(response.data)
            assert 'id' in data
            assert data['amount'] == mock_transaction_data['amount']
            assert 'prediction' in data
            assert data['prediction']['fraud_probability'] == 0.25
    
    def test_create_transaction_user_not_found(self, client, mock_transaction_data):
        """Test transaction creation when user doesn't exist."""
        with patch('app.db_manager.get_session') as mock_session:
            # Mock session returning no user
            mock_session_obj = Mock()
            mock_session_obj.__enter__ = Mock(return_value=mock_session_obj)
            mock_session_obj.__exit__ = Mock(return_value=None)
            mock_session_obj.query.return_value.filter.return_value.first.return_value = None
            mock_session.return_value = mock_session_obj
            
            response = client.post('/api/v1/transactions',
                                 data=json.dumps(mock_transaction_data),
                                 content_type='application/json')
            
            assert response.status_code == 404
            data = json.loads(response.data)
            assert data['error'] == 'Not Found'
    
    def test_create_transaction_invalid_data(self, client):
        """Test transaction creation with invalid data."""
        invalid_data = {
            'user_id': 'invalid',  # Should be integer
            'amount': -100,  # Should be positive
            'currency': 'INVALID',  # Should be 3 letters
        }
        
        response = client.post('/api/v1/transactions',
                             data=json.dumps(invalid_data),
                             content_type='application/json')
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['error'] == 'Validation Error'
    
    def test_get_transaction_success(self, client):
        """Test successful transaction retrieval."""
        with patch('app.db_manager.get_session') as mock_session:
            # Mock session, transaction, and prediction
            mock_session_obj = Mock()
            mock_session_obj.__enter__ = Mock(return_value=mock_session_obj)
            mock_session_obj.__exit__ = Mock(return_value=None)
            
            # Mock transaction
            mock_transaction = Mock()
            mock_transaction.id = 1
            mock_transaction.user_id = 1
            mock_transaction.amount = 100.50
            mock_transaction.currency = 'USD'
            mock_transaction.merchant_category = 'retail'
            mock_transaction.device_id = 'device123'
            mock_transaction.ip_address = '192.168.1.1'
            mock_transaction.timestamp = datetime.utcnow()
            mock_transaction.created_at = datetime.utcnow()
            
            # Mock prediction
            mock_prediction = Mock()
            mock_prediction.id = 1
            mock_prediction.transaction_id = 1
            mock_prediction.model_version = 'test_v1.0.0'
            mock_prediction.fraud_probability = 0.25
            mock_prediction.prediction_label = False
            mock_prediction.confidence_score = 0.75
            mock_prediction.inference_time_ms = 50
            mock_prediction.created_at = datetime.utcnow()
            
            # Setup query mocks
            query_mock = Mock()
            query_mock.filter.return_value.first.return_value = mock_transaction
            query_mock.filter.return_value.order_by.return_value.first.return_value = mock_prediction
            
            mock_session_obj.query.return_value = query_mock
            mock_session.return_value = mock_session_obj
            
            response = client.get('/api/v1/transactions/1')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['id'] == 1
            assert data['amount'] == 100.50
            assert 'prediction' in data
    
    def test_get_transaction_not_found(self, client):
        """Test transaction retrieval when transaction doesn't exist."""
        with patch('app.db_manager.get_session') as mock_session:
            # Mock session returning no transaction
            mock_session_obj = Mock()
            mock_session_obj.__enter__ = Mock(return_value=mock_session_obj)
            mock_session_obj.__exit__ = Mock(return_value=None)
            mock_session_obj.query.return_value.filter.return_value.first.return_value = None
            mock_session.return_value = mock_session_obj
            
            response = client.get('/api/v1/transactions/999')
            
            assert response.status_code == 404
            data = json.loads(response.data)
            assert data['error'] == 'Not Found'

class TestModelsAPI:
    """Test model management endpoints."""
    
    def test_get_active_model(self, client):
        """Test getting active model information."""
        with patch('app.fraud_detector.get_model_status') as mock_status:
            mock_status.return_value = {
                'model_loaded': True,
                'model_info': {
                    'model_version': 'test_v1.0.0',
                    'model_type': 'logistic_regression',
                    'inference_count': 10,
                    'average_inference_time_ms': 25.5
                },
                'fraud_threshold': 0.5,
                'high_risk_threshold': 0.8,
                'status': 'healthy'
            }
            
            response = client.get('/api/v1/models/active')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['is_model_loaded'] is True
            assert data['active_model']['model_version'] == 'test_v1.0.0'
    
    def test_train_model_request(self, client):
        """Test model training request."""
        training_request = {
            'model_type': 'logistic_regression',
            'hyperparameters': {'C': 1.0}
        }
        
        response = client.post('/api/v1/train',
                             data=json.dumps(training_request),
                             content_type='application/json')
        
        # Should return 202 (Accepted) as training starts in background
        assert response.status_code == 202
        data = json.loads(response.data)
        assert 'message' in data
        assert data['model_type'] == 'logistic_regression'
        assert data['status'] == 'training_started'
    
    def test_train_model_invalid_type(self, client):
        """Test model training with invalid model type."""
        training_request = {
            'model_type': 'invalid_model'
        }
        
        response = client.post('/api/v1/train',
                             data=json.dumps(training_request),
                             content_type='application/json')
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['error'] == 'Validation Error'
    
    def test_get_training_status_idle(self, client):
        """Test getting training status when idle."""
        response = client.get('/api/v1/train/status')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'idle'
    
    def test_list_models(self, client):
        """Test listing all models."""
        with patch('app.db_manager.get_session') as mock_session:
            # Mock session and models
            mock_session_obj = Mock()
            mock_session_obj.__enter__ = Mock(return_value=mock_session_obj)
            mock_session_obj.__exit__ = Mock(return_value=None)
            
            mock_model = Mock()
            mock_model.model_name = 'fraud_detector_test'
            mock_model.model_version = 'test_v1.0.0'
            mock_model.model_type = 'logistic_regression'
            mock_model.metrics = {'auc': 0.85}
            mock_model.is_active = True
            mock_model.created_at = datetime.utcnow()
            mock_model.feature_schema_version = '1.0.0'
            
            mock_session_obj.query.return_value.order_by.return_value.all.return_value = [mock_model]
            mock_session.return_value = mock_session_obj
            
            response = client.get('/api/v1/models')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert 'total_models' in data
            assert 'models' in data
            assert len(data['models']) == 1