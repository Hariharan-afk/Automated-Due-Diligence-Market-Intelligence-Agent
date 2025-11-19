#!/bin/bash
# Quick Start Script for Combined Data Pipeline
# This automates the setup process

set -e  # Exit on any error

echo "================================================================================"
echo "  🚀 Combined Data Pipeline - Quick Start"
echo "================================================================================"
echo ""

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Step 1: Check prerequisites
echo "📋 Step 1: Checking prerequisites..."
echo "------------------------------------------------------------"

if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker not found. Please install Docker Desktop.${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Docker installed${NC}"

if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}❌ Docker Compose not found. Please install Docker Compose.${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Docker Compose installed${NC}"

if ! command -v python3 &> /dev/null && ! command -v python &> /dev/null; then
    echo -e "${RED}❌ Python not found. Please install Python 3.9+${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Python installed${NC}"
echo ""

# Step 2: Create .env if it doesn't exist
echo "🔧 Step 2: Setting up environment..."
echo "------------------------------------------------------------"

if [ ! -f .env ]; then
    echo "Creating .env from template..."
    cp .env.example .env
    echo -e "${YELLOW}⚠️  IMPORTANT: Please edit .env and add your API keys:${NC}"
    echo "   1. GROQ_API_KEY (get from https://console.groq.com)"
    echo "   2. NEWSAPI_KEY (get from https://newsapi.org)"
    echo "   3. SEC_API_KEY (optional, get from https://sec-api.io)"
    echo ""
    echo "   Also generate Airflow keys:"
    echo "   - Fernet: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
    echo "   - Secret: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
    echo ""
    read -p "Press Enter after you've updated .env..."
else
    echo -e "${GREEN}✅ .env file already exists${NC}"
fi
echo ""

# Step 3: Start Docker services
echo "🐳 Step 3: Starting Docker services..."
echo "------------------------------------------------------------"

cd docker
echo "Starting PostgreSQL, Qdrant, and Airflow..."
docker-compose up -d

echo "Waiting for services to be ready (30 seconds)..."
sleep 30

# Check if services are running
if docker-compose ps | grep -q "Up"; then
    echo -e "${GREEN}✅ Docker services started${NC}"
else
    echo -e "${RED}❌ Some services failed to start. Check logs with: docker-compose logs${NC}"
    exit 1
fi

cd ..
echo ""

# Step 4: Install Python dependencies
echo "📦 Step 4: Installing Python dependencies..."
echo "------------------------------------------------------------"

if command -v python3 &> /dev/null; then
    PYTHON_CMD=python3
else
    PYTHON_CMD=python
fi

echo "Installing requirements..."
$PYTHON_CMD -m pip install -q -r requirements.txt
echo -e "${GREEN}✅ Dependencies installed${NC}"
echo ""

# Step 5: Initialize databases
echo "🗄️  Step 5: Initializing databases..."
echo "------------------------------------------------------------"

echo "Checking PostgreSQL readiness..."
sleep 5

echo "Creating database schema..."
$PYTHON_CMD scripts/setup/init_databases.py

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Database initialized${NC}"
else
    echo -e "${RED}❌ Database initialization failed${NC}"
    exit 1
fi
echo ""

# Step 6: Create Qdrant collections
echo "📊 Step 6: Creating Qdrant vector collections..."
echo "------------------------------------------------------------"

$PYTHON_CMD scripts/setup/create_vector_collections.py

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Qdrant collections created${NC}"
else
    echo -e "${RED}❌ Qdrant collection creation failed${NC}"
    exit 1
fi
echo ""

# Step 7: Verify setup
echo "✅ Step 7: Verifying setup..."
echo "------------------------------------------------------------"

echo "Checking database connection..."
$PYTHON_CMD -c "
import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
from src.storage.metadata_store_manager import MetadataStoreManager
db = MetadataStoreManager()
stats = db.get_pipeline_stats()
print(f'✅ Companies in database: {stats.get(\"company_count\", 0)}')
"

echo "Checking Qdrant connection..."
$PYTHON_CMD -c "
import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
from src.storage.vector_store_manager import VectorStoreManager
vs = VectorStoreManager()
print(f'✅ Qdrant is accessible')
"

echo ""

# Step 8: Success message
echo "================================================================================"
echo -e "${GREEN}  🎉 Setup Complete!${NC}"
echo "================================================================================"
echo ""
echo "Next steps:"
echo ""
echo "1. Access Airflow UI:"
echo "   URL: http://localhost:8080"
echo "   Username: admin"
echo "   Password: (check your .env file)"
echo ""
echo "2. Enable and trigger DAGs:"
echo "   - sec_filings_pipeline (NEW - for SEC 10-K/10-Q)"
echo "   - wikipedia_refresh_pipeline"
echo "   - news_ingestion_pipeline"
echo "   - data_cleanup_pipeline"
echo ""
echo "3. Monitor pipeline execution:"
echo "   - Click on DAG name → Graph view"
echo "   - Click on task → Log to see details"
echo ""
echo "4. Useful commands:"
echo "   - View logs: docker-compose -f docker/docker-compose.yml logs -f"
echo "   - Stop services: docker-compose -f docker/docker-compose.yml down"
echo "   - Restart: docker-compose -f docker/docker-compose.yml restart"
echo ""
echo "================================================================================"
echo ""
