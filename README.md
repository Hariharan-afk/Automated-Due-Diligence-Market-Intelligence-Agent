project_structure
```
due-diligence-agent/
├─ README.md
├─ CONTRIBUTING.md
├─ CODE_OF_CONDUCT.md
├─ LICENSE
├─ .gitignore
├─ .gitattributes
├─ .pre-commit-config.yaml
├─ pyproject.toml                  # poetry or hatch; or use requirements.txt
├─ requirements.txt                # if not using pyproject
├─ .env.example                    # all needed env keys with dummy values
├─ Makefile                        # common dev & pipeline commands
│
├─ configs/                        # typed, composable configs (Hydra or pydantic)
│  ├─ base.yaml
│  ├─ dev.yaml
│  ├─ prod.yaml
│  ├─ sources/
│  │  ├─ edgar.yaml
│  │  ├─ gdelt.yaml
│  │  └─ wikipedia.yaml
│  ├─ rag/
│  │  ├─ chunking.yaml
│  │  ├─ embeddings.yaml
│  │  └─ retriever.yaml
│  ├─ llm/
│  │  ├─ provider_openai.yaml
│  │  └─ policies.yaml             # grounding, max_length, temperature
│  └─ report/
│     ├─ template.yaml
│     └─ acceptance_gates.yaml
│
├─ prompts/                        # versioned prompt contracts
│  ├─ researcher.md
│  ├─ analyst.md
│  ├─ synthesizer.md
│  └─ evaluator.md
│
├─ src/
│  ├─ __init__.py
│  ├─ app/                         # API/UI entrypoints
│  │  ├─ api.py                    # FastAPI service (trigger runs, status, fetch report)
│  │  └─ ui_streamlit/             # optional Streamlit prototype
│  │     └─ app.py
│  ├─ core/                        # shared utilities
│  │  ├─ logging.py
│  │  ├─ config.py                 # loads configs/*
│  │  ├─ storage.py                # GCS/S3 + local paths
│  │  ├─ hashing.py                # content hashes for caching
│  │  ├─ schemas.py                # pydantic models for Facts/Chunks/Reports
│  │  ├─ tracing.py                # OpenTelemetry integration
│  │  └─ errors.py
│  ├─ ingest/                      # Phase 2
│  │  ├─ edgar_client.py           # CIK lookup, submissions JSON, throttled fetch
│  │  ├─ gdelt_client.py
│  │  ├─ wikipedia_client.py
│  │  ├─ fetch_runner.py           # parallel fetch, retries, manifest build
│  │  └─ manifest.py               # immutable run manifest
│  ├─ normalize/                   # Phase 3: normalize → dedup → chunk → index
│  │  ├─ parse_edgar.py            # PDF/HTML → clean text + sections
│  │  ├─ parse_news.py
│  │  ├─ deduplicate.py            # URL canonicalization + minhash/embeddings
│  │  ├─ chunker.py                # 400–800 token windows, overlap, metadata
│  │  ├─ embeddings.py
│  │  ├─ index_vector.py           # FAISS/Milvus/Pinecone adapters
│  │  └─ index_keyword.py          # BM25
│  ├─ agents/                      # Phase 4–6
│  │  ├─ researcher.py             # retrieves into KB; returns candidate chunks
│  │  ├─ analyst.py                # extracts structured facts w/ citations
│  │  ├─ synthesizer.py            # template-driven report writer (cited)
│  │  ├─ evaluator.py              # groundedness, completeness, freshness checks
│  │  └─ toolbox.py                # small tools: ratio calc, time-series clean
│  ├─ pipeline/                    # orchestration glue
│  │  ├─ dag_prefect.py            # Prefect flow (default)
│  │  ├─ dag_airflow.py            # optional Airflow DAG
│  │  ├─ run_local.py              # CLI: run one company end-to-end
│  │  └─ triggers.py               # EDGAR/newsevent watchers
│  ├─ report/
│  │  ├─ templates/
│  │  │  ├─ html/
│  │  │  │  └─ base.html.j2        # Jinja2 template with citation anchors
│  │  │  └─ pdf/
│  │  │     └─ base.tex.j2         # optional LaTeX template
│  │  └─ render.py                 # HTML/PDF renderer; diff output
│  ├─ evaluate/                    # automated quality metrics
│  │  ├─ groundedness.py
│  │  ├─ citation_coverage.py
│  │  ├─ completeness.py
│  │  ├─ bench_runner.py           # nightly eval over test companies
│  │  └─ goldsets/                 # small curated eval set
│  └─ monitor/
│     ├─ metrics.py                # token usage, latency, costs
│     ├─ exporters.py              # Prometheus/OpenTelemetry
│     └─ dashboard/                # Grafana JSON or Cloud Monitoring setup docs
│
├─ data/                           # DVC/LakeFS tracked pointers; not raw blobs
│  ├─ .gitignore                   # ignore large artifacts
│  ├─ dvc.yaml                     # stages for ingest→normalize→index
│  └─ params.yaml                  # DVC params (chunk size, top_k, etc.)
│
├─ artifacts/                      # .gitignored (local runs)
│  ├─ raw/                         # /raw/{source}/{date}/{id}.*
│  ├─ normalized/
│  ├─ chunks/
│  ├─ indices/
│  ├─ notes/                       # structured facts JSON
│  ├─ analysis/                    # derived metrics JSON
│  ├─ reports/                     # rendered HTML/PDF
│  └─ qa/                          # evaluator outputs
│
├─ infra/                          # deploy targets
│  ├─ docker/
│  │  ├─ Dockerfile.app
│  │  ├─ Dockerfile.worker
│  │  └─ Dockerfile.vector
│  ├─ k8s/                         # GKE manifests (or Helm)
│  │  ├─ deployment-app.yaml
│  │  ├─ deployment-worker.yaml
│  │  ├─ service.yaml
│  │  └─ hpa.yaml
│  ├─ helm/
│  │  └─ due-diligence/...
│  └─ terraform/                   # optional: GCS, GKE, Secret Manager
│     ├─ main.tf
│     └─ variables.tf
│
├─ .github/
│  └─ workflows/
│     ├─ ci.yml                    # lint, typecheck, tests
│     ├─ build_push.yml            # docker build & push
│     └─ deploy.yml                # prod deploy (on tag)
│
├─ tests/
│  ├─ unit/
│  │  ├─ test_chunker.py
│  │  ├─ test_deduplicate.py
│  │  └─ test_schemas.py
│  ├─ integration/
│  │  ├─ test_ingest_roundtrip.py
│  │  └─ test_rag_retrieval.py
│  └─ e2e/
│     └─ test_company_run.py       # mocks external APIs; verifies citations
│
└─ notebooks/                      # exploratory; kept lightweight
   ├─ 01_ingest_playground.ipynb
   └─ 02_rag_eval.ipynb
```

