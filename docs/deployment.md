# FraudNet.AI Deployment Guide

## Overview

This guide provides comprehensive instructions for deploying FraudNet.AI in various environments, from local development to production-grade cloud deployments.

## Prerequisites

### System Requirements

**Minimum Requirements:**
- CPU: 2 cores
- RAM: 4 GB
- Storage: 20 GB
- Network: 1 Gbps

**Recommended Production:**
- CPU: 4+ cores
- RAM: 8+ GB  
- Storage: 100+ GB SSD
- Network: 10 Gbps

### Software Dependencies

**Required:**
- Docker 20.10+
- Docker Compose 2.0+
- Python 3.11+ (for manual deployment)
- MySQL 8.0+ or compatible database
- Redis 7.0+ or compatible cache

**Optional:**
- Kubernetes 1.20+ (for K8s deployment)
- Nginx (for reverse proxy)
- Prometheus/Grafana (for monitoring)

## Quick Start Deployment

### Docker Compose (Recommended)

1. **Clone Repository**
   ```bash
   git clone https://github.com/your-org/fraudnet-ai.git
   cd fraudnet-ai
   ```

2. **Environment Configuration**
   ```bash
   cp .env.template .env
   # Edit .env with your configuration
   vim .env
   ```

3. **Start Services**
   ```bash
   make docker-up
   ```

4. **Initialize Database**
   ```bash
   make migrate
   make seed-data  # Optional: For development/testing
   ```

5. **Verify Deployment**
   ```bash
   curl http://localhost:5000/api/v1/health
   ```

### Development Setup

For local development with hot reloading:

```bash
# Start development environment
make docker-up

# View logs
make docker-logs

# Access application shell
make docker-shell

# Run tests
make test
```

## Production Deployment

### Environment Configuration

#### Required Environment Variables

```bash
# Security (REQUIRED in production)
SECRET_KEY=your-256-bit-secret-key-here
JWT_SECRET_KEY=your-jwt-secret-key-here

# Database
DATABASE_URL=mysql+pymysql://fraudnet:password@mysql-host:3306/fraudnet
DATABASE_POOL_SIZE=20
DATABASE_POOL_TIMEOUT=30

# Redis
REDIS_URL=redis://redis-host:6379/0
REDIS_TIMEOUT=5

# Application
FLASK_ENV=production
LOG_LEVEL=WARNING
```

#### Optional Environment Variables

```bash
# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_PER_MINUTE=1000
RATE_LIMIT_BURST=50

# Security Headers
CORS_ENABLED=false
VALIDATE_CONTENT_TYPE=true
MAX_CONTENT_LENGTH=1048576

# Model Configuration
MODEL_CACHE_TTL=3600
MODEL_RETRAIN_THRESHOLD=0.05

# Monitoring
PROMETHEUS_ENABLED=true
PROMETHEUS_PORT=8000
```

### Docker Production Deployment

#### 1. Build Production Image

```bash
# Build the production image
docker build --target production -t fraudnet/api:latest .

# Or use make command
make prod-build
```

#### 2. Production Docker Compose

Create `docker-compose.prod.yml`:

