"""Model training pipeline for fraud detection."""

import pandas as pd
import numpy as np
import joblib
import json
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Tuple, Optional, Union
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import (
    train_test_split, GridSearchCV, StratifiedKFold, cross_val_score
)
from sklearn.metrics import (
    roc_auc_score, precision_score, recall_score, f1_score, 
    confusion_matrix, classification_report, roc_curve, precision_recall_curve
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
import matplotlib.pyplot as plt
import os

from app.utils.logging import get_logger, ModelLogger
from app.utils.helpers import generate_model_version, generate_hash, measure_execution_time
from app.preprocessing.feature_engineering import FeatureEngineeringPipeline, FeatureConfig
from app.validation.feature_validation import FeatureValidator
from app.models.database import Transaction, Prediction, ModelRegistry
from app.utils.database import DatabaseManager

logger = get_logger(__name__)

class ModelTrainer:
    """Comprehensive model training pipeline."""
    
    def __init__(self, db_manager: DatabaseManager, artifacts_path: str):
        self.db_manager = db_manager
        self.artifacts_path = artifacts_path
        self.models_path = os.path.join(artifacts_path, 'models')
        self.metrics_path = os.path.join(artifacts_path, 'metrics')
        self.preprocessing_path = os.path.join(artifacts_path, 'preprocessing')
        self.logger = get_logger(__name__)
        self.model_logger = ModelLogger()
        
        # Ensure directories exist
        os.makedirs(self.models_path, exist_ok=True)
        os.makedirs(self.metrics_path, exist_ok=True)
        os.makedirs(self.preprocessing_path, exist_ok=True)
        
        # Model configurations
        self.model_configs = {
            'logistic_regression': {
                'model': LogisticRegression(random_state=42, max_iter=1000),
                'params': {
                    'C': [0.1, 1.0, 10.0],
                    'penalty': ['l1', 'l2'],
                    'solver': ['liblinear', 'lbfgs']
                }
            },
            'random_forest': {
                'model': RandomForestClassifier(random_state=42),
                'params': {
                    'n_estimators': [100, 200, 300],
                    'max_depth': [5, 10, None],
                    'min_samples_split': [2, 5, 10],
                    'min_samples_leaf': [1, 2, 4]
                }
            },
            'gradient_boosting': {
                'model': GradientBoostingClassifier(random_state=42),
                'params': {
                    'n_estimators': [100, 200],
                    'learning_rate': [0.05, 0.1, 0.15],
                    'max_depth': [3, 4, 5],
                    'subsample': [0.8, 0.9, 1.0]
                }
            }
        }
    
    @measure_execution_time
    def prepare_training_data(self, start_date: Optional[datetime] = None,
                            end_date: Optional[datetime] = None,
                            min_samples: int = 1000) -> Tuple[pd.DataFrame, pd.Series]:
        """Prepare training data with features and labels."""
        
        # Set default date range if not provided
        if end_date is None:
            end_date = datetime.utcnow()
        if start_date is None:
            start_date = end_date - timedelta(days=90)  # 3 months of data
        
        self.logger.info(f"Preparing training data from {start_date} to {end_date}")
        
        with self.db_manager.get_session() as session:
            # Query transactions with their predictions (labels)
            query = session.query(Transaction, Prediction.prediction_label).join(
                Prediction, Transaction.id == Prediction.transaction_id
            ).filter(
                Transaction.timestamp >= start_date,
                Transaction.timestamp <= end_date
            ).order_by(Transaction.timestamp)
            
            transactions_with_labels = query.all()
            
            if len(transactions_with_labels) < min_samples:
                raise ValueError(f"Insufficient training data: {len(transactions_with_labels)} samples, minimum required: {min_samples}")
            
            # Separate transactions and labels
            transactions = [t[0] for t in transactions_with_labels]
            labels = pd.Series([t[1] for t in transactions_with_labels])
            
            self.logger.info(f"Found {len(transactions)} transactions with labels")
            self.logger.info(f"Fraud rate: {labels.mean():.2%}")
            
            # Extract features using feature engineering pipeline
            feature_pipeline = FeatureEngineeringPipeline(session)
            features_df = feature_pipeline.extract_features_for_training(transactions)
            
            # Validate features
            validator = FeatureValidator(feature_pipeline)
            validation_results = validator.validate_feature_ranges(features_df)
            
            if not validation_results['valid']:
                self.logger.warning("Feature validation issues found:")
                for issue in validation_results['issues']:
                    self.logger.warning(f"  - {issue}")
            
            # Remove transaction_id column for training
            feature_columns = [col for col in features_df.columns if col != 'transaction_id']
            X = features_df[feature_columns]
            
            self.logger.info(f"Prepared features: {X.shape}")
            self.logger.info(f"Feature columns: {list(X.columns)}")
            
            return X, labels
    
    def train_model(self, model_type: str, X: pd.DataFrame, y: pd.Series,
                   hyperparameters: Optional[Dict[str, Any]] = None,
                   use_cross_validation: bool = True) -> Dict[str, Any]:
        """Train a single model with hyperparameter tuning."""
        
        if model_type not in self.model_configs:
            raise ValueError(f"Unknown model type: {model_type}")
        
        start_time = time.time()
        
        self.model_logger.log_training_start(model_type, len(X), hyperparameters)
        
        # Get model configuration
        model_config = self.model_configs[model_type]
        base_model = model_config['model']
        param_grid = hyperparameters or model_config['params']
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
        
        self.logger.info(f"Training set: {X_train.shape}, Test set: {X_test.shape}")
        
        # Create preprocessing pipeline
        feature_pipeline = FeatureEngineeringPipeline(None)  # No DB session needed for just preprocessing
        feature_pipeline.fit_preprocessing_pipeline(X_train)
        
        # Create full pipeline with preprocessing and model
        pipeline = Pipeline([
            ('preprocessor', feature_pipeline.preprocessing_pipeline),
            ('classifier', base_model)
        ])
        
        # Hyperparameter tuning with grid search
        if len(param_grid) > 0:
            # Add 'classifier__' prefix to parameter names for pipeline
            pipeline_param_grid = {f'classifier__{k}': v for k, v in param_grid.items()}
            
            cv_strategy = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
            
            grid_search = GridSearchCV(
                pipeline,
                pipeline_param_grid,
                cv=cv_strategy,
                scoring='roc_auc',
                n_jobs=-1,
                verbose=0
            )
            
            grid_search.fit(X_train, y_train)
            best_model = grid_search.best_estimator_
            best_params = grid_search.best_params_
            cv_score = grid_search.best_score_
            
            self.logger.info(f"Best parameters: {best_params}")
            self.logger.info(f"Best CV score: {cv_score:.4f}")
        else:
            pipeline.fit(X_train, y_train)
            best_model = pipeline
            best_params = {}
            cv_score = None
        
        # Evaluate model
        train_predictions = best_model.predict_proba(X_train)[:, 1]
        test_predictions = best_model.predict_proba(X_test)[:, 1]
        
        # Calculate metrics
        metrics = self._calculate_metrics(y_train, train_predictions, y_test, test_predictions)
        
        # Cross-validation metrics
        if use_cross_validation:
            cv_scores = cross_val_score(
                best_model, X_train, y_train, 
                cv=StratifiedKFold(n_splits=5, shuffle=True, random_state=42),
                scoring='roc_auc'
            )
            metrics['cv_auc_mean'] = float(np.mean(cv_scores))
            metrics['cv_auc_std'] = float(np.std(cv_scores))
        
        # Generate model version and paths
        model_version = generate_model_version()
        model_filename = f"{model_type}_{model_version}.joblib"
        preprocessing_filename = f"preprocessing_{model_version}.joblib"
        
        model_path = os.path.join(self.models_path, model_filename)
        preprocessing_path = os.path.join(self.preprocessing_path, preprocessing_filename)
        
        # Save model and preprocessing pipeline
        joblib.dump(best_model, model_path)
        feature_pipeline.save_pipeline(preprocessing_path)
        
        # Save metrics
        metrics_data = {
            'model_type': model_type,
            'model_version': model_version,
            'metrics': metrics,
            'best_parameters': best_params,
            'training_samples': len(X_train),
            'test_samples': len(X_test),
            'feature_columns': list(X.columns),
            'training_date': datetime.utcnow().isoformat()
        }
        
        metrics_filename = f"metrics_{model_version}.json"
        metrics_path_file = os.path.join(self.metrics_path, metrics_filename)
        
        with open(metrics_path_file, 'w') as f:
            json.dump(metrics_data, f, indent=2)
        
        # Log training completion
        training_duration = time.time() - start_time
        self.model_logger.log_training_complete(
            model_version, model_type, metrics, training_duration
        )
        
        # Save to model registry
        self._save_to_model_registry(
            model_type, model_version, model_path, preprocessing_path, 
            metrics, X, best_params
        )
        
        return {
            'model_version': model_version,
            'model_type': model_type,
            'model_path': model_path,
            'preprocessing_path': preprocessing_path,
            'metrics': metrics,
            'best_parameters': best_params,
            'training_duration': training_duration
        }
    
    def train_all_models(self, X: pd.DataFrame, y: pd.Series) -> List[Dict[str, Any]]:
        """Train all available model types and return results."""
        results = []
        
        for model_type in self.model_configs.keys():
            try:
                self.logger.info(f"Training {model_type} model...")
                result = self.train_model(model_type, X, y)
                results.append(result)
                self.logger.info(f"Completed training {model_type}")
            except Exception as e:
                self.logger.error(f"Failed to train {model_type}: {e}")
                continue
        
        # Select best model based on test AUC
        if results:
            best_model = max(results, key=lambda x: x['metrics']['test_auc'])
            self.logger.info(f"Best model: {best_model['model_type']} with AUC {best_model['metrics']['test_auc']:.4f}")
            
            # Mark best model as active
            self._set_active_model(best_model['model_version'])
        
        return results
    
    def _calculate_metrics(self, y_train: pd.Series, train_pred: np.ndarray,
                          y_test: pd.Series, test_pred: np.ndarray,
                          threshold: float = 0.5) -> Dict[str, float]:
        """Calculate comprehensive evaluation metrics."""
        
        # Binary predictions
        train_pred_binary = (train_pred > threshold).astype(int)
        test_pred_binary = (test_pred > threshold).astype(int)
        
        metrics = {
            # AUC scores
            'train_auc': float(roc_auc_score(y_train, train_pred)),
            'test_auc': float(roc_auc_score(y_test, test_pred)),
            
            # Precision, Recall, F1 for test set
            'test_precision': float(precision_score(y_test, test_pred_binary)),
            'test_recall': float(recall_score(y_test, test_pred_binary)),
            'test_f1': float(f1_score(y_test, test_pred_binary)),
            
            # Confusion matrix for test set
            'test_true_negatives': int(confusion_matrix(y_test, test_pred_binary)[0, 0]),
            'test_false_positives': int(confusion_matrix(y_test, test_pred_binary)[0, 1]),
            'test_false_negatives': int(confusion_matrix(y_test, test_pred_binary)[1, 0]),
            'test_true_positives': int(confusion_matrix(y_test, test_pred_binary)[1, 1]),
        }
        
        # Calculate specificity
        tn = metrics['test_true_negatives']
        fp = metrics['test_false_positives']
        metrics['test_specificity'] = float(tn / (tn + fp)) if (tn + fp) > 0 else 0.0
        
        return metrics
    
    def _save_to_model_registry(self, model_type: str, model_version: str,
                               model_path: str, preprocessing_path: str,
                               metrics: Dict[str, Any], X: pd.DataFrame,
                               hyperparameters: Dict[str, Any]):
        """Save model information to the model registry."""
        
        # Generate feature schema hash
        feature_pipeline = FeatureEngineeringPipeline(None)
        feature_schema_hash = feature_pipeline.get_feature_schema_hash()
        
        # Generate training data hash
        training_data_hash = generate_hash({
            'feature_columns': list(X.columns),
            'data_shape': X.shape,
            'feature_schema_version': FeatureConfig.VERSION
        })
        
        model_registry_entry = ModelRegistry(
            model_name=f"fraud_detector_{model_type}",
            model_version=model_version,
            model_type=model_type,
            model_path=model_path,
            preprocessing_path=preprocessing_path,
            metrics=metrics,
            is_active=False,  # Will be set to True for best model
            training_data_hash=training_data_hash,
            feature_schema_version=FeatureConfig.VERSION
        )
        
        with self.db_manager.get_session() as session:
            session.add(model_registry_entry)
            session.commit()
            self.logger.info(f"Model {model_version} saved to registry")
    
    def _set_active_model(self, model_version: str):
        """Set a model as active (deactivate all others)."""
        with self.db_manager.get_session() as session:
            # Deactivate all models
            session.query(ModelRegistry).update({'is_active': False})
            
            # Activate the specified model
            session.query(ModelRegistry).filter(
                ModelRegistry.model_version == model_version
            ).update({'is_active': True})
            
            session.commit()
            self.logger.info(f"Model {model_version} set as active")
    
    def get_model_metrics(self, model_version: str) -> Optional[Dict[str, Any]]:
        """Retrieve metrics for a specific model version."""
        with self.db_manager.get_session() as session:
            model_entry = session.query(ModelRegistry).filter(
                ModelRegistry.model_version == model_version
            ).first()
            
            if model_entry:
                return {
                    'model_version': model_entry.model_version,
                    'model_type': model_entry.model_type,
                    'metrics': model_entry.metrics,
                    'is_active': model_entry.is_active,
                    'created_at': model_entry.created_at.isoformat(),
                    'feature_schema_version': model_entry.feature_schema_version
                }
            return None

class ModelEvaluator:
    """Advanced model evaluation and comparison utilities."""
    
    def __init__(self, artifacts_path: str):
        self.artifacts_path = artifacts_path
        self.logger = get_logger(__name__)
    
    def compare_models(self, model_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Compare multiple trained models and provide recommendations."""
        
        if not model_results:
            return {'error': 'No models to compare'}
        
        comparison = {
            'summary': {
                'total_models': len(model_results),
                'evaluation_date': datetime.utcnow().isoformat()
            },
            'models': [],
            'rankings': {},
            'recommendations': []
        }
        
        # Extract key metrics for comparison
        for result in model_results:
            model_summary = {
                'model_type': result['model_type'],
                'model_version': result['model_version'],
                'test_auc': result['metrics']['test_auc'],
                'test_precision': result['metrics']['test_precision'],
                'test_recall': result['metrics']['test_recall'],
                'test_f1': result['metrics']['test_f1'],
                'training_duration': result['training_duration']
            }
            comparison['models'].append(model_summary)
        
        # Rank models by different metrics
        comparison['rankings'] = {
            'by_auc': sorted(comparison['models'], key=lambda x: x['test_auc'], reverse=True),
            'by_precision': sorted(comparison['models'], key=lambda x: x['test_precision'], reverse=True),
            'by_recall': sorted(comparison['models'], key=lambda x: x['test_recall'], reverse=True),
            'by_f1': sorted(comparison['models'], key=lambda x: x['test_f1'], reverse=True),
            'by_speed': sorted(comparison['models'], key=lambda x: x['training_duration'])
        }
        
        # Generate recommendations
        best_auc_model = comparison['rankings']['by_auc'][0]
        fastest_model = comparison['rankings']['by_speed'][0]
        
        comparison['recommendations'] = [
            f"Best overall performance: {best_auc_model['model_type']} (AUC: {best_auc_model['test_auc']:.4f})",
            f"Fastest training: {fastest_model['model_type']} ({fastest_model['training_duration']:.2f}s)",
        ]
        
        # Check for significant performance differences
        auc_values = [m['test_auc'] for m in comparison['models']]
        auc_std = np.std(auc_values)
        
        if auc_std < 0.02:  # Low variance in performance
            comparison['recommendations'].append(
                "Performance is similar across models. Consider the fastest model for deployment."
            )
        
        return comparison