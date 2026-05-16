.PHONY: setup dev

PYTHON := .venv/bin/python
VENV_CREATE := python3 -m venv .venv

setup:
	$(VENV_CREATE)
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r requirements.txt
dev:
	$(PYTHON) -m pip install -r requirements.txt
	$(PYTHON) -m uvicorn app.main:app --reload
