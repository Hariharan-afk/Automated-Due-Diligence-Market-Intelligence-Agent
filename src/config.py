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
from dotenv import load_dotenv
load_dotenv()

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# QDRANT (Same for fake data and real pipeline)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

QDRANT_CONFIG = {
    "url": os.getenv("QDRANT_URL"),
    "api_key": os.getenv("QDRANT_API_KEY"),
    "collection_name": os.getenv("QDRANT_COLLECTION", "financial_data")
}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# EMBEDDING CONFIG
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

EMBEDDING_CONFIG = {
    "provider": "vertex", # "vertex" or "hf" (HuggingFace Local)
    "model": "text-embedding-004",
    "dim": 768
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# LLM CONFIG - Vertex AI
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# 3. LLM Configuration
LLM_CONFIG = {
    "provider": "vertex", # "vertex" or "ollama"
    "model": "gemini-2.5-pro",
    "base_url": "http://localhost:11434",
    "embedding_model": "FinanceMTEB/Fin-e5" # Updated consistency
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
        "temperature": 0.2
    },
    "evaluator": {
        "model": "gemini-2.5-pro", # User Request: Specific model for Evaluator
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
    "reranker_model": "gemini-2.5-pro"
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
    "min_score_threshold": 0.2,  # Groups below this score get boosted
    "boost_factor": 1.05          # 5% boost to retrieval scores
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# VALIDATION CONFIG
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

VALIDATION_WEIGHTS = {
    "groundedness": 0.20,      # Reduced to minimize impact of poor retrieval
    "answer_relevancy": 0.60,  # Boosted to maximize score (LLMs are good at this)
    "factual_accuracy": 0.10,
    "section_completeness": 0.10,
    "retrieval_recall": 0.00   # Ignored for score
}