# 🚀 Unified Due Diligence Data Pipeline

Automated data pipeline for fetching, processing, embedding, and storing financial data from multiple sources to power AI-driven due diligence research.

## 📋 Overview

This pipeline integrates three major data sources:
- **SEC Filings** (10-K, 10-Q) - Corporate financial reports
- **Wikipedia** - Company background and context
- **Financial News** - Real-time market intelligence

### Data Flow
```
Data Sources → Fetch → Parse → Chunk → Embed → Store
                                              ↓
                                    PostgreSQL + Qdrant
```

## ✨ Key Features

### Multi-Source Data Ingestion
- **SEC Filings**: Daily monitoring for new 10-K/10-Q filings
- **Wikipedia**: Weekly refresh with change detection
- **News**: Every 6 hours with smart relevance scoring

### Intelligent Processing
- **Section-Aware Chunking**: Different chunk sizes for different SEC sections (Risk Factors: 768 tokens, Financial Statements: 512 tokens)
- **Table Extraction**: Converts HTML tables to markdown with LLM-based summarization
- **Quality Controls**: English detection, deduplication, validation at each step

### Automated Orchestration
- **Airflow DAGs**: 4 production pipelines with proper scheduling
- **Error Handling**: Automatic retries with exponential backoff
- **Monitoring**: Comprehensive logging and statistics tracking

### Data Retention
- **SEC Filings**: Permanent storage
- **Wikipedia**: Update in place, track revisions
- **News**: 3-day sliding window for freshness

## 🏗️ Architecture

### Data Pipeline Schedules

| Pipeline | Schedule | Description |
|----------|----------|-------------|
| SEC Filings | Daily at midnight | Monitor & process new 10-K/10-Q filings |
| Wikipedia | Sundays at 3 AM | Weekly refresh with change detection |
| News | Every 6 hours | Fetch recent articles with relevance filtering |
| Cleanup | Daily at 1 AM | Delete news older than 3 days |

### Technology Stack

- **Orchestration**: Apache Airflow
- **Databases**: PostgreSQL (metadata), Qdrant (vectors)
- **Embeddings**: SentenceTransformers (all-mpnet-base-v2, 768 dims)
- **LLM**: Groq (Llama 3.1 8B for table summarization)
- **Containerization**: Docker Compose

### Tracked Companies

- Apple Inc. (AAPL)
- Microsoft Corporation (MSFT)
- Alphabet Inc. (GOOGL)
- Amazon.com Inc. (AMZN)
- Tesla Inc. (TSLA)

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.9+
- 8GB+ RAM recommended

### Installation

1. **Clone and navigate to the combined pipeline**
```bash
cd combined_data_pipeline
```

2. **Set up environment variables**
```bash
cp .env.example .env
# Edit .env with your API keys
```

3. **Start services**
```bash
docker-compose up -d
```

4. **Initialize databases**
```bash
python scripts/setup/init_databases.py
python scripts/setup/create_vector_collections.py
```

5. **Access Airflow UI**
```
http://localhost:8080
Username: admin
Password: (from .env)
```

## 🔑 API Keys Required

### Required
- **Groq API** (Free tier: 14,400 req/day)
  - Get at: https://console.groq.com
  - Used for: Table summarization

- **NewsAPI** (Free tier: 1000 req/day)
  - Get at: https://newsapi.org
  - Used for: Financial news

### Optional
- **SEC API** (sec-api.io)
  - Enhances SEC data fetching
  - Free tier available

## 📊 Usage

### Running Pipelines

**Trigger SEC Pipeline Manually**
```bash
airflow dags trigger sec_filings_pipeline
```

**Trigger Wikipedia Refresh**
```bash
airflow dags trigger wikipedia_refresh_pipeline
```

**Trigger News Ingestion**
```bash
airflow dags trigger news_ingestion_pipeline
```

### Monitoring

**View Pipeline Statistics**
```bash
python scripts/validation/check_data_quality.py
```

**Check Airflow Logs**
```bash
docker-compose logs -f airflow-scheduler
```

## 📁 Project Structure