```yaml
version: '3.8'

services:
  app:
    image: fraudnet/api:latest
    ports:
      - "5000:5000"
    environment:
      - FLASK_ENV=production
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
      - SECRET_KEY=${SECRET_KEY}
      - JWT_SECRET_KEY=${JWT_SECRET_KEY}
    volumes:
      - app_artifacts:/app/artifacts
      - app_logs:/app/logs
    depends_on:
      - mysql
      - redis
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5000/api/v1/health/live"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./docker/nginx/nginx.conf:/etc/nginx/nginx.conf
      - ./docker/nginx/ssl:/etc/nginx/ssl
    depends_on:
      - app
    restart: unless-stopped

  mysql:
    image: mysql:8.0
    environment:
      MYSQL_ROOT_PASSWORD: ${MYSQL_ROOT_PASSWORD}
      MYSQL_DATABASE: fraudnet
      MYSQL_USER: fraudnet
      MYSQL_PASSWORD: ${MYSQL_PASSWORD}
    volumes:
      - mysql_data:/var/lib/mysql
      - ./docker/mysql/init.sql:/docker-entrypoint-initdb.d/01-init.sql
      - ./docker/mysql/my.cnf:/etc/mysql/conf.d/my.cnf
    restart: unless-stopped
    command: --character-set-server=utf8mb4 --collation-server=utf8mb4_unicode_ci

  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes --requirepass ${REDIS_PASSWORD}
    volumes:
      - redis_data:/data
    restart: unless-stopped

  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./docker/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    restart: unless-stopped

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000" 
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD}
    volumes:
      - grafana_data:/var/lib/grafana
      - ./docker/grafana/dashboards:/etc/grafana/provisioning/dashboards
    restart: unless-stopped

volumes:
  mysql_data:
  redis_data:
  app_artifacts:
  app_logs:
  prometheus_data:
  grafana_data:

networks:
  default:
    driver: bridge
```

#### 3. Deploy Production Stack

```bash
# Create production environment file
cp .env.production .env

# Edit environment variables
vim .env

# Deploy the stack
docker-compose -f docker-compose.prod.yml up -d

# Check service health
docker-compose -f docker-compose.prod.yml ps
```

### Manual Production Deployment

For deployments without Docker:

#### 1. System Setup

```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Install Python 3.11
sudo apt install python3.11 python3.11-venv python3.11-dev

# Install MySQL/PostgreSQL
sudo apt install mysql-server-8.0

# Install Redis
sudo apt install redis-server

# Install Nginx
sudo apt install nginx
```

#### 2. Application Setup

```bash
# Create application user
sudo useradd -r -s /bin/false fraudnet
sudo mkdir -p /opt/fraudnet
sudo chown fraudnet:fraudnet /opt/fraudnet

# Switch to application user
sudo -u fraudnet bash

# Clone and setup application
cd /opt/fraudnet
git clone https://github.com/your-org/fraudnet-ai.git app
cd app

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Install application
pip install -e .
```

#### 3. Database Setup

```bash
# Connect to MySQL as root
sudo mysql -u root -p

# Create database and user
CREATE DATABASE fraudnet CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'fraudnet'@'localhost' IDENTIFIED BY 'secure_password';
GRANT ALL PRIVILEGES ON fraudnet.* TO 'fraudnet'@'localhost';
FLUSH PRIVILEGES;
EXIT;

# Initialize database schema
cd /opt/fraudnet/app
source venv/bin/activate
python -c "from app.models.database import create_tables; create_tables()"
```

#### 4. System Service Configuration

Create systemd service `/etc/systemd/system/fraudnet.service`:

```ini
[Unit]
Description=FraudNet.AI API Server
After=network.target mysql.service redis.service

[Service]
Type=exec
User=fraudnet
Group=fraudnet
WorkingDirectory=/opt/fraudnet/app
Environment=PATH=/opt/fraudnet/app/venv/bin
EnvironmentFile=/opt/fraudnet/app/.env
ExecStart=/opt/fraudnet/app/venv/bin/gunicorn --bind 127.0.0.1:5000 --workers 4 --timeout 120 run:app
ExecReload=/bin/kill -s HUP $MAINPID
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable fraudnet
sudo systemctl start fraudnet
sudo systemctl status fraudnet
```

#### 5. Nginx Configuration

Create `/etc/nginx/sites-available/fraudnet`:

