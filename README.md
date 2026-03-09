# CED Suite

AI-assisted grant proposal workspace with:
- A FastAPI backend for parsing grant calls, drafting proposal content, and export
- A Next.js frontend for the end-to-end proposal workflow
- A local RAG pipeline backed by Chroma for retrieval over proposal/program documents

## What This Repo Contains

- `api/` - FastAPI entrypoint and API routes
- `backend/app/` - parsing, LLM, validation, and RAG logic
- `frontend/` - Next.js application (App Router, TypeScript)
- `scripts/` - helper scripts (for example, rebuilding the vector index)
- `streamlit_app/` - Streamlit app assets

## Core Workflow

1. Upload grant package (PDF, DOCX, TXT)
2. Parse requirements into structured sections
3. Enter community/project details
4. Generate and refine draft proposal
5. Validate and export proposal to PDF

## Prerequisites

- Python 3.9+
- Node.js 18+ and npm
- `OPENAI_API_KEY` environment variable

## Local Setup

### 1. Clone and enter repo

```bash
git clone https://github.com/praveenachen/ced-suite.git
cd ced-suite
```

### 2. Set up Python environment

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

macOS/Linux:

```bash
source .venv/bin/activate
```

Install backend dependencies:

```bash
pip install -r requirements.txt
pip install -r api/requirements.txt
```

### 3. Set environment variables

Windows PowerShell:

```powershell
$env:OPENAI_API_KEY = "your_key_here"
$env:PYTHONPATH = (Get-Location).Path
```

macOS/Linux:

```bash
export OPENAI_API_KEY="your_key_here"
export PYTHONPATH="$(pwd)"
```

### 4. Run API server

From repo root:

```bash
uvicorn api.main:app --reload --port 8000
```

### 5. Run frontend

In a new terminal:

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

Frontend: `http://localhost:3002`  
Backend: `http://localhost:8000`

## RAG Index (Optional but Recommended)

If you add or update `.txt` source files in `backend/app/data/app_library/`, rebuild the index:

```bash
python scripts/build_index.py --use-case default --reset
```

Notes:
- This writes to `backend/app/data/app_library/vector_store/`
- Do not commit generated `vector_store` artifacts unless intentionally versioning them

## Team Collaboration (Beginner Friendly)

Use this exact process during feature sprints to reduce conflicts.

### Sprint structure

1. Keep `main` always deployable and stable.
2. Create one issue per feature/bug with a clear owner.
3. Every change goes through a pull request (PR). No direct pushes to `main`.
4. Require at least one review before merging.

### Branch naming

Use short branch prefixes:
- `feat/<short-name>` for new feature
- `fix/<short-name>` for bug fix
- `chore/<short-name>` for maintenance/docs

Example:

```bash
git checkout main
git pull origin main
git checkout -b feat/proposal-export-improvements
```

### Daily developer flow

1. Sync `main`
```bash
git checkout main
git pull origin main
```
2. Create or switch to your feature branch
```bash
git checkout -b feat/my-feature
```
3. Make small commits with clear messages
```bash
git add .
git commit -m "feat: add proposal section rewrite endpoint"
```
4. Push branch
```bash
git push -u origin feat/my-feature
```
5. Open PR to `main`
6. Address review comments
7. Merge PR (squash merge is recommended for clean history)

### Rules that prevent common issues

1. Pull latest `main` before starting work each day.
2. Keep PRs small (target under 300 changed lines when possible).
3. One feature per branch. Do not bundle unrelated changes.
4. Never commit secrets (`.env`, API keys, credentials).
5. Do not commit generated local artifacts:
   - `frontend/tsconfig.tsbuildinfo`
   - `backend/app/data/app_library/vector_store/` contents
6. Resolve merge conflicts on your branch, then re-push.
7. Use PR descriptions that include:
   - what changed
   - why it changed
   - how reviewer can test

### Recommended GitHub repo settings

Enable these in `Settings -> Branches -> Branch protection rules`:

1. Require pull request before merging
2. Require approvals (at least 1)
3. Require status checks to pass (if CI is added)
4. Restrict direct pushes to `main`

Also:
1. Keep repository visibility `Private` for internal use.
2. Add collaborators/teams with least-privilege access.

## License

MIT (see `LICENSE`)
