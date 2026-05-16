.PHONY: setup frontend-setup backend-setup dev frontend-dev backend-dev

FRONTEND_DIR := frontend
BACKEND_DIR := backend
# Start-Job does not inherit Make's cwd; use absolute paths under the repo.
REPO_ROOT := $(CURDIR)

DEV_RUN_BOTH = bash -lc "trap 'kill 0' EXIT; cd '$(FRONTEND_DIR)' && npm run dev -- --host & cd '$(BACKEND_DIR)' && make dev & wait"

setup: frontend-setup backend-setup

frontend-setup:
	cd $(FRONTEND_DIR) && npm ci

backend-setup:
	$(MAKE) -C $(BACKEND_DIR) setup

dev:
	$(DEV_RUN_BOTH)