```nginx
upstream fraudnet_app {
    server 127.0.0.1:5000;
}

server {
    listen 80;
    server_name your-domain.com;

    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    # SSL Configuration
    ssl_certificate /etc/ssl/certs/fraudnet.crt;
    ssl_certificate_key /etc/ssl/private/fraudnet.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA384:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-RSA-AES256-SHA384;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;

    # Security Headers
    add_header X-Content-Type-Options nosniff;
    add_header X-Frame-Options DENY;
    add_header X-XSS-Protection "1; mode=block";
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains";

    # Gzip Compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types application/json text/css application/javascript;

    # Rate Limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
    
    location / {
        limit_req zone=api burst=20 nodelay;
        
        proxy_pass http://fraudnet_app;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Timeouts
        proxy_connect_timeout 5s;
        proxy_send_timeout 10s;
        proxy_read_timeout 30s;
    }

    # Health check endpoint (no rate limiting)
    location /api/v1/health {
        proxy_pass http://fraudnet_app;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Static content (if any)
    location /static {
        alias /opt/fraudnet/app/static;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

Enable the site:

```bash
sudo ln -s /etc/nginx/sites-available/fraudnet /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

## Cloud Deployment

### AWS Deployment

#### ECS with Fargate

1. **Create ECS Cluster**

```bash
# Create cluster
aws ecs create-cluster --cluster-name fraudnet-prod

# Create task definition
cat > task-definition.json << 'EOF'
{
  "family": "fraudnet-api",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "executionRoleArn": "arn:aws:iam::account:role/ecsTaskExecutionRole",
  "taskRoleArn": "arn:aws:iam::account:role/fraudnetTaskRole",
  "containerDefinitions": [
    {
      "name": "fraudnet-api",
      "image": "your-account.dkr.ecr.region.amazonaws.com/fraudnet:latest",
      "portMappings": [
        {
          "containerPort": 5000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {
          "name": "FLASK_ENV",
          "value": "production"
        }
      ],
      "secrets": [
        {
          "name": "DATABASE_URL",
          "valueFrom": "arn:aws:ssm:region:account:parameter/fraudnet/database-url"
        },
        {
          "name": "SECRET_KEY", 
          "valueFrom": "arn:aws:ssm:region:account:parameter/fraudnet/secret-key"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/fraudnet",
          "awslogs-region": "us-west-2",
          "awslogs-stream-prefix": "ecs"
        }
      },
      "healthCheck": {
        "command": ["CMD-SHELL", "curl -f http://localhost:5000/api/v1/health/live || exit 1"],
        "interval": 30,
        "timeout": 5,
        "retries": 3,
        "startPeriod": 60
      }
    }
  ]
}
EOF

# Register task definition
aws ecs register-task-definition --cli-input-json file://task-definition.json
```

2. **Create ECS Service**

```bash
# Create service
aws ecs create-service \
  --cluster fraudnet-prod \
  --service-name fraudnet-api \
  --task-definition fraudnet-api:1 \
  --desired-count 2 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx,subnet-yyy],securityGroups=[sg-xxx],assignPublicIp=ENABLED}" \
  --load-balancers "targetGroupArn=arn:aws:elasticloadbalancing:region:account:targetgroup/fraudnet-tg,containerName=fraudnet-api,containerPort=5000"
```

#### RDS Database Setup

```bash
# Create RDS instance
aws rds create-db-instance \
  --db-instance-identifier fraudnet-prod \
  --db-instance-class db.t3.medium \
  --engine mysql \
  --engine-version 8.0.35 \
  --master-username fraudnet \
  --master-user-password SecurePassword123! \
  --allocated-storage 100 \
  --storage-type gp2 \
  --storage-encrypted \
  --vpc-security-group-ids sg-xxx \
  --db-subnet-group-name fraudnet-subnet-group \
  --backup-retention-period 7 \
  --preferred-backup-window "03:00-04:00" \
  --preferred-maintenance-window "sun:04:00-sun:05:00"
```

#### ElastiCache Redis Setup

```bash
# Create Redis cluster
aws elasticache create-replication-group \
  --replication-group-id fraudnet-redis \
  --description "FraudNet Redis Cluster" \
  --node-type cache.t3.medium \
  --engine redis \
  --engine-version 7.0 \
  --num-cache-clusters 2 \
  --cache-subnet-group-name fraudnet-cache-subnet \
  --security-group-ids sg-xxx \
  --at-rest-encryption-enabled \
  --transit-encryption-enabled \
  --auth-token YourAuthTokenHere
```