current work:

```
due-diligence-agent/
├─ README.md
├─ LICENSE
├─ pyproject.toml                # or requirements.txt + setup.cfg
├─ .env.example                  # SEC_USER_AGENT, DATABASE_URL, etc.
├─ .gitignore
├─ Makefile
├─ configs/
│  ├─ edgar.defaults.yaml        # rate limits, paths, chunk sizes, models
│  └─ logging.yaml               # log levels/format/rotation
├─ docs/
│  ├─ architecture.md
│  └─ rag_playbook.md
├─ scripts/                      # thin CLIs (users run these)
│  ├─ fetch_filings.py           # calls src/.../ingest pipeline
│  ├─ parse_filings.py           # HTML→MD + sectionize + XBRL facts
│  ├─ index_filings.py           # embeddings/pgvector/FAISS upsert
│  ├─ rebuild_embeddings.py
│  └─ query_demo.py              # tiny demo: ask → citations
├─ src/
│  └─ dd_agent/                  # all Python packages live here
│     ├─ __init__.py
│     ├─ config.py               # load/validate .env + YAML config
│     ├─ utils/
│     │  ├─ io.py                # read/write helpers, hashing
│     │  ├─ text.py              # cleaning, HTML→MD, chunking utils
│     │  └─ logging.py
│     ├─ edgar/                  # SEC-specific logic
│     │  ├─ sec_filings.py       # (your file) fetch index + submissions
│     │  ├─ ingest.py            # download + persist raw + manifest
│     │  ├─ parse_html.py        # bs4 tidy, section split (Item 1A/7…)
│     │  ├─ xbrl.py              # Arelle-powered fact extraction
│     │  └─ normalize.py         # metadata, paths, accession→urls
│     ├─ indexing/
│     │  ├─ embed.py             # model loader + embed(text[]) -> vectors
│     │  ├─ vectorstore.py       # pgvector/FAISS adapter (upsert/search)
│     │  └─ bm25.py              # optional: simple keyword index
│     ├─ store/
│     │  ├─ db.py                # Postgres engine/session
│     │  ├─ schema.sql           # DDL for filings/sections/facts
│     │  └─ migrations/          # alembic or sql files
│     ├─ retrieval/
│     │  ├─ router.py            # numeric vs narrative
│     │  ├─ facts_query.py       # SQL for XBRL facts
│     │  └─ rag.py               # hybrid retrieve + prompt assembly
│     └─ api/
│        └─ service.py           # (optional) FastAPI endpoints later
├─ artifacts/                    # data lake on disk (OK to gitignore)
│  ├─ raw/                       # immutable raw downloads
│  │  └─ edgar/{cik}/{accession}/...
│  ├─ derived/                   # deterministic outputs (rebuildable)
│  │  └─ edgar/{cik}/{accession}/
│  │     ├─ text/cleaned.md
│  │     ├─ sections/index.json
│  │     └─ xbrl/facts.parquet
│  ├─ vectors/                   # embeddings / index shards
│  └─ manifests/
│     └─ ingest_manifest.jsonl   # one line per filing with hashes
├─ tests/
│  ├─ test_sec_filings.py
│  ├─ test_parse_html.py
│  ├─ test_xbrl.py
│  ├─ test_embed_and_index.py
│  └─ data/                      # tiny fixtures
└─ .github/
   └─ workflows/
      └─ ci.yaml                 # lint + unit tests
```