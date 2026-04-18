.PHONY: setup dev

ifeq ($(OS),Windows_NT)
PYTHON := .venv/Scripts/python.exe
VENV_CREATE := py -3 -m venv .venv
else
PYTHON := .venv/bin/python
VENV_CREATE := python3 -m venv .venv
endif

setup:
	$(VENV_CREATE)
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r requirements.txt
dev:
	$(PYTHON) -m uvicorn app.main:app --reload