### Kubernetes Deployment

#### Namespace and Secrets

```yaml
# namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: fraudnet

---
# secrets.yaml
apiVersion: v1
kind: Secret
metadata:
  name: fraudnet-secrets
  namespace: fraudnet
type: Opaque
stringData:
  database-url: "mysql+pymysql://user:pass@mysql-host:3306/fraudnet"
  redis-url: "redis://redis-host:6379/0"
  secret-key: "your-secret-key"
  jwt-secret-key: "your-jwt-secret-key"
```

#### ConfigMap

```yaml
# configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: fraudnet-config
  namespace: fraudnet
data:
  FLASK_ENV: "production"
  LOG_LEVEL: "WARNING"
  RATE_LIMIT_ENABLED: "true"
  RATE_LIMIT_PER_MINUTE: "1000"
  PROMETHEUS_ENABLED: "true"
```

#### Deployment

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: fraudnet-api
  namespace: fraudnet
  labels:
    app: fraudnet-api
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
          name: http
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: fraudnet-secrets
              key: database-url
        - name: REDIS_URL
          valueFrom:
            secretKeyRef:
              name: fraudnet-secrets
              key: redis-url
        - name: SECRET_KEY
          valueFrom:
            secretKeyRef:
              name: fraudnet-secrets
              key: secret-key
        - name: JWT_SECRET_KEY
          valueFrom:
            secretKeyRef:
              name: fraudnet-secrets
              key: jwt-secret-key
        envFrom:
        - configMapRef:
            name: fraudnet-config
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /api/v1/health/live
            port: http
          initialDelaySeconds: 30
          periodSeconds: 10
          timeoutSeconds: 5
          successThreshold: 1
          failureThreshold: 3
        readinessProbe:
          httpGet:
            path: /api/v1/health/ready
            port: http
          initialDelaySeconds: 5
          periodSeconds: 5
          timeoutSeconds: 5
          successThreshold: 1
          failureThreshold: 3
        startupProbe:
          httpGet:
            path: /api/v1/health/live
            port: http
          initialDelaySeconds: 10
          periodSeconds: 5
          timeoutSeconds: 5
          failureThreshold: 30
      restartPolicy: Always
```

#### Service and Ingress

```yaml
# service.yaml
apiVersion: v1
kind: Service
metadata:
  name: fraudnet-api-service
  namespace: fraudnet
  labels:
    app: fraudnet-api
spec:
  selector:
    app: fraudnet-api
  ports:
  - name: http
    port: 80
    targetPort: 5000
    protocol: TCP
  type: ClusterIP

---
# ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: fraudnet-api-ingress
  namespace: fraudnet
  annotations:
    nginx.ingress.kubernetes.io/rate-limit: "1000"
    nginx.ingress.kubernetes.io/rate-limit-window: "1m"
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
spec:
  tls:
  - hosts:
    - api.fraudnet.example.com
    secretName: fraudnet-api-tls
  rules:
  - host: api.fraudnet.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: fraudnet-api-service
            port:
              number: 80
```

#### Horizontal Pod Autoscaler  

```yaml
# hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: fraudnet-api-hpa
  namespace: fraudnet
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: fraudnet-api
  minReplicas: 3
  maxReplicas: 20
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
      - type: Percent
        value: 10
        periodSeconds: 60
    scaleUp:
      stabilizationWindowSeconds: 60
      policies:
      - type: Percent
        value: 50
        periodSeconds: 60
      - type: Pods
        value: 2
        periodSeconds: 60
      selectPolicy: Max
```

#### Deploy to Kubernetes

```bash
# Apply all configurations
kubectl apply -f namespace.yaml
kubectl apply -f secrets.yaml
kubectl apply -f configmap.yaml
kubectl apply -f deployment.yaml
kubectl apply -f service.yaml
kubectl apply -f ingress.yaml
kubectl apply -f hpa.yaml

