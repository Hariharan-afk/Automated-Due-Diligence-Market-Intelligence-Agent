@echo off
REM Quick Start Script for Combined Data Pipeline (Windows)
REM This automates the setup process

echo ================================================================================
echo   🚀 Combined Data Pipeline - Quick Start (Windows)
echo ================================================================================
echo.

REM Step 1: Check prerequisites
echo 📋 Step 1: Checking prerequisites...
echo ------------------------------------------------------------

where docker >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ❌ Docker not found. Please install Docker Desktop.
    exit /b 1
)
echo ✅ Docker installed

where docker-compose >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ❌ Docker Compose not found. Please install Docker Desktop.
    exit /b 1
)
echo ✅ Docker Compose installed

where python >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ❌ Python not found. Please install Python 3.9+
    exit /b 1
)
echo ✅ Python installed
echo.

REM Step 2: Create .env if it doesn't exist
echo 🔧 Step 2: Setting up environment...
echo ------------------------------------------------------------

if not exist .env (
    echo Creating .env from template...
    copy .env.example .env
    echo.
    echo ⚠️  IMPORTANT: Please edit .env and add your API keys:
    echo    1. GROQ_API_KEY ^(get from https://console.groq.com^)
    echo    2. NEWSAPI_KEY ^(get from https://newsapi.org^)
    echo    3. SEC_API_KEY ^(optional, get from https://sec-api.io^)
    echo.
    echo    Also generate Airflow keys:
    echo    - Fernet: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    echo    - Secret: python -c "import secrets; print(secrets.token_urlsafe(32))"
    echo.
    pause
) else (
    echo ✅ .env file already exists
)
echo.

REM Step 3: Start Docker services
echo 🐳 Step 3: Starting Docker services...
echo ------------------------------------------------------------

cd docker
echo Starting PostgreSQL, Qdrant, and Airflow...
docker-compose up -d

echo Waiting for services to be ready (30 seconds)...
timeout /t 30 /nobreak >nul

docker-compose ps | find "Up" >nul
if %ERRORLEVEL% EQU 0 (
    echo ✅ Docker services started
) else (
    echo ❌ Some services failed to start. Check logs with: docker-compose logs
    exit /b 1
)

cd ..
echo.

REM Step 4: Install Python dependencies
echo 📦 Step 4: Installing Python dependencies...
echo ------------------------------------------------------------

echo Installing requirements...
python -m pip install -q -r requirements.txt
echo ✅ Dependencies installed
echo.

REM Step 5: Initialize databases
echo 🗄️  Step 5: Initializing databases...
echo ------------------------------------------------------------

echo Checking PostgreSQL readiness...
timeout /t 5 /nobreak >nul

echo Creating database schema...
python scripts\setup\init_databases.py

if %ERRORLEVEL% EQU 0 (
    echo ✅ Database initialized
) else (
    echo ❌ Database initialization failed
    exit /b 1
)
echo.

REM Step 6: Create Qdrant collections
echo 📊 Step 6: Creating Qdrant vector collections...
echo ------------------------------------------------------------

python scripts\setup\create_vector_collections.py

if %ERRORLEVEL% EQU 0 (
    echo ✅ Qdrant collections created
) else (
    echo ❌ Qdrant collection creation failed
    exit /b 1
)
echo.

REM Step 7: Verify setup
echo ✅ Step 7: Verifying setup...
echo ------------------------------------------------------------

echo Checking database connection...
python -c "import sys; from pathlib import Path; sys.path.insert(0, str(Path.cwd())); from src.storage.metadata_store_manager import MetadataStoreManager; db = MetadataStoreManager(); stats = db.get_pipeline_stats(); print(f'✅ Companies in database: {stats.get(\"company_count\", 0)}')"

echo Checking Qdrant connection...
python -c "import sys; from pathlib import Path; sys.path.insert(0, str(Path.cwd())); from src.storage.vector_store_manager import VectorStoreManager; vs = VectorStoreManager(); print('✅ Qdrant is accessible')"

echo.

REM Step 8: Success message
echo ================================================================================
echo   🎉 Setup Complete!
echo ================================================================================
echo.
echo Next steps:
echo.
echo 1. Access Airflow UI:
echo    URL: http://localhost:8080
echo    Username: admin
echo    Password: (check your .env file)
echo.
echo 2. Enable and trigger DAGs:
echo    - sec_filings_pipeline (NEW - for SEC 10-K/10-Q)
echo    - wikipedia_refresh_pipeline
echo    - news_ingestion_pipeline
echo    - data_cleanup_pipeline
echo.
echo 3. Monitor pipeline execution:
echo    - Click on DAG name → Graph view
echo    - Click on task → Log to see details
echo.
echo 4. Useful commands:
echo    - View logs: docker-compose -f docker\docker-compose.yml logs -f
echo    - Stop services: docker-compose -f docker\docker-compose.yml down
echo    - Restart: docker-compose -f docker\docker-compose.yml restart
echo.
echo ================================================================================
echo.

pause
