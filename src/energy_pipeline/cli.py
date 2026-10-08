"""Command-line entry point: ``energy-pipeline ingest | build | report | run``."""

from __future__ import annotations

import argparse
import logging
import os
import sys

from energy_pipeline.config import PROJECT_ROOT, Paths, load_config
from energy_pipeline.ingest import ingest


def build(paths: Paths, select: str | None = None) -> bool:
    """Run ``dbt build`` (models + tests) against the local DuckDB warehouse."""
    from dbt.cli.main import dbtRunner

    os.environ["BRONZE_DIR"] = str(paths.bronze)
    os.environ["WAREHOUSE_PATH"] = str(paths.warehouse)
    args = [
        "build",
        "--project-dir",
        str(paths.dbt_project),
        "--profiles-dir",
        str(paths.dbt_project),
        "--target-path",
        str(paths.data / "dbt_target"),
        "--log-path",
        str(paths.data / "dbt_logs"),
    ]
    if select:
        args += ["--select", select]
    result = dbtRunner().invoke(args)
    return bool(result.success)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="energy-pipeline", description=__doc__)
    parser.add_argument("command", choices=["ingest", "build", "report", "run"])
    parser.add_argument("--force", action="store_true", help="re-land releases already in bronze")
    parser.add_argument("--select", help="dbt selection for build")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    paths = Paths(PROJECT_ROOT)

    if args.command in ("ingest", "run"):
        ingest(load_config(), paths, force=args.force)
    if args.command in ("build", "run") and not build(paths, args.select):
        return 1
    if args.command in ("report", "run"):
        from energy_pipeline.report import write_reports

        write_reports(paths)
    return 0


if __name__ == "__main__":
    sys.exit(main())
