"""Database models for FraudNet.AI."""

from datetime import datetime, timezone
from typing import Optional, Dict, Any
import json
import hashlib
from sqlalchemy import (
    Column, Integer, String, DateTime, Numeric, Text, JSON, 
    ForeignKey, Boolean, Index, CheckConstraint, UniqueConstraint
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from werkzeug.security import generate_password_hash

Base = declarative_base()

class TimestampMixin:
    """Mixin for created_at and updated_at timestamps."""
    created_at = Column(DateTime(timezone=True), 
                       server_default=func.now(), 
                       nullable=False)
    updated_at = Column(DateTime(timezone=True), 
                       server_default=func.now(), 
                       onupdate=func.now(),
                       nullable=False)

class User(Base, TimestampMixin):
    """User model for authentication and RBAC."""
    __tablename__ = 'users'
    
    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # User identification
    name = Column(String(100), nullable=False)
    email = Column(String(120), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    
    # Role-based access control
    role = Column(String(20), nullable=False, default='viewer')  # admin, analyst, viewer
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    
    # Timestamps - these come from TimestampMixin
    last_login_at = Column(DateTime)
    password_changed_at = Column(DateTime)
    
    # Additional fields
    login_count = Column(Integer, default=0)
    profile_picture = Column(String(255))  # URL or path to profile picture
    phone = Column(String(20))
    department = Column(String(50))
    notes = Column(Text)  # Admin notes about the user
    
    # Relationships
    transactions = relationship("Transaction", back_populates="user", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index('idx_users_email', 'email'),
        Index('idx_users_role', 'role'),
        Index('idx_users_is_active', 'is_active'),
        Index('idx_users_created_at', 'created_at'),
    )
    
    def __init__(self, name, email, password, role='viewer', **kwargs):
        """Initialize a new user."""
        self.name = name
        self.email = email.lower()  # Store email in lowercase
        self.password_hash = generate_password_hash(password)
        self.role = role
        
        # Set optional fields
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
    
    def __repr__(self):
        return f'<User {self.email} ({self.role})>'
    
    def to_dict(self, include_sensitive=False):
        """Convert user to dictionary representation."""
        data = {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'role': self.role,
            'is_active': self.is_active,
            'is_verified': self.is_verified,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'last_login_at': self.last_login_at.isoformat() if self.last_login_at else None,
            'login_count': self.login_count or 0,
            'phone': self.phone,
            'department': self.department,
            'profile_picture': self.profile_picture
        }
        
        if include_sensitive:
            data.update({
                'password_changed_at': self.password_changed_at.isoformat() if self.password_changed_at else None,
                'notes': self.notes
            })
        
        return data
    
    @property
    def is_admin(self):
        """Check if user has admin role."""
        return self.role == 'admin'
    
    @property
    def is_analyst(self):
        """Check if user has analyst role or higher."""
        return self.role in ['admin', 'analyst']
    
    @property
    def is_viewer(self):
        """Check if user has at least viewer role."""
        return self.role in ['admin', 'analyst', 'viewer']
    
    def has_permission(self, required_role):
        """Check if user has required role permission."""
        role_hierarchy = {
            'viewer': 1,
            'analyst': 2,
            'admin': 3
        }
        
        user_level = role_hierarchy.get(self.role, 0)
        required_level = role_hierarchy.get(required_role, 0)
        
        return user_level >= required_level
    
    def update_last_login(self):
        """Update last login timestamp and increment login count."""
        self.last_login_at = datetime.utcnow()
        self.login_count = (self.login_count or 0) + 1
    
    @classmethod
    def create_default_users(cls, db_session):
        """Create default users for demo/development."""
        default_users = [
            {
                'name': 'System Administrator',
                'email': 'admin@fraudnet.ai',
                'password': 'admin123',
                'role': 'admin',
                'is_verified': True,
                'department': 'IT Security'
            },
            {
                'name': 'Fraud Analyst',
                'email': 'analyst@fraudnet.ai',
                'password': 'analyst123',
                'role': 'analyst',
                'is_verified': True,
                'department': 'Risk Management'
            },
            {
                'name': 'Dashboard Viewer',
                'email': 'viewer@fraudnet.ai',
                'password': 'viewer123',
                'role': 'viewer',
                'is_verified': True,
                'department': 'Operations'
            },
            {
                'name': 'John Smith',
                'email': 'john.smith@fraudnet.ai',
                'password': 'demo123',
                'role': 'analyst',
                'is_verified': True,
                'department': 'Fraud Investigation',
                'phone': '+1-555-0123'
            },
            {
                'name': 'Sarah Johnson',
                'email': 'sarah.johnson@fraudnet.ai',
                'password': 'demo123',
                'role': 'viewer',
                'is_verified': True,
                'department': 'Customer Service',
                'phone': '+1-555-0124'
            }
        ]
        
        created_users = []
        
        try:
            for user_data in default_users:
                # Check if user already exists
                existing_user = db_session.query(cls).filter_by(email=user_data['email']).first()
                
                if not existing_user:
                    user = cls(**user_data)
                    db_session.add(user)
                    created_users.append(user.email)
            
            db_session.commit()
            
            if created_users:
                print(f"Created default users: {', '.join(created_users)}")
            else:
                print("Default users already exist")
                
        except Exception as e:
            db_session.rollback()
            print(f"Error creating default users: {str(e)}")
            raise
    
    @classmethod
    def get_by_email(cls, db_session, email):
        """Get user by email address."""
        return db_session.query(cls).filter_by(email=email.lower()).first()
    
    @classmethod
    def get_active_users(cls, db_session):
        """Get all active users."""
        return db_session.query(cls).filter_by(is_active=True).all()
    
    @classmethod
    def get_by_role(cls, db_session, role):
        """Get users by role."""
        return db_session.query(cls).filter_by(role=role, is_active=True).all()

class Transaction(Base, TimestampMixin):
    """Transaction model."""
    __tablename__ = 'transactions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    amount = Column(Numeric(15, 2), nullable=False)
    currency = Column(String(3), nullable=False, default='USD')
    merchant_category = Column(String(100), nullable=False)
    device_id = Column(String(255), nullable=True)
    ip_address = Column(String(45), nullable=True)  # IPv6 compatible
    timestamp = Column(DateTime(timezone=True), nullable=False)
    raw_payload = Column(JSON, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="transactions")
    features = relationship("Feature", back_populates="transaction", cascade="all, delete-orphan")
    predictions = relationship("Prediction", back_populates="transaction", cascade="all, delete-orphan")
    
    # Constraints
    __table_args__ = (
        CheckConstraint('amount > 0', name='check_positive_amount'),
        Index('idx_transactions_user_id', 'user_id'),
        Index('idx_transactions_timestamp', 'timestamp'),
        Index('idx_transactions_merchant_category', 'merchant_category'),
        Index('idx_transactions_created_at', 'created_at'),
        Index('idx_transactions_user_timestamp', 'user_id', 'timestamp'),
    )
    
    def __repr__(self):
        return f"<Transaction(id={self.id}, amount={self.amount}, user_id={self.user_id})>"

class Feature(Base, TimestampMixin):
    """Feature model for storing extracted features."""
    __tablename__ = 'features'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    transaction_id = Column(Integer, ForeignKey('transactions.id'), nullable=False)
    feature_vector = Column(JSON, nullable=False)
    feature_schema_version = Column(String(100), nullable=False)
    
    # Relationships
    transaction = relationship("Transaction", back_populates="features")
    
    # Indexes
    __table_args__ = (
        Index('idx_features_transaction_id', 'transaction_id'),
        Index('idx_features_schema_version', 'feature_schema_version'),
        Index('idx_features_created_at', 'created_at'),
    )
    
    def __repr__(self):
        return f"<Feature(id={self.id}, transaction_id={self.transaction_id})>"

class Prediction(Base, TimestampMixin):
    """Prediction model for storing ML model outputs."""
    __tablename__ = 'predictions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    transaction_id = Column(Integer, ForeignKey('transactions.id'), nullable=False)
    model_version = Column(String(100), nullable=False)
    fraud_probability = Column(Numeric(5, 4), nullable=False)  # 0.0000 to 1.0000
    prediction_label = Column(Boolean, nullable=False)
    confidence_score = Column(Numeric(5, 4), nullable=True)
    inference_time_ms = Column(Integer, nullable=True)
    
    # Relationships
    transaction = relationship("Transaction", back_populates="predictions")
    
    # Constraints
    __table_args__ = (
        CheckConstraint('fraud_probability >= 0 AND fraud_probability <= 1', 
                       name='check_probability_range'),
        CheckConstraint('confidence_score >= 0 AND confidence_score <= 1', 
                       name='check_confidence_range'),
        Index('idx_predictions_transaction_id', 'transaction_id'),
        Index('idx_predictions_model_version', 'model_version'),
        Index('idx_predictions_fraud_probability', 'fraud_probability'),
        Index('idx_predictions_created_at', 'created_at'),
    )
    
    def __repr__(self):
        return f"<Prediction(id={self.id}, fraud_probability={self.fraud_probability})>"

class AuditLog(Base):
    """Immutable audit log model.""" 
    __tablename__ = 'audit_logs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    entity_type = Column(String(100), nullable=False)  # 'transaction', 'prediction', etc.
    entity_id = Column(Integer, nullable=False)
    action_type = Column(String(50), nullable=False)  # 'CREATE', 'UPDATE', 'DELETE'
    metadata = Column(JSON, nullable=False)
    checksum_hash = Column(String(64), nullable=False)  # SHA-256 hash
    created_at = Column(DateTime(timezone=True), 
                       server_default=func.now(), 
                       nullable=False)
    
    # Indexes
    __table_args__ = (
        Index('idx_audit_logs_entity', 'entity_type', 'entity_id'),
        Index('idx_audit_logs_action_type', 'action_type'),
        Index('idx_audit_logs_created_at', 'created_at'),
        Index('idx_audit_logs_checksum', 'checksum_hash'),
    )
    
    def __init__(self, entity_type: str, entity_id: int, action_type: str, metadata: Dict[str, Any]):
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.action_type = action_type
        self.metadata = metadata
        self.checksum_hash = self._generate_checksum()
    
    def _generate_checksum(self) -> str:
        """Generate SHA-256 checksum for integrity verification."""
        data = json.dumps({
            'entity_type': self.entity_type,
            'entity_id': self.entity_id,
            'action_type': self.action_type,
            'metadata': self.metadata
        }, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(data.encode('utf-8')).hexdigest()
    
    def verify_integrity(self) -> bool:
        """Verify the integrity of the audit log entry."""
        return self.checksum_hash == self._generate_checksum()
    
    def __repr__(self):
        return f"<AuditLog(id={self.id}, entity_type='{self.entity_type}', action_type='{self.action_type}')>"

class ModelRegistry(Base, TimestampMixin):
    """Model registry for tracking ML model versions."""
    __tablename__ = 'model_registry'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    model_name = Column(String(100), nullable=False)
    model_version = Column(String(100), nullable=False)
    model_type = Column(String(50), nullable=False)  # 'logistic_regression', 'random_forest', etc.
    model_path = Column(String(500), nullable=False)
    preprocessing_path = Column(String(500), nullable=False)
    metrics = Column(JSON, nullable=False)
    is_active = Column(Boolean, default=False, nullable=False)
    training_data_hash = Column(String(64), nullable=False)
    feature_schema_version = Column(String(100), nullable=False)
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('model_name', 'model_version', name='uq_model_name_version'),
        Index('idx_model_registry_active', 'is_active'),
        Index('idx_model_registry_model_type', 'model_type'),
        Index('idx_model_registry_created_at', 'created_at'),
    )
    
    def __repr__(self):
        return f"<ModelRegistry(id={self.id}, model_name='{self.model_name}', version='{self.model_version}')>"