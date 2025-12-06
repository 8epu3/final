#!/bin/bash

# Script to run tests locally matching GitHub Actions workflow
# Ensure Docker is installed and running

set -e # Exit on error

# Define cleanup function
cleanup() {
    echo "Cleaning up..."
    if [ -n "$VIRTUAL_ENV" ]; then
        deactivate || true
    fi
    docker stop test-postgres >/dev/null 2>&1 || true
    docker rm test-postgres >/dev/null 2>&1 || true
    echo "Cleanup completed!"
}

# Trap errors and exit to run cleanup
trap cleanup ERR EXIT

# Step 0: Pre-cleanup to handle existing container
cleanup

# Step 1: Start PostgreSQL Docker container
echo "Starting PostgreSQL test database..."
docker run -d --name test-postgres \
    -e POSTGRES_USER=user \
    -e POSTGRES_PASSWORD=password \
    -e POSTGRES_DB=mytestdb \
    -p 5432:5432 \
    postgres:latest

# Wait for DB to be ready (health check similar to workflow)
echo "Waiting for database to be ready..."
for i in {1..30}; do
    if docker exec test-postgres pg_isready -U user -d mytestdb >/dev/null 2>&1; then
        echo "Database ready!"
        break
    fi
    sleep 1
done
if [ "$i" == 30 ]; then
    echo "Database failed to start in time."
    exit 1
fi

# Step 2: Set up Python environment
export DATABASE_URL=postgresql://user:password@localhost:5432/mytestdb
python -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt # Now includes redis instead of aioredis
pip install setuptools          # For distutils compatibility
playwright install

# Step 3: Run the tests
# Unit tests
pytest tests/unit/ --cov=app --junitxml=test-results/junit.xml

# Integration tests
pytest tests/integration/

# E2E tests
pytest tests/e2e/

# Optional: Full coverage report
# pytest --cov=app tests/ --cov-report=term-missing

echo "Tests completed!"