# Check deployment status
kubectl get pods -n fraudnet
kubectl get svc -n fraudnet
kubectl get ingress -n fraudnet

# View logs
kubectl logs -f deployment/fraudnet-api -n fraudnet
```

## Monitoring and Maintenance

### Health Monitoring

#### Health Check Endpoints

```bash
# Basic health check
curl http://your-domain.com/api/v1/health

# Kubernetes liveness probe
curl http://your-domain.com/api/v1/health/live

# Kubernetes readiness probe  
curl http://your-domain.com/api/v1/health/ready

# Detailed health check (requires admin API key)
curl -H "X-API-Key: admin-key" http://your-domain.com/api/v1/health/detailed
```

#### Prometheus Metrics

Key metrics to monitor:

```
# Request metrics
fraudnet_requests_total{method="POST",endpoint="/api/v1/transactions"}
fraudnet_request_duration_seconds_bucket

# Prediction metrics  
fraudnet_predictions_total{risk_level="high"}
fraudnet_prediction_duration_seconds

# System metrics
fraudnet_db_connections_active
fraudnet_model_accuracy
fraudnet_cache_hit_rate
```

#### Alerting Rules

```yaml
# prometheus-alerts.yml
groups:
- name: fraudnet
  rules:
  - alert: HighErrorRate
    expr: rate(fraudnet_requests_total{status=~"5.."}[5m]) > 0.1
    for: 5m
    labels:
      severity: critical
    annotations:
      summary: "High error rate detected"
      
  - alert: HighLatency
    expr: fraudnet_request_duration_seconds{quantile="0.95"} > 1
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "High request latency detected"
      
  - alert: ModelAccuracyDrop
    expr: fraudnet_model_accuracy < 0.9
    for: 10m
    labels:
      severity: critical
    annotations:
      summary: "Model accuracy below threshold"
```

### Database Maintenance

#### Backup Strategy

```bash
# Automated daily backup script
#!/bin/bash
BACKUP_DIR="/backups/fraudnet"
DATE=$(date +%Y%m%d_%H%M%S)
DB_HOST="your-db-host"
DB_NAME="fraudnet"
DB_USER="backup_user"

# Create backup
mysqldump -h $DB_HOST -u $DB_USER -p$DB_PASSWORD \
  --single-transaction \
  --routines \
  --triggers \
  $DB_NAME | gzip > $BACKUP_DIR/fraudnet_$DATE.sql.gz

# Keep backups for 30 days
find $BACKUP_DIR -name "fraudnet_*.sql.gz" -mtime +30 -delete

# Upload to S3 (optional)
aws s3 cp $BACKUP_DIR/fraudnet_$DATE.sql.gz s3://your-backup-bucket/database/
```

#### Database Optimization

```sql
-- Index maintenance
ANALYZE TABLE transactions, predictions, users;

-- Check for slow queries
SELECT * FROM mysql.slow_log 
WHERE start_time > DATE_SUB(NOW(), INTERVAL 1 DAY)
ORDER BY query_time DESC LIMIT 10;

