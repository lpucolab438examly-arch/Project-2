#!/usr/bin/env python
"""
Database seeding script for FraudNet.AI development and testing.
"""

import os
import sys
import argparse
from datetime import datetime, timedelta
import random

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.models.database import db, User, Transaction, Prediction, ModelRegistry, AuditLog
from app.core.database_manager import DatabaseManager


def create_sample_users(count: int = 100):
    """Create sample users."""
    users = []
    for i in range(count):
        user = User(
            user_id=f"user_{i:06d}",
            email=f"user{i}@example.com",
            phone=f"+1555{i:07d}",
            registration_date=datetime.now() - timedelta(days=random.randint(1, 365)),
            user_type=random.choice(['premium', 'basic', 'enterprise'])
        )
        users.append(user)
    
    db.session.bulk_save_objects(users)
    db.session.commit()
    print(f"Created {count} sample users")
    return users


def create_sample_transactions(users: list, count: int = 1000):
    """Create sample transactions."""
    transactions = []
    merchants = [
        'Amazon', 'Walmart', 'Target', 'Best Buy', 'Home Depot',
        'Starbucks', 'McDonald\'s', 'Shell', 'Exxon', 'CVS',
        'Local Store', 'Online Shop', 'Gas Station', 'Restaurant', 'Mall'
    ]
    
    categories = [
        'grocery', 'electronics', 'fuel', 'restaurant', 'retail',
        'entertainment', 'travel', 'healthcare', 'utilities', 'other'
    ]
    
    for i in range(count):
        user = random.choice(users)
        is_fraud = random.random() < 0.05  # 5% fraud rate
        
        # Fraud transactions tend to be higher amounts and unusual times
        if is_fraud:
            amount = random.uniform(500, 5000)
            hour = random.choice([2, 3, 4, 23, 24, 1])  # Unusual hours
        else:
            amount = random.uniform(5, 500)
            hour = random.randint(6, 22)  # Normal business hours
        
        transaction = Transaction(
            transaction_id=f"txn_{i:08d}",
            user_id=user.id,
            amount=round(amount, 2),
            merchant=random.choice(merchants),
            merchant_category=random.choice(categories),
            transaction_date=datetime.now() - timedelta(
                days=random.randint(0, 30),
                hours=random.randint(0, 23),
                minutes=random.randint(0, 59)
            ),
            location_country=random.choice(['US', 'CA', 'GB', 'DE', 'FR']),
            location_city=random.choice([
                'New York', 'Los Angeles', 'Chicago', 'Houston', 'Phoenix',
                'Toronto', 'London', 'Berlin', 'Paris', 'Madrid'
            ]),
            payment_method=random.choice(['credit_card', 'debit_card', 'bank_transfer', 'digital_wallet']),
            device_type=random.choice(['mobile', 'web', 'pos']),
            is_fraud=is_fraud
        )
        transactions.append(transaction)
    
    db.session.bulk_save_objects(transactions)
    db.session.commit()
    print(f"Created {count} sample transactions ({sum(1 for t in transactions if t.is_fraud)} fraud)")
    return transactions


def create_sample_predictions(transactions: list, count: int = 500):
    """Create sample predictions."""
    predictions = []
    model_versions = ['v1.0', 'v1.1', 'v1.2']
    
    for i in range(min(count, len(transactions))):
        transaction = transactions[i]
        
        # Simulate model predictions (with some accuracy)
        if transaction.is_fraud:
            fraud_probability = random.uniform(0.7, 0.95)  # High probability for actual fraud
        else:
            fraud_probability = random.uniform(0.01, 0.3)  # Low probability for legitimate
        
        prediction = Prediction(
            transaction_id=transaction.id,
            model_version=random.choice(model_versions),
            fraud_probability=fraud_probability,
            risk_level='high' if fraud_probability > 0.8 else 'medium' if fraud_probability > 0.5 else 'low',
            prediction_date=transaction.transaction_date + timedelta(seconds=random.randint(1, 10)),
            processing_time_ms=random.randint(50, 200)
        )
        predictions.append(prediction)
    
    db.session.bulk_save_objects(predictions)
    db.session.commit()
    print(f"Created {len(predictions)} sample predictions")
    return predictions


