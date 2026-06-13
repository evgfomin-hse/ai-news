#!/usr/bin/env bash
set -e

rm -rf .venv
uv venv --python 3.13 .venv
source .venv/Scripts/activate
pip install --upgrade pip
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
