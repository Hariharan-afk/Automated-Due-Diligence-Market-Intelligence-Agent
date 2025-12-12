# Automated Due Diligence Market Intelligence Agent - Data Pipeline

> **MLOps Course Project**: Production-grade data pipeline for ingesting, processing, and storing financial data to power an AI-driven due diligence and market intelligence system.

## Table of Contents
- [Project Overview](#project-overview)
- [System Architecture](#system-architecture)
- [Data Flow](#data-flow)
- [Key Features](#key-features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Setup Instructions](#setup-instructions)
- [Configuration](#configuration)
- [Usage](#usage)
- [Data Sources](#data-sources)
- [Pipeline Components](#pipeline-components)
- [Airflow DAGs](#airflow-dags)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)

---

## Project Overview

This data pipeline is part of a larger **Automated Due Diligence Market Intelligence Agent** system. Its primary purpose is to:

1. **Ingest** financial data from multiple sources (SEC filings, Wikipedia, news articles)
2. **Process** documents including table extraction, chunking, and summarization
3. **Generate** vector embeddings optimized for financial domain
4. **Store** data in vector and relational databases
5. **Ensure** fair coverage across companies through bias mitigation
6. **Validate** data quality at each stage

The processed data populates a **Qdrant vector database** and **PostgreSQL database**, which are then accessed by a **RAG (Retrieval-Augmented Generation) system** to generate comprehensive due diligence reports.

### Tracked Companies (12 Total)
Apple (AAPL), Microsoft (MSFT), Alphabet (GOOGL), Amazon (AMZN), Tesla (TSLA), NVIDIA (NVDA), Meta (META), JPMorgan (JPM), Oracle (ORCL), IBM, Toyota (TM), Citigroup (C)

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        DATA PIPELINE SYSTEM                          │
└─────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│                          DATA SOURCES                                 │
├──────────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐             │
│  │ SEC Filings │    │  Wikipedia  │    │ News APIs   │             │
│  │ (EdgarTools)│    │    Pages    │    │ (NewsAPI +  │             │
│  │             │    │             │    │   GDELT)    │             │
│  └─────────────┘    └─────────────┘    └─────────────┘             │
└──────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌──────────────────────────────────────────────────────────────────────┐
│                      INGESTION LAYER (src/data_ingestion)            │
├──────────────────────────────────────────────────────────────────────┤
│  • Rate limiting & retry logic                                       │
│  • Exponential backoff                                               │
│  • Multi-source fetching with fuzzy matching                         │
└──────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    PROCESSING LAYER (src/data_processing)            │
├──────────────────────────────────────────────────────────────────────┤
│  ┌────────────┐   ┌────────────┐   ┌────────────┐                  │
│  │  Parsers   │──▶│   Table    │──▶│  Chunker   │                  │
│  │ (HTML→MD)  │   │  Detector  │   │ (800 token)│                  │
│  └────────────┘   └────────────┘   └────────────┘                  │
│                           │                                           │
│                           ▼                                           │
│                  ┌────────────────┐                                  │
│                  │ Table Summary  │                                  │
│                  │  (Groq LLM)    │                                  │
│                  └────────────────┘                                  │
└──────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌──────────────────────────────────────────────────────────────────────┐
│                     EMBEDDING LAYER (src/embedding)                  │
├──────────────────────────────────────────────────────────────────────┤
│  • BGE-large-en-v1.5 / FinE5 embeddings                              │
│  • 1024-dimensional vectors                                          │
│  • Finance-domain optimized                                          │
└──────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    STORAGE LAYER (src/cloud)                         │
├──────────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │    Qdrant    │  │  PostgreSQL  │  │     GCS      │              │
│  │   (Vectors)  │  │  (Metadata)  │  │ (Raw Backup) │              │
│  └──────────────┘  └──────────────┘  └──────────────┘              │
└──────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌──────────────────────────────────────────────────────────────────────┐
│                  QUALITY ASSURANCE LAYER                             │
├──────────────────────────────────────────────────────────────────────┤
│  ┌────────────────┐           ┌────────────────┐                    │
│  │  Validation    │           │ Bias Mitigation│                    │
│  │ (src/validation)│           │   (src/bias)   │                    │
│  │ • Completeness │           │ • Coverage     │                    │
│  │ • Schema check │           │ • Fairness     │                    │
│  │ • Quality      │           │ • Boost factors│                    │
│  └────────────────┘           └────────────────┘                    │
└──────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌──────────────────────────────────────────────────────────────────────┐
│              ORCHESTRATION LAYER (Apache Airflow)                    │
├──────────────────────────────────────────────────────────────────────┤
│  • Initial Load DAG                                                  │
│  • Daily SEC Monitoring                                              │
│  • Weekly Wikipedia Updates                                          │
│  • 2x Daily News Fetching                                            │
└──────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
                    ┌────────────────────────┐
                    │   RAG SYSTEM (Client)  │
                    │  Due Diligence Reports │
                    └────────────────────────┘
```

---

## Data Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                         DETAILED DATA FLOW                           │
└─────────────────────────────────────────────────────────────────────┘

STAGE 1: DATA INGESTION
┌──────────────────────────────────────┐
│ For each company (12 total):        │
│                                      │
│ SEC Fetcher                          │
│  ├─ Fetch 10-K/10-Q filings         │
│  ├─ Date range: 2023+               │
│  └─ No API key needed (EdgarTools)  │
│                                      │
│ Wikipedia Fetcher                    │
│  ├─ Fetch company page              │
│  └─ Track revision ID               │
│                                      │
│ News Fetcher                         │
│  ├─ NewsAPI + GDELT                 │
│  ├─ Fuzzy matching for relevance    │
│  └─ Rate limiting: 100 req/day      │
└──────────────────────────────────────┘
            │
            ▼
STAGE 2: PARSING & EXTRACTION
┌──────────────────────────────────────┐
│ Raw HTML/Text → Structured Data     │
│                                      │
│ ├─ Parse HTML to Markdown           │
│ ├─ Extract metadata (date, type)    │
│ ├─ Clean and normalize text         │
│ └─ Detect document structure        │
└──────────────────────────────────────┘
            │
            ▼
STAGE 3: TABLE PROCESSING
┌──────────────────────────────────────┐
│ Financial Table Detection            │
│                                      │
│ ├─ Identify tables in documents     │
│ ├─ Extract table content            │
│ ├─ LLM Summarization (Groq)         │
│ │   └─ Model: llama-3.1-8b-instant  │
│ └─ Store table references           │
└──────────────────────────────────────┘
            │
            ▼
STAGE 4: CHUNKING
┌──────────────────────────────────────┐
│ Text Splitting (LangChain)           │
│                                      │
│ ├─ RecursiveCharacterTextSplitter   │
│ ├─ Chunk size: 800 tokens           │
│ ├─ Overlap: 100 tokens              │
│ ├─ Token counter: tiktoken          │
│ └─ Preserve semantic boundaries     │
└──────────────────────────────────────┘
            │
            ▼
STAGE 5: EMBEDDING GENERATION
┌──────────────────────────────────────┐
│ Vector Embeddings                    │
│                                      │
│ ├─ Model: BGE-large-en-v1.5 or FinE5│
│ ├─ Dimensions: 1024                 │
│ ├─ Domain: Finance-optimized        │
│ └─ Batch processing for efficiency  │
└──────────────────────────────────────┘
            │
            ▼
STAGE 6: STORAGE
┌──────────────────────────────────────┐
│ Multi-Storage Strategy               │
│                                      │
│ Qdrant Cloud                         │
│  ├─ Vector embeddings                │
│  ├─ Metadata (company, source, date)│
│  └─ Semantic search index            │
│                                      │
│ PostgreSQL (Supabase)                │
│  ├─ Pipeline state tracking         │
│  ├─ Processed file records          │
│  └─ Coverage metrics                 │
│                                      │
│ Google Cloud Storage                 │
│  ├─ Raw data backup                 │
│  └─ Processed JSON outputs          │
└──────────────────────────────────────┘
            │
            ▼
STAGE 7: VALIDATION & BIAS MITIGATION
┌──────────────────────────────────────┐
│ Quality Assurance                    │
│                                      │
│ Data Validation                      │
│  ├─ Completeness check              │
│  ├─ Schema compliance               │
│  ├─ Token size validation           │
│  └─ Content quality                 │
│                                      │
│ Bias Mitigation                      │
│  ├─ Calculate coverage per company  │
│  ├─ Identify underrepresented firms │
│  ├─ Apply boost factors             │
│  └─ Generate fairness report        │
└──────────────────────────────────────┘
            │
            ▼
┌──────────────────────────────────────┐
│    READY FOR RAG CONSUMPTION         │
│                                      │
│ Downstream system can query:        │
│  ├─ Semantic search via Qdrant      │
│  ├─ Metadata filtering via Postgres │
│  └─ Fair retrieval across companies │
└──────────────────────────────────────┘
```

---

## Key Features

### MLOps Best Practices
- **Orchestration**: Apache Airflow for workflow management and scheduling
- **State Management**: PostgreSQL-based pipeline state tracking for incremental updates
- **Data Validation**: Comprehensive quality checks at each pipeline stage
- **Bias Mitigation**: Fairness monitoring and coverage balancing across companies
- **Containerization**: Docker Compose for reproducible local development
- **Logging**: Structured logging for debugging and monitoring
- **Configuration Management**: YAML-based configs with environment variable support

### Data Engineering
- **Multi-Source Ingestion**: SEC filings, Wikipedia, news (3 sources × 12 companies)
- **Intelligent Processing**: Table detection, LLM-based summarization, token-aware chunking
- **Vector Embeddings**: Finance-domain optimized embeddings (BGE-large-en-v1.5/FinE5)
- **Scalable Storage**: Qdrant (vectors) + PostgreSQL (metadata) + GCS (raw data)
- **Incremental Updates**: State tracking prevents redundant processing

### Production-Ready
- **Error Handling**: Retry logic with exponential backoff
- **Rate Limiting**: API request throttling to respect rate limits
- **Modular Design**: Clear separation of concerns across modules
- **Testing Suite**: End-to-end and component-level test scripts

---

## Tech Stack

| Category | Technology | Purpose |
|----------|-----------|---------|
| **Language** | Python 3.11 | Core implementation |
| **Orchestration** | Apache Airflow 2.8+ | Workflow scheduling and monitoring |
| **Vector DB** | Qdrant Cloud | Semantic search and embeddings storage |
| **SQL DB** | PostgreSQL (Supabase) | State tracking and metadata |
| **Object Storage** | Google Cloud Storage | Raw data backup |
| **LLM** | Groq (llama-3.1-8b-instant) | Fast table summarization |
| **Embeddings** | BGE-large-en-v1.5 / FinE5 | Financial domain vectors |
| **Text Processing** | LangChain, tiktoken | Chunking and tokenization |
| **Data Sources** | EdgarTools, NewsAPI, Wikipedia-API | Multi-source ingestion |
| **Containerization** | Docker, Docker Compose | Local development environment |
| **Task Queue** | Celery + Redis | Distributed task execution |

---

## Project Structure

```
Data_Pipeline/
├── src/                              # Core backend modules
│   ├── bias/                         # Bias mitigation & fairness
│   │   ├── coverage_tracker.py       # Track data coverage per company
│   │   ├── boost_manager.py          # Boost configuration management
│   │   ├── baseline_calculator.py    # Baseline metrics calculation
│   │   └── retrieval_enhancer.py     # Fair retrieval boosting
│   ├── cloud/                        # Cloud connectors
│   │   ├── gcs_connector.py          # Google Cloud Storage
│   │   ├── postgres_connector.py     # PostgreSQL (Supabase)
│   │   └── qdrant_connector.py       # Qdrant vector DB
│   ├── data_ingestion/               # Data fetching
│   │   ├── base_fetcher.py           # Abstract base with retry logic
│   │   ├── sec_fetcher.py            # SEC filings (EdgarTools)
│   │   ├── news_fetcher.py           # News articles (NewsAPI + GDELT)
│   │   └── wikipedia_fetcher.py      # Wikipedia pages
│   ├── data_processing/              # Data transformation
│   │   ├── sec_parser.py             # Parse SEC HTML filings
│   │   ├── news_parser.py            # Extract news content
│   │   ├── wikipedia_parser.py       # Process Wikipedia pages
│   │   ├── sec_processor.py          # Complete SEC pipeline
│   │   ├── news_processor.py         # Complete news pipeline
│   │   ├── wikipedia_processor.py    # Complete Wikipedia pipeline
│   │   ├── chunker.py                # LangChain text splitting
│   │   ├── table_detector.py         # Financial table detection
│   │   └── table_processor.py        # Table extraction & processing
│   ├── data_storage/                 # Storage management
│   │   └── table_storage.py          # Table data storage
│   ├── embedding/                    # Vector embeddings
│   │   └── embedder.py               # BGE/FinE5 embeddings
│   ├── orchestration/                # Airflow utilities
│   │   └── airflow_helpers.py        # DAG task utilities
│   ├── state/                        # Pipeline state tracking
│   │   └── state_manager.py          # PostgreSQL state management
│   ├── utils/                        # Shared utilities
│   │   ├── config.py                 # Configuration loader
│   │   ├── logging_config.py         # Structured logging
│   │   ├── table_summarizer.py       # Groq LLM summarization
│   │   └── chunk_stats.py            # Chunking analytics
│   └── validation/                   # Data quality
│       └── data_validator.py         # Validation checks
│
├── scripts/                          # Helper & test scripts
│   ├── test_end_to_end.py            # Full pipeline test
│   ├── fetch_single_company.py       # Single company fetch
│   ├── test_apple_2024.py            # Historical load test
│   ├── test_infrastructure.py        # Cloud connection test
│   ├── fetch_and_process_sec.py      # SEC workflow test
│   ├── configure_bias_mitigation.py  # Bias setup
│   ├── validate_data.py              # Data validation runner
│   └── cleanup_all_data.py           # Data cleanup utility
│
├── configs/                          # YAML configuration files
│   ├── companies.yaml                # 12 companies with CIK numbers
│   ├── sec_config.yaml               # SEC fetching parameters
│   ├── database_config.yaml          # DB & embedding config
│   └── scheduler_config.yaml         # Scheduling parameters
│
├── bias_config/                      # Bias mitigation metrics
│   ├── baseline_config.json          # Baseline coverage metrics
│   ├── boost_config.json             # Boost factors
│   ├── coverage_metrics.json         # Coverage per source
│   ├── coverage_report.json          # Coverage analysis
│   ├── classification_report.json    # Company classification
│   └── boost_summary.json            # Boost adjustments
│
├── docker/                           # Docker configuration
│   ├── docker-compose.yaml           # Complete Airflow stack
│   ├── Dockerfile                    # Airflow image
│   └── .env.docker                   # Docker environment vars
│
├── airflow_data/                     # Airflow workspace
│   ├── dags/                         # DAG definitions
│   │   ├── initial_load_dag.py       # Historical data load
│   │   ├── sec_monitoring_dag.py     # Daily SEC monitoring
│   │   ├── wikipedia_update_dag.py   # Weekly Wikipedia updates
│   │   └── news_fetch_dag.py         # 2x daily news fetching
│   ├── airflow.cfg                   # Airflow configuration
│   ├── airflow.db                    # SQLite state DB
│   ├── config/                       # Airflow configs
│   ├── plugins/                      # Custom Airflow plugins
│   └── logs/                         # Airflow execution logs
│
├── data/                             # Local data storage (testing)
│   ├── <company_tickers>/            # Processed company data (JSON)
│   ├── validation/                   # Validation reports
│   └── tables/                       # Extracted financial tables
│
├── logs/                             # Application logs
├── requirements.txt                  # Python dependencies
└── .env.example                      # Environment variables template
```

---

## Prerequisites

Before setting up the pipeline, ensure you have:

### Required Software
- **Python 3.11+** ([Download](https://www.python.org/downloads/))
- **Docker Desktop** ([Download](https://www.docker.com/products/docker-desktop/))
- **Git** ([Download](https://git-scm.com/downloads))

### Required API Keys & Services

1. **Groq API Key** (Free tier available)
   - Sign up at [https://groq.com/](https://groq.com/)
   - Used for: Table summarization with llama-3.1-8b-instant

2. **NewsAPI Key** (Free tier: 100 requests/day)
   - Sign up at [https://newsapi.org/](https://newsapi.org/)
   - Used for: News article fetching

3. **Google Cloud Platform** (Free tier available)
   - Create project at [https://console.cloud.google.com/](https://console.cloud.google.com/)
   - Enable Cloud Storage API
   - Create service account and download JSON credentials
   - Used for: Raw data backup

4. **Supabase PostgreSQL** (Free tier available)
   - Sign up at [https://supabase.com/](https://supabase.com/)
   - Create new project and note connection details
   - Used for: State tracking and metadata

5. **Qdrant Cloud** (Free tier: 1GB cluster)
   - Sign up at [https://cloud.qdrant.io/](https://cloud.qdrant.io/)
   - Create cluster and generate API key
   - Used for: Vector embeddings storage

### Optional (for SEC filings)
- **Email address** for SEC Edgar API identification (required by SEC)

---

## Setup Instructions

### Step 1: Clone the Repository

```bash
git clone <repository-url>
cd Data_Pipeline
```

### Step 2: Set Up Python Environment

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Step 3: Configure Environment Variables

```bash
# Copy example environment file
cp .env.example .env

# Edit .env file with your credentials
```

Fill in the following in `.env`:

```env
# Groq API (LLM for table summarization)
GROQ_API_KEY=your_groq_api_key_here

# NewsAPI (News article fetching)
NEWS_API_KEY=your_newsapi_key_here

# Google Cloud Platform
GCP_PROJECT_ID=your_gcp_project_id
GCP_BUCKET_NAME=your_bucket_name
GOOGLE_APPLICATION_CREDENTIALS=path/to/your/service-account-key.json

# PostgreSQL (Supabase)
POSTGRES_HOST=your_supabase_host.supabase.co
POSTGRES_PORT=5432
POSTGRES_DB=postgres
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_supabase_password

# Qdrant Cloud
QDRANT_URL=https://your-cluster.qdrant.io
QDRANT_API_KEY=your_qdrant_api_key

# SEC Edgar API
SEC_USER_AGENT=your_name your_email@example.com

# Embedding Model (choose one)
EMBEDDING_MODEL=BAAI/bge-large-en-v1.5
# Alternative: EMBEDDING_MODEL=FinE5
```

### Step 4: Set Up Google Cloud Storage

```bash
# Create GCS bucket (replace with your bucket name)
gsutil mb -p your-project-id gs://your-bucket-name/

# Create folder structure
gsutil mkdir gs://your-bucket-name/raw_data/
gsutil mkdir gs://your-bucket-name/processed_data/
```

### Step 5: Initialize PostgreSQL Database

```bash
# Run database initialization script (if provided)
python scripts/init_database.py

# Or manually create tables using SQL schema (see database_schema.sql)
```

### Step 6: Configure Qdrant Collection

```bash
# Create Qdrant collection for embeddings
python scripts/init_qdrant.py
```

### Step 7: Test Infrastructure Connections

```bash
# Verify all cloud services are accessible
python scripts/test_infrastructure.py
```

Expected output:
```
✓ Google Cloud Storage connection: OK
✓ PostgreSQL connection: OK
✓ Qdrant connection: OK
✓ Groq API: OK
✓ NewsAPI: OK
```

### Step 8: Set Up Airflow with Docker (Optional but Recommended)

```bash
cd docker

# Start Airflow stack
docker-compose up -d

# Wait for services to initialize (~2 minutes)
docker-compose ps
```

Access Airflow UI:
- URL: [http://localhost:8080](http://localhost:8080)
- Username: `airflow`
- Password: `airflow` (check `docker/.env.docker` for default credentials)

### Step 9: Run Initial Test

```bash
# Test with a single company (Apple)
python scripts/fetch_single_company.py --ticker AAPL

# This will:
# 1. Fetch SEC filings, Wikipedia page, and news for Apple
# 2. Process and chunk the data
# 3. Generate embeddings
# 4. Store in Qdrant and PostgreSQL
```

---

## Configuration

### Company Configuration (`configs/companies.yaml`)

Define which companies to track:

```yaml
companies:
  - ticker: AAPL
    name: Apple Inc.
    cik: "0000320193"
    sector: Technology
  - ticker: MSFT
    name: Microsoft Corporation
    cik: "0000789019"
    sector: Technology
  # ... 10 more companies
```

### SEC Configuration (`configs/sec_config.yaml`)

Control SEC data fetching:

```yaml
sec:
  filing_types:
    - "10-K"
    - "10-Q"
  start_year: 2023
  chunk_size: 800
  chunk_overlap: 100
  table_detection_enabled: true
  table_summarization_enabled: true
```

### Database Configuration (`configs/database_config.yaml`)

Configure storage backends:

```yaml
databases:
  postgres:
    pool_size: 10
    max_overflow: 20
  qdrant:
    collection_name: "financial_documents"
    vector_size: 1024
    distance: "Cosine"
  embedding:
    model: "BAAI/bge-large-en-v1.5"
    batch_size: 32
```

---

## Usage

### Running the Complete Pipeline (via Airflow)

1. **Start Airflow** (if using Docker):
   ```bash
   cd docker
   docker-compose up -d
   ```

2. **Access Airflow UI**: [http://localhost:8080](http://localhost:8080)

3. **Trigger Initial Load**:
   - Navigate to DAGs
   - Find `initial_load_dag`
   - Click trigger (▶️ icon)
   - This will load all historical data (2023+) for all 12 companies
   - Expected duration: 30-60 minutes per company

4. **Enable Scheduled DAGs**:
   - `sec_monitoring_dag`: Runs weekdays at 6 PM
   - `wikipedia_update_dag`: Runs Sundays at 12 AM
   - `news_fetch_dag`: Runs daily at 9 AM and 5 PM

### Running Scripts Manually (Without Airflow)

#### Test End-to-End Pipeline
```bash
python scripts/test_end_to_end.py
```

#### Fetch Data for Single Company
```bash
python scripts/fetch_single_company.py --ticker AAPL
```

#### Process SEC Filings Only
```bash
python scripts/fetch_and_process_sec.py --ticker MSFT --year 2024
```

#### Configure Bias Mitigation
```bash
python scripts/configure_bias_mitigation.py
```

#### Validate Data Quality
```bash
python scripts/validate_data.py --output reports/validation_report.json
```

#### Clean Up All Data
```bash
python scripts/cleanup_all_data.py --confirm
```

---

## Data Sources

### 1. SEC Filings (EdgarTools)
- **Filing Types**: 10-K (annual reports), 10-Q (quarterly reports)
- **Date Range**: 2023 onwards
- **Refresh**: Daily monitoring for new filings
- **API**: Free, no API key required (email required for user agent)
- **Content**: Financial statements, MD&A, risk factors, business descriptions

### 2. Wikipedia
- **Pages**: Company overview pages
- **Refresh**: Weekly updates (checks for new revisions)
- **API**: Free Wikipedia API
- **Content**: Company history, products, subsidiaries, operations

### 3. News Articles
- **Sources**: NewsAPI (mainstream media) + GDELT (global news)
- **Refresh**: 2x daily (9 AM, 5 PM)
- **Rate Limit**: 100 requests/day (NewsAPI free tier)
- **Filtering**: Fuzzy matching for company relevance
- **Content**: Recent news, press releases, market commentary

---

## Pipeline Components

### Data Ingestion (`src/data_ingestion/`)

**Base Fetcher** (`base_fetcher.py`)
- Abstract class with common fetching logic
- Features: Rate limiting, retry logic, exponential backoff
- Configurable timeouts and max retries

**SEC Fetcher** (`sec_fetcher.py`)
- Uses EdgarTools library for SEC Edgar access
- Fetches 10-K and 10-Q filings by CIK number
- No API key required (uses email for user agent)
- Handles HTML parsing and metadata extraction

**Wikipedia Fetcher** (`wikipedia_fetcher.py`)
- Uses Wikipedia-API library
- Tracks page revision IDs to detect changes
- Fetches full page content including sections

**News Fetcher** (`news_fetcher.py`)
- Dual-source: NewsAPI (premium) + GDELT (comprehensive)
- Fuzzy matching (Levenshtein distance) for relevance filtering
- Deduplication across sources
- Date-based filtering

### Data Processing (`src/data_processing/`)

**Parsers**
- `sec_parser.py`: Converts SEC HTML filings to clean Markdown
- `news_parser.py`: Extracts article content from HTML (newspaper3k)
- `wikipedia_parser.py`: Structures Wikipedia content by sections

**Chunker** (`chunker.py`)
- LangChain RecursiveCharacterTextSplitter
- Token-accurate chunking using tiktoken
- Default: 800 tokens per chunk, 100-token overlap
- Preserves semantic boundaries (paragraphs, sentences)

**Table Processor** (`table_detector.py`, `table_processor.py`)
- Detects financial tables in documents
- Extracts table content (rows, columns, values)
- LLM-based summarization via Groq (llama-3.1-8b-instant)
- Stores table references with parent chunks

**Processors** (End-to-End Orchestration)
- `sec_processor.py`: Fetch → Parse → Chunk → Embed → Store (SEC)
- `news_processor.py`: Fetch → Parse → Chunk → Embed → Store (News)
- `wikipedia_processor.py`: Fetch → Parse → Chunk → Embed → Store (Wikipedia)

### Embedding (`src/embedding/`)

**Embedder** (`embedder.py`)
- Models supported:
  - BAAI/bge-large-en-v1.5 (general-purpose, strong performance)
  - FinE5 (finance-domain optimized)
- Dimensions: 1024
- Batch processing for efficiency
- Normalization for cosine similarity

### Storage (`src/cloud/`)

**Qdrant Connector** (`qdrant_connector.py`)
- Vector database for semantic search
- Collection: "financial_documents"
- Metadata: company, source, date, chunk_id, table_refs
- Distance metric: Cosine similarity

**PostgreSQL Connector** (`postgres_connector.py`)
- State tracking tables:
  - `processed_files`: Track processed documents
  - `pipeline_runs`: Execution history
  - `sec_filings`: SEC filing metadata
  - `wikipedia_revisions`: Wikipedia page versions
  - `news_articles`: News article records
- Connection pooling for performance

**GCS Connector** (`gcs_connector.py`)
- Raw data backup in JSON format
- Folder structure: `raw_data/{source}/{company}/{date}/`
- Processed data: `processed_data/{company}/`

### State Management (`src/state/`)

**State Manager** (`state_manager.py`)
- Tracks processed files to avoid reprocessing
- Records pipeline run metadata
- Enables incremental updates
- Supports rollback on failures

### Bias Mitigation (`src/bias/`)

**Coverage Tracker** (`coverage_tracker.py`)
- Monitors data coverage per company
- Metrics: number of chunks, sources, tables, date ranges
- Identifies underrepresented companies

**Boost Manager** (`boost_manager.py`)
- Configures boost factors for fair retrieval
- Example: Small companies get 1.5x boost, large get 0.8x
- Ensures balanced representation in RAG results

**Retrieval Enhancer** (`retrieval_enhancer.py`)
- Applies boost factors to search results
- Re-ranks results for fairness
- Preserves relevance while improving coverage

### Validation (`src/validation/`)

**Data Validator** (`data_validator.py`)
- Completeness: All expected sources present?
- Schema: Correct data types and fields?
- Token size: Within acceptable ranges?
- Content quality: No corruption or encoding issues?
- Statistical: Expected distributions (chunk lengths, embedding norms)?
- Table references: All references valid?

---

## Airflow DAGs

### 1. Initial Load DAG (`initial_load_dag.py`)
- **Purpose**: One-time historical data load
- **Trigger**: Manual
- **Scope**: All 12 companies, all sources, 2023+
- **Duration**: 6-12 hours total (~30-60 min per company)
- **Tasks**:
  1. Fetch SEC filings (2023-2024)
  2. Fetch Wikipedia pages
  3. Fetch historical news (last 6 months)
  4. Process and chunk all data
  5. Generate embeddings
  6. Store in Qdrant + PostgreSQL + GCS
  7. Run validation
  8. Configure bias mitigation

### 2. SEC Monitoring DAG (`sec_monitoring_dag.py`)
- **Schedule**: Weekdays at 6 PM EST
- **Purpose**: Check for new SEC filings
- **Logic**:
  1. Query Edgar for new filings since last run
  2. Download new 10-K/10-Q filings
  3. Process and embed
  4. Update vector DB
  5. Update coverage metrics

### 3. Wikipedia Update DAG (`wikipedia_update_dag.py`)
- **Schedule**: Sundays at 12 AM
- **Purpose**: Refresh company Wikipedia pages
- **Logic**:
  1. Check revision IDs for all 12 companies
  2. If changed, fetch updated page
  3. Re-process and embed
  4. Update vector DB (replace old chunks)

### 4. News Fetch DAG (`news_fetch_dag.py`)
- **Schedule**: Daily at 9 AM and 5 PM
- **Purpose**: Fetch latest news articles
- **Logic**:
  1. Query NewsAPI + GDELT for last 12 hours
  2. Fuzzy match for relevance
  3. Deduplicate
  4. Process and embed
  5. Store in vector DB
  6. Update coverage metrics

---

## Testing

### Infrastructure Tests
```bash
# Test all cloud connections
python scripts/test_infrastructure.py
```

### End-to-End Pipeline Test
```bash
# Run complete pipeline for Apple
python scripts/test_end_to_end.py
```

### Component Tests
```bash
# Test SEC fetching only
python scripts/fetch_and_process_sec.py --ticker AAPL

# Test specific year
python scripts/test_apple_2024.py
```

### Validation Tests
```bash
# Run data quality validation
python scripts/validate_data.py

# Expected output: validation_report.json with:
# - Completeness scores
# - Schema compliance
# - Quality metrics
# - Identified issues
```

### Bias Mitigation Tests
```bash
# Configure and test bias mitigation
python scripts/configure_bias_mitigation.py

# Check coverage metrics in bias_config/coverage_metrics.json
```

---

## Troubleshooting

### Common Issues

#### 1. API Rate Limiting
**Symptom**: `429 Too Many Requests` errors

**Solution**:
```python
# Adjust rate limits in configs/sec_config.yaml
rate_limit:
  requests_per_minute: 10  # Lower this value
  retry_after_seconds: 60
```

#### 2. Qdrant Connection Timeout
**Symptom**: `QdrantException: Connection timeout`

**Solution**:
- Check Qdrant URL and API key in `.env`
- Verify cluster is running in Qdrant Cloud dashboard
- Test connection:
  ```bash
  python -c "from src.cloud.qdrant_connector import QdrantConnector; print(QdrantConnector().test_connection())"
  ```

#### 3. PostgreSQL Connection Failed
**Symptom**: `psycopg2.OperationalError: could not connect`

**Solution**:
- Verify Supabase project is active
- Check connection string format:
  ```
  postgresql://postgres:password@host.supabase.co:5432/postgres
  ```
- Whitelist your IP in Supabase dashboard

#### 4. GCS Authentication Error
**Symptom**: `google.auth.exceptions.DefaultCredentialsError`

**Solution**:
- Verify `GOOGLE_APPLICATION_CREDENTIALS` path in `.env`
- Check service account has Storage Admin role
- Test authentication:
  ```bash
  gcloud auth application-default login
  ```

#### 5. Airflow DAG Not Showing Up
**Symptom**: DAG not visible in Airflow UI

**Solution**:
- Check DAG file has no syntax errors:
  ```bash
  python airflow_data/dags/initial_load_dag.py
  ```
- Verify DAG file is in `airflow_data/dags/` directory
- Refresh Airflow UI (wait 30 seconds for DAG bag refresh)
- Check Airflow logs:
  ```bash
  docker logs docker-airflow-webserver-1
  ```

#### 6. Out of Memory Errors
**Symptom**: `MemoryError` or Docker container crashes

**Solution**:
- Reduce batch size in `configs/database_config.yaml`:
  ```yaml
  embedding:
    batch_size: 16  # Lower from 32
  ```
- Increase Docker memory allocation:
  - Docker Desktop → Settings → Resources → Memory (recommend 8GB+)

#### 7. News Fetching Returns No Results
**Symptom**: Empty news articles list

**Solution**:
- Check NewsAPI quota (100 requests/day free tier)
- Verify date range is within last 30 days (free tier limit)
- Test NewsAPI key:
  ```bash
  curl "https://newsapi.org/v2/everything?q=Apple&apiKey=YOUR_KEY"
  ```

---

## Project Team

**Course**: MLOps
**Institution**: [Your University]
**Term**: [Current Term]

---

## License

This project is for educational purposes as part of an MLOps course.

---

## Acknowledgments

- **EdgarTools**: SEC filing access without API keys
- **LangChain**: Text processing and chunking utilities
- **Qdrant**: High-performance vector database
- **Apache Airflow**: Workflow orchestration
- **Groq**: Fast LLM inference for table summarization

---

## Additional Resources

- [SEC Edgar API Documentation](https://www.sec.gov/edgar/sec-api-documentation)
- [Qdrant Documentation](https://qdrant.tech/documentation/)
- [Apache Airflow Documentation](https://airflow.apache.org/docs/)
- [LangChain Documentation](https://python.langchain.com/docs/)

---

**For questions or issues, please contact the project team or refer to course materials.**
