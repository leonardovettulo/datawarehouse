.PHONY: up up-build down build logs migrate shell test-local

up: ## Start services (no rebuild — use after first build)
	docker compose up -d

up-build: ## Rebuild image and start (use after pyproject.toml changes)
	docker compose up -d --build

down: ## Stop and remove containers (keeps Postgres volume)
	docker compose down

build: ## Build the Dagster image once
	docker compose build dagster-webserver

logs: ## Follow all service logs
	docker compose logs -f

migrate: ## Run Dagster DB migrations manually
	docker compose run --rm dagster-webserver dagster instance migrate

shell: ## Open a shell in the Dagster container
	docker compose run --rm dagster-webserver bash

test-local: ## Quick smoke test: materialize the example asset
	docker compose run --rm dagster-webserver \
		dagster asset materialize -m my_pipelines.definitions --select hello_world

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*##' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

.DEFAULT_GOAL := help
