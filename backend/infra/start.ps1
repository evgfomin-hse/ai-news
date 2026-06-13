$ErrorActionPreference = "Stop"

# Remove existing venv
if (Test-Path .venv) {
    Remove-Item -Recurse -Force .venv
}

# Create venv with Python 3.13 using python's venv module
& python3.13 -m venv .venv

$python = ".\.venv\Scripts\python.exe"

# Upgrade pip and install requirements
& $python -m pip install --upgrade pip
& $python -m pip install -r requirements.txt

# Run the app
& $python -m uvicorn app.main:app --reload --port 8000