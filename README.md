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

This starts a `hse-ai-news-postgres` container on port 5432. The HSE coursework DDL for `interests`, `summaries`, `transports`, and `scores` is expected to exist; see `backend/.env.example` for the schema.

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

- English README: this file (also [`README_en.md`](README_en.md))
- Backend setup: [`backend/README.md`](backend/README.md)
- Frontend setup: [`frontend/README.md`](frontend/README.md)
- Audit / project state: [`docs/`](docs/)

# Backend — HSE AI News

## Локальный запуск
Для запуска приложения нам понадобиться база данных PostgreSQL, дефолтный способ для локального запуска - запуск докер контейнера:

```bash
./infra/start-local-db.sh
```

Для запуска самого приложения - скрипты.
Для Linux/MacOS:

```bash
./infra/start.sh
```

Для Windows:

```powershell
.\infra\start.ps1
```

## Ручной запуск генерации
Для запуска ночного прогона генерации можно использовать публичный эндпоинт. Для запуска в сервисе необходим настроенный X-Summary-Job-Secret, впоследсвтии передаваемый в хедерах.

```bash
curl -X POST http://localhost:8000/tasks/summary/run-bulk -H "X-Summary-Job-Secret: ItsASecretIConfiguredInEnv"
```

Пример запуска:
```bash
evgen@tokyo MINGW64 ~/repos/ai-news-hse (stable)
$ curl -X POST http://localhost:8000/tasks/summary/run-bulk     -H "X-Summary-Job-Secret: somesecret"
{"users_total":1,"users_processed":1,"skipped_no_interests":0,"digest_failed":0,"news_articles_fetched":76,"keyword_extraction_failed":0,"telegram_sent":0,"telegram_skipped_no_config":1,"telegram_failed":0,"telegram_no_sender":0}
```

## Тесты
