# FraudNet.AI Architecture Guide

## System Overview

FraudNet.AI is designed as a modular, scalable fraud detection system following microservices principles and cloud-native patterns. The system is built for high availability, real-time processing, and enterprise-grade security.

## Architecture Principles

### 1. Separation of Concerns
- **API Layer**: REST endpoints with authentication and rate limiting
- **Business Logic**: Core fraud detection and model management
- **Data Layer**: Persistent storage and caching
- **ML Pipeline**: Feature engineering, training, and inference

### 2. Scalability
- **Horizontal scaling**: Stateless application design
- **Caching strategies**: Redis for session and model caching
- **Database optimization**: Connection pooling and query optimization
- **Asynchronous processing**: Background jobs for model training

### 3. Security-First Design
- **Authentication**: API key-based authentication with permissions
- **Rate limiting**: Token bucket algorithm with Redis backend
- **Input validation**: Comprehensive request validation and sanitization
- **Audit trails**: Immutable logging with cryptographic integrity

### 4. Observability
- **Structured logging**: JSON logs with correlation IDs
- **Health monitoring**: Multiple health check endpoints
- **Performance metrics**: Request timing and ML model performance
- **Error tracking**: Detailed error responses with debugging context

## System Components

```
┌─────────────────────────────────────────────────────────────────┐
│                        Load Balancer / API Gateway              │
│                          (Nginx/Traefik)                        │
└─────────────────────────┬───────────────────────────────────────┘
                         │
┌─────────────────────────▼───────────────────────────────────────┐
│                     Flask Application                          │
│  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐   │
│  │   API Layer     │ │  Security Layer │ │ Business Logic  │   │
│  │                 │ │                 │ │                 │   │
│  │ • REST Routes   │ │ • Authentication│ │ • Fraud Engine  │   │
│  │ • Validation    │ │ • Rate Limiting │ │ • Model Manager │   │
│  │ • Serialization │ │ • Input Sanitiz │ │ • Feature Eng   │   │
│  └─────────────────┘ └─────────────────┘ └─────────────────┘   │
└─────────────────────────┬───────────────────────────────────────┘
                         │
┌─────────────────────────▼───────────────────────────────────────┐
│                      Data Layer                                │
│  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐   │
│  │     MySQL       │ │      Redis      │ │  File System    │   │
│  │                 │ │                 │ │                 │   │
│  │ • Transactions  │ │ • Sessions      │ │ • Model Files   │   │
│  │ • Users         │ │ • Cache         │ │ • Artifacts     │   │
│  │ • Predictions   │ │ • Rate Limits   │ │ • Logs          │   │
│  │ • Audit Logs    │ │ • ML Models     │ │ • Metrics       │   │
│  └─────────────────┘ └─────────────────┘ └─────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

## Core Components Deep Dive

### API Layer

The API layer provides RESTful endpoints following OpenAPI 3.0 specifications:

**Key Features:**
- **Modular blueprints**: Separate concern areas (transactions, models, health, users)
- **Request validation**: Marshmallow schemas for input/output validation
- **Response formatting**: Consistent JSON response structure
- **Error handling**: Standardized error responses with correlation IDs

**Component Structure:**
```
app/api/
├── __init__.py          # Blueprint registration
├── transactions.py      # Transaction endpoints
├── models.py           # Model management endpoints
├── health.py           # Health check endpoints
└── users.py            # User management endpoints
```

### Security Layer

Comprehensive security middleware protecting all application layers:

**Authentication System:**
- **API Key Management**: Redis-backed API key storage with TTL
- **Permission System**: Role-based access control (read, write, admin, bulk)
- **Session Management**: Secure session handling with Redis

**Rate Limiting:**
- **Token Bucket Algorithm**: Sliding window rate limiting
- **Per-User Limits**: Different limits based on API key permissions
- **Burst Handling**: Configurable burst capacity for traffic spikes

**Input Validation:**
- **Schema Validation**: Marshmallow-based request validation
- **SQL Injection Prevention**: SQLAlchemy ORM with parameterized queries
- **XSS Protection**: Input sanitization and security headers

### Business Logic Layer

Core fraud detection and model management functionality:

**Fraud Detection Engine:**
- **Real-time Processing**: Sub-200ms prediction latency
- **Model Management**: Versioned model loading and caching
- **Feature Engineering**: Consistent feature extraction pipeline
- **Risk Assessment**: Multi-level risk classification

**Feature Engineering Pipeline:**
- **Historical Features**: Time-series aggregations and statistics
- **Real-time Features**: Current transaction context
- **Feature Validation**: Schema versioning and compatibility checks
- **Training-Inference Parity**: Identical feature extraction logic

### Data Layer

Multi-tier data storage optimized for different access patterns:

**MySQL (Primary Storage):**
- **ACID Compliance**: Transaction integrity and consistency
- **Normalized Schema**: Efficient storage and query performance
- **Connection Pooling**: Optimized database connections
- **Indexing Strategy**: Performance-tuned indexes for common queries

**Redis (Caching & Sessions):**
- **Session Storage**: API key and session management
- **Model Caching**: In-memory model storage for fast access
- **Rate Limiting**: Token bucket counters
- **Feature Caching**: Computed feature caching

**File System (Artifacts):**
- **ML Models**: Serialized model files with versioning
- **Training Metrics**: Model performance and evaluation reports
- **Preprocessing**: Feature encoders and transformations
- **Logging**: Structured log files with rotation

## Database Schema

### Entity Relationship Diagram

```mermaid
erDiagram
    User ||--o{ Transaction : creates
    User {
        int id PK
        string user_id UK
        string email
        string phone
        datetime registration_date
        enum user_type
    }
    
    Transaction ||--|| Prediction : has
    Transaction {
        int id PK
        string transaction_id UK
        int user_id FK
        decimal amount
        string merchant
        string merchant_category
        datetime transaction_date
        string location_country
        string location_city
        enum payment_method
        enum device_type
        boolean is_fraud
    }
    
    Prediction {
        int id PK
        int transaction_id FK
        string model_version
        decimal fraud_probability
        enum risk_level
        datetime prediction_date
        int processing_time_ms
    }
    
    ModelRegistry {
        int id PK
        string model_name
        string version UK
        string algorithm
        text hyperparameters
        decimal training_accuracy
        decimal validation_accuracy
        decimal precision
        decimal recall
        decimal f1_score
        boolean is_active
        datetime created_at
    }
    
    AuditLog {
        int id PK
        string action
        string entity_type
        int entity_id
        string user_id
        text changes
        string ip_address
        string user_agent
        string checksum
        datetime timestamp
    }
```

### Table Specifications

**Users Table:**
- Primary key: Auto-incrementing ID
- Unique constraints: user_id, email
- Indexes: user_id, email, registration_date
- Business keys: user_id for external references

**Transactions Table:**
- Primary key: Auto-incrementing ID
- Foreign key: user_id references Users.id
- Unique constraints: transaction_id
- Indexes: transaction_id, user_id, transaction_date, amount, is_fraud
- Partitioning: Consider date-based partitioning for large volumes

**Predictions Table:**
- Primary key: Auto-incrementing ID
- Foreign key: transaction_id references Transactions.id
- Indexes: transaction_id, model_version, prediction_date
- One-to-one relationship with Transactions

**Model Registry:**
- Primary key: Auto-incrementing ID
- Unique constraints: version
- Indexes: version, is_active, created_at
- Stores model metadata and performance metrics

**Audit Log:**
- Primary key: Auto-incrementing ID
- Immutable records: No updates or deletes allowed
- Checksum: SHA-256 hash for integrity verification
- Indexes: entity_type, entity_id, timestamp, user_id

## ML Pipeline Architecture

### Training Pipeline

```mermaid
graph TD
    A[Raw Transaction Data] --> B[Data Validation]
    B --> C[Feature Engineering]
    C --> D[Data Splitting]
    D --> E[Model Training]
    E --> F[Model Evaluation]
    F --> G{Performance Check}
    G -->|Pass| H[Model Registration]
    G -->|Fail| I[Retrain with Different Params]
    H --> J[Model Deployment]
    I --> E
```

**Pipeline Stages:**

1. **Data Collection**: Query transactions from specified time window
2. **Data Validation**: Check data quality and completeness
3. **Feature Engineering**: Extract features using historical aggregations
4. **Data Splitting**: Train/validation split with temporal consideration
5. **Model Training**: GridSearchCV for hyperparameter optimization
6. **Model Evaluation**: Comprehensive metrics calculation
7. **Performance Check**: Compare against baseline and thresholds
8. **Model Registration**: Store model with metadata and artifacts
9. **Model Deployment**: Activate model for inference

### Inference Pipeline

```mermaid
graph TD
    A[Transaction Request] --> B[Input Validation]
    B --> C[Feature Extraction]
    C --> D[Model Loading]
    D --> E[Prediction Generation]
    E --> F[Risk Assessment]
    F --> G[Response Formatting]
    G --> H[Audit Logging]
```

**Pipeline Stages:**

1. **Input Validation**: Validate transaction data against schema
2. **Feature Extraction**: Generate features using real-time data
3. **Model Loading**: Load active model from cache or storage
4. **Prediction**: Generate fraud probability using ML model
5. **Risk Assessment**: Classify risk level based on probability
6. **Response Formatting**: Structure response with metadata
7. **Audit Logging**: Log prediction for compliance and monitoring

### Feature Engineering

**Feature Categories:**

1. **Transaction Features**:
   - Amount z-score (normalized by user history)
   - Time-based features (hour, day of week, time since last transaction)
   - Merchant features (category, frequency of use)
   - Location features (country, city, velocity)

2. **User Behavioral Features**:
   - Average transaction amount (7/30/90 days)
   - Transaction frequency patterns
   - Merchant diversity metrics
   - Payment method preferences

3. **Contextual Features**:
   - Device type and consistency
   - Location velocity (impossible travel)
   - Time velocity (rapid consecutive transactions)
   - Amount velocity (sudden spending pattern changes)

**Feature Store Design:**

```python
class FeatureStore:
    def __init__(self):
        self.historical_extractor = HistoricalFeatureExtractor()
        self.realtime_extractor = RealTimeFeatureExtractor()
    
    def extract_features(self, transaction, mode='inference'):
        # Ensure training-inference parity
        historical_features = self.historical_extractor.extract(transaction)
        realtime_features = self.realtime_extractor.extract(transaction)
        
        return {**historical_features, **realtime_features}
```

## Security Architecture

### Defense in Depth

FraudNet.AI implements multiple security layers:

**Network Security:**
- TLS termination at load balancer
- Internal service communication encryption
- VPC/subnet isolation in cloud deployments
- Firewall rules and security groups

**Application Security:**
- API key authentication with permissions
- Rate limiting with Redis backend
- Input validation and sanitization
- SQL injection prevention via ORM
- XSS protection with security headers

**Data Security:**
- Database connection encryption
- Sensitive data hashing (API keys)
- Audit trail with cryptographic integrity
- PII data handling compliance

**Infrastructure Security:**
- Container image scanning
- Non-root container execution
- Secret management with environment variables
- Security-hardened Docker images

### Authentication Flow

```mermaid
sequenceDiagram
    participant Client
    participant API Gateway
    participant Auth Service
    participant Redis
    participant Application
    
    Client->>API Gateway: Request with API Key
    API Gateway->>Auth Service: Validate API Key
    Auth Service->>Redis: Check API Key
    Redis-->>Auth Service: Key Data
    Auth Service-->>API Gateway: Validation Result
    API Gateway->>Application: Authorized Request
    Application-->>API Gateway: Response
    API Gateway-->>Client: Response with Rate Limit Headers
```

### Rate Limiting Algorithm

```python
class TokenBucket:
    def __init__(self, capacity, refill_rate):
        self.capacity = capacity
        self.tokens = capacity
        self.refill_rate = refill_rate
        self.last_refill = time.time()
    
    def allow_request(self):
        now = time.time()
        # Add tokens based on time elapsed
        tokens_to_add = (now - self.last_refill) * self.refill_rate
        self.tokens = min(self.capacity, self.tokens + tokens_to_add)
        self.last_refill = now
        
        if self.tokens >= 1:
            self.tokens -= 1
            return True
        return False
```

## Deployment Architecture

### Container Strategy

**Multi-stage Docker Build:**

```dockerfile
# Build stage
FROM python:3.11-slim as builder
COPY requirements.txt .
RUN pip install --user -r requirements.txt

# Development stage
FROM builder as development
COPY . .
CMD ["flask", "run", "--host=0.0.0.0"]

# Production stage
FROM python:3.11-slim
COPY --from=builder /root/.local /root/.local
COPY . .
USER fraudnet
CMD ["gunicorn", "--workers", "4", "--bind", "0.0.0.0:5000", "run:app"]
```

**Container Orchestration:**

```yaml
version: '3.8'
services:
  app:
    build: .
    ports: ["5000:5000"]
    environment:
      - DATABASE_URL=mysql+pymysql://user:pass@mysql/db
      - REDIS_URL=redis://redis:6379/0
    depends_on: [mysql, redis]
    
  nginx:
    image: nginx:alpine
    ports: ["80:80", "443:443"]
    volumes: ["./nginx.conf:/etc/nginx/nginx.conf"]
    depends_on: [app]
    
  mysql:
    image: mysql:8.0
    environment:
      - MYSQL_ROOT_PASSWORD=rootpass
    volumes: ["mysql_data:/var/lib/mysql"]
    
  redis:
    image: redis:7-alpine
    volumes: ["redis_data:/data"]
```

### Cloud Architecture

**AWS Deployment Example:**

```
┌─────────────────────────────────────────────────────────────┐
│                    Application Load Balancer                │
│                       (SSL Termination)                     │
└─────────────┬───────────────────────────────────────────────┘
             │
┌─────────────▼───────────────────────────────────────────────┐
│                      ECS Service                            │
│  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐│
│  │   ECS Task 1    │ │   ECS Task 2    │ │   ECS Task N    ││
│  │                 │ │                 │ │                 ││
│  │ ┌─────────────┐ │ │ ┌─────────────┐ │ │ ┌─────────────┐ ││
│  │ │ App Container│ │ │ │ App Container│ │ │ │ App Container│ ││
│  │ └─────────────┘ │ │ └─────────────┘ │ │ └─────────────┘ ││
│  └─────────────────┘ └─────────────────┘ └─────────────────┘│
└─────────────┬───────────────────────────────────────────────┘
             │
┌─────────────▼───────────────────────────────────────────────┐
│                       Data Layer                            │
│  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐│
│  │      RDS        │ │  ElastiCache    │ │       S3        ││
│  │    (MySQL)      │ │    (Redis)      │ │  (Artifacts)    ││
│  └─────────────────┘ └─────────────────┘ └─────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

**Kubernetes Deployment:**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: fraudnet-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: fraudnet-api
  template:
    metadata:
      labels:
        app: fraudnet-api
    spec:
      containers:
      - name: api
        image: fraudnet/api:latest
        ports:
        - containerPort: 5000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: database-secret
              key: url
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /api/v1/health/live
            port: 5000
          initialDelaySeconds: 30
        readinessProbe:
          httpGet:
            path: /api/v1/health/ready
            port: 5000
          initialDelaySeconds: 5
```

## Monitoring and Observability

### Logging Strategy

**Structured Logging:**

```python
import structlog

logger = structlog.get_logger(__name__)

logger.info(
    "Transaction processed",
    transaction_id=transaction.id,
    user_id=transaction.user_id,
    amount=transaction.amount,
    fraud_probability=prediction.fraud_probability,
    processing_time_ms=processing_time,
    model_version=model.version,
    correlation_id=request.correlation_id
)
```

**Log Levels and Categories:**

- **ERROR**: System errors, failed predictions, database failures
- **WARNING**: Rate limiting, authentication failures, validation errors
- **INFO**: Transaction processing, model training, user actions
- **DEBUG**: Detailed execution flow, performance metrics

### Metrics Collection

**Application Metrics:**

```python
from prometheus_client import Counter, Histogram, Gauge

# Request counters
request_count = Counter('fraudnet_requests_total', 'Total requests', ['method', 'endpoint'])
prediction_count = Counter('fraudnet_predictions_total', 'Total predictions', ['risk_level'])

# Performance histograms
request_duration = Histogram('fraudnet_request_duration_seconds', 'Request duration')
prediction_time = Histogram('fraudnet_prediction_duration_seconds', 'Prediction time')

# System gauges
active_connections = Gauge('fraudnet_db_connections_active', 'Active DB connections')
model_accuracy = Gauge('fraudnet_model_accuracy', 'Current model accuracy')
```

**Health Check Endpoints:**

```python
@health_bp.route('/health')
def basic_health():
    return jsonify({"status": "healthy", "timestamp": datetime.utcnow().isoformat()})

@health_bp.route('/health/ready')
def readiness_check():
    checks = {
        'database': check_database_connection(),
        'redis': check_redis_connection(),
        'model': check_model_loaded()
    }
    
    if all(checks.values()):
        return jsonify({"status": "ready", "dependencies": checks})
    else:
        return jsonify({"status": "not_ready", "dependencies": checks}), 503
```

### Performance Optimization

**Database Optimization:**
- Connection pooling with SQLAlchemy
- Query optimization with proper indexing
- Read replicas for analytics workloads
- Connection timeout and retry logic

**Caching Strategy:**
- Redis for API key and session caching
- Model caching in memory with TTL
- Feature caching for repeated calculations
- HTTP response caching for static content

**Application Performance:**
- Asynchronous processing for non-critical operations
- Connection pooling for external services
- Efficient serialization with optimized schemas
- Background job processing for model training

## Scaling Considerations

### Horizontal Scaling

**Stateless Design:**
- No server-side session storage (Redis-based sessions)
- Shared cache layer across instances
- Externalized configuration
- Load balancer health checks

**Database Scaling:**
- Read replicas for analytics and reporting
- Connection pooling across application instances
- Database partitioning by date or user_id
- Automated failover and backup strategies

**Cache Scaling:**
- Redis Cluster for high availability
- Cache partitioning by key patterns
- Cache warm-up strategies
- Eviction policies for memory management

### Vertical Scaling

**Resource Optimization:**
- Memory profiling and optimization
- CPU usage monitoring and scaling
- Disk I/O optimization for ML models
- Container resource limits and requests

**Model Performance:**
- Model size optimization
- Inference time optimization
- Batch prediction capabilities
- Model compression techniques

## Disaster Recovery

### Backup Strategy

**Database Backups:**
- Automated daily full backups
- Transaction log backups every 15 minutes
- Cross-region backup replication
- Point-in-time recovery capability

**Application State:**
- Model artifacts versioning and backup
- Configuration backup and version control
- Infrastructure as code for quick recovery
- Automated deployment pipelines

### High Availability

**Multi-Region Deployment:**
- Active-passive failover setup
- Database replication across regions
- DNS-based traffic routing
- Automated health monitoring and failover

**Fault Tolerance:**
- Circuit breaker pattern for external services
- Graceful degradation during partial failures
- Retry logic with exponential backoff
- Error handling and recovery procedures

---

This architecture guide provides the foundation for understanding, deploying, and scaling FraudNet.AI. The modular design enables independent scaling of components while maintaining system integrity and security.