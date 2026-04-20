# RepoBrain 🧠

RepoBrain is a production-grade, AI-powered repository intelligence platform. It provides deep codebase understanding through AST-based semantic analysis, graph-based dependency mapping, and hybrid retrieval-augmented generation (RAG).

## 🚀 Key Features

*   **Whole-Codebase Understanding**: AST-based symbol extraction for Python and JavaScript/TypeScript.
*   **Graph-Based Analysis**: Neo4j-powered dependency mapping and blast-radius estimation.
*   **AI Repository Expert**: Grounded Q&A ("Ask Repo") with file and line-level citations using Gemini.
*   **Risk Hotspots**: Automated ranking of files by complexity, dependency churn, and change-proneness.
*   **Semantic Search**: High-performance vector search across the entire codebase.
*   **Automated Onboarding**: AI-generated repository guides and architecture summaries.
*   **PR Impact Analysis**: Predictive analysis of code changes and suggested reviewers.

## 🛠️ Tech Stack

*   **Frontend**: Next.js 15 (App Router), Tailwind CSS, TypeScript.
*   **Backend**: FastAPI, SQLAlchemy, Pydantic 2.
*   **Database**: PostgreSQL + `pgvector` for metadata and embeddings.
*   **Graph**: Neo4j for code relationship mapping.
*   **Async Processing**: Redis + Celery for background ingestion and parsing.
*   **AI Engine**: Google Gemini (via `google-genai`).

## 📦 Project Structure

```text
repobrain/
├── apps/
│   ├── api/            # FastAPI Backend
│   └── web/            # Next.js Frontend
├── infra/
│   └── compose/        # Docker Compose configurations
└── scripts/            # Development and utility scripts
```

## 🚥 Getting Started

> **All make commands must be run from the repository root** (`repobrain/`).
> Running them from subdirectories (e.g. `apps/api/`) will fail with "No rule to make target".

### 1. Prerequisites

- Docker & Docker Compose
- A `.env` file with valid credentials (copy from `.env.example`)
- Google Gemini API Key (set `GEMINI_API_KEY` in `.env`)

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env and fill in GEMINI_API_KEY and any other required values
```

### 3. Start the full stack

```bash
# From repo root
make up
```

This builds and starts all services: API, frontend (Next.js), background worker (Celery), PostgreSQL, Redis, and Neo4j. The build step installs all Python and Node dependencies inside the containers.

Visit **[http://localhost:3000](http://localhost:3000)** once the stack is healthy.

### 4. Stop the stack

```bash
# From repo root
make down
```

### Other useful make targets (all run from repo root)

| Command | Purpose |
|---|---|
| `make logs` | Tail live logs from all containers |
| `make restart` | Hard restart (tears down volumes, rebuilds) |
| `make api-shell` | Open a shell in the API container |
| `make api-worker-shell` | Open a shell in the Celery worker container |
| `make postgres-shell` | Open a psql session |
| `make neo4j-shell` | Open a Cypher shell |

---

> **⚠️ Do not start the backend with `uvicorn` directly from `apps/api/`.**
>
> The backend depends on `neo4j`, `celery`, `redis`, and other packages that are only installed
> inside the Docker image (via `apps/api/requirements.txt` during `docker build`).
> Running `uvicorn app.main:app` on your system Python without first installing all requirements
> locally will fail with `ModuleNotFoundError`. The Docker-based `make up` workflow is the
> intended and supported local development path.

### 5. Safari Manual Verification Checklist
- [ ] Open `http://localhost:3000` in Safari on macOS.
- [ ] Click "Add Repository" and provide a public GitHub URL (e.g., `https://github.com/tiangolo/fastapi.git`).
- [ ] Ensure the "Jobs" auto-refresh functions without Safari cross-origin policy blockages.
- [ ] Verify CSR (Client-Side Rendering) transitions smoothly between the Dashboard and Repository Detail pages.
- [ ] Confirm no 500 errors appear in the Safari web inspector console during SSR hydration.

## 🚀 Production Deployment

RepoBrain is optimized for containerized environments.

### 1. Database Migrations (Alembic)
Ensure the database is up to date:
```bash
cd apps/api
DATABASE_URL="your_prod_db_url" alembic upgrade head
```

### 2. Docker Orchestration
We provide a hardened production compose stack:
```bash
docker compose -f infra/compose/docker-compose.prod.yml up --build -d
```

### 3. CI/CD
Automated pipelines are configured in `.github/workflows/ci.yml` to:
- Lint Python (Ruff) and TypeScript (ESLint).
- Run Backend Tests (Pytest).
- Verify Frontend Builds (Next.js Standalone).

## 📜 License
MIT
# repobrain
