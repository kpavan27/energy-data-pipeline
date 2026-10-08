"""End to end on the synthetic fixture: ingest, dbt build (models + data tests), then
check that change data capture classifies every cell as the fixture intends."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import duckdb
import pytest

from energy_pipeline.cli import build
from energy_pipeline.ingest import ingest
from tests.conftest import sha256


@pytest.fixture
def warehouse(fixture_sources):
    config, paths = fixture_sources
    ingest(config, paths)
    assert build(paths), "dbt build (models and data tests) failed on the fixture"
    return duckdb.connect(str(paths.warehouse))


def test_aggregates_are_excluded(warehouse):
    assert warehouse.sql("SELECT count(*) FROM stg_energy WHERE iso_code LIKE 'OWID%'").fetchone()[0] == 0


def test_cdc_classifies_inserts_deletes_and_updates(warehouse):
    counts = dict(
        warehouse.sql(
            "SELECT change_type, count(DISTINCT (iso_code, year)) FROM fct_metric_revisions "
            "WHERE change_type IN ('insert', 'delete') GROUP BY 1"
        ).fetchall()
    )
    assert counts == {"insert": 1, "delete": 1}  # IRL 2004 added, FRA 2000 removed

    coal = warehouse.sql(
        "SELECT iso_code, year, old_value, new_value FROM fct_metric_revisions "
        "WHERE metric = 'coal_consumption' AND change_type = 'update'"
    ).fetchall()
    assert coal == [("IRL", 2000, 10.0, 11.0)]


def test_revision_ratios_isolate_the_rescaled_metrics(warehouse):
    # The fixture rescales four metrics by 0.94. It is far below the 100-update
    # threshold for the looks_like_rescaling flag, so check the ratios directly.
    rows = dict(
        warehouse.sql(
            "SELECT metric, round(median_ratio, 3) FROM mart_revision_summary WHERE updated > 0"
        ).fetchall()
    )
    for metric in ("hydro_consumption", "wind_consumption", "solar_consumption", "nuclear_consumption"):
        assert rows[metric] == pytest.approx(0.94)
    assert "oil_consumption" not in rows
    flagged = warehouse.sql("SELECT count(*) FROM mart_revision_summary WHERE looks_like_rescaling")
    assert flagged.fetchone()[0] == 0


def test_shares_are_recomputed_from_sums(warehouse):
    share = warehouse.sql(
        "SELECT low_carbon_share_elec_pct FROM fct_energy_country_year WHERE iso_code = 'IRL' AND year = 2001"
    ).fetchone()[0]
    assert share == pytest.approx(100 * 13.0 / 23.0)


def test_inconsistent_release_fails_the_build(fixture_sources):
    """A release whose fossil total disagrees with coal + oil + gas must stop the build."""
    config, paths = fixture_sources
    latest = config.releases_for("energy")[-1]
    csv_path = Path(latest.url.removeprefix("file://"))
    # Bump the first fossil_fuel_consumption value so it no longer equals coal + oil + gas.
    csv_path.write_text(csv_path.read_text().replace(",60.0,", ",70.0,", 1))
    broken = dataclasses.replace(latest, sha256=sha256(csv_path))
    config = dataclasses.replace(config, releases=[r if r is not latest else broken for r in config.releases])

    ingest(config, paths)
    assert not build(paths)
