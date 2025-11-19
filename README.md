# Automated Due Diligence & Market Intelligence System

A production-ready MLOps pipeline for financial intelligence gathering combining automated data ingestion, hybrid RAG retrieval, and comprehensive model validation with bias detection.

---

## Overview

### What This System Does

This project implements a complete end-to-end machine learning operations (MLOps) system for automated financial analysis and due diligence. It solves the challenge of efficiently gathering, processing, and intelligently retrieving information from multiple financial data sources.

**The Problem:**
- Financial analysts spend days reading SEC filings (100+ pages per document)
- Information is scattered across multiple sources (SEC, Wikipedia, news)
- Manual research is slow, error-prone, and potentially biased
- No systematic way to ensure comprehensive coverage

**Our Solution:**
- **Automated Ingestion**: Daily updates from SEC filings, Wikipedia, and financial news
- **Intelligent Processing**: Parse documents, extract tables, chunk intelligently
- **Hybrid Retrieval**: Combine semantic understanding with keyword precision
- **Quality Validation**: Comprehensive metrics and bias detection
- **Experiment Tracking**: Optimize and improve continuously

### System Capabilities

1. **Multi-Source Data Pipeline**
   - SEC 10-K and 10-Q filings (annual and quarterly reports)
   - Company Wikipedia pages (business overviews)
   - Financial news articles (current events)
   - Automated daily/weekly/6-hourly updates

2. **Advanced Document Processing**
   - HTML parsing preserving structure
   - Table extraction and markdown conversion
   - LLM-based table summarization
   - Smart chunking with context preservation (512 tokens, 50 overlap)

3. **Hybrid Search System**
   - Semantic search via 768-dimensional embeddings
   - Keyword search via BM25 algorithm
   - Configurable weighting (α parameter)
   - ~50-200ms query latency

4. **Comprehensive Validation**
   - Standard IR metrics (Precision, Recall, nDCG, MRR, MAP)
   - Bias detection using data slicing techniques
   - MLflow experiment tracking
   - Sensitivity analysis for parameter optimization

---

## 🏗️ Architecture

### High-Level System Design

```
┌──────────────────────────────────────────┐
│      APACHE AIRFLOW ORCHESTRATION         │
│   (4 DAGs: SEC, Wikipedia, News, Cleanup) │
└────────────┬─────────────────────────────┘
             │
     ┌───────┴────────┬────────────┐
     │                │            │
┌────▼─────┐   ┌─────▼────┐   ┌──▼───┐
│   SEC    │   │Wikipedia │   │ News │
│ Fetcher  │   │ Fetcher  │   │Fetch │
└────┬─────┘   └─────┬────┘   └──┬───┘
     │                │            │
     └────────┬───────┴────────────┘
              │
      ┌───────▼────────┐
      │  PROCESSING    │
      │  1. Parse HTML │
      │  2. Extract    │
      │  3. Chunk      │
      │  4. Embed      │
      └───────┬────────┘
              │
      ┌───────┴────────┐
      │                │
 ┌────▼─────┐    ┌────▼────┐
 │PostgreSQL│    │ Qdrant  │
 │ Metadata │    │ Vectors │
 └──────────┘    └────┬────┘
                      │
              ┌───────▼────────┐
              │ RESEARCHER     │
              │    AGENT       │
              │ (Hybrid RAG)   │
              └───────┬────────┘
                      │
          ┌───────────┴──────────┐
          │                      │
    ┌─────▼──────┐      ┌───────▼──────┐
    │VALIDATION  │      │BIAS DETECTION│
    │IR Metrics  │      │Data Slicing  │
    └─────┬──────┘      └───────┬──────┘
          │                      │
          └──────────┬───────────┘
                     │
             ┌───────▼────────┐
             │     MLFLOW     │
             │   Experiment   │
             │    Tracking    │
             └────────────────┘
```

### Technology Stack

| Layer | Technologies |
|-------|-------------|
| **Orchestration** | Apache Airflow 2.7.3 |
| **Storage** | PostgreSQL 15, Qdrant Vector DB |
| **Processing** | Python 3.11, NLTK, BeautifulSoup |
| **Embeddings** | sentence-transformers (all-mpnet-base-v2) |
| **Retrieval** | Hybrid: Dense vectors + BM25 sparse |
| **Validation** | MLflow, Fairlearn, Custom IR metrics |
| **Infrastructure** | Docker, Docker Compose |
| **APIs** | SEC API, Groq API, NewsAPI |

