PYTHON ?= .venv/bin/python
ROOT := $(CURDIR)
# Every recipe and parse-time package probe receives the project import root.
export PYTHONPATH := $(ROOT)
DATASET ?= adventureworks
SOURCE_HOST_PORT ?= 5433
CUBE_HOST_PORT ?= 4000
COMPOSE_PROJECT := grounded-$(DATASET)
COMPOSE := docker compose -p $(COMPOSE_PROJECT) -f infra/docker-compose.yml
DATASETS := $(filter-out _template,$(patsubst datasets/%/pack.yml,%,$(wildcard datasets/*/pack.yml)))
export GROUNDED_PACK := $(DATASET)
export COMPOSE_PROJECT_NAME := $(COMPOSE_PROJECT)
export SOURCE_HOST_PORT
export CUBE_HOST_PORT
PACK_SOURCE_LOAD := $(shell GROUNDED_PACK=$(DATASET) $(PYTHON) -m packlib source_load_or_empty)
PACK_SOURCE_TYPE := $(shell GROUNDED_PACK=$(DATASET) $(PYTHON) -m packlib source_type)
PACK_HAS_TRANSFORM := $(shell GROUNDED_PACK=$(DATASET) $(PYTHON) -m packlib has_transform)
PACK_SEMANTICS_BACKEND := $(shell GROUNDED_PACK=$(DATASET) $(PYTHON) -m packlib semantics_backend)
PACK_TRANSFORM = $(shell GROUNDED_PACK=$(DATASET) $(PYTHON) -m packlib transform)
PACK_DESTINATION = $(shell GROUNDED_PACK=$(DATASET) $(PYTHON) -m packlib destination)
GROUNDED_PACK_DATABASE := $(notdir $(PACK_DESTINATION))
GROUNDED_PACK_SEMANTICS := $(shell GROUNDED_PACK=$(DATASET) $(PYTHON) -m packlib semantics_cube_or_empty)
export GROUNDED_PACK_SEMANTICS
export GROUNDED_PACK_DATABASE

.PHONY: demo test benchmark benchmark-all lakehouse new-pack validate-pack release-scrub set-secret preflight-spine preflight-benchmark source-up source-load source-verify ingest bronze-verify transform cube-up down lineage lineage-view marquez-up benchmark-aw spine spine-all _require-docker _require-postgres _require-cube _require-ollama _require-source-dsn _free-conflicting-cube

new-pack:
	PYTHONPATH=$(ROOT) $(PYTHON) scripts/new_pack.py $(NAME)

validate-pack:
	PYTHONPATH=$(ROOT) $(PYTHON) scripts/validate_pack.py $(DATASET)

set-secret:
	$(PYTHON) scripts/set_secret.py

preflight-spine:
	$(PYTHON) scripts/preflight.py --dataset $(DATASET) --run spine

preflight-benchmark:
	$(PYTHON) scripts/preflight.py --dataset $(DATASET) --run benchmark

release-scrub:
	@! git grep -n -iE 'v[y]per|w[e]ave|k[u]zu|k[ù]zu|n[i]lus|iceb[e]rg|tri[n]o|mi[n]io' -- .

_require-docker:
	@command -v docker >/dev/null 2>&1 || { echo "Docker is required for the AdventureWorks spine. Install and start Docker, then retry." >&2; exit 1; }
	@docker info >/dev/null 2>&1 || { echo "Docker Desktop must be running for the AdventureWorks spine. Start it, then retry." >&2; exit 1; }

_require-postgres: _require-docker
	@$(COMPOSE) ps --services --filter status=running | grep -qx postgres || { echo "PostgreSQL is not running for $(DATASET). Run `make source-up DATASET=$(DATASET)` first." >&2; exit 1; }

_require-cube: _require-docker
	@$(COMPOSE) ps --services --filter status=running | grep -qx cube || { echo "Cube is not running for $(DATASET). Run `make cube-up DATASET=$(DATASET)` first." >&2; exit 1; }

_require-ollama:
	@command -v ollama >/dev/null 2>&1 || { echo "Ollama is required for the real-data benchmark. Install Ollama and pull the configured local models, then retry." >&2; exit 1; }
	@ollama list >/dev/null 2>&1 || { echo "Ollama must be running for the real-data benchmark. Start it, then retry." >&2; exit 1; }

_require-source-dsn:
	$(PYTHON) scripts/check_source_secret.py $(DATASET)

demo:
	$(MAKE) --no-print-directory DATASET=fixture demo-pack

demo-pack:
	$(PYTHON) scripts/demo.py

test:
	$(PYTHON) -m pytest

benchmark: cube-up preflight-benchmark
	$(PYTHON) -m evals.compare --dataset $(DATASET)

benchmark-all:
	$(PYTHON) -m evals.orchestration

lakehouse:
	PYTHONPATH=$(ROOT) $(PYTHON) scripts/lakehouse.py

source-up:
ifeq ($(PACK_SOURCE_TYPE),postgres)
	@$(MAKE) --no-print-directory _require-docker
	$(PACK_SOURCE_LOAD) up
else
	@:
endif

source-load:
ifeq ($(PACK_SOURCE_TYPE),duckdb_seed)
	PYTHONPATH=$(ROOT) $(PYTHON) $(PACK_SOURCE_LOAD)
else ifeq ($(PACK_SOURCE_TYPE),sqlite)
	@:
else
	@$(MAKE) --no-print-directory _require-docker
	$(PACK_SOURCE_LOAD) load
endif

source-verify:
ifeq ($(PACK_SOURCE_TYPE),postgres)
	@$(MAKE) --no-print-directory _require-postgres
	$(PACK_SOURCE_LOAD) verify
else
	@:
endif

ingest:
ifeq ($(PACK_SOURCE_TYPE),postgres)
	@$(MAKE) --no-print-directory _require-postgres
endif
	$(PYTHON) -m infra.ingest ingest

bronze-verify:
ifeq ($(PACK_SOURCE_TYPE),postgres)
	@$(MAKE) --no-print-directory _require-postgres
endif
	$(PYTHON) -m infra.ingest verify

transform:
ifeq ($(PACK_HAS_TRANSFORM),true)
	cd $(PACK_TRANSFORM) && $(ROOT)/.venv/bin/sqlmesh plan --auto-apply
	cd $(PACK_TRANSFORM) && $(ROOT)/.venv/bin/sqlmesh audit
else
	@echo "Skipping transform: $(DATASET) has no SQLMesh capability."
endif

cube-up:
ifeq ($(PACK_SEMANTICS_BACKEND),cube)
	@$(MAKE) --no-print-directory _require-docker
	@$(MAKE) --no-print-directory _free-conflicting-cube
	$(COMPOSE) up -d cube
else
	@echo "Skipping Cube: $(DATASET) uses the fixture backend."
endif

_free-conflicting-cube:
	@active_cube="$$($(COMPOSE) ps -q cube)"; \
	for container in $$(docker ps -q --filter publish=$(CUBE_HOST_PORT)); do \
		if [ "$$container" != "$$active_cube" ]; then \
			name="$$(docker inspect --format '{{.Name}}' "$$container" | sed 's#^/##')"; \
			echo "Stopping conflicting Cube container $$name on host port $(CUBE_HOST_PORT) before starting $(COMPOSE_PROJECT)."; \
			docker stop "$$container" >/dev/null; \
		fi; \
	done

down:
	@$(MAKE) --no-print-directory _require-docker
	$(COMPOSE) down

marquez-up: _require-docker
	docker compose -f infra/docker-compose.yml up -d marquez-web

lineage:
ifeq ($(PACK_SEMANTICS_BACKEND),cube)
	$(PYTHON) scripts/build_ontology.py
else
	@echo "Skipping lineage: $(DATASET) has no real-source/Cube spine."
endif

lineage-view:
	open http://localhost:3000

benchmark-aw: _require-ollama _require-cube
	$(MAKE) --no-print-directory DATASET=adventureworks benchmark

spine: preflight-spine
ifeq ($(PACK_SOURCE_TYPE),postgres)
	@$(MAKE) --no-print-directory DATASET=$(DATASET) _require-source-dsn
	@printf '\n=== Grounded spine: source-up ===\n'
	@$(MAKE) --no-print-directory DATASET=$(DATASET) source-up
endif
	@printf '\n=== Grounded spine: source-load ===\n'
	@$(MAKE) --no-print-directory DATASET=$(DATASET) source-load
ifeq ($(PACK_SOURCE_TYPE),postgres)
	@printf '\n=== Grounded spine: ingest ===\n'
	@$(MAKE) --no-print-directory DATASET=$(DATASET) ingest
	@printf '\n=== Grounded spine: bronze-verify ===\n'
	@$(MAKE) --no-print-directory DATASET=$(DATASET) bronze-verify
endif
ifeq ($(PACK_SOURCE_TYPE),sqlite)
	@printf '\n=== Grounded spine: ingest ===\n'
	@$(MAKE) --no-print-directory DATASET=$(DATASET) ingest
	@printf '\n=== Grounded spine: bronze-verify ===\n'
	@$(MAKE) --no-print-directory DATASET=$(DATASET) bronze-verify
endif
ifeq ($(PACK_HAS_TRANSFORM),true)
	@printf '\n=== Grounded spine: transform ===\n'
	@$(MAKE) --no-print-directory DATASET=$(DATASET) transform
endif
ifeq ($(PACK_SEMANTICS_BACKEND),cube)
	@printf '\n=== Grounded spine: cube-up ===\n'
	@$(MAKE) --no-print-directory DATASET=$(DATASET) cube-up
	@printf '\n=== Grounded spine: lineage ===\n'
	@$(MAKE) --no-print-directory DATASET=$(DATASET) lineage
endif

spine-all:
	$(PYTHON) scripts/spine_all.py
