# MLOps Project: Agentic RAG Pipeline with Bias Detection

This project implements an **Agentic RAG (Retrieval-Augmented Generation)** system designed for financial due diligence. It features a multi-agent architecture, hybrid search with re-ranking, and a robust validation pipeline to detect and mitigate bias across different companies.

This repository is structured to meet the **Model Development** and **MLOps** requirements of the course.

---

## 1. Overview
We utilize a **Retrieval-Augmented Generation (RAG)** approach, leveraging pre-trained Large Language Models (Gemini 2.0) and embeddings. Instead of fine-tuning a model weights, we optimize the retrieval pipeline and agentic workflows.

**Core Technologies:**
-   **LLM**: `gemini-2.0-flash-exp` (Google Vertex AI)
-   **Embeddings**: `text-embedding-004`
-   **Vector DB**: Qdrant Cloud
-   **Orchestration**: Custom Multi-Agent System (Analyser, Researcher, Synthesiser)

---

## 2. Model Development & Code

### 2.1 Data Loading
Data is processed and stored in **Qdrant** (Vector Database). For validation, we load a versioned test dataset acting as our "Hold-out Set".
-   **Code**: `src/model_validation/test_dataset.py` (Loads `test_dataset.json`)

### 2.2 Model Architecture (RAG)
Our "Model" is the composite system of agents:
1.  **Analyser**: Decomposes queries.
2.  **Researcher**: Performs Hybrid Search (BM25 + Vector) and Re-ranking (`cross-encoder/ms-marco-MiniLM-L-6-v2`).
3.  **Synthesiser**: Generates answers using retrieved context.

### 2.3 Model Validation
We implement a rigorous validation pipeline on a hold-out dataset (`test_dataset.json`).
-   **Script**: `src/model_validation/run_validation.py`
-   **Metrics**:
    -   **Retrieval Recall (Recall@k)**: Measures retrieval quality.
    -   **Groundedness**: Measures hallucination rates.
    -   **Citation F1**: Ensures sources are correctly cited.
    -   **Answer Relevancy**: Ensures the query is actually answered.

### 2.4 Bias Detection (Slicing)
We evaluate model performance across different **Data Slices** (specifically, by Company/Ticker) to ensure fairness.
-   **Script**: `src/model_validation/bias_check.py`
-   **Methodology**: We group test cases by Company (e.g., Microsoft, Tesla, Apple) and compute metrics for each group.
-   **Thresholds**: The pipeline fails if any group's performance drops below 60% or if the disparity between groups exceeds 20%.

### 2.5 Artifact Registry
The finalized model (application code + environment) is containerized and pushed to **Google Artifact Registry (GAR)**.
-   **Registry**: `us-central1-docker.pkg.dev/[PROJECT_ID]/agents-repo/ml-app`

---

## 3. CI/CD Pipeline Automation

We use **GitHub Actions** to automate the MLOps lifecycle.

**Workflow File**: `.github/workflows/ci-cd.yml`

### Pipeline Steps:
1.  **Trigger**: Pushes to **any branch** (`**`).
2.  **Automated Validation**:
    -   Runs `bias_check.py`.
    -   Calculates Global and Per-Group metrics.
    -   **Gate**: Fails the pipeline if Bias Checks or Quality Thresholds are not met.
3.  **Containerization**: Builds a Docker image.
4.  **Registry Push**:
    -   Pushes the validated image to **Google Artifact Registry**.
    -   Tags: `:latest` and `:sha` (enabling rollback to specific commits).

---

## 4. Project Structure

```text
src/
├── agents/             # Agent Logic (Model)
├── tools/              # Tools (Search, Reranker)
├── model_validation/   # MLOps Validation Suite
│   ├── bias_check.py           # Bias Detection & Slicing
│   ├── run_validation.py       # Performance Validation
│   ├── metrics.py              # Metric Definitions
│   └── test_dataset.json       # Hold-out Dataset
├── config.py           # Hyperparameters
└── main.py             # App Entry Point
```

## 7. How to Run

### Local Validation
```bash
python src/model_validation/run_validation.py
```

### Bias Check
```bash
python src/model_validation/bias_check.py
```

### Docker Execution
```bash
docker compose exec -it ml-app python src/model_validation/bias_check.py
```
