"""Unit tests for model training and inference."""

import pytest
import pandas as pd
import numpy as np
import joblib
import os
import tempfile
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from app.training.model_trainer import ModelTrainer, ModelEvaluator
from app.inference.fraud_detector import (
    FraudDetectionInference, ModelManager, InferenceError, ModelLoadError
)

class TestModelTrainer:
    """Test ModelTrainer class."""
    
    @pytest.fixture
    def trainer(self, db_manager, temp_artifacts_dir):
        """Create model trainer for testing."""
        return ModelTrainer(db_manager, temp_artifacts_dir)
    
    def test_trainer_initialization(self, trainer, temp_artifacts_dir):
        """Test trainer initialization."""
        assert trainer.db_manager is not None
        assert trainer.artifacts_path == temp_artifacts_dir
        assert os.path.exists(trainer.models_path)
        assert os.path.exists(trainer.metrics_path)
        assert os.path.exists(trainer.preprocessing_path)
        assert len(trainer.model_configs) > 0
    
    def test_model_configs(self, trainer):
        """Test that model configurations are properly defined."""
        expected_models = ['logistic_regression', 'random_forest', 'gradient_boosting']
        
        for model_type in expected_models:
            assert model_type in trainer.model_configs
            config = trainer.model_configs[model_type]
            assert 'model' in config
            assert 'params' in config
    
    def test_calculate_metrics(self, trainer):
        """Test metrics calculation."""
        # Create mock predictions and labels
        y_train = pd.Series([0, 0, 1, 1, 0, 1, 0, 0, 1, 1])
        y_test = pd.Series([0, 1, 0, 1, 0])
        train_pred = np.array([0.1, 0.2, 0.7, 0.8, 0.3, 0.9, 0.1, 0.15, 0.85, 0.75])
        test_pred = np.array([0.2, 0.8, 0.3, 0.9, 0.1])
        
        metrics = trainer._calculate_metrics(y_train, train_pred, y_test, test_pred)
        
        # Check that all expected metrics are present
        expected_metrics = [
            'train_auc', 'test_auc', 'test_precision', 'test_recall', 'test_f1',
            'test_true_negatives', 'test_false_positives', 
            'test_false_negatives', 'test_true_positives', 'test_specificity'
        ]
        
        for metric in expected_metrics:
            assert metric in metrics
            assert isinstance(metrics[metric], (int, float))
    
    def test_train_model_invalid_type(self, trainer, mock_training_data):
        """Test training with invalid model type."""
        X, y = mock_training_data
        
        with pytest.raises(ValueError, match="Unknown model type"):
            trainer.train_model('invalid_model', X, y)
    
    @patch('app.training.model_trainer.GridSearchCV')
    @patch('app.training.model_trainer.cross_val_score')
    def test_train_model_success(self, mock_cv, mock_grid, trainer, mock_training_data, db_manager):
        """Test successful model training."""
        X, y = mock_training_data
        
        # Mock GridSearchCV
        mock_estimator = Mock()
        mock_estimator.predict_proba.return_value = np.random.rand(len(y), 2)
        
        mock_grid_instance = Mock()
        mock_grid_instance.fit.return_value = None
        mock_grid_instance.best_estimator_ = mock_estimator
        mock_grid_instance.best_params_ = {'C': 1.0}
        mock_grid_instance.best_score_ = 0.85
        
        mock_grid.return_value = mock_grid_instance
        
        # Mock cross_val_score
        mock_cv.return_value = np.array([0.8, 0.82, 0.85, 0.83, 0.81])
        
        # Mock joblib.dump
        with patch('joblib.dump') as mock_dump, \
             patch('builtins.open', Mock()), \
             patch('json.dump') as mock_json_dump:
            
            result = trainer.train_model('logistic_regression', X, y)
            
            # Check result structure
            assert 'model_version' in result
            assert 'model_type' in result
            assert 'metrics' in result
            assert 'best_parameters' in result
            assert 'training_duration' in result
            
            # Check that files were saved
            assert mock_dump.called
            assert mock_json_dump.called

class TestModelEvaluator:
    """Test ModelEvaluator class."""
    
    @pytest.fixture
    def evaluator(self, temp_artifacts_dir):
        """Create model evaluator for testing."""
        return ModelEvaluator(temp_artifacts_dir)
    
    def test_compare_models_empty(self, evaluator):
        """Test model comparison with empty list."""
        result = evaluator.compare_models([])
        
        assert 'error' in result
        assert result['error'] == 'No models to compare'
    
    def test_compare_models_success(self, evaluator):
        """Test successful model comparison."""
        model_results = [
            {
                'model_type': 'logistic_regression',
                'model_version': 'v1',
                'metrics': {
                    'test_auc': 0.85,
                    'test_precision': 0.80,
                    'test_recall': 0.75,
                    'test_f1': 0.77
                },
                'training_duration': 120.5
            },
            {
                'model_type': 'random_forest',
                'model_version': 'v2',
                'metrics': {
                    'test_auc': 0.88,
                    'test_precision': 0.82,
                    'test_recall': 0.78,
                    'test_f1': 0.80
                },
                'training_duration': 300.2
            }
        ]
        
        result = evaluator.compare_models(model_results)
        
        # Check result structure
        assert 'summary' in result
        assert 'models' in result
        assert 'rankings' in result
        assert 'recommendations' in result
        
        # Check that best model is identified
        best_auc_model = result['rankings']['by_auc'][0]
        assert best_auc_model['model_type'] == 'random_forest'
        assert best_auc_model['test_auc'] == 0.88