---

### Data Pipeline Components
- ✅ **SEC Filings Fetcher** - Queries and extracts 10-K/10-Q sections
- ✅ **Wikipedia Fetcher** - Company pages with revision tracking
- ✅ **News Fetcher** - Financial news with auto-expiration
- ✅ **Document Parser** - HTML parsing, table extraction
- ✅ **Chunking Engine** - Intelligent 512-token chunks
- ✅ **Embedding Generator** - 768-dim semantic vectors
- ✅ **Storage Managers** - PostgreSQL and Qdrant integration

### Model & Validation Components
- ✅ **Researcher Agent** - Hybrid search (semantic + BM25)
- ✅ **Retrieval Evaluator** - Precision, Recall, nDCG, MRR, MAP
- ✅ **Bias Detector** - Company/source/category slicing
- ✅ **Experiment Tracker** - MLflow integration
- ✅ **Sensitivity Analyzer** - Parameter optimization
- ✅ **Model Registry** - Version control

### Infrastructure
- ✅ **Docker Setup** - Full containerization
- ✅ **Airflow DAGs** - 4 production workflows
- ✅ **Database Schema** - Complete PostgreSQL schema
- ✅ **Vector Collection** - Qdrant collection configured

---

## 🚀 Quick Start Guide

### Prerequisites

**System Requirements:**
- Docker Desktop (4GB+ RAM allocated)
- Python 3.11 or higher
- 8GB RAM recommended
- Git

**API Keys (all have free tiers):**
- **SEC API**: https://sec-api.io (100 calls/day free)
- **Groq API**: https://console.groq.com (free tier available)
- **NewsAPI**: https://newsapi.org (1000 calls/day free)

### Installation (10 minutes)

#### Step 1: Clone Repository

```bash
git clone git@github.com:Hariharan-afk/Automated-Due-Diligence-Market-Intelligence-Agent.git
cd Automated-Due-Diligence-Market-Intelligence-Agent
```

#### Step 2: Setup Python Environment

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install all dependencies
pip install -r requirements.txt
pip install -r requirements-validation.txt
```

#### Step 3: Configure Environment

```bash
# Copy template
cp .env.example .env

# Edit and add your API keys
nano .env  # or use your preferred editor

# Required variables:
# SEC_API_KEY=your_key_here
# GROQ_API_KEY=your_key_here
# NEWSAPI_KEY=your_key_here
# POSTGRES_HOST=localhost
# QDRANT_HOST=localhost
```

#### Step 4: Start Docker Services

```bash
cd docker

# Start all services (PostgreSQL, Qdrant, Airflow)
docker-compose up -d

# Wait for services to initialize
sleep 30

# Verify all containers are running
docker-compose ps
# Should show: postgres, qdrant, airflow-scheduler, airflow-webserver

cd ..
```

#### Step 5: Initialize Databases

```bash
# Create PostgreSQL schema and tables
python scripts/setup/init_databases.py

# Create Qdrant vector collection
python scripts/setup/create_vector_collections.py
```

#### Step 6: Setup Airflow

```bash
# Initialize Airflow metadata database
docker run --rm \
  --network docker_default \
  -e AIRFLOW__DATABASE__SQL_ALCHEMY_CONN=postgresql+psycopg2://airflow:airflow@postgres:5432/airflow \
  docker-airflow-scheduler \
  airflow db init

# Create admin user
docker run --rm \
  --network docker_default \
  -e AIRFLOW__DATABASE__SQL_ALCHEMY_CONN=postgresql+psycopg2://airflow:airflow@postgres:5432/airflow \
  docker-airflow-scheduler \
  airflow users create \
    --username admin \
    --password admin \
    --firstname Admin \
    --lastname User \
    --role Admin \
    --email admin@example.com
