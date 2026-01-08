"""Feature validation and parity testing utilities."""

import pandas as pd
import numpy as np
from typing import Dict, Any, List, Tuple
from datetime import datetime
import json

from app.utils.logging import get_logger
from app.preprocessing.feature_engineering import FeatureEngineeringPipeline

logger = get_logger(__name__)

class FeatureValidator:
    """Validates feature engineering pipeline for training-inference parity."""
    
    def __init__(self, feature_pipeline: FeatureEngineeringPipeline):
        self.feature_pipeline = feature_pipeline
        self.logger = get_logger(__name__)
    
    def validate_feature_consistency(self, training_data: List[Dict[str, Any]], 
                                   sample_size: int = 100) -> bool:
        """Validate that features are consistent between training and inference modes."""
        
        self.logger.info("Starting feature consistency validation")
        
        # Take a sample of training data
        sample_data = training_data[:sample_size]
        
        inconsistencies = []
        
        for i, transaction_data in enumerate(sample_data):
            try:
                # Extract features using training mode (from transaction object simulation)
                training_features = self._simulate_training_feature_extraction(transaction_data)
                
                # Extract features using inference mode
                inference_features = self.feature_pipeline.extract_features_for_inference(transaction_data)
                
                # Compare features
                if not self._compare_feature_vectors(training_features, inference_features):
                    inconsistencies.append({
                        'transaction_index': i,
                        'training_features': training_features.tolist(),
                        'inference_features': inference_features.tolist(),
                        'transaction_data': transaction_data
                    })
                    
            except Exception as e:
                self.logger.error(f"Error validating transaction {i}: {e}")
                inconsistencies.append({
                    'transaction_index': i,
                    'error': str(e),
                    'transaction_data': transaction_data
                })
        
        success_rate = (sample_size - len(inconsistencies)) / sample_size
        
        if inconsistencies:
            self.logger.warning(f"Found {len(inconsistencies)} inconsistencies out of {sample_size} samples")
            self.logger.warning(f"Success rate: {success_rate:.2%}")
            
            # Log first few inconsistencies for debugging
            for inconsistency in inconsistencies[:3]:
                self.logger.warning(f"Inconsistency details: {inconsistency}")
        else:
            self.logger.info("All feature extractions are consistent between training and inference")
        
        return len(inconsistencies) == 0
    
    def _simulate_training_feature_extraction(self, transaction_data: Dict[str, Any]) -> np.ndarray:
        """Simulate feature extraction as it would happen during training."""
        # Create a mock transaction object
        from app.models.database import Transaction
        
        mock_transaction = Transaction(
            id=transaction_data.get('id', 1),
            user_id=transaction_data['user_id'],
            amount=transaction_data['amount'],
            currency=transaction_data['currency'],
            merchant_category=transaction_data['merchant_category'],
            device_id=transaction_data.get('device_id'),
            ip_address=transaction_data.get('ip_address'),
            timestamp=transaction_data['timestamp'],
            raw_payload=transaction_data.get('raw_payload', {})
        )
        
        # Extract features as if it's for training
        features_df = self.feature_pipeline.extract_features_for_training([mock_transaction])
        
        # Get feature vector (exclude transaction_id)
        feature_columns = [col for col in features_df.columns if col != 'transaction_id']
        return features_df[feature_columns].values[0]
    
    def _compare_feature_vectors(self, features1: np.ndarray, features2: np.ndarray, 
                               tolerance: float = 1e-6) -> bool:
        """Compare two feature vectors for equality with tolerance."""
        if features1.shape != features2.shape:
            return False
        
        return np.allclose(features1, features2, atol=tolerance)
    
    def validate_feature_ranges(self, features_df: pd.DataFrame) -> Dict[str, Any]:
        """Validate that features are within expected ranges."""
        validation_results = {
            'valid': True,
            'issues': [],
            'feature_stats': {}
        }
        
        feature_columns = [col for col in features_df.columns if col != 'transaction_id']
        
        for column in feature_columns:
            if column not in features_df.columns:
                validation_results['issues'].append(f"Missing feature: {column}")
                validation_results['valid'] = False
                continue
            
            values = features_df[column].values
            
            # Calculate statistics
            validation_results['feature_stats'][column] = {
                'mean': float(np.mean(values)),
                'std': float(np.std(values)),
                'min': float(np.min(values)),
                'max': float(np.max(values)),
                'null_count': int(np.sum(pd.isna(values)))
            }
            
            # Check for issues
            if np.any(pd.isna(values)):
                validation_results['issues'].append(f"Feature {column} has null values")
                validation_results['valid'] = False
            
            if np.any(np.isinf(values)):
                validation_results['issues'].append(f"Feature {column} has infinite values")
                validation_results['valid'] = False
            
            # Feature-specific validations
            if 'probability' in column or 'score' in column:
                if np.any((values < 0) | (values > 1)):
                    validation_results['issues'].append(f"Feature {column} has values outside [0,1] range")
                    validation_results['valid'] = False
            
            if 'count' in column:
                if np.any(values < 0):
                    validation_results['issues'].append(f"Feature {column} has negative count values")
                    validation_results['valid'] = False
        
        return validation_results
    
    def generate_feature_report(self, features_df: pd.DataFrame) -> Dict[str, Any]:
        """Generate comprehensive feature analysis report."""
        feature_columns = [col for col in features_df.columns if col != 'transaction_id']
        
        report = {
            'summary': {
                'total_samples': len(features_df),
                'total_features': len(feature_columns),
                'timestamp': datetime.utcnow().isoformat()
            },
            'features': {},
            'correlations': {},
            'validation_results': self.validate_feature_ranges(features_df)
        }
        
        # Feature-wise analysis
        for column in feature_columns:
            if column in features_df.columns:
                values = features_df[column].values
                
                report['features'][column] = {
                    'type': str(features_df[column].dtype),
                    'mean': float(np.mean(values)),
                    'median': float(np.median(values)),
                    'std': float(np.std(values)),
                    'min': float(np.min(values)),
                    'max': float(np.max(values)),
                    'percentiles': {
                        'p25': float(np.percentile(values, 25)),
                        'p50': float(np.percentile(values, 50)),
                        'p75': float(np.percentile(values, 75)),
                        'p95': float(np.percentile(values, 95)),
                        'p99': float(np.percentile(values, 99))
                    },
                    'null_count': int(np.sum(pd.isna(values))),
                    'unique_count': int(features_df[column].nunique())
                }
        
        # Correlation analysis (limit to prevent memory issues)
        if len(feature_columns) < 50:
            numeric_features = features_df[feature_columns].select_dtypes(include=[np.number])
            if len(numeric_features.columns) > 1:
                corr_matrix = numeric_features.corr()
                
                # Find highly correlated feature pairs
                high_correlations = []
                for i in range(len(corr_matrix.columns)):
                    for j in range(i+1, len(corr_matrix.columns)):
                        corr_value = corr_matrix.iloc[i, j]
                        if abs(corr_value) > 0.8:  # High correlation threshold
                            high_correlations.append({
                                'feature1': corr_matrix.columns[i],
                                'feature2': corr_matrix.columns[j],
                                'correlation': float(corr_value)
                            })
                
                report['correlations'] = {
                    'high_correlations': high_correlations,
                    'max_correlation': float(corr_matrix.abs().max().max()),
                    'mean_correlation': float(corr_matrix.abs().mean().mean())
                }
        
        return report

