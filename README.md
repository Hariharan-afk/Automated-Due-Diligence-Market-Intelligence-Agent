# Automated Due Diligence & Market Intelligence Agent - Researcher Agent

## Overview
The Researcher Agent is responsible for fetching, processing, and indexing SEC filings for retrieval-augmented generation (RAG) applications.

## Features
- ✅ Natural language query parsing
- ✅ SEC filing data fetching (10-K, 10-Q)
- ✅ Table-aware document chunking
- ✅ LLM-generated table summaries
- ✅ Semantic embeddings with open-source models
- ✅ Vector database storage (Qdrant)
- ✅ PostgreSQL metadata management
- ✅ Rate limiting and caching

## Setup

### 1. Prerequisites
```bash
# Python 3.9+
python --version

# PostgreSQL 14+
psql --version

# Docker (for Qdrant)
docker --version
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Environment Configuration
```bash
cp .env.example .env
# Edit .env with your API keys and configuration
```

### 4. Start Qdrant
```bash
docker run -p 6333:6333 qdrant/qdrant
```

### 5. Initialize Database
```bash
python database/setup_database.py
```

## Usage

### Process a Company Filing
```python
from researcher_agent.src.researcher_agent import ResearcherAgent

agent = ResearcherAgent()

# Option 1: Direct filing processing
result = agent.process_company_filing("AAPL", "10-K")

# Option 2: Natural language query
result = agent.process_query(
    "Analyze Apple's risk factors from their latest annual report"
)
```

### Search Indexed Content
```python
results = agent.search("revenue growth trends", limit=10)

for result in results:
    print(f"Score: {result['score']}")
    print(f"Company: {result['metadata']['company_name']}")
    print(f"Content: {result['content']}\n")
```

## Architecture
```
User Query
    ↓
Query Parser → Company Resolver
    ↓
SEC API Fetcher
    ↓
Document Processor (Parse sections, identify tables)
    ↓
Table Processor (LLM summaries)
    ↓
Embeddings Manager (Generate vectors)
    ↓
Qdrant (Vector DB) + PostgreSQL (Metadata)
```

## Project Structure
```
researcher_agent/
├── src/
│   ├── query_parser.py          # Parse user queries
│   ├── data_fetcher.py           # Fetch SEC filings
│   ├── document_processor.py     # Parse and chunk documents
│   ├── table_processor.py        # Generate table summaries
│   ├── embeddings_manager.py     # Embeddings and Qdrant
│   ├── metadata_manager.py       # PostgreSQL operations
│   └── researcher_agent.py       # Main orchestrator
├── assets/
│   └── company_tickers.json
└── data/

database/
├── init_db.sql                   # Database schema
└── setup_database.py             # Setup script

utils/
└── config.py                     # Configuration management
```

## Configuration

Key configuration options in `utils/config.py`:
- **Embedding Model**: `BAAI/bge-large-en-v1.5` (1024 dimensions)
- **Chunk Size**: 500 tokens with 75 token overlap
- **Rate Limit**: 8 requests/second to SEC API
- **Table Summary Model**: `llama-3.3-70b-versatile`

## Testing
```bash
# Test individual components
python researcher_agent/src/data_fetcher.py
python researcher_agent/src/document_processor.py
python researcher_agent/src/table_processor.py

# Run full pipeline
python researcher_agent/src/researcher_agent.py
```

## Next Steps
- [ ] Add 10-Q support
- [ ] Saving processed and raw data in postgreSQL
- [ ] Implement freshness checking
- [ ] test all components
- [ ] Add batch processing for multiple companies
- [ ] Build API endpoint for downstream agents
- [ ] Add monitoring and logging

