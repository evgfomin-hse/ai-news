# HSE AI News

A small full-stack app that delivers a daily personalized AI news digest to your Telegram. Built as an HSE coursework project.

Users sign in with Google, describe their interests in free text, and receive a markdown summary at 00:00 UTC. Summaries are also browsable in the web UI.

## Stack

- **Backend:** FastAPI · SQLAlchemy 2 · PostgreSQL 16 · APScheduler · Python 3.11
- **Frontend:** React 19 · TypeScript · Vite · React Router · react-markdown
- **Auth:** Google Sign-In (HttpOnly JWT session cookie)
- **Tests:** pytest (backend) · Playwright (e2e)

## Repository layout

```
backend/   FastAPI app, services, repositories, models, tests
frontend/  React + Vite SPA
e2e/       Playwright end-to-end tests
docs/      Audit reports, specs, plans
```

## Quick start (local dev)

You need: **Docker**, **Python 3.11**, **uv**, **Node 24**.

### 1. Postgres

```bash
bash backend/db.sh
```

Starts a `hse-ai-news-postgres` container on port 5432. The HSE coursework DDL for `interests`, `summaries`, `transports`, and `scores` is expected to exist; see `backend/.env.example` for the schema.

### 2. Backend

```bash
cp backend/.env.example backend/.env
# Fill in GOOGLE_CLIENT_ID and JWT_SECRET in backend/.env

cd backend
uv venv --python 3.11 .venv
uv pip install -r requirements-dev.txt
.venv/bin/python -m uvicorn app.main:app --reload --port 8000
```

### 3. Frontend

```bash
cp frontend/.env.example frontend/.env
# Fill in VITE_APP_CLIENT_ID (same OAuth Web client ID as backend)

cd frontend
npm install
npm run dev
```

Open <http://127.0.0.1:5173>.

## Tests

```bash
# Backend
cd backend && .venv/bin/python -m pytest

# E2E — see e2e/README.md. Needs E2E_BOOTSTRAP_SECRET set in backend/.env.
cd e2e && npm install && npm run install:browsers && npm test
```

## Documentation

- This file is the English README; for parity see [`README.md`](README.md)
- Backend setup: [`backend/README.md`](backend/README.md)
- Frontend setup: [`frontend/README.md`](frontend/README.md)
- Audit / project state: [`docs/`](docs/)
