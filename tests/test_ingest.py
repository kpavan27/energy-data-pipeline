from __future__ import annotations

import dataclasses
import json

import duckdb
import pytest

from energy_pipeline.ingest import (
    ChecksumMismatchError,
    ContractViolationError,
    check_contract,
    fetch,
    ingest,
)
from tests.conftest import energy_row, write_csv


def test_ingest_lands_every_release_with_lineage(fixture_sources):
    config, paths = fixture_sources
    manifest = ingest(config, paths)

    assert set(manifest) == {
        "energy/2024-01-01",
        "energy/2025-01-01",
        "co2/2025-01-01",
        "country_codes/2025-01-01",
    }
    parquet = paths.bronze / "energy" / "release=2024-01-01" / "data.parquet"
    query = f"SELECT _release, _source_sha256, typeof(year) FROM '{parquet}' LIMIT 1"
    row = duckdb.sql(query).fetchone()
    assert row[0] == "2024-01-01"
    assert row[1] == config.releases_for("energy")[0].sha256
    assert row[2] == "VARCHAR"  # bronze keeps values as published text


def test_ingest_is_idempotent(fixture_sources):
    config, paths = fixture_sources
    ingest(config, paths)
    parquet = paths.bronze / "energy" / "release=2024-01-01" / "data.parquet"
    first_mtime = parquet.stat().st_mtime_ns
    first_manifest = paths.manifest.read_text()

    ingest(config, paths)

    assert parquet.stat().st_mtime_ns == first_mtime
    assert json.loads(paths.manifest.read_text()) == json.loads(first_manifest)


def test_checksum_mismatch_is_fatal(fixture_sources):
    config, paths = fixture_sources
    tampered = dataclasses.replace(config.releases[0], sha256="0" * 64)
    with pytest.raises(ChecksumMismatchError):
        fetch(tampered, paths.cache)


def test_contract_rejects_missing_column(tmp_path, fixture_sources):
    config, _ = fixture_sources
    row = energy_row("IRL", "Ireland", 2000)
    del row["coal_consumption"]
    path = write_csv(tmp_path / "broken.csv", [row])
    with pytest.raises(ContractViolationError, match="coal_consumption"):
        check_contract(duckdb.connect(), path, config.contracts["energy"])


def test_contract_rejects_duplicate_keys(tmp_path, fixture_sources):
    config, _ = fixture_sources
    row = energy_row("IRL", "Ireland", 2000)
    path = write_csv(tmp_path / "dupes.csv", [row, row])
    with pytest.raises(ContractViolationError, match="duplicate"):
        check_contract(duckdb.connect(), path, config.contracts["energy"])


def test_contract_tolerates_new_columns(tmp_path, fixture_sources):
    config, _ = fixture_sources
    path = write_csv(tmp_path / "extra.csv", [{**energy_row("IRL", "Ireland", 2000), "new_metric": 1}])
    info = check_contract(duckdb.connect(), path, config.contracts["energy"])
    assert info["extra_columns"] == ["new_metric"]
