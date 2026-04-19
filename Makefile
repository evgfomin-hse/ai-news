.PHONY: setup frontend-setup backend-setup dev frontend-dev backend-dev

FRONTEND_DIR := frontend
BACKEND_DIR := backend
# Start-Job does not inherit Make's cwd; use absolute paths under the repo.
REPO_ROOT := $(CURDIR)

ifeq ($(OS),Windows_NT)
DEV_RUN_BOTH = powershell -NoProfile -Command "$$frontend = Start-Job -Name frontend -ScriptBlock { Set-Location '$(REPO_ROOT)/$(FRONTEND_DIR)'; npm run dev }; $$backend = Start-Job -Name backend -ScriptBlock { Set-Location '$(REPO_ROOT)/$(BACKEND_DIR)'; make dev }; try { Receive-Job -Job $$frontend, $$backend -Wait } finally { Stop-Job -Job $$frontend, $$backend -ErrorAction SilentlyContinue; Remove-Job -Job $$frontend, $$backend -Force -ErrorAction SilentlyContinue }"
else
DEV_RUN_BOTH = bash -lc "trap 'kill 0' EXIT; cd '$(FRONTEND_DIR)' && npm run dev -- --host & cd '$(BACKEND_DIR)' && make dev & wait"
endif

setup: frontend-setup backend-setup

frontend-setup:
	cd $(FRONTEND_DIR) && npm install

backend-setup:
	$(MAKE) -C $(BACKEND_DIR) setup

frontend-dev:
	cd $(FRONTEND_DIR) && npm run dev -- --host

backend-dev:
	$(MAKE) -C $(BACKEND_DIR) dev

dev:
	$(DEV_RUN_BOTH)
