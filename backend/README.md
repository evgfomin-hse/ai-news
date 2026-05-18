# How to run

```bash
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
