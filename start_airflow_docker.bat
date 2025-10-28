@echo off
echo ========================================
echo  Starting Airflow with Docker
echo ========================================
echo.

echo [1] Checking Docker Desktop...
docker --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Docker is not running
    echo Please start Docker Desktop and try again
    pause
    exit /b 1
)
echo Docker is running.
echo.

echo [2] Starting Airflow services...
echo This may take 2-3 minutes on first run (downloading images)
echo.

docker-compose up -d

if %errorlevel% neq 0 (
    echo ERROR: Failed to start services
    pause
    exit /b 1
)

echo.
echo ========================================
echo  Airflow Started Successfully!
echo ========================================
echo.
echo Services running:
docker-compose ps
echo.
echo ========================================
echo  ACCESS AIRFLOW WEB UI
echo ========================================
echo.
echo URL: http://localhost:8080
echo Username: admin
echo Password: admin
echo.
echo Wait 30-60 seconds for services to fully start
echo.
echo ========================================
echo  USEFUL COMMANDS
echo ========================================
echo.
echo View logs:
echo   docker-compose logs -f
echo.
echo Stop Airflow:
echo   docker-compose down
echo.
echo Restart Airflow:
echo   docker-compose restart
echo.
echo ========================================
echo.
echo Opening browser in 10 seconds...
timeout /t 10 /nobreak >nul
start http://localhost:8080
echo.
pause
