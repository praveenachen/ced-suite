# Community Grant Assistant — Frontend

Next.js frontend for the Grant Proposal Builder. Matches the workflow:

1. **Upload grant application package** (PDF, DOCX, TXT)
2. **AI extracts key sections** — review requirements and sections
3. **User enters community info** — community name, region, priority, budget, etc.
4. **AI generates proposal** — RAG + LLM pipeline produces a draft with compliance check

## Tech stack

- **Next.js 14** (App Router) + TypeScript
- **Tailwind CSS** + **tailwindcss-animate**
- **shadcn-style UI** (Button, Card, Input, Label, Textarea)
- **Framer Motion** — animations
- **React Hook Form** + **Zod** — community form validation
- **TanStack Query** — API state (mutations for parse / generate)
- **Lucide Icons**

## Setup

```bash
cd frontend
npm install
cp .env.example .env.local
# Edit .env.local if your API runs on another host/port
npm run dev
```

Runs at **http://localhost:3002**.

## Backend API

The app expects the FastAPI backend to be running at `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`).

From the repo root:

```bash
# Install API deps (optional, if using a venv that already has backend deps)
pip install -r api/requirements.txt

# Run API (from repo root; ensure backend is on PYTHONPATH)
set PYTHONPATH=%CD%
uvicorn api.main:app --reload --port 8000
```

On Windows PowerShell:

```powershell
$env:PYTHONPATH = (Get-Location).Path
uvicorn api.main:app --reload --port 8000
```

The API uses the existing `backend.app` modules (parsers, grant_utils, llm_utils, validation_utils, RAG).
