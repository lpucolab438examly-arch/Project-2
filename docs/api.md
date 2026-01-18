# FraudNet.AI API Reference

## Overview

The FraudNet.AI REST API provides comprehensive endpoints for fraud detection, transaction management, model training, and system monitoring. All endpoints follow RESTful conventions and return JSON responses.

## Base URL

```
Development: http://localhost:5000/api/v1
Production: https://your-domain.com/api/v1
```

## Authentication

All API endpoints (except health checks) require API key authentication via the `X-API-Key` header:

```http
X-API-Key: your-api-key-here
```

### API Key Permissions

API keys have different permission levels:

- **read**: Access to GET endpoints for transactions and models
- **write**: Access to POST/PUT endpoints for transactions
- **admin**: Full access including user management and system configuration
- **bulk**: Access to bulk processing endpoints

## Response Format

### Success Response

```json
{
  "status": "success",
  "data": { ... },
  "timestamp": "2024-01-15T10:30:00Z",
  "correlation_id": "abc-123-def"
}
```

### Error Response

```json
{
  "error": "error_type",
  "message": "Human readable error message",
  "details": { ... },
  "timestamp": "2024-01-15T10:30:00Z",
  "correlation_id": "abc-123-def"
}
```

### HTTP Status Codes

- `200` - Success
- `201` - Created
- `400` - Bad Request (validation error)
- `401` - Unauthorized (invalid API key)
- `403` - Forbidden (insufficient permissions)
- `404` - Not Found
- `429` - Rate Limit Exceeded
- `500` - Internal Server Error

## Rate Limiting

API endpoints are rate-limited per API key:

| Endpoint Category | Limit | Window |
|------------------|-------|--------|
| Transaction Creation | 50 requests | 1 minute |
| Transaction Reads | 100 requests | 1 minute |
| Bulk Processing | 10 requests | 1 minute |
| Model Training | 5 requests | 1 hour |
| Health Checks | 1000 requests | 1 minute |

Rate limit information is included in response headers:

```
X-RateLimit-Limit: 50
X-RateLimit-Remaining: 47
X-RateLimit-Reset: 1642248600
```

---

## Transactions API

### Create Transaction

Process a new transaction and return fraud prediction.

**Endpoint:** `POST /transactions`  
**Permissions:** `write`  
**Rate Limit:** 50/minute

**Request Body:**

```json
{
  "user_id": "string",           // Required: User identifier
  "amount": 150.50,              // Required: Transaction amount
  "merchant": "Amazon",          // Required: Merchant name
  "merchant_category": "online", // Required: Merchant category
  "location_country": "US",      // Optional: Country code
  "location_city": "New York",   // Optional: City name
  "payment_method": "credit_card", // Optional: Payment method
  "device_type": "web",          // Optional: Device type
  "metadata": {                  // Optional: Additional metadata
    "ip_address": "192.168.1.1",
    "session_id": "sess_123"
  }
}
```

**Response:**

```json
{
  "status": "success",
  "data": {
    "transaction_id": 12345,
    "user_id": "user_001",
    "amount": 150.50,
    "fraud_prediction": {
      "fraud_probability": 0.15,
      "risk_level": "low",
      "prediction_id": 67890,
      "model_version": "v1.2",
      "processing_time_ms": 89
    },
    "features_used": [
      "amount_zscore",
      "merchant_frequency",
      "time_since_last_transaction",
      "location_velocity"
    ],
    "created_at": "2024-01-15T10:30:00Z"
  }
}
```

### Get Transaction

Retrieve transaction details with fraud prediction.

**Endpoint:** `GET /transactions/{transaction_id}`  
**Permissions:** `read`  
**Rate Limit:** 100/minute

**Response:**

