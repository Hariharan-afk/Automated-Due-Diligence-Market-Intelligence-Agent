# Makefile for Combined Data Pipeline
# Convenient commands for managing the pipeline

.PHONY: help install setup start stop restart logs clean test init-db create-collections status

# Default target
help:
	@echo "=================================================================================="
	@echo "  Combined Data Pipeline - Available Commands"
	@echo "=================================================================================="
	@echo ""
	@echo "  Setup & Installation:"
	@echo "    make install          - Install Python dependencies"
	@echo "    make setup            - Complete initial setup (env + install + init)"
	@echo "    make init-db          - Initialize PostgreSQL database schema"
	@echo "    make create-collections - Create Qdrant vector collections"
	@echo ""
	@echo "  Docker Management:"
	@echo "    make start            - Start all Docker services"
	@echo "    make stop             - Stop all Docker services"
	@echo "    make restart          - Restart all services"
	@echo "    make logs             - View logs (all services)"
	@echo "    make logs-airflow     - View Airflow scheduler logs"
	@echo "    make status           - Check status of all services"
	@echo ""
	@echo "  Testing:"
	@echo "    make test             - Run all tests"
	@echo "    make test-unit        - Run unit tests only"
	@echo "    make test-integration - Run integration tests only"
	@echo ""
	@echo "  Data Pipeline:"
	@echo "    make trigger-sec      - Trigger SEC filings pipeline"
	@echo "    make trigger-wiki     - Trigger Wikipedia refresh pipeline"
	@echo "    make trigger-news     - Trigger news ingestion pipeline"
	@echo "    make trigger-cleanup  - Trigger data cleanup pipeline"
	@echo ""
	@echo "  Maintenance:"
	@echo "    make clean            - Clean cache and temporary files"
	@echo "    make backup           - Backup metadata database"
	@echo "    make rebuild-index    - Rebuild Qdrant vector index"
	@echo ""
	@echo "  Development:"
	@echo "    make shell            - Open Python shell with imports"
	@echo "    make airflow-shell    - Open Airflow container shell"
	@echo "=================================================================================="

# Installation
install:
	@echo "📦 Installing Python dependencies..."
	pip install -r requirements.txt
	pip install -r requirements-dev.txt
	@echo "✅ Dependencies installed"

# Complete setup
setup:
	@echo "🚀 Running complete setup..."
	@if [ ! -f .env ]; then \
		echo "📝 Creating .env from template..."; \
		cp .env.example .env; \
		echo "⚠️  Please edit .env with your API keys before continuing"; \
		exit 1; \
	fi
	@make install
	@make start
	@sleep 10
	@make init-db
	@make create-collections
	@echo "✅ Setup complete! Access Airflow at http://localhost:8080"

# Database initialization
init-db:
	@echo "🗄️  Initializing PostgreSQL database..."
	python scripts/setup/init_databases.py
	@echo "✅ Database initialized"

create-collections:
	@echo "📊 Creating Qdrant vector collections..."
	python scripts/setup/create_vector_collections.py
	@echo "✅ Collections created"

# Docker management
start:
	@echo "🚀 Starting Docker services..."
	docker-compose up -d
	@echo "✅ Services started"
	@make status

stop:
	@echo "🛑 Stopping Docker services..."
	docker-compose down
	@echo "✅ Services stopped"

restart:
	@echo "🔄 Restarting services..."
	@make stop
	@make start

logs:
	@echo "📋 Viewing logs (Ctrl+C to exit)..."
	docker-compose logs -f

logs-airflow:
	@echo "📋 Viewing Airflow scheduler logs..."
	docker-compose logs -f airflow-scheduler

status:
	@echo "📊 Service Status:"
	@echo "=================================================================================="
	@docker-compose ps
	@echo "=================================================================================="

# Testing
test:
	@echo "🧪 Running all tests..."
	pytest tests/ -v --tb=short

test-unit:
	@echo "🧪 Running unit tests..."
	pytest tests/unit/ -v

test-integration:
	@echo "🧪 Running integration tests..."
	pytest tests/integration/ -v

# Pipeline triggers
trigger-sec:
	@echo "🔄 Triggering SEC filings pipeline..."
	docker exec -it $$(docker-compose ps -q airflow-scheduler) \
		airflow dags trigger sec_filings_pipeline
	@echo "✅ SEC pipeline triggered"

trigger-wiki:
	@echo "🔄 Triggering Wikipedia refresh pipeline..."
	docker exec -it $$(docker-compose ps -q airflow-scheduler) \
		airflow dags trigger wikipedia_refresh_pipeline
	@echo "✅ Wikipedia pipeline triggered"

trigger-news:
	@echo "🔄 Triggering news ingestion pipeline..."
	docker exec -it $$(docker-compose ps -q airflow-scheduler) \
		airflow dags trigger news_ingestion_pipeline
	@echo "✅ News pipeline triggered"

trigger-cleanup:
	@echo "🔄 Triggering cleanup pipeline..."
	docker exec -it $$(docker-compose ps -q airflow-scheduler) \
		airflow dags trigger data_cleanup_pipeline
	@echo "✅ Cleanup pipeline triggered"

# Maintenance
clean:
	@echo "🧹 Cleaning cache and temporary files..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf data/cache/api_responses/* 2>/dev/null || true
	@echo "✅ Cleaned"

backup:
	@echo "💾 Backing up metadata database..."
	python scripts/maintenance/backup_metadata.py
	@echo "✅ Backup complete"

rebuild-index:
	@echo "🔨 Rebuilding Qdrant vector index..."
	python scripts/maintenance/rebuild_index.py
	@echo "✅ Index rebuilt"

# Development
shell:
	@echo "🐍 Opening Python shell..."
	python -i -c "import sys; from pathlib import Path; sys.path.insert(0, str(Path.cwd())); \
	from src.utils.config import config; \
	from src.data_ingestion.sec_fetcher import SECFetcher; \
	from src.data_processing.chunking_engine import ChunkingEngine; \
	print('Loaded: config, SECFetcher, ChunkingEngine')"

airflow-shell:
	@echo "🐚 Opening Airflow container shell..."
	docker exec -it $$(docker-compose ps -q airflow-scheduler) /bin/bash

# Quick validation
validate:
	@echo "✅ Running pipeline validation..."
	python scripts/validation/validate_pipeline.py
	python scripts/validation/check_data_quality.py

# View stats
stats:
	@echo "📊 Pipeline Statistics:"
	@echo "=================================================================================="
	@python -c "import sys; from pathlib import Path; sys.path.insert(0, str(Path.cwd())); \
	from src.storage.metadata_store_manager import MetadataStoreManager; \
	db = MetadataStoreManager(); \
	stats = db.get_pipeline_stats(); \
	print(f\"Companies: {stats.get('company_count', 0)}\"); \
	print(f\"SEC Filings: {stats.get('total_filings', 0)}\"); \
	print(f\"Total Chunks: {stats.get('total_chunks', 0)}\")"
	@echo "=================================================================================="
