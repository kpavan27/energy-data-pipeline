.PHONY: install ingest build report run test lint docs clean

install:        ## install the package with dev tools
	pip install -e ".[dev]"

ingest:         ## download pinned releases, verify checksums and contracts, land bronze Parquet
	energy-pipeline ingest

build:          ## dbt build: staging, marts and all data tests
	energy-pipeline build

report:         ## regenerate reports/ (metrics.json, revision_summary.csv, figures)
	energy-pipeline report

run:            ## ingest + build + report
	energy-pipeline run

test:           ## unit and end-to-end tests on synthetic fixtures (no network)
	pytest

lint:
	ruff check src tests && ruff format --check src tests

docs:           ## dbt docs with lineage graph at http://localhost:8080
	cd dbt && BRONZE_DIR=../data/bronze dbt docs generate --profiles-dir . --target-path ../data/dbt_target \
	  && dbt docs serve --profiles-dir . --target-path ../data/dbt_target

clean:
	rm -rf data/bronze data/warehouse.duckdb data/dbt_target data/dbt_logs
