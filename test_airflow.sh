#!/bin/bash
# Quick Airflow Testing Script for Linux/Mac
# This script automates the Airflow setup and testing process

echo "========================================"
echo " Airflow DAG Testing - Quick Start"
echo "========================================"
echo ""

# Set Airflow home directory
export AIRFLOW_HOME="$(pwd)/airflow_home"
echo "[1/7] Setting AIRFLOW_HOME to: $AIRFLOW_HOME"
echo ""

# Check if Airflow is installed
echo "[2/7] Checking Airflow installation..."
if ! python -c "import airflow" 2>/dev/null; then
    echo "Airflow not found. Installing..."
    pip install apache-airflow==2.8.0
    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to install Airflow"
        exit 1
    fi
fi
echo "Airflow is installed."
echo ""

# Initialize Airflow database (if not already done)
echo "[3/7] Checking Airflow database..."
if [ ! -f "$AIRFLOW_HOME/airflow.db" ]; then
    echo "Initializing Airflow database..."
    airflow db init
    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to initialize Airflow database"
        exit 1
    fi

    echo "Creating admin user..."
    airflow users create \
        --username admin \
        --firstname Admin \
        --lastname User \
        --role Admin \
        --email admin@example.com \
        --password admin
else
    echo "Airflow database already initialized."
fi
echo ""

# Configure DAG folder
echo "[4/7] Configuring DAG folder..."
if [ ! -d "$AIRFLOW_HOME/dags" ]; then
    ln -s "$(pwd)/dags" "$AIRFLOW_HOME/dags"
    if [ $? -ne 0 ]; then
        echo "WARNING: Failed to create symbolic link. Copying DAGs folder..."
        cp -r "$(pwd)/dags" "$AIRFLOW_HOME/dags"
    fi
fi
echo "DAG folder configured."
echo ""

# Set Airflow variable
echo "[5/7] Setting target_company variable..."
airflow variables set target_company "Apple Inc."
echo "Variable set to: Apple Inc."
echo ""

# Test DAG file
echo "[6/7] Testing DAG file for syntax errors..."
python dags/company_research_dag.py
if [ $? -ne 0 ]; then
    echo "ERROR: DAG file has syntax errors"
    exit 1
fi
echo "DAG file is valid."
echo ""

# Display instructions
echo "[7/7] Setup Complete!"
echo ""
echo "========================================"
echo " NEXT STEPS:"
echo "========================================"
echo ""
echo "1. Open TWO separate terminal windows"
echo ""
echo "2. In Terminal 1, run:"
echo "   cd $(pwd)"
echo "   export AIRFLOW_HOME=$AIRFLOW_HOME"
echo "   airflow webserver --port 8080"
echo ""
echo "3. In Terminal 2, run:"
echo "   cd $(pwd)"
echo "   export AIRFLOW_HOME=$AIRFLOW_HOME"
echo "   airflow scheduler"
echo ""
echo "4. Open browser: http://localhost:8080"
echo "   Username: admin"
echo "   Password: admin"
echo ""
echo "5. Find DAG: company_research_pipeline"
echo "   Click the Play button to trigger"
echo ""
echo "6. View Gantt chart: Click DAG name, then 'Gantt' tab"
echo ""
echo "========================================"
echo " USEFUL COMMANDS:"
echo "========================================"
echo ""
echo "List DAGs:"
echo "  airflow dags list"
echo ""
echo "Trigger DAG:"
echo "  airflow dags trigger company_research_pipeline"
echo ""
echo "Test single task:"
echo "  airflow tasks test company_research_pipeline initialize_database 2025-10-27"
echo ""
echo "Check import errors:"
echo "  airflow dags list-import-errors"
echo ""
echo "========================================"
echo ""
