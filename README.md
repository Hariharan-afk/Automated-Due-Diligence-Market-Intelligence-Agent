# Automated Due Diligence & Market Intelligence System

Production-ready MLOps pipeline for financial intelligence with RAG retrieval, automated validation, and bias detection.

---

## 🎯 Overview

Automated system for gathering and retrieving financial intelligence from SEC filings, Wikipedia, and news sources.

**Key Capabilities:**
- Automated daily data ingestion and processing
- Hybrid search (semantic + keyword matching)
- Comprehensive model validation with bias detection
- Experiment tracking and optimization

**Companies Tracked:** AAPL, MSFT, GOOGL, AMZN, TSLA
---

## 🚀 Quick Start

```bash
# 1. Clone and setup
git clone git@github.com:Hariharan-afk/Automated-Due-Diligence-Market-Intelligence-Agent.git
cd Automated-Due-Diligence-Market-Intelligence-Agent
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt requirements-validation.txt

# 2. Configure (add API keys to .env)
cp .env.example .env && nano .env

# 3. Start services
cd docker && docker-compose up -d && sleep 30 && cd ..

# 4. Initialize
python scripts/setup/init_databases.py
python scripts/setup/create_vector_collections.py

# 5. Setup Airflow
docker run --rm --network docker_default \
  -e AIRFLOW__DATABASE__SQL_ALCHEMY_CONN=postgresql+psycopg2://airflow:airflow@postgres:5432/airflow \
  docker-airflow-scheduler airflow db init

docker run --rm --network docker_default \
  -e AIRFLOW__DATABASE__SQL_ALCHEMY_CONN=postgresql+psycopg2://airflow:airflow@postgres:5432/airflow \
  docker-airflow-scheduler airflow users create \
  --username admin --password admin --firstname Admin --lastname User \
  --role Admin --email admin@example.com
```

**Access:**
- Airflow: http://localhost:8081 (admin/admin)
- Qdrant: http://localhost:6333/dashboard
- MLflow: `mlflow ui` → http://localhost:5000

---

## 💻 Usage

### Search with Researcher Agent

```python
from src.agents.researcher_agent import ResearcherAgent

agent = ResearcherAgent(qdrant_host='localhost', alpha=0.5, top_k=5)
agent.load_corpus()

results = agent.search("What are Apple's regulatory risks?", ticker="AAPL")
```

### Run Model Validation

```bash
# Create ground truth
python scripts/validation/create_ground_truth.py --mode sample

# Label relevant documents
python scripts/validation/create_ground_truth.py --mode interactive

# Run validation
python scripts/validation/run_complete_validation.py --alpha 0.5 --track-mlflow

# View results
mlflow ui
open results/validation/<timestamp>/retrieval_report.html
```

### Trigger Data Pipelines

```bash
# Via Airflow UI: http://localhost:8081 → Click DAG → Play button

# Via CLI
docker exec datapipeline_airflow_scheduler airflow dags trigger sec_filings_pipeline
```

---

## 📊 Validation Metrics

| Metric | Target | Description |
|--------|--------|-------------|
| **Precision@5** | ≥ 0.50 | % of retrieved docs that are relevant |
| **Recall@5** | ≥ 0.40 | % of relevant docs retrieved |
| **nDCG@5** | ≥ 0.60 | Ranking quality (position-aware) |
| **MRR** | ≥ 0.65 | Quality of first result |

**Bias Thresholds:**
- ✅ None: < 0.10 difference across slices
- ⚠️ Medium: 0.15 - 0.25 difference
- 🔴 High: > 0.25 difference (blocks deployment)

**Quality Gates:**
- nDCG@5 ≥ 0.60
- Precision@5 ≥ 0.50
- No high-severity bias

---

## 📋 Pipelines

| Pipeline | Schedule | Function |
|----------|----------|----------|
| **SEC Filings** | Daily 00:00 | Fetch 10-K/10-Q filings, extract sections, embed |
| **Wikipedia** | Weekly (Sat) | Update company pages |
| **News** | Every 6 hours | Ingest financial news (30-day retention) |
| **Cleanup** | Daily 01:00 | Remove expired data |

---

## ⚙️ Configuration

### Add Companies

`configs/companies.yaml`:
```yaml
companies:
  - ticker: NVDA
    name: NVIDIA Corporation
    cik: "0001045810"
```

### Adjust Retrieval

```python
agent = ResearcherAgent(
    alpha=0.6,    # Higher = more semantic, lower = more keyword
    top_k=10
)
```

### Pipeline Settings

`configs/development.yaml`:
```yaml
pipeline:
  chunk_size: 512
  chunk_overlap: 50
  embedding_model: "all-mpnet-base-v2"
```

---

## 🗂️ Project Structure

```
├── src/
│   ├── agents/              # Researcher agent (hybrid search)
│   ├── validation/          # IR metrics, bias detection
│   ├── tracking/            # MLflow integration
│   ├── data_ingestion/      # SEC, Wikipedia, News fetchers
│   ├── data_processing/     # Parsing, chunking
│   ├── embeddings/          # Embedding generation
│   └── storage/             # DB managers
├── airflow/dags/            # 4 production DAGs
├── scripts/validation/      # Validation runners
├── configs/                 # YAML configurations
└── docker/                  # Docker setup
```

---

## 🔬 Experiment Tracking

```python
from src.tracking.experiment_tracker import ExperimentTracker

tracker = ExperimentTracker()
evaluator = RetrievalEvaluator('data/validation/ground_truth.json')

# Test different alphas
results = tracker.run_ablation_study(
    evaluator,
    alpha_values=[0.0, 0.3, 0.5, 0.7, 1.0]
)

print(f"Best alpha: {results['best_config']['alpha']}")
```

**View in MLflow:**
```bash
mlflow ui  # http://localhost:5000
```

---

## 🐛 Troubleshooting

| Issue | Solution |
|-------|----------|
| Metrics are 0.000 | Label ground truth: `python scripts/validation/create_ground_truth.py --mode interactive` |
| PostgreSQL connection failed | Stop local postgres: `brew services stop postgresql` |
| DAG not updating | Restart: `docker-compose restart airflow-scheduler` |
| Module not found | Rebuild: `docker-compose build && docker-compose up -d` |

**View Logs:**
```bash
docker logs datapipeline_airflow_scheduler --tail=100
docker logs -f datapipeline_airflow_scheduler  # Follow live
```

---

## 🎓 Technologies

**Core:** Python 3.11, Docker, Apache Airflow 2.7.3, PostgreSQL 15, Qdrant  
**ML:** sentence-transformers, rank-bm25, torch  
**Validation:** MLflow, fairlearn, matplotlib, scipy  
**APIs:** sec-api, Groq, NewsAPI  

---

## 📈 Performance

- **Query Latency:** 50-200ms
- **Processing:** ~15-20 min per company
- **Embedding:** ~100 chunks/sec (CPU)
- **Storage:** ~50MB per company per year

---
