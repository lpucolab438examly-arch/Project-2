"""Database utilities and connection management."""

from contextlib import contextmanager
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from typing import Generator
import logging

from app.models.database import Base, AuditLog

logger = logging.getLogger(__name__)

class DatabaseManager:
    """Database connection and session management."""
    
    def __init__(self, database_url: str, **engine_kwargs):
        """Initialize database manager."""
        self.engine = create_engine(database_url, **engine_kwargs)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        
        # Add audit logging listeners
        self._setup_audit_listeners()
    
    def _setup_audit_listeners(self):
        """Setup SQLAlchemy event listeners for audit logging."""
        
        @event.listens_for(Session, 'after_insert')
        def log_insert(mapper, connection, target):
            """Log insert operations."""
            if hasattr(target, '__tablename__') and target.__tablename__ != 'audit_logs':
                self._create_audit_log('CREATE', target)
        
        @event.listens_for(Session, 'after_update') 
        def log_update(mapper, connection, target):
            """Log update operations."""
            if hasattr(target, '__tablename__') and target.__tablename__ != 'audit_logs':
                self._create_audit_log('UPDATE', target)
    
    def _create_audit_log(self, action_type: str, target):
        """Create audit log entry."""
        try:
            metadata = {
                'table': target.__tablename__,
                'primary_key': getattr(target, 'id', None),
                'timestamp': str(target.created_at) if hasattr(target, 'created_at') else None
            }
            
            # Add specific fields based on table type
            if target.__tablename__ == 'transactions':
                metadata.update({
                    'user_id': target.user_id,
                    'amount': float(target.amount),
                    'currency': target.currency
                })
            elif target.__tablename__ == 'predictions':
                metadata.update({
                    'transaction_id': target.transaction_id,
                    'fraud_probability': float(target.fraud_probability),
                    'model_version': target.model_version
                })
            
            audit_entry = AuditLog(
                entity_type=target.__tablename__,
                entity_id=getattr(target, 'id', 0),
                action_type=action_type,
                metadata=metadata
            )
            
            # Create new session for audit log to avoid recursion
            with self.get_session() as audit_session:
                audit_session.add(audit_entry)
                audit_session.commit()
                
        except Exception as e:
            logger.error(f"Failed to create audit log: {e}")
    
    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """Get database session with automatic cleanup."""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    def create_tables(self):
        """Create all database tables."""
        Base.metadata.create_all(bind=self.engine)
    
    def drop_tables(self):
        """Drop all database tables."""
        Base.metadata.drop_all(bind=self.engine)