.PHONY: data-dirs up up-build down build logs logs-platform logs-orch \
	wait pipeline setup-metabase verify bootstrap reset shell migrate deploy test help

COMPOSE := docker compose -p dw-local -f platform/compose.yaml -f compose.yaml --project-directory .
export COMPOSE_PROJECT_NAME := dw-local

data-dirs: ## no-op locally (named volumes); kept so recipes stay identical
	@true

up: data-dirs ## Start platform + orchestration (no rebuild)
	$(COMPOSE) up -d

up-build: data-dirs ## Rebuild the Dagster image and start everything
	$(COMPOSE) up -d --build

down: ## Stop containers (keeps local named volumes)
	$(COMPOSE) down

reset: ## Stop containers and delete local volumes (postgres, clickhouse, archive, metabase)
	$(COMPOSE) down -v --remove-orphans
	@echo "Local volumes removed. Run: make bootstrap"

build: ## Build the Dagster image
	$(COMPOSE) build dagster-webserver

logs: ## Follow all logs
	$(COMPOSE) logs -f

logs-platform: ## Follow postgres / clickhouse / metabase
	$(COMPOSE) logs -f postgres clickhouse metabase

logs-orch: ## Follow Dagster webserver + daemon
	$(COMPOSE) logs -f dagster-webserver dagster-daemon

wait: ## Block until Dagster, Metabase, and ClickHouse answer
	set -a && . ./.env && set +a && python3 scripts/wait_for_stack.py

pipeline: ## Queue ingest_and_marts (respects max_concurrent_runs) and wait for it
	$(COMPOSE) exec -T dagster-webserver python dagster_ops.py launch ingest_and_marts --wait

deploy: ## Rebuild Dagster with new code; waits for running jobs before restarting
	scripts/deploy.sh local

TEST_COMPOSE := docker compose -p dw-test -f platform/compose.yaml -f compose.test.yaml --project-directory .

test: ## End-to-end tests on a throwaway stack (project dw-test; never touches dw-local)
	$(TEST_COMPOSE) build tests
	$(TEST_COMPOSE) run --rm tests; status=$$?; \
		$(TEST_COMPOSE) down -v --remove-orphans >/dev/null 2>&1; exit $$status

setup-metabase: ## Idempotent Metabase admin + ClickHouse connection
	set -a && . ./.env && set +a && python3 scripts/setup_metabase.py

verify: ## Check ClickHouse counts, parquet files, and Metabase connection
	set -a && . ./.env && set +a && python3 scripts/verify.py

bootstrap: up-build wait pipeline setup-metabase verify ## Full local path from zero
	@echo
	@echo "Dagster UI:  http://127.0.0.1:3030"
	@echo "Metabase:    http://127.0.0.1:3000  ($$(grep MB_ADMIN_EMAIL .env | cut -d= -f2))"
	@echo "ClickHouse:  http://127.0.0.1:8123  (admin user default)"
	@echo "Tracker:     docs/STATUS.md"

migrate: ## Run Dagster DB migrations manually
	$(COMPOSE) run --rm dagster-webserver dagster instance migrate

shell: ## Shell in the Dagster webserver container
	$(COMPOSE) exec dagster-webserver bash

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*##' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

.DEFAULT_GOAL := help