```json
{
  "status": "success",
  "data": {
    "transaction_id": 12345,
    "user_id": "user_001",
    "amount": 150.50,
    "merchant": "Amazon",
    "merchant_category": "online",
    "location_country": "US",
    "location_city": "New York",
    "payment_method": "credit_card",
    "device_type": "web",
    "transaction_date": "2024-01-15T10:30:00Z",
    "fraud_prediction": {
      "fraud_probability": 0.15,
      "risk_level": "low",
      "prediction_id": 67890,
      "model_version": "v1.2",
      "confidence_score": 0.92
    },
    "is_fraud": null,  // Actual fraud status (if known)
    "status": "processed"
  }
}
```

### Bulk Transaction Processing

Process multiple transactions in a single request.

**Endpoint:** `POST /transactions/bulk`  
**Permissions:** `write`, `bulk`  
**Rate Limit:** 10/minute

**Request Body:**

```json
{
  "transactions": [
    {
      "user_id": "user_001",
      "amount": 100.00,
      "merchant": "Store A",
      "merchant_category": "retail"
    },
    {
      "user_id": "user_002", 
      "amount": 250.00,
      "merchant": "Store B",
      "merchant_category": "grocery"
    }
  ]
}
```

**Response:**

```json
{
  "status": "success",
  "data": {
    "processed_count": 2,
    "success_count": 2,
    "error_count": 0,
    "results": [
      {
        "transaction_id": 12346,
        "fraud_probability": 0.08,
        "risk_level": "low",
        "processing_time_ms": 76
      },
      {
        "transaction_id": 12347,
        "fraud_probability": 0.32,
        "risk_level": "medium", 
        "processing_time_ms": 81
      }
    ],
    "errors": []
  }
}
```

### Rerun Fraud Prediction

Rerun fraud prediction for an existing transaction with latest model.

**Endpoint:** `POST /transactions/{transaction_id}/predict`  
**Permissions:** `write`  
**Rate Limit:** 50/minute

**Response:**

```json
{
  "status": "success",
  "data": {
    "transaction_id": 12345,
    "new_prediction": {
      "fraud_probability": 0.18,
      "risk_level": "low",
      "prediction_id": 67891,
      "model_version": "v1.3",
      "processing_time_ms": 72
    },
    "previous_prediction": {
      "fraud_probability": 0.15,
      "risk_level": "low", 
      "model_version": "v1.2"
    },
    "model_comparison": {
      "probability_change": 0.03,
      "risk_level_changed": false
    }
  }
}
```

---

## Models API

### Train New Model

Initiate training of a new fraud detection model.

**Endpoint:** `POST /models/train`  
**Permissions:** `admin`  
**Rate Limit:** 5/hour

**Request Body:**

```json
{
  "algorithm": "xgboost",       // Optional: Algorithm (default: randomforest)
  "hyperparameters": {          // Optional: Custom hyperparameters
    "n_estimators": 200,
    "max_depth": 8,
    "learning_rate": 0.1
  },
  "training_data_days": 30,     // Optional: Days of data to use (default: 30)
  "validation_split": 0.2       // Optional: Validation split (default: 0.2)
}
```

**Response:**

```json
{
  "status": "success", 
  "data": {
    "job_id": "train_job_123",
    "status": "started",
    "estimated_completion": "2024-01-15T11:00:00Z",
    "training_config": {
      "algorithm": "xgboost",
      "hyperparameters": { ... },
      "training_samples": 50000,
      "validation_samples": 12500
    }
  }
}
```

### Get Training Job Status

Check the status of a model training job.

**Endpoint:** `GET /models/train/{job_id}`  
**Permissions:** `admin`

**Response:**

