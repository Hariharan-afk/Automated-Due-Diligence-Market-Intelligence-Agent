# SEC Filing Processor - EdgarTools Integration

This guide explains how to use the updated SEC filing processor that uses **edgartools** (free, no API key required) to fetch and process 10-K and 10-Q filings.

## Overview

The pipeline:
1. Fetches SEC filings using **CIK** (not ticker) from edgartools
2. Extracts **full document text** (entire filing, not specific sections)
3. Chunks the documents with overlap
4. Generates metadata for each chunk
5. Calculates statistics (min/max/avg chunk sizes by company/filing type)
6. Saves outputs as JSON files

## Setup

### 1. Install Dependencies

```bash
pip install edgartools pyyaml tqdm
```

### 2. Configure User Identity

Edit `configs/sec_config.yaml` and replace the placeholder email with your actual email:

```yaml
# EdgarTools identity (required by SEC for compliance)
user_identity: "your.actual.email@example.com"
```

> [!IMPORTANT]
> The SEC requires you to identify yourself when accessing their data. Use a real email address.

### 3. Review Configuration

**Companies to process** (`configs/companies.yaml`):
- Contains list of companies with ticker, name, and **CIK**
- Currently configured: AAPL, MSFT, GOOGL, AMZN, TSLA

**SEC fetch configuration** (`configs/sec_config.yaml`):
- `fetch_start_date`: Start date for filings (default: "2024-01-01")
- `fetch_end_date`: End date (null = today)
- `user_identity`: Your email (required)
- `chunk_size`: Chunk size in tokens (default: 800)
- `overlap`: Overlap between chunks (default: 100)

## Usage

### Basic Usage - Process All Companies

```bash
cd Data_Pipeline
python scripts/fetch_and_process_sec.py
```

This will:
- Fetch 10-K and 10-Q filings for all companies in `companies.yaml`
- Process filings from `fetch_start_date` to today
- Save outputs to `data/` folder

### Test Mode - Single Company

Test with just one company (first in the list):

```bash
python scripts/fetch_and_process_sec.py --test-mode
```

### Process Specific Company by CIK

Process only a specific company:

```bash
python scripts/fetch_and_process_sec.py --cik 0000320193  # Apple
```

### Command-Line Options

```bash
python scripts/fetch_and_process_sec.py --help

Options:
  --test-mode          Test mode: only process first company
  --cik CIK           Process only specific CIK
  --config-dir DIR    Configuration directory (default: configs)
  --output-dir DIR    Output directory (default: data)
```

## Outputs

The script generates two JSON files in the `data/` folder:

### 1. Chunks File: `sec_chunks_<timestamp>.json`

Contains all chunks with metadata:

```json
{
  "metadata": {
    "generated_at": "2024-12-08T13:00:00",
    "data_source": "sec",
    "total_companies": 5,
    "total_filings": 25,
    "total_chunks": 1250,
    "chunk_size": 800,
    "chunk_overlap": 100
  },
  "chunks": [
    {
      "chunk_id": "AAPL_sec_0001193125-24-123456_0",
      "company": "Apple Inc.",
      "ticker": "AAPL",
      "cik": "0000320193",
      "filing_type": "10-K",
      "filing_date": "2024-11-01",
      "fiscal_year": 2024,
      "fiscal_quarter": null,
      "filing_url": "https://www.sec.gov/...",
      "accession_number": "0001193125-24-123456",
      "chunk_text": "...",
      "chunk_length": 1250,
      "chunk_index": 0,
      "total_chunks_in_filing": 45,
      "data_source": "sec",
      "fetched_date": "2024-12-08T13:00:00"
    }
  ]
}
```

### 2. Statistics File: `chunk_statistics_<timestamp>.json`

Contains chunk size statistics:

```json
{
  "metadata": {
    "generated_at": "2024-12-08T13:00:00",
    "total_chunks": 1250
  },
  "global_stats": {
    "total_chunks": 1250,
    "min_chunk_size": 450,
    "max_chunk_size": 3200,
    "avg_chunk_size": 1180.5,
    "total_characters": 1475625
  },
  "by_company": {
    "AAPL": {
      "company_name": "Apple Inc.",
      "total_chunks": 250,
      "min_chunk_size": 500,
      "max_chunk_size": 3200,
      "avg_chunk_size": 1200.3,
      "by_filing_type": {
        "10-K": {...},
        "10-Q": {...}
      }
    }
  },
  "by_data_source": {
    "sec": {...}
  },
  "by_filing_type": {
    "10-K": {...},
    "10-Q": {...}
  }
}
```

## Example Workflow

```bash
# 1. Test with one company first
python scripts/fetch_and_process_sec.py --test-mode

# 2. Check the outputs
ls -la data/sec_chunks_*.json
ls -la data/chunk_statistics_*.json

# 3. If successful, process all companies
python scripts/fetch_and_process_sec.py

# 4. Review statistics
python -c "
import json
stats = json.load(open('data/chunk_statistics_<latest>.json'))
print(f'Total chunks: {stats[\"global_stats\"][\"total_chunks\"]}')
print(f'Avg chunk size: {stats[\"global_stats\"][\"avg_chunk_size\"]:.1f} chars')
"
```

## Architecture

```
fetch_and_process_sec.py (Orchestration)
    │
    ├─→ SECFetcher (src/data_ingestion/sec_fetcher.py)
    │   └─→ edgartools (Company.get_filings())
    │
    ├─→ TextChunker (src/data_processing/chunker.py)
    │   └─→ Chunk documents with overlap
    │
    └─→ calculate_statistics (src/utils/chunk_stats.py)
        └─→ Calculate min/max/avg by company/source/type
```

## Key Features

✅ **No API Key Required** - edgartools is free  
✅ **CIK-based Fetching** - Direct company identification  
✅ **Full Document Processing** - Entire filing, not just sections  
✅ **Smart Chunking** - Preserves context with overlap  
✅ **Rich Metadata** - Complete filing information  
✅ **Comprehensive Statistics** - Multi-level grouping  
✅ **Progress Tracking** - Progress bars and logging  
✅ **Error Handling** - Continues on individual failures  

## Troubleshooting

### Error: "edgartools not found"

```bash
pip install edgartools
```

### Error: "user_identity not set"

Edit `configs/sec_config.yaml` and add your email:
```yaml
user_identity: "your.email@example.com"
```

### Error: HTTP 403 from SEC

The SEC is rate-limiting. The script includes delays, but if you process many companies, you may need to wait and retry.

### Empty Results

Check:
- Date range in `sec_config.yaml` (filings may be outside date range)
- CIK is correct in `companies.yaml`
- Company has filed 10-K/10-Q during the date range

## Next Steps

After generating chunks:
1. Use chunks for RAG (Retrieval Augmented Generation)
2. Embed chunks with FinE5 or similar financial embeddings
3. Store in vector database (Qdrant, Pinecone, etc.)
4. Build Q&A or analysis applications

## Differences from Previous Implementation

| Feature | Old (SEC-API) | New (edgartools) |
|---------|---------------|------------------|
| API Key | Required ($) | Not required (free) |
| Fetch Method | QueryApi | Company(cik).get_filings() |
| Content | Specific sections | Full document |
| Fiscal Quarters | Manual calculation | Automatic from edgartools |
| Cost | ~$50-200/month | Free |