def create_sample_model_registry():
    """Create sample model registry entries."""
    models = [
        {
            'model_name': 'fraud_detector_v1',
            'version': 'v1.0',
            'algorithm': 'RandomForest',
            'hyperparameters': '{"n_estimators": 100, "max_depth": 10}',
            'training_accuracy': 0.94,
            'validation_accuracy': 0.92,
            'precision': 0.89,
            'recall': 0.87,
            'f1_score': 0.88,
            'is_active': False
        },
        {
            'model_name': 'fraud_detector_v1',
            'version': 'v1.1',
            'algorithm': 'RandomForest',
            'hyperparameters': '{"n_estimators": 150, "max_depth": 12}',
            'training_accuracy': 0.95,
            'validation_accuracy': 0.93,
            'precision': 0.91,
            'recall': 0.89,
            'f1_score': 0.90,
            'is_active': False
        },
        {
            'model_name': 'fraud_detector_v1',
            'version': 'v1.2',
            'algorithm': 'XGBoost',
            'hyperparameters': '{"n_estimators": 200, "max_depth": 8, "learning_rate": 0.1}',
            'training_accuracy': 0.96,
            'validation_accuracy': 0.94,
            'precision': 0.93,
            'recall': 0.91,
            'f1_score': 0.92,
            'is_active': True
        }
    ]
    
    for model_data in models:
        model = ModelRegistry(**model_data)
        db.session.add(model)
    
    db.session.commit()
    print(f"Created {len(models)} model registry entries")


def create_sample_audit_logs(count: int = 200):
    """Create sample audit log entries."""
    actions = ['CREATE', 'UPDATE', 'DELETE', 'LOGIN', 'LOGOUT', 'PREDICT', 'TRAIN']
    entities = ['User', 'Transaction', 'Model', 'Prediction']
    
    logs = []
    for i in range(count):
        log = AuditLog(
            action=random.choice(actions),
            entity_type=random.choice(entities),
            entity_id=random.randint(1, 1000),
            user_id=f"user_{random.randint(0, 99):06d}",
            changes=f'{{"field": "updated", "old_value": "old", "new_value": "new"}}',
            ip_address=f"192.168.{random.randint(1, 255)}.{random.randint(1, 255)}",
            user_agent="FraudNet.AI/1.0"
        )
        logs.append(log)
    
    db.session.bulk_save_objects(logs)
    db.session.commit()
    print(f"Created {count} audit log entries")


def seed_database(users_count: int = 100, transactions_count: int = 1000, 
                 predictions_count: int = 500, audit_logs_count: int = 200):
    """Seed the database with sample data."""
    print("Starting database seeding...")
    
    # Create users first
    users = create_sample_users(users_count)
    
    # Create transactions
    transactions = create_sample_transactions(users, transactions_count)
    
    # Create predictions
    create_sample_predictions(transactions, predictions_count)
    
    # Create model registry entries
    create_sample_model_registry()
    
    # Create audit logs
    create_sample_audit_logs(audit_logs_count)
    
    print("Database seeding completed successfully!")


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Seed FraudNet.AI database with sample data')
    parser.add_argument('--users', type=int, default=100, help='Number of users to create')
    parser.add_argument('--transactions', type=int, default=1000, help='Number of transactions to create')
    parser.add_argument('--predictions', type=int, default=500, help='Number of predictions to create')
    parser.add_argument('--audit-logs', type=int, default=200, help='Number of audit logs to create')
    parser.add_argument('--reset', action='store_true', help='Reset database before seeding')
    
    args = parser.parse_args()
    
    # Create Flask app and application context
    app = create_app()
    
    with app.app_context():
        try:
            # Initialize database manager
            db_manager = DatabaseManager()
            
            if args.reset:
                print("Resetting database...")
                db.drop_all()
                db_manager.create_tables()
            
            # Seed the database
            seed_database(
                users_count=args.users,
                transactions_count=args.transactions,
                predictions_count=args.predictions,
                audit_logs_count=args.audit_logs
            )
            
        except Exception as e:
            print(f"Error seeding database: {e}")
            sys.exit(1)


if __name__ == '__main__':
    main()