class TestModelManager:
    """Test ModelManager class."""
    
    @pytest.fixture
    def manager(self, db_manager, temp_artifacts_dir):
        """Create model manager for testing."""
        return ModelManager(db_manager, temp_artifacts_dir)
    
    def test_manager_initialization(self, manager):
        """Test model manager initialization."""
        assert manager.db_manager is not None
        assert manager._current_model is None
        assert manager._current_model_version is None
        assert manager._inference_count == 0
    
    def test_is_model_loaded_false(self, manager):
        """Test model loaded check when no model."""
        assert not manager.is_model_loaded()
    
    def test_predict_fraud_no_model(self, manager):
        """Test prediction when no model is loaded."""
        features = np.array([[1, 2, 3, 4, 5]])
        
        with pytest.raises(InferenceError, match="No model loaded"):
            manager.predict_fraud_probability(features)
    
    @patch('os.path.exists')
    @patch('joblib.load')
    def test_load_active_model_success(self, mock_joblib, mock_exists, manager, sample_model_registry):
        """Test successful active model loading."""
        # Mock file existence
        mock_exists.return_value = True
        
        # Mock model loading
        mock_model = Mock()
        mock_model.predict_proba.return_value = np.array([[0.7, 0.3]])
        
        mock_preprocessing = Mock()
        mock_preprocessing.feature_names_in_ = ['feature1', 'feature2']
        
        # Configure joblib.load to return different objects based on call order
        mock_joblib.side_effect = [
            mock_model,  # First call for model
            {'pipeline': mock_preprocessing}  # Second call for preprocessing
        ]
        
        with patch.object(manager.db_manager, 'get_session') as mock_get_session:
            mock_session = Mock()
            mock_session.__enter__ = Mock(return_value=mock_session)
            mock_session.__exit__ = Mock(return_value=None)
            mock_session.query.return_value.filter.return_value.first.return_value = sample_model_registry
            mock_get_session.return_value = mock_session
            
            result = manager.load_active_model()
            
            assert result is True
            assert manager._current_model is not None
            assert manager._current_model_version == sample_model_registry.model_version

class TestFraudDetectionInference:
    """Test FraudDetectionInference class."""
    
    @pytest.fixture
    def inference_engine(self, db_manager, temp_artifacts_dir):
        """Create fraud detection inference engine for testing."""
        return FraudDetectionInference(db_manager, temp_artifacts_dir)
    
    def test_engine_initialization(self, inference_engine):
        """Test inference engine initialization."""
        assert inference_engine.db_manager is not None
        assert inference_engine.model_manager is not None
        assert inference_engine.fraud_threshold == 0.5
        assert inference_engine.high_risk_threshold == 0.8
    
    def test_determine_risk_level(self, inference_engine):
        """Test risk level determination."""
        # Test different probability ranges
        assert inference_engine._determine_risk_level(0.9) == 'HIGH'
        assert inference_engine._determine_risk_level(0.7) == 'MEDIUM'
        assert inference_engine._determine_risk_level(0.3) == 'LOW'
        assert inference_engine._determine_risk_level(0.1) == 'MINIMAL'
    
    def test_predict_fraud_not_initialized(self, inference_engine):
        """Test prediction when engine is not initialized."""
        transaction_data = {
            'id': 1,
            'user_id': 1,
            'amount': 100.0,
            'currency': 'USD',
            'merchant_category': 'retail',
            'timestamp': datetime.utcnow()
        }
        
        with pytest.raises(InferenceError, match="not properly initialized"):
            inference_engine.predict_fraud(transaction_data)
    
    @patch('app.preprocessing.feature_engineering.FeatureEngineeringPipeline')
    def test_predict_fraud_feature_extraction_error(self, mock_pipeline_class, inference_engine):
        """Test prediction when feature extraction fails."""
        # Mock model manager as loaded
        inference_engine.model_manager._current_model = Mock()
        
        # Mock feature pipeline to raise error
        mock_pipeline = Mock()
        mock_pipeline.extract_features_for_inference.side_effect = Exception("Feature extraction failed")
        mock_pipeline_class.return_value = mock_pipeline
        
        inference_engine.feature_pipeline = mock_pipeline
        
        transaction_data = {
            'id': 1,
            'user_id': 1,
            'amount': 100.0,
            'currency': 'USD',
            'merchant_category': 'retail',
            'timestamp': datetime.utcnow()
        }
        
        result = inference_engine.predict_fraud(transaction_data)
        
        # Should return zero vector result due to error handling
        assert 'fraud_probability' in result
        assert 'prediction_label' in result

class TestIntegration:
    """Integration tests for model training and inference."""
    
    def test_model_training_to_inference_flow(self, db_manager, temp_artifacts_dir, mock_training_data):
        """Test complete flow from training to inference."""
        # This would be a more complex integration test
        # that verifies the entire pipeline works together
        pass
    
    def test_feature_parity_validation(self, db_manager, mock_training_data):
        """Test that training and inference features are consistent."""
        # This would test that the same features are extracted
        # during training and inference for the same data
        pass