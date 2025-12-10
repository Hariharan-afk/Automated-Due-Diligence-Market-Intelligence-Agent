# Market Due Diligence AI (Agentic RAG) 🤖 📈

A production-grade Multi-Agent AI system for financial analysis, powered by **LangGraph**, **FastAPI**, **Streamlit**, and **Google Vertex AI**.

This system autonomously:
1.  **Deconstructs** complex queries (Planner Agent).
2.  **Researches** live data from SEC filings, News, and Wikipedia (Researcher Agent).
3.  **Synthesizes** findings into a professional report (Synthesiser Agent).
4.  **Validates** accuracy and hallucinations (Evaluator Agent).

---

## ⚡ Quick Start (For Developers)

### 1. Prerequisites
*   **Python 3.10+**
*   **Google Cloud SDK** (For deployment)
*   **Docker** (For containerization)

### 2. Setup Environment
```bash
# 1. Clone & Enter
git clone <repo_url>
cd agents-repo

# 2. Create Virtual Env
python -m venv .venv
source .venv/bin/activate

# 3. Install Dependencies
pip install -r requirements.txt
```

### 3. Configure Secrets (`.env`)
Create a `.env` file in the root directory:
```properties
# Google Cloud (Required)
GOOGLE_APPLICATION_CREDENTIALS=vertex-key.json
PROJECT_ID=coherent-rite-473622-j0
LOCATION=us-central1

# Vector Database (Qdrant)
QDRANT_URL=https://your-qdrant-cluster.qdrant.tech
QDRANT_API_KEY=your-qdrant-key
```
*Make sure `vertex-key.json` is present in the root folder!*

---

## 🤝 For New Developers (Handoff Guide)

## 🤝 For New Developers (Handoff Guide)

**If you just received this code folder, follow these steps:**

### Step 1: Get the Keys 🔑
Ask the previous owner (Saumith) for:
1.  `vertex-key.json` (Google Cloud Service Account Key)
2.  `.env` file (API Keys)
*Place these in the root folder.*

### Step 2: Choose Your Path

**Option A: "I just want to RUN it" (No Install Needed) 🐳**
If you have Docker, you don't need to install Python or libraries. Just run:
```bash
# Terminal 1: Backend
docker run -p 8080:8080 --env-file .env us-central1-docker.pkg.dev/coherent-rite-473622-j0/agents-repo/agent-api:v2

# Terminal 2: Frontend
docker run -p 8501:8501 us-central1-docker.pkg.dev/coherent-rite-473622-j0/agents-repo/agent-ui:v1
```
*Access App at http://localhost:8501*

**Option B: "I want to EDIT the code" (Developer Mode) 💻**
To change the code, you need Python:
1.  Create Env: `python -m venv .venv && source .venv/bin/activate`
2.  Install: `pip install -r requirements.txt`
3.  Run:
    *   `uvicorn src.api:api --reload --port 8080`
    *   `streamlit run src/ui/app.py`

---

---

## 🚀 Running Locally

You can run the full stack (UI + Backend) on your machine.

**Terminal 1: The Backend (API)**
```bash
uvicorn src.api:api --reload --port 8080
```
*Test it: Open http://localhost:8080/docs*

**Terminal 2: The Frontend (UI)**
```bash
streamlit run src/ui/app.py
```
*Access App: http://localhost:8501*

### Option 2: Run with Docker (Cleaner)
If you don't want to install Python dependencies, you can run the Docker image directly:

```bash
# Backend
docker run -p 8080:8080 --env-file .env us-central1-docker.pkg.dev/coherent-rite-473622-j0/agents-repo/agent-api:v2

# Frontend
docker run -p 8501:8501 us-central1-docker.pkg.dev/coherent-rite-473622-j0/agents-repo/agent-ui:v1
```

---

## ☁️ Cloud Deployment

### 1. Backend API (GKE)
The backend runs on Google Kubernetes Engine (GKE) for high availability.

```bash
# 1. Build Backend Image (Use --no-cache if debugging)
docker build --no-cache --platform linux/amd64 -t us-central1-docker.pkg.dev/coherent-rite-473622-j0/agents-repo/agent-api:v2 .

# 2. Push to Registry
docker push us-central1-docker.pkg.dev/coherent-rite-473622-j0/agents-repo/agent-api:v2

# 3. Update Kubernetes Deployment
kubectl set image deployment/agent-api agent-api=us-central1-docker.pkg.dev/coherent-rite-473622-j0/agents-repo/agent-api:v2
```

### 2. Frontend UI (Cloud Run)
The frontend runs on Cloud Run (Serverless) for cost efficiency.

```bash
# 1. Build Frontend Image (Dockerfile.frontend)
docker build -f Dockerfile.frontend --platform linux/amd64 -t us-central1-docker.pkg.dev/coherent-rite-473622-j0/agents-repo/agent-ui:v1 .

# 2. Push to Registry
docker push us-central1-docker.pkg.dev/coherent-rite-473622-j0/agents-repo/agent-ui:v1

# 3. Deploy to Cloud Run
gcloud run deploy agent-ui \
    --image us-central1-docker.pkg.dev/coherent-rite-473622-j0/agents-repo/agent-ui:v1 \
    --platform managed \
    --region us-central1 \
    --allow-unauthenticated \
    --port 8501
```

---

## 📂 Project Structure

*   `src/agents/`: Core logic for the 5 agents (Planner, Researcher, etc.).
*   `src/ui/`: Streamlit Application (Chat Interface + Admin Dashboard).
*   `src/graph.py`: LangGraph state machine definition.
*   `k8s/`: Kubernetes deployment manifests.
*   `Dockerfile`: Production container config.

## 🛠 Troubleshooting

*   **UI shows "Connection Timeout"**: 
    *   The complex queries might take >120s. The UI handles this gracefully now.
*   **Admin Dashboard shows "404"**:
    *   This means the backend is running an old image. Run the **Cloud Deployment** steps above to push a new tag (`v2`, `v3`...) to force an update.