class FeatureMonitor:
    """Monitor feature drift and quality in production."""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self.baseline_stats = None
    
    def set_baseline(self, features_df: pd.DataFrame):
        """Set baseline feature statistics for drift detection."""
        feature_columns = [col for col in features_df.columns if col != 'transaction_id']
        
        self.baseline_stats = {}
        for column in feature_columns:
            if column in features_df.columns:
                values = features_df[column].values
                self.baseline_stats[column] = {
                    'mean': float(np.mean(values)),
                    'std': float(np.std(values)),
                    'min': float(np.min(values)),
                    'max': float(np.max(values)),
                    'percentiles': {
                        'p25': float(np.percentile(values, 25)),
                        'p50': float(np.percentile(values, 50)),
                        'p75': float(np.percentile(values, 75))
                    }
                }
    
    def detect_drift(self, current_features_df: pd.DataFrame, 
                    drift_threshold: float = 0.1) -> Dict[str, Any]:
        """Detect feature drift compared to baseline."""
        if not self.baseline_stats:
            raise ValueError("Baseline statistics not set. Call set_baseline() first.")
        
        drift_report = {
            'has_drift': False,
            'drifted_features': [],
            'feature_comparisons': {},
            'overall_drift_score': 0.0
        }
        
        feature_columns = [col for col in current_features_df.columns if col != 'transaction_id']
        drift_scores = []
        
        for column in feature_columns:
            if column in current_features_df.columns and column in self.baseline_stats:
                current_values = current_features_df[column].values
                baseline_stats = self.baseline_stats[column]
                
                # Calculate current statistics
                current_stats = {
                    'mean': float(np.mean(current_values)),
                    'std': float(np.std(current_values)),
                    'min': float(np.min(current_values)),
                    'max': float(np.max(current_values))
                }
                
                # Calculate drift score (normalized difference in means and stds)
                mean_diff = abs(current_stats['mean'] - baseline_stats['mean']) / (baseline_stats['std'] + 1e-6)
                std_diff = abs(current_stats['std'] - baseline_stats['std']) / (baseline_stats['std'] + 1e-6)
                
                drift_score = (mean_diff + std_diff) / 2
                drift_scores.append(drift_score)
                
                drift_report['feature_comparisons'][column] = {
                    'baseline': baseline_stats,
                    'current': current_stats,
                    'drift_score': drift_score,
                    'has_drift': drift_score > drift_threshold
                }
                
                if drift_score > drift_threshold:
                    drift_report['drifted_features'].append(column)
                    drift_report['has_drift'] = True
        
        drift_report['overall_drift_score'] = float(np.mean(drift_scores)) if drift_scores else 0.0
        
        return drift_report