```json
{
  "status": "success",
  "data": {
    "job_id": "train_job_123",
    "status": "completed",  // started, running, completed, failed
    "progress": 100,
    "started_at": "2024-01-15T10:30:00Z",
    "completed_at": "2024-01-15T10:55:00Z",
    "duration_seconds": 1500,
    "model_version": "v1.4",
    "metrics": {
      "training_accuracy": 0.956,
      "validation_accuracy": 0.942,
      "precision": 0.918,
      "recall": 0.897,
      "f1_score": 0.907,
      "auc_roc": 0.965
    },
    "artifact_paths": {
      "model_file": "/artifacts/models/v1.4/model.joblib",
      "feature_encoder": "/artifacts/preprocessing/v1.4/encoder.joblib",
      "metrics_report": "/artifacts/metrics/v1.4/report.json"
    }
  }
}
```

### List Models

Get list of all trained models with their metrics.

**Endpoint:** `GET /models`  
**Permissions:** `read`

**Query Parameters:**
- `active_only` (boolean): Return only active models
- `limit` (int): Maximum number of models to return
- `algorithm` (string): Filter by algorithm

**Response:**

```json
{
  "status": "success",
  "data": {
    "models": [
      {
        "model_name": "fraud_detector_v1",
        "version": "v1.3",
        "algorithm": "xgboost",
        "is_active": true,
        "created_at": "2024-01-10T15:30:00Z",
        "metrics": {
          "validation_accuracy": 0.942,
          "precision": 0.918,
          "recall": 0.897,
          "f1_score": 0.907
        }
      },
      {
        "model_name": "fraud_detector_v1", 
        "version": "v1.2",
        "algorithm": "randomforest",
        "is_active": false,
        "created_at": "2024-01-05T12:15:00Z",
        "metrics": {
          "validation_accuracy": 0.925,
          "precision": 0.901,
          "recall": 0.883,
          "f1_score": 0.892
        }
      }
    ],
    "total_count": 5,
    "active_model": "v1.3"
  }
}
```

### Get Model Metrics

Get detailed metrics for a specific model version.

**Endpoint:** `GET /models/{version}/metrics`  
**Permissions:** `read`

**Response:**

```json
{
  "status": "success",
  "data": {
    "model_version": "v1.3",
    "algorithm": "xgboost",
    "hyperparameters": {
      "n_estimators": 200,
      "max_depth": 8,
      "learning_rate": 0.1
    },
    "training_metrics": {
      "accuracy": 0.956,
      "precision": 0.925,
      "recall": 0.912,
      "f1_score": 0.918,
      "auc_roc": 0.981
    },
    "validation_metrics": {
      "accuracy": 0.942,
      "precision": 0.918,
      "recall": 0.897,
      "f1_score": 0.907,
      "auc_roc": 0.965
    },
    "confusion_matrix": {
      "true_positive": 1250,
      "true_negative": 11750,
      "false_positive": 125,
      "false_negative": 175
    },
    "feature_importance": [
      {
        "feature": "amount_zscore",
        "importance": 0.23
      },
      {
        "feature": "merchant_frequency",
        "importance": 0.18
      },
      {
        "feature": "time_velocity",
        "importance": 0.15
      }
    ],
    "training_info": {
      "training_samples": 50000,
      "validation_samples": 12500,
      "training_duration_seconds": 1500,
      "created_at": "2024-01-10T15:30:00Z"
    }
  }
}
```

### Activate Model

Set a specific model version as the active model for predictions.

**Endpoint:** `POST /models/{version}/activate`  
**Permissions:** `admin`

**Response:**

```json
{
  "status": "success",
  "data": {
    "model_version": "v1.3",
    "activated_at": "2024-01-15T10:45:00Z",
    "previous_active_model": "v1.2"
  }
}
```

---

## Users API

### Create User

Create a new user in the system.

**Endpoint:** `POST /users`  
**Permissions:** `write`

**Request Body:**

```json
{
  "user_id": "user_123",
  "email": "user@example.com",
  "phone": "+1234567890",
  "user_type": "premium",    // premium, basic, enterprise
  "metadata": {
    "signup_source": "web",
    "country": "US"
  }
}
```

**Response:**