```
combined_data_pipeline/
├── airflow/
│   ├── dags/                    # 4 Airflow DAGs
│   └── plugins/                 # Custom operators & sensors
├── src/
│   ├── data_ingestion/          # SEC, Wikipedia, News fetchers
│   ├── data_processing/         # Parsers, chunkers, cleaners
│   ├── embeddings/              # Embedding generation
│   ├── storage/                 # PostgreSQL, Qdrant, Blob
│   └── utils/                   # Config, logging, retry
├── configs/                     # YAML configurations
├── scripts/                     # Setup & maintenance scripts
├── tests/                       # Minimal unit & integration tests
├── data/                        # Raw, processed, cached data
└── docker/                      # Docker configurations
```

## 🧪 Testing

**Run Unit Tests**
```bash
pytest tests/unit/ -v
```

**Run Integration Tests**
```bash
pytest tests/integration/ -v
```

**Run All Tests**
```bash
pytest tests/ -v
```

## 🔧 Configuration

### Main Config: `configs/development.yaml`

```yaml
database:
  postgres: {host: postgres, port: 5432, database: due_diligence_dev}
  qdrant: {host: qdrant, port: 6333, collection: due_diligence_kb}

pipeline:
  chunk_size: 512
  chunk_overlap: 50
  batch_size: 32
  embedding_model: all-mpnet-base-v2

apis:
  sec: {rate_limit: 10}
  groq: {model: llama-3.1-8b-instant}
  newsapi: {rate_limit: 1000}
```

### Section-Specific Config: `configs/sections_config.yaml`

Defines different chunk sizes for SEC sections:
- Risk Factors (1A): 768 tokens, 100 overlap
- MD&A (7): 768 tokens, 100 overlap
- Business (1): 512 tokens, 50 overlap
- Financial Statements (8): 512 tokens, 50 overlap

### Companies: `configs/companies.yaml`

List of tracked companies with ticker, CIK, sector, industry.

## 📈 Database Schema

### PostgreSQL Tables

**companies** - Company master data
**sec_filings** - SEC filing metadata & status
**wikipedia_pages** - Wikipedia page revisions
**news_articles** - News articles with delete_after timestamps

### Qdrant Collection

**due_diligence_kb** - 768-dimensional vectors with metadata filtering

## 🛠️ Maintenance

### Rebuild Vector Index
```bash
python scripts/maintenance/rebuild_index.py
```

### Manual Cleanup
```bash
python scripts/maintenance/cleanup_old_data.py
```

### Backup Metadata
```bash
python scripts/maintenance/backup_metadata.py
```

## 🐛 Troubleshooting

### Common Issues

**Airflow DAGs not showing up**
```bash
# Restart scheduler
docker-compose restart airflow-scheduler
```

**Database connection errors**
```bash
# Check PostgreSQL is running
docker-compose ps postgres
# Reinitialize if needed
python scripts/setup/init_databases.py
```

**Out of memory errors**
```bash
# Reduce batch_size in configs/development.yaml
# Restart services
docker-compose restart
```

**API rate limits**
- SEC: Max 10 requests/sec (built-in rate limiter)
- NewsAPI: 1000 requests/day (monitor usage)
- Groq: 14,400 requests/day (cached summaries reduce usage)

## 📝 Development

### Adding New Companies

Edit `configs/companies.yaml`:
```yaml
- ticker: NFLX
  name: Netflix Inc.
  cik: "0001065280"
  sector: Communication Services
  industry: Entertainment
```

Then reinitialize:
```bash
python scripts/setup/init_databases.py
```

### Custom Data Sources

1. Create fetcher in `src/data_ingestion/`
2. Create parser in `src/data_processing/`
3. Update `ChunkingEngine` for source-specific logic
4. Create Airflow DAG in `airflow/dags/`

## 🤝 Contributing

1. Create feature branch
2. Add tests for new functionality
3. Update documentation
4. Submit pull request

## 📄 License

MIT License - see LICENSE file for details

## 🙏 Acknowledgments

- SEC EDGAR API
- Wikipedia API
- NewsAPI & GDELT
- Groq for LLM API
- Qdrant for vector database
- Apache Airflow community

## 📞 Support

For issues and questions:
- GitHub Issues: [Your repo URL]
- Email: research@university.edu

---

**Status**: ✅ Production Ready
**Version**: 1.0.0
**Last Updated**: 2025-01-18
