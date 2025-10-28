# 🏢 Automated Due Diligence & Market Intelligence Agent

**MLOps Course Project - Production-Ready Data Pipeline**

A comprehensive, cross-platform data pipeline that automates company research by fetching data from Wikipedia, news sources, and SEC filings, with complete data validation, bias detection, and quality assurance.

---

## 📁 Project Structure

```
data_pipeline_main/
├── .env.example                  # Environment variables template
├── .gitignore                    # Git ignore rules
├── README.md                     # This file
├── requirements.txt              # Production dependencies
├── dvc.yaml                      # DVC pipeline definition
├── params.yaml                   # DVC parameters
│
├── config/                       # Configuration files
│   └── config.yaml              # Main application configuration
│
├── dags/                         # Airflow DAG definitions
│   └── company_research_dag.py  # Main pipeline DAG
│
├── src/                          # Source code (modular, reusable)
│   ├── __init__.py
│   ├── data_acquisition.py      # Data fetching from APIs
│   ├── data_preprocessing.py    # Data cleaning & transformation
│   ├── schema_validator.py      # Schema validation & quality checks
│   ├── bias_detector.py         # Bias detection & fairness analysis
│   ├── db_manager.py            # Database operations
│   ├── sec_fetcher.py           # SEC filing fetcher
│   ├── vector_store.py          # Vector embeddings storage
│   ├── chunking.py              # Text chunking for RAG
│   ├── alert_manager.py         # Alert/notification system
│   └── utils/                   # Utility modules
│       ├── __init__.py
│       ├── config.py            # Configuration management
│       ├── logger.py            # Centralized logging
│       └── path_resolver.py     # Cross-platform path resolution
│
├── scripts/                      # Standalone scripts
│   ├── run_pipeline.py          # Manual pipeline execution
│   └── convert_ticker_format.py # Utility scripts
│
├── tests/                        # Unit tests (pytest)
│   ├── __init__.py
│   ├── test_data_acquisition.py
│   ├── test_data_preprocessing.py
│   ├── test_sec_fetcher.py
│   └── test_bias_detector.py
│
├── data/                         # Data directory (DVC tracked)
│   ├── raw/                     # Raw data from APIs
│   ├── processed/               # Preprocessed data
│   ├── quality_reports/         # Data quality reports
│   ├── bias_reports/            # Bias analysis reports
│   ├── metrics/                 # Pipeline metrics
│   └── company_tickers.json     # Static reference data
│
├── logs/                         # Application logs (gitignored)
│   ├── airflow/                 # Airflow logs
│   └── *.log                    # Component logs
│
├── docs/                         # Documentation
│   ├── AIRFLOW_SETUP.md         # Airflow setup guide
│   ├── TESTING_GUIDE.md         # Testing guide
│   └── REQUIREMENTS_CHECKLIST.md # Project requirements
│
└── docker/                       # Docker configuration
    ├── Dockerfile.airflow       # Airflow Docker image
    └── docker-compose.yml       # Docker Compose configuration
```

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Git
- Docker & Docker Compose (for Airflow)

### 1. Clone the Repository

```bash
git clone <repository-url>
cd data_pipeline_main
```

### 2. Set Up Environment

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure Environment Variables

```bash
# Copy the example environment file
cp .env.example .env

# Edit .env and add your API keys
# Required:
NEWS_API_KEY=your_newsapi_key_here
SEC_API_KEY=your_sec_api_key_here
```

### 4. Run the Pipeline

#### Option A: Manual Execution (Local)

```bash
python scripts/run_pipeline.py
```

#### Option B: Airflow (Docker)

```bash
# Navigate to docker directory
cd docker

# Start Airflow
docker-compose up -d

# Access Airflow UI: http://localhost:8080
# Username: admin
# Password: admin
```

---

## 🔑 Environment Variables

Create a `.env` file from `.env.example` and configure:

| Variable | Description | Required |
|----------|-------------|----------|
| `NEWS_API_KEY` | NewsAPI.org API key | Yes |
| `SEC_API_KEY` | SEC-API.io API key | Yes |
| `POLYGON_API_KEY` | Polygon.io API key | Optional |
| `PROJECT_ROOT` | Project root directory | No (auto-detected) |
| `DATA_DIR` | Data storage directory | No (default: ./data) |
| `LOGS_DIR` | Logs directory | No (default: ./logs) |
| `DB_PATH` | Database file path | No (default: data/company_data.db) |

---

## 🏗️ Architecture

### Pipeline Flow