```json
{
  "status": "success",
  "data": {
    "id": 456,
    "user_id": "user_123",
    "email": "user@example.com",
    "phone": "+1234567890", 
    "user_type": "premium",
    "registration_date": "2024-01-15T10:30:00Z",
    "status": "active",
    "transaction_count": 0
  }
}
```

### Get User

Retrieve user details and statistics.

**Endpoint:** `GET /users/{user_id}`  
**Permissions:** `read`

**Response:**

```json
{
  "status": "success",
  "data": {
    "id": 456,
    "user_id": "user_123",
    "email": "user@example.com",
    "phone": "+1234567890",
    "user_type": "premium",
    "registration_date": "2024-01-15T10:30:00Z",
    "status": "active",
    "statistics": {
      "total_transactions": 127,
      "total_amount": 15420.50,
      "avg_transaction_amount": 121.42,
      "fraud_incidents": 2,
      "fraud_rate": 0.016,
      "last_transaction_date": "2024-01-15T09:15:00Z"
    }
  }
}
```

### Update User

Update user information.

**Endpoint:** `PUT /users/{user_id}`  
**Permissions:** `write`

**Request Body:**

```json
{
  "email": "newemail@example.com",
  "phone": "+1987654321",
  "user_type": "enterprise"
}
```

---

## Health API

### Basic Health Check

Simple health check endpoint (no authentication required).

**Endpoint:** `GET /health`

**Response:**

```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00Z",
  "version": "1.0.0"
}
```

### Liveness Probe

Kubernetes liveness probe endpoint.

**Endpoint:** `GET /health/live`

**Response:**

```json
{
  "status": "alive",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### Readiness Probe

Kubernetes readiness probe endpoint.

**Endpoint:** `GET /health/ready`

**Response:**

```json
{
  "status": "ready",
  "timestamp": "2024-01-15T10:30:00Z",
  "dependencies": {
    "database": "healthy",
    "redis": "healthy",
    "model": "loaded"
  }
}
```

### Detailed Health Check

Comprehensive system health information.

**Endpoint:** `GET /health/detailed`  
**Permissions:** `admin`

**Response:**

```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00Z",
  "version": "1.0.0",
  "uptime_seconds": 86400,
  "system": {
    "cpu_usage": 25.5,
    "memory_usage": 67.2,
    "disk_usage": 45.8
  },
  "dependencies": {
    "database": {
      "status": "healthy",
      "connection_pool": {
        "active": 5,
        "idle": 15,
        "max": 20
      },
      "response_time_ms": 12
    },
    "redis": {
      "status": "healthy",
      "memory_usage": "15.2MB",
      "response_time_ms": 2
    },
    "model": {
      "status": "loaded",
      "version": "v1.3",
      "load_time": "2024-01-15T08:30:00Z",
      "prediction_count": 1523,
      "avg_prediction_time_ms": 89
    }
  },
  "cache": {
    "hit_rate": 0.85,
    "size_mb": 125.6,
    "evictions": 23
  }
}
```

---

## Error Codes

### Validation Errors (400)

| Error Code | Message | Description |
|------------|---------|-------------|
| `INVALID_JSON` | Invalid JSON payload | Request body is not valid JSON |
| `MISSING_FIELD` | Missing required field: {field} | Required field is missing |
| `INVALID_TYPE` | Invalid type for field: {field} | Field has wrong data type |
| `INVALID_RANGE` | Value out of range for field: {field} | Numeric value outside allowed range |
| `INVALID_FORMAT` | Invalid format for field: {field} | String field doesn't match expected format |

### Authentication Errors (401)

| Error Code | Message | Description |
|------------|---------|-------------|
| `MISSING_API_KEY` | API key is required | No API key provided in header |
| `INVALID_API_KEY` | Invalid or expired API key | API key is invalid or expired |
| `API_KEY_REVOKED` | API key has been revoked | API key was revoked |

### Authorization Errors (403)

| Error Code | Message | Description |
|------------|---------|-------------|
| `INSUFFICIENT_PERMISSIONS` | Insufficient permissions | API key lacks required permissions |
| `ACCESS_DENIED` | Access denied | General access denial |

### Rate Limit Errors (429)

| Error Code | Message | Description |
|------------|---------|-------------|
| `RATE_LIMIT_EXCEEDED` | Rate limit exceeded | Too many requests |

### System Errors (500)

| Error Code | Message | Description |
|------------|---------|-------------|
| `DATABASE_ERROR` | Database connection error | Database is unavailable |
| `MODEL_ERROR` | Model prediction error | ML model failed to make prediction |
| `INTERNAL_ERROR` | Internal server error | General server error |

---

## SDKs and Examples

### Python SDK Example

```python
import requests

