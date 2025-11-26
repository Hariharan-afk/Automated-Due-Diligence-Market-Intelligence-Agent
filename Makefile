.PHONY: help build up down logs shell test validate clean

# Default target
.DEFAULT_GOAL := help

# Colors for output
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[0;33m
NC := \033[0m # No Color

help: ## Show this help message
	@echo '$(GREEN)Available commands:$(NC)'
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(BLUE)%-20s$(NC) %s\n", $$1, $$2}'

# ================================================
# Docker Commands
# ================================================

build: ## Build Docker images
	@echo '$(GREEN)Building Docker images...$(NC)'
	docker-compose build

up: ## Start all services
	@echo '$(GREEN)Starting services...$(NC)'
	docker-compose up -d
	@echo '$(GREEN)Services started! Check status with: make ps$(NC)'

down: ## Stop all services
	@echo '$(YELLOW)Stopping services...$(NC)'
	docker-compose down

restart: down up ## Restart all services

ps: ## Show running containers
	docker-compose ps

logs: ## Show logs (use: make logs SERVICE=agent-system)
	@if [ -z "$(SERVICE)" ]; then \
		docker-compose logs -f; \
	else \
		docker-compose logs -f $(SERVICE); \
	fi

shell: ## Open shell in agent-system container
	docker-compose exec agent-system /bin/bash

# ================================================
# Data & Testing Commands
# ================================================

generate-data: ## Generate fake test data
	@echo '$(GREEN)Generating test data...$(NC)'
	docker-compose --profile data up data-pipeline

validate: ## Run validation
	@echo '$(GREEN)Running validation...$(NC)'
	docker-compose exec agent-system python validation/run_validation.py

validate-quick: ## Run quick validation (3 tests)
	@echo '$(GREEN)Running quick validation...$(NC)'
	docker-compose exec agent-system python -c "from validation import ValidationPipeline; p = ValidationPipeline(); p.run_all_tests(limit=3); p.save_results()"

test: ## Run tests
	@echo '$(GREEN)Running tests...$(NC)'
	docker-compose exec agent-system pytest -v

test-coverage: ## Run tests with coverage
	@echo '$(GREEN)Running tests with coverage...$(NC)'
	docker-compose exec agent-system pytest --cov=agents --cov=tools --cov=validation --cov-report=html

# ================================================
# Development Commands
# ================================================

dev: ## Start in development mode with hot reload
	@echo '$(GREEN)Starting development environment...$(NC)'
	docker-compose up

qdrant-ui: ## Open Qdrant UI in browser
	@echo '$(GREEN)Opening Qdrant UI...$(NC)'
	@python -c "import webbrowser; webbrowser.open('http://localhost:6333/dashboard')"

# ================================================
# Production Commands
# ================================================

build-prod: ## Build production image
	@echo '$(GREEN)Building production image...$(NC)'
	docker-compose -f docker-compose.yml -f docker-compose.prod.yml build

up-prod: ## Start production services
	@echo '$(GREEN)Starting production services...$(NC)'
	docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

deploy-gcp: ## Deploy to GCP (builds and pushes image)
	@echo '$(GREEN)Deploying to GCP...$(NC)'
	./scripts/deploy.sh

# ================================================
# Maintenance Commands
# ================================================

clean: ## Clean up containers and volumes
	@echo '$(YELLOW)Cleaning up...$(NC)'
	docker-compose down -v
	docker system prune -f

clean-all: ## Clean everything including images
	@echo '$(YELLOW)Cleaning everything...$(NC)'
	docker-compose down -v --rmi all
	docker system prune -af

reset: clean build up ## Reset everything (clean, rebuild, start)

backup-qdrant: ## Backup Qdrant data
	@echo '$(GREEN)Backing up Qdrant data...$(NC)'
	docker-compose exec qdrant /bin/sh -c 'tar czf /tmp/qdrant-backup.tar.gz /qdrant/storage'
	docker cp $$(docker-compose ps -q qdrant):/tmp/qdrant-backup.tar.gz ./backups/qdrant-backup-$$(date +%Y%m%d_%H%M%S).tar.gz
	@echo '$(GREEN)Backup complete!$(NC)'

# ================================================
# Monitoring Commands
# ================================================

health: ## Check health of all services
	@echo '$(GREEN)Checking service health...$(NC)'
	@echo 'Qdrant:'
	@curl -s http://localhost:6333/healthz | jq . || echo 'Not responding'
	@echo ''
	@echo 'Agent System:'
	@docker-compose exec agent-system python -c "import sys; print('✅ OK'); sys.exit(0)" || echo '❌ Not OK'

stats: ## Show container resource usage
	docker stats $$(docker-compose ps -q)

# ================================================
# Setup Commands
# ================================================

setup: ## Initial setup (copy env, create directories)
	@echo '$(GREEN)Setting up environment...$(NC)'
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo '$(YELLOW)Created .env file. Please edit it with your configuration.$(NC)'; \
	else \
		echo '$(YELLOW).env file already exists$(NC)'; \
	fi
	@mkdir -p logs data backups validation/reports Model_Validation/reports
	@echo '$(GREEN)Setup complete!$(NC)'
	@echo '$(YELLOW)Next steps:$(NC)'
	@echo '  1. Edit .env with your GCP credentials'
	@echo '  2. Run: make build'
	@echo '  3. Run: make up'
	@echo '  4. Run: make generate-data'
	@echo '  5. Run: make validate'