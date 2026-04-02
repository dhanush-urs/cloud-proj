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

### 1. Requirements
*   Docker & Docker Compose
*   Node.js 20+
*   Python 3.11+
*   Google Gemini API Key

### 2. Infrastructure Setup
```bash
cp .env.example .env
docker compose -f infra/compose/docker-compose.dev.yml up -d
```

### 3. Backend Setup
```bash
cd apps/api
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### 4. Frontend Setup
```bash
cd apps/web
npm install
npm run dev
```

Visit **[http://localhost:3000](http://localhost:3000)** to explore RepoBrain!

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
