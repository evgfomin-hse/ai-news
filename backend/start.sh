#!/usr/bin/env bash
set -e

rm -rf .venv
uv venv --python 3.11 .venv
uv pip install --python .venv/bin/python --upgrade pip
uv pip install --python .venv/bin/python -r requirements.txt
.venv/bin/python -m uvicorn app.main:app --reload --port 8000
