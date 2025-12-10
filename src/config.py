"""
config.py - System Configuration
Using GCP Vertex AI with Gemini 2.0 Flash Experimental
"""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# GCP PROJECT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

GCP_PROJECT_ID = "coherent-rite-473622-j0"
GCP_LOCATION = "us-central1"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# QDRANT (Same for fake data and real pipeline)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

import os

QDRANT_CONFIG = {
    "url": os.getenv("QDRANT_URL"),
    "api_key": os.getenv("QDRANT_API_KEY"),
    "collection_name": os.getenv("QDRANT_COLLECTION", "financial_data")
}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# EMBEDDING CONFIG
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

EMBEDDING_CONFIG = {
    "model": "text-embedding-004",
    "dimension": 768  # Google embeddings are 768-dimensional
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# LLM CONFIG - Local (Ollama)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

LLM_CONFIG = {
    "provider": "vertex",
    "base_url": "http://localhost:11434",
    "model": "gemini-2.5-flash", # Latest Stable (June 2025)
    "embedding_model": "text-embedding-004"
}

AGENT_CONFIG = {
    "orchestrator": {
        "model": LLM_CONFIG["model"],
        "temperature": 0.1
    },
    "planner": {  # Formerly Analyser
        "model": LLM_CONFIG["model"],
        "temperature": 0.3
    },
    "researcher": {
        "model": LLM_CONFIG["model"],
        "temperature": 0.2
    },
    "synthesiser": {
        "model": LLM_CONFIG["model"],
        "temperature": 0.5
    },
    "evaluator": {
        "model": LLM_CONFIG["model"],
        "temperature": 0.1
    }
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SEARCH CONFIG
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SEARCH_CONFIG = {
    "alpha": 0.7,              # 70% semantic, 30% keyword
    "initial_k": 50,           # Candidates from hybrid search (Increased for better recall)
    "final_k": 5,              # Results after re-ranking
    "reranker_model": "cross-encoder/ms-marco-MiniLM-L-6-v2"
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CHUNKING
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CHUNKING_CONFIG = {
    "chunk_size": 512,
    "overlap": 50
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# LOGGING CONFIG
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

import logging

LOGGING_CONFIG = {
    "level": logging.INFO,
    "agents_log_file": "logs/agents.log",
    "system_log_file": "logs/system.log"
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# BIAS CONFIG
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

BIAS_CONFIG = {
    "min_score_threshold": 0.4,  # Groups below this score get boosted
    "boost_factor": 1.05          # 5% boost to retrieval scores
}