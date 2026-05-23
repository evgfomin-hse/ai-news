# Backend — HSE AI News

FastAPI + SQLAlchemy 2 + Postgres 16. Python 3.11.

## Requirements

- Docker (for Postgres)
- Python 3.11
- [uv](https://github.com/astral-sh/uv)

## Quick start

```bash
# 1. Copy env example and fill in the marked values
cp .env.example .env
# Required: GOOGLE_CLIENT_ID, JWT_SECRET
# Optional: E2E_BOOTSTRAP_SECRET, SUMMARY_JOB_SECRET

# 2. Start Postgres (container name: hse-ai-news-postgres)
bash db.sh

# 3. Create venv + install dev deps
uv venv --python 3.11 .venv
uv pip install --python .venv/bin/python -r requirements-dev.txt

# 4. Run the dev server
.venv/bin/python -m uvicorn app.main:app --reload --port 8000

# 5. (Anytime) Run tests
.venv/bin/python -m pytest
```

The dev server is at <http://127.0.0.1:8000>. OpenAPI: <http://127.0.0.1:8000/docs>.

## Notes

- `start.sh` exists for convenience but recreates `.venv` on every run and then blocks running uvicorn. Prefer the explicit commands above.
- Tests use in-memory SQLite via `tests/conftest.py`; no real Postgres needed for `pytest`.
- The `Transport` table uses Postgres JSONB and is excluded from the SQLite test schema — transport API tests substitute a stub at the dependency boundary.