```
┌─────────────────┐
│ 1. Initialize DB│
└────────┬────────┘
         │
┌────────▼────────────┐
│ 2. Acquire Data     │
│  - Wikipedia        │
│  - News (API+GDELT) │
│  - SEC Filings      │
└────────┬────────────┘
         │
┌────────▼───────────┐
│ 3. Preprocess Data │
│  - Clean           │
│  - Normalize       │
│  - Transform       │
└────────┬───────────┘
         │
    ┌────▼────┐
    │         │
┌───▼──┐  ┌──▼───┐
│Validate│ │Detect│
│Schema  │ │Bias  │
└───┬────┘ └──┬───┘
    │         │
┌───▼─────────▼───┐
│ 4. Store to DB  │
└────────┬─────────┘
         │
┌────────▼────────┐
│ 5. Generate     │
│    Statistics   │
└────────┬────────┘
         │
┌────────▼────────┐
│ 6. Check &      │
│    Alert        │
└─────────────────┘
```

### Key Features

- **Cross-Platform**: Works on Windows, Linux, and Docker
- **Path Resolution**: Automatic path handling via `PathResolver`
- **Error Handling**: Comprehensive exception handling with logging
- **Data Quality**: Automated schema validation and quality scoring
- **Bias Detection**: Fairness analysis across data sources
- **Monitoring**: Real-time metrics and alerts
- **Reproducibility**: DVC integration for data versioning

---

## 📊 Pipeline Components

### 1. Data Acquisition (`src/data_acquisition.py`)

Fetches company data from multiple sources:

- **Wikipedia**: Company profiles and information
- **NewsAPI**: Recent news articles (up to 20)
- **GDELT**: Additional news sources
- **SEC EDGAR**: 10-K and 10-Q filings

**Features**:
- Ticker matching (company name → ticker symbol)
- Rate limiting and retry logic
- Caching for API efficiency
- UTF-8 encoding for cross-platform compatibility

### 2. Data Preprocessing (`src/data_preprocessing.py`)

Cleans and transforms raw data:

- HTML removal
- Date normalization
- Duplicate removal
- Content validation

### 3. Schema Validation (`src/schema_validator.py`)

Validates data quality:

- Schema compliance checking
- Data completeness scoring
- Anomaly detection
- Quality metrics generation

### 4. Bias Detection (`src/bias_detector.py`)

Analyzes data for bias:

- Source diversity checks
- Recency bias detection
- Geographic bias analysis
- Fairness scoring

---

## 🧪 Testing

Run tests with pytest:

```bash
# Run all tests
pytest tests/

# Run specific test file
pytest tests/test_data_acquisition.py

# Run with coverage
pytest --cov=src tests/
```

---

## 📈 Monitoring & Metrics

### Airflow UI

Access http://localhost:8080 to:
- Monitor DAG runs
- View Gantt charts
- Check task logs
- Manage variables

### Quality Metrics

Pipeline generates metrics in `data/metrics/`:
- `pipeline_statistics.json`: Overall pipeline stats
- `acquisition_metrics.json`: Data acquisition metrics
- `quality_metrics.json`: Data quality scores
- `bias_metrics.json`: Bias analysis results

---

## 🐛 Troubleshooting

### Common Issues

#### 1. Import Errors

**Problem**: `ModuleNotFoundError: No module named 'src'`

**Solution**:
```bash
# Ensure PROJECT_ROOT is set
export PROJECT_ROOT=$(pwd)  # Linux/Mac
set PROJECT_ROOT=%cd%       # Windows
```

#### 2. Path Not Found Errors

**Problem**: `FileNotFoundError: [Errno 2] No such file or directory: 'data/company_data.db'`

**Solution**: The pipeline uses `PathResolver` which auto-detects paths. Ensure:
- You're running from the project root
- Or set `PROJECT_ROOT` environment variable

#### 3. Database Locked

**Problem**: `sqlite3.OperationalError: database is locked`

**Solution**: The pipeline uses context managers with timeout. If persists:
```bash
# Check for zombie processes
ps aux | grep python
# Kill if necessary
kill <PID>
```

#### 4. Docker Build Fails

**Problem**: Docker build fails with "context" error

**Solution**:
```bash
# Ensure you're in the docker directory
cd docker
docker-compose build --no-cache
```

---

## 📚 Additional Documentation

- [AIRFLOW_SETUP.md](docs/AIRFLOW_SETUP.md) - Complete Airflow setup guide
- [TESTING_GUIDE.md](docs/TESTING_GUIDE.md) - Testing best practices
- [REQUIREMENTS_CHECKLIST.md](docs/REQUIREMENTS_CHECKLIST.md) - MLOps requirements

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📝 License

This project is part of an MLOps course assignment.

---

## 🙏 Acknowledgments

- Apache Airflow for workflow orchestration
- DVC for data version control
- NewsAPI and SEC-API for data sources
