#!/bin/bash

# Test runner script for FraudNet.AI

set -e

echo "🚀 Running FraudNet.AI Test Suite"
echo "=================================="

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔄 Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "📦 Installing dependencies..."
pip install -r requirements.txt

# Set environment variables for testing
export FLASK_ENV=testing
export DB_NAME=test_fraudnet_ai

# Run linting
echo "🔍 Running code quality checks..."
echo "  - Black (code formatting)"
black --check app/ tests/ || echo "❌ Black formatting issues found"

echo "  - Flake8 (style guide)"
flake8 app/ tests/ --max-line-length=100 --ignore=E203,W503 || echo "❌ Flake8 style issues found"

# Run type checking
echo "  - MyPy (type checking)"  
mypy app/ --ignore-missing-imports || echo "❌ MyPy type issues found"

# Run security checks
echo "🔒 Running security checks..."
# bandit -r app/ -f json || echo "❌ Security issues found"

# Run unit tests
echo "🧪 Running unit tests..."
pytest tests/unit/ -v --tb=short

# Run integration tests
echo "🔗 Running integration tests..."
pytest tests/integration/ -v --tb=short

# Run full test suite with coverage
echo "📊 Running full test suite with coverage..."
pytest tests/ --cov=app --cov-report=html:htmlcov --cov-report=term-missing --cov-fail-under=80

# Run performance tests if they exist
if [ -d "tests/performance" ]; then
    echo "⚡ Running performance tests..."
    pytest tests/performance/ -v --tb=short
fi

echo ""
echo "✅ Test suite completed successfully!"
echo "📈 Coverage report available at: htmlcov/index.html"