```

#### Step 7: Access Services ✅

- **Airflow UI**: http://localhost:8081 (login: admin/admin)
- **Qdrant Dashboard**: http://localhost:6333/dashboard
- **PostgreSQL**: localhost:5432

---

## Using the System

### Running Data Pipelines

#### Via Airflow UI (Recommended)

1. Open http://localhost:8081
2. Login with `admin` / `admin`
3. You'll see 4 DAGs:
   - `sec_filings_pipeline`
   - `wikipedia_refresh_pipeline`
   - `news_ingestion_pipeline`
   - `data_cleanup_pipeline`
4. Click on any DAG
5. Click the ▶️ **Play** button → "Trigger DAG"
6. Monitor progress in **Grid** view
7. Click on tasks to view logs

#### Via Command Line

```bash
# Trigger SEC filings pipeline
docker exec datapipeline_airflow_scheduler \
  airflow dags trigger sec_filings_pipeline

# View logs
docker logs -f datapipeline_airflow_scheduler

# Check task status
docker exec datapipeline_airflow_scheduler \
  airflow dags list-runs -d sec_filings_pipeline
```

### Using Researcher Agent for Search

#### Basic Search

```python
from src.agents.researcher_agent import ResearcherAgent

# Initialize agent
agent = ResearcherAgent(
    qdrant_host='localhost',
    alpha=0.5,      # Balanced: 50% semantic, 50% keyword
    top_k=5         # Return top 5 results
)

# Load corpus for BM25 indexing (required for hybrid search)
print("Loading corpus...")
agent.load_corpus()

# Perform search
results = agent.search(
    query="What are Apple's main revenue sources?",
    ticker="AAPL",   # Optional: filter by company
    verbose=True     # Print formatted results
)

# Access individual results
for result in results:
    print(f"\nRank #{result.rank}")
    print(f"Company: {result.metadata['ticker']}")
    print(f"Source: {result.metadata['source_type']}")
    print(f"Hybrid Score: {result.hybrid_score:.3f}")
    print(f"Content: {result.content[:200]}...")
```

#### Advanced: Compare Search Strategies

```python
# Pure Semantic (α=1.0): Best for conceptual queries
semantic_agent = ResearcherAgent(alpha=1.0)
semantic_agent.load_corpus()
semantic_results = semantic_agent.search("innovation strategy")

# Pure Keyword (α=0.0): Best for exact terms
keyword_agent = ResearcherAgent(alpha=0.0)
keyword_agent.load_corpus()
keyword_results = keyword_agent.search("GAAP revenue")

# Hybrid (α=0.5): Balanced approach
hybrid_agent = ResearcherAgent(alpha=0.5)
hybrid_agent.load_corpus()
hybrid_results = hybrid_agent.search("regulatory risks")
```

#### Filtering Results

```python
# Search specific company
results = agent.search("cloud computing", ticker="MSFT")

# Multi-company comparison
for ticker in ['AAPL', 'MSFT', 'GOOGL']:
    results = agent.search("AI strategy", ticker=ticker)
    print(f"\n{ticker} Results:")
    for r in results[:3]:
        print(f"  {r.content[:100]}...")
```

### Model Validation Workflow

#### Step 1: Create Ground Truth Dataset

```bash
# Generate template with 10 sample queries
python scripts/validation/create_ground_truth.py --mode sample

# This creates: data/validation/ground_truth.json
```

#### Step 2: Label Relevant Documents (Interactive)

```bash
python scripts/validation/create_ground_truth.py --mode interactive
```

**What this does:**
1. Shows you each query
2. Runs search and displays top 10 results
3. You mark which results are relevant (e.g., "1,3,5")
4. Builds labeled dataset automatically
5. Saves after each query

**Labeling Tips:**
- Label 20-50 queries for robust validation
- Mark a result as relevant if it directly answers the query
- Include at least 2-3 relevant chunks per query
- Cover all companies and categories

#### Step 3: Run Complete Validation

```bash
# Full validation with all components
python scripts/validation/run_complete_validation.py \
  --alpha 0.5 \
  --top-k 5 \
  --track-mlflow \
  --run-sensitivity

# Quick validation (without sensitivity analysis)
python scripts/validation/run_complete_validation.py \
  --alpha 0.5 \
  --track-mlflow