class FraudNetClient:
    def __init__(self, base_url, api_key):
        self.base_url = base_url
        self.headers = {
            'X-API-Key': api_key,
            'Content-Type': 'application/json'
        }
    
    def create_transaction(self, transaction_data):
        response = requests.post(
            f"{self.base_url}/transactions",
            headers=self.headers,
            json=transaction_data
        )
        return response.json()
    
    def get_transaction(self, transaction_id):
        response = requests.get(
            f"{self.base_url}/transactions/{transaction_id}",
            headers=self.headers
        )
        return response.json()

# Usage
client = FraudNetClient('http://localhost:5000/api/v1', 'your-api-key')

result = client.create_transaction({
    'user_id': 'user_001',
    'amount': 150.50,
    'merchant': 'Amazon',
    'merchant_category': 'online'
})

print(f"Fraud probability: {result['data']['fraud_prediction']['fraud_probability']}")
```

### JavaScript/Node.js Example

```javascript
const axios = require('axios');

class FraudNetClient {
    constructor(baseUrl, apiKey) {
        this.baseUrl = baseUrl;
        this.headers = {
            'X-API-Key': apiKey,
            'Content-Type': 'application/json'
        };
    }
    
    async createTransaction(transactionData) {
        const response = await axios.post(
            `${this.baseUrl}/transactions`,
            transactionData,
            { headers: this.headers }
        );
        return response.data;
    }
    
    async getTransaction(transactionId) {
        const response = await axios.get(
            `${this.baseUrl}/transactions/${transactionId}`,
            { headers: this.headers }
        );
        return response.data;
    }
}

// Usage
const client = new FraudNetClient('http://localhost:5000/api/v1', 'your-api-key');

const result = await client.createTransaction({
    user_id: 'user_001',
    amount: 150.50,
    merchant: 'Amazon',
    merchant_category: 'online'
});

console.log(`Fraud probability: ${result.data.fraud_prediction.fraud_probability}`);
```

### cURL Examples

```bash
# Create transaction
curl -X POST http://localhost:5000/api/v1/transactions \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user_001",
    "amount": 150.50,
    "merchant": "Amazon",
    "merchant_category": "online"
  }'

# Get transaction
curl -X GET http://localhost:5000/api/v1/transactions/123 \
  -H "X-API-Key: your-api-key"

# Train model
curl -X POST http://localhost:5000/api/v1/models/train \
  -H "X-API-Key: your-admin-key" \
  -H "Content-Type: application/json" \
  -d '{
    "algorithm": "xgboost",
    "hyperparameters": {
      "n_estimators": 200,
      "max_depth": 8
    }
  }'

# Health check
curl -X GET http://localhost:5000/api/v1/health
```

---

## Postman Collection

A complete Postman collection is available at `docs/postman/FraudNet-AI.postman_collection.json` with:

- All API endpoints
- Example requests and responses
- Environment variables for easy testing
- Pre-request scripts for authentication
- Response validation tests

Import the collection and set the following environment variables:
- `base_url`: API base URL
- `api_key`: Your API key
- `admin_api_key`: Admin API key (for restricted endpoints)