-- Table optimization
OPTIMIZE TABLE transactions, predictions, users;
```

### Log Management

#### Log Rotation

```bash
# /etc/logrotate.d/fraudnet
/opt/fraudnet/app/logs/*.log {
    daily
    missingok
    rotate 30
    compress
    notifempty
    create 644 fraudnet fraudnet
    postrotate
        /bin/kill -USR1 `cat /run/fraudnet.pid 2> /dev/null` 2> /dev/null || true
    endscript
}
```

#### Centralized Logging

```yaml
# filebeat.yml
filebeat.inputs:
- type: log
  enabled: true
  paths:
    - /opt/fraudnet/app/logs/*.log
  fields:
    service: fraudnet
    environment: production
  fields_under_root: true
  
output.elasticsearch:
  hosts: ["elasticsearch:9200"]
  index: "fraudnet-%{+yyyy.MM.dd}"
```

### Security Maintenance

#### SSL Certificate Renewal

```bash
# Let's Encrypt renewal (automated)
# Add to crontab: 0 0 * * * /usr/bin/certbot renew --quiet --post-hook "systemctl reload nginx"

# Manual renewal
certbot renew --nginx -d your-domain.com

# Check certificate expiry
openssl x509 -enddate -noout -in /etc/ssl/certs/fraudnet.crt
```

#### Security Updates

```bash
# System updates
sudo apt update && sudo apt upgrade -y

# Container image updates
docker pull fraudnet/api:latest
docker-compose up -d app

# Dependency updates
pip freeze > current-requirements.txt
pip install --upgrade -r requirements.txt
pip freeze > new-requirements.txt
diff current-requirements.txt new-requirements.txt
```

### Performance Tuning

#### Application Tuning

```python
# gunicorn.conf.py
import multiprocessing

# Server socket
bind = "0.0.0.0:5000"
backlog = 2048

# Worker processes
workers = min(multiprocessing.cpu_count() * 2 + 1, 8)
worker_class = "sync"
worker_connections = 1000
timeout = 120
keepalive = 2

# Memory management  
max_requests = 1000
max_requests_jitter = 50
preload_app = True

# Logging
loglevel = "warning"
accesslog = "-"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'
```

#### Database Tuning

```ini
# MySQL configuration (/etc/mysql/my.cnf)
[mysqld]
# InnoDB settings
innodb_buffer_pool_size = 2G
innodb_log_file_size = 256M
innodb_flush_method = O_DIRECT
innodb_file_per_table = ON

# Query cache
query_cache_type = ON
query_cache_size = 64M

# Connection settings
max_connections = 200
thread_cache_size = 16
table_open_cache = 4096

# Logging
slow_query_log = ON
long_query_time = 2
```

## Troubleshooting

### Common Issues

#### Application Won't Start

```bash
# Check logs
docker-compose logs app
journalctl -u fraudnet -f

# Common causes:
# 1. Database connection failed
# 2. Missing environment variables
# 3. Port conflicts
# 4. Permission issues
```

#### Database Connection Issues

```bash
# Test database connectivity
mysql -h database-host -u fraudnet -p fraudnet

# Check connection pool
curl -H "X-API-Key: admin-key" http://localhost:5000/api/v1/health/detailed

# Common fixes:
# 1. Check firewall rules
# 2. Verify credentials
# 3. Check connection limits
```

#### High Memory Usage

```bash
# Check memory usage
docker stats
ps aux --sort=-%mem | head

# Optimize:
# 1. Reduce model cache TTL
# 2. Implement model compression
# 3. Tune garbage collection
# 4. Add more RAM or scale horizontally
```

#### Performance Issues

```bash
# Profile database queries
mysql> SET profiling = 1;
mysql> [your query]
mysql> SHOW PROFILES;

# Check application metrics
curl http://localhost:8000/metrics

# Common optimizations:
# 1. Add database indexes
# 2. Implement query caching
# 3. Optimize feature extraction
# 4. Use connection pooling
```

### Recovery Procedures

#### Database Recovery

```bash
# Point-in-time recovery
mysql -u root -p < backup_YYYYMMDD.sql

# Verify data integrity
python -c "
from app.models.database import AuditLog
logs = AuditLog.verify_integrity()
print(f'Verified {len(logs)} audit log entries')
"
```

#### Application Recovery

```bash
# Rolling restart (zero downtime)
docker-compose up -d --scale app=2  # Scale up
sleep 30                             # Wait for health checks
docker-compose up -d --scale app=1  # Scale down

# Full restart
docker-compose restart app
```

This deployment guide covers the essential aspects of deploying FraudNet.AI across various environments. Choose the deployment method that best fits your infrastructure requirements and operational capabilities.