```

**What runs:**
1. **Retrieval Evaluation** - Computes Precision, Recall, nDCG, MRR, MAP
2. **Bias Detection** - Checks fairness across companies, sources, categories
3. **Sensitivity Analysis** (optional) - Tests α from 0.0 to 1.0, K from 1 to 20
4. **MLflow Logging** - Tracks all experiments automatically

**Execution Time:**
- Quick validation: ~2 minutes
- Full validation with sensitivity: ~5-10 minutes

#### Step 4: View Results

```bash
# Open HTML reports
open results/validation/<timestamp>/retrieval_report.html
open results/validation/<timestamp>/bias_report.html
open results/validation/<timestamp>/sensitivity_analysis/sensitivity_report.html

# Start MLflow UI
mlflow ui
# Then open: http://localhost:5000
```

---

## 📊 Understanding the Metrics

### Information Retrieval Metrics

**Precision@K** = Relevance of retrieved results
- Formula: (# relevant in top-K) / K
- Example: If 4 out of 5 results are relevant → Precision@5 = 0.80
- **Target: ≥ 0.50**

**Recall@K** = Coverage of relevant documents
- Formula: (# relevant in top-K) / (total # relevant)
- Example: If found 7 out of 10 relevant docs → Recall@10 = 0.70
- **Target: ≥ 0.40**

**nDCG@K** = Ranking quality (normalized discounted cumulative gain)
- Accounts for position: top results weighted more
- Range: 0.0 (worst) to 1.0 (perfect)
- **Target: ≥ 0.60**

**MRR** = Mean Reciprocal Rank
- Formula: 1 / (rank of first relevant result)
- Example: First relevant result at rank 2 → RR = 0.50
- **Target: ≥ 0.65**

**MAP** = Mean Average Precision
- Average precision across all queries
- Balances precision and recall
- **Target: ≥ 0.60**

### Bias Detection Metrics

**What We Check:**

1. **Company Bias** - Is performance equal across all companies?
   - Compare AAPL vs MSFT vs GOOGL vs AMZN vs TSLA
   - Check if any company is under/over-represented
   - Threshold: < 0.15 difference acceptable

2. **Source Type Bias** - Do different sources perform equally?
   - Compare SEC filings vs Wikipedia vs News
   - Check if retrieval favors certain source types
   - Threshold: < 0.15 difference acceptable

3. **Category Bias** - Are different query types handled equally?
   - Compare revenue vs risk vs technology vs operations queries
   - Check for systematic weaknesses in certain topics
   - Threshold: < 0.15 difference acceptable

**Severity Levels:**
- 🟢 **None**: Δ < 0.10 (acceptable natural variation)
- 🟡 **Medium**: 0.15 ≤ Δ < 0.25 (investigate and document)
- 🔴 **High**: Δ ≥ 0.25 (blocks deployment - must fix)

**Example:**
```
Company Bias Detection:
  AAPL: Precision@5 = 0.80
  MSFT: Precision@5 = 0.75
  AMZN: Precision@5 = 0.50  ← Disparity!
  
  Max difference: 0.30 (HIGH SEVERITY)
  Action: Add more AMZN documents or improve AMZN data quality
```

### Quality Gates

System deployment is **blocked** if:
- ❌ nDCG@5 < 0.60 (poor ranking quality)
- ❌ Precision@5 < 0.50 (too many irrelevant results)
- ❌ Any high-severity bias detected (unfair to subgroups)

---

## 🔍 Hybrid Search Explained

### The Formula

```
hybrid_score = α × semantic_score + (1-α) × bm25_score
```

Where:
- **α ∈ [0, 1]**: Weight parameter
- **semantic_score**: Cosine similarity from embeddings (0-1)
- **bm25_score**: Keyword relevance score (normalized 0-1)

### How It Works

**Semantic Search (Dense Vectors):**
- Understands meaning and context
- Handles synonyms: "revenue" matches "income"
- Works for conceptual queries
- Uses 768-dimensional embeddings
- Computed via cosine similarity

**BM25 Search (Sparse Keywords):**
- Exact keyword matching
- Handles rare/technical terms well
- Works for specific codes (e.g., "CIK", "GAAP")
- Uses statistical term frequency
- Computed via BM25 algorithm

**Hybrid Combination:**
- Combines strengths of both approaches
- α controls the balance
- Normalized and weighted sum
- Optimal α typically 0.5-0.6

### When to Adjust Alpha

| α Value | Search Type | Best For |
|---------|-------------|----------|
| **0.0** | Pure BM25 | Exact keywords, technical terms, codes |
| **0.3** | Keyword-heavy | Specific terminology with some context |
| **0.5** | Balanced | General queries (recommended default) |
| **0.7** | Semantic-heavy | Conceptual understanding |
| **1.0** | Pure Semantic | Paraphrased queries, synonyms |

**Examples:**
```python
# For exact accounting term
results = agent.search("GAAP revenue recognition", alpha=0.2)

# For general business question
results = agent.search("What drives profitability?", alpha=0.5)

# For conceptual analysis
results = agent.search("competitive advantages", alpha=0.8)
```

---

## 📋 Available Pipelines

### 1. SEC Filings Pipeline

**Schedule**: Daily at midnight (00:00 UTC)  
**Duration**: 15-30 minutes for all companies  
**DAG**: `sec_filings_pipeline`

**What It Does:**
1. Queries SEC API for new 10-K and 10-Q filings (last 365 days)
2. Extracts key sections from each filing
3. Parses tables and text separately
4. Chunks content (512 tokens, 50 overlap)
5. Generates embeddings (768-dim)
6. Stores in PostgreSQL + Qdrant
7. Updates status tracking

**Sections Extracted:**
- **10-K** (Annual): Business, Risk Factors, MD&A, Financial Statements
- **10-Q** (Quarterly): Financial Statements, MD&A

**Companies**: AAPL, MSFT, GOOGL, AMZN, TSLA (configurable)

### 2. Wikipedia Refresh Pipeline

**Schedule**: Weekly on Saturdays (03:00 UTC)  
**Duration**: ~5 minutes  
**DAG**: `wikipedia_refresh_pipeline`

**What It Does:**
1. Fetches latest Wikipedia pages for all companies
2. Checks revision IDs to detect changes
3. Re-chunks and re-embeds if content changed
4. Updates vector database
5. Skips if no changes (efficient)

### 3. News Ingestion Pipeline

**Schedule**: Every 6 hours  
**Duration**: ~10 minutes  
**DAG**: `news_ingestion_pipeline`

**What It Does:**
1. Fetches latest financial news for each company
2. Filters for relevance
3. Parses and extracts content
4. Chunks and embeds
5. Stores with 30-day auto-expiration
6. Automatically removes old news

### 4. Data Cleanup Pipeline

**Schedule**: Daily at 01:00 UTC  
**Duration**: ~2 minutes  
**DAG**: `data_cleanup_pipeline`

**What It Does:**
1. Removes expired news articles (> 30 days old)
2. Cleans up orphaned vector chunks
3. Optimizes PostgreSQL tables
4. Reports cleanup statistics

---

## 🔬 Experiment Tracking with MLflow

### Running Experiments

**Ablation Study** - Find optimal α:

```python
from src.tracking.experiment_tracker import ExperimentTracker
from src.validation.retrieval_evaluator import RetrievalEvaluator

# Initialize
tracker = ExperimentTracker(experiment_name="retrieval_optimization")
evaluator = RetrievalEvaluator('data/validation/ground_truth.json')

# Test different alpha values
results = tracker.run_ablation_study(
    evaluator,
    alpha_values=[0.0, 0.3, 0.5, 0.7, 1.0],
    top_k_values=[5]
)

# Results
print(f"Best configuration:")
print(f"  Alpha: {results['best_config']['alpha']}")
print(f"  nDCG@5: {results['best_config']['ndcg@5']:.3f}")
print(f"  Precision@5: {results['best_config']['precision@5']:.3f}")
```

**Compare Embedding Models:**

```python
# Test different models
results = tracker.compare_embedding_models(
    evaluator,
    models=[
        "sentence-transformers/all-mpnet-base-v2",      # 768-dim (current)
        "sentence-transformers/all-MiniLM-L6-v2",       # 384-dim (faster)
        "sentence-transformers/multi-qa-mpnet-base-dot-v1"  # QA-optimized
    ]
)
```

### Viewing Results in MLflow

```bash
# Start MLflow UI
mlflow ui

# Or with custom port
mlflow ui --port 5001

# Open: http://localhost:5000
```

**In MLflow Dashboard:**
1. **Experiments List** - See all experiments
2. **Select Experiment** - Click "retrieval_optimization"
3. **Compare Runs** - Check multiple runs, click "Compare"
4. **View Charts** - Parallel coordinates, metric plots
5. **Download Artifacts** - HTML reports, plots, configs
6. **Find Best Run** - Sort by nDCG@5 column

**What's Logged:**
- Parameters: α, top_k, embedding_model
- Metrics: precision_at_1, recall_at_5, ndcg_at_10, etc.
- Artifacts: HTML reports, JSON results, plots
- Tags: experiment_type, timestamp

---

## ⚖️ Bias Detection Details

### Running Bias Analysis

```python
from src.agents.researcher_agent import ResearcherAgent
from src.validation.retrieval_evaluator import RetrievalEvaluator
from src.validation.bias_detector import BiasDetector

# Initialize components
agent = ResearcherAgent(qdrant_host='localhost', alpha=0.5)
agent.load_corpus()

evaluator = RetrievalEvaluator('data/validation/ground_truth.json')
detector = BiasDetector(evaluator)

# Run complete analysis
results = detector.run_complete_bias_analysis(agent)

# Check results
if results['overall_bias_detected']:
    print(f"⚠️ {results['total_disparities']} disparities found")
    for disp in results['all_disparities']:
        print(f"  {disp['severity']}: {disp['description']}")
else:
    print("✅ No significant bias detected")

# Save reports
detector.save_bias_report(results, 'results/bias/report.json')
detector.generate_bias_html_report(results, 'results/bias/report.html')
```

### Interpreting Bias Reports

**Example Output:**
```
  BIAS DETECTION SUMMARY
================================
Company Performance:
  AAPL: P@5=0.750, R@5=0.700, nDCG@5=0.780
  MSFT: P@5=0.740, R@5=0.680, nDCG@5=0.770
  GOOGL: P@5=0.680, R@5=0.650, nDCG@5=0.720
  AMZN: P@5=0.720, R@5=0.690, nDCG@5=0.750
  TSLA: P@5=0.710, R@5=0.670, nDCG@5=0.740

Max difference: 0.070 (AAPL vs GOOGL)
Status: ✅ ACCEPTABLE (< 0.15 threshold)
```

**With Bias:**
```
 2 DISPARITIES DETECTED

🔴 HIGH SEVERITY: COMPANY BIAS
   precision@5 disparity: MSFT (0.850) outperforms AMZN (0.550) by 0.300
   
   Recommended Actions:
   1. Add more AMZN SEC filings to database
   2. Check AMZN data quality and parsing
   3. Review AMZN document chunking
   4. Balance training examples across companies
```

---

## Database Schema Details

### PostgreSQL Tables

**companies** - Master company list
```sql
CREATE TABLE companies (
    ticker VARCHAR(10) PRIMARY KEY,
    company_name VARCHAR(255) NOT NULL,
    cik VARCHAR(10) NOT NULL UNIQUE,
    sector VARCHAR(100),
    industry VARCHAR(100)
);
```

**sec_filings** - Filing tracking
```sql
CREATE TABLE sec_filings (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) REFERENCES companies(ticker),
    filing_type VARCHAR(10) CHECK (filing_type IN ('10-K', '10-Q')),
    filing_date DATE NOT NULL,
    fiscal_year INTEGER,
    fiscal_quarter INTEGER CHECK (fiscal_quarter BETWEEN 1 AND 4),
    accession_number VARCHAR(50) UNIQUE NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    sections_extracted TEXT[],
    total_chunks INTEGER DEFAULT 0,
    text_chunks INTEGER DEFAULT 0,
    table_chunks INTEGER DEFAULT 0,
    indexed_in_vector_db BOOLEAN DEFAULT FALSE
);
```

**Common Queries:**
```sql
-- Filing status overview
SELECT ticker, filing_type, status, COUNT(*) 
FROM sec_filings 
GROUP BY ticker, filing_type, status;

-- Recent filings
SELECT ticker, filing_type, filing_date, status, total_chunks
FROM sec_filings 
WHERE filing_date > CURRENT_DATE - INTERVAL '90 days'
ORDER BY filing_date DESC;

-- Failed filings needing attention
SELECT ticker, filing_type, accession_number, error_message
FROM sec_filings 
WHERE status = 'failed';
```

### Qdrant Collection

**Collection**: `due_diligence_kb`

**Configuration:**
- Vectors: 768 dimensions (all-mpnet-base-v2)
- Distance: Cosine similarity
- Indexing: HNSW for fast search
- Payload: Rich metadata

**Example Payload:**
```json
{
  "text": "The Company's total net sales increased 8% year over year...",
  "chunk_id": "550e8400-e29b-41d4-a716-446655440000",
  "ticker": "AAPL",
  "company_name": "Apple Inc.",
  "source_type": "sec",
  "filing_type": "10-K",
  "filing_date": "2024-11-01",
  "fiscal_year": 2024,
  "section_code": "7",
  "section_name": "Management's Discussion and Analysis",
  "chunk_type": "text",
  "contains_table": false,
  "position": 5,
  "token_count": 487,
  "word_count": 362
}
```

---

## ⚙️ Configuration Guide

### Adding New Companies

1. Edit `configs/companies.yaml`:
```yaml
companies:
  - ticker: NVDA
    name: NVIDIA Corporation
    cik: "0001045810"
    sector: Technology
    industry: Semiconductors
```

2. Update database:
```bash
python scripts/setup/init_databases.py
```

3. Airflow will automatically process on next scheduled run

### Customizing Retrieval Behavior

**Per-Query Tuning:**
```python
# Technical/exact queries - favor keywords
results = agent.search("Form 10-K Item 1A", alpha=0.2, top_k=5)

# Conceptual queries - favor semantic
results = agent.search("innovation strategy", alpha=0.8, top_k=10)

# Balanced
results = agent.search("revenue trends", alpha=0.5, top_k=5)
```

**Global Configuration:**

Edit `configs/development.yaml`:
```yaml
pipeline:
  chunk_size: 512           # Larger = more context, fewer chunks
  chunk_overlap: 50         # Overlap for continuity
  batch_size: 32            # Embedding batch size
  embedding_model: "all-mpnet-base-v2"
```

---

## 🐛 Troubleshooting

### Common Issues

**All metrics show 0.000**

Cause: Ground truth has no labeled data  
Solution:
```bash
python scripts/validation/create_ground_truth.py --mode interactive
```

---

**"BM25 not loaded" warning**

Cause: Corpus not loaded  
Solution:
```python
agent.load_corpus()  # Call this before searching
```

---

**PostgreSQL connection failed**

Cause: Local PostgreSQL running on same port  
Solution:
```bash
lsof -i :5432  # Check what's using port 5432
brew services stop postgresql  # Stop local instance
```

---

**Airflow DAG not updating**

Cause: Airflow cached old code  
Solution:
```bash
docker-compose restart airflow-scheduler
# Or: docker exec datapipeline_airflow_scheduler touch /opt/airflow/dags/<dag_name>.py
```

---

**"Module not found" in Airflow**

Cause: Missing Python package in Docker  
Solution:
```bash
# Add to docker/requirements.txt
cd docker
docker-compose build airflow-scheduler airflow-webserver
docker-compose up -d
```

### Viewing Logs

```bash
# Airflow scheduler
docker logs datapipeline_airflow_scheduler --tail=100 -f

# Specific task
docker exec datapipeline_airflow_scheduler \
  cat /opt/airflow/logs/dag_id=sec_filings_pipeline/run_id=*/task_id=check_new_filings/attempt=1.log

# All services
docker-compose logs -f
```

---

## 🎓 Technologies

**Infrastructure:** Docker, Apache Airflow 2.7.3, PostgreSQL 15, Qdrant  
**Python:** 3.11, sentence-transformers, rank-bm25, torch, NLTK  
**Validation:** MLflow 2.9.2, fairlearn, matplotlib, scipy  
**APIs:** sec-api 1.0.19, Groq, NewsAPI  

---

## 📈 Performance Metrics

| Metric | Value |
|--------|-------|
| **Query Latency** | 50-200ms |
| **Embedding Speed** | ~100 chunks/sec (CPU) |
| **Processing Time** | 15-20 min per company |
| **Storage per Company** | ~50MB/year |
| **API Calls** | ~20-30 per day (well within free tiers) |

---
