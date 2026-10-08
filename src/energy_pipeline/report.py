"""Write the committed outputs in ``reports/`` from the DuckDB warehouse.

Everything here is derived from the marts, so the numbers quoted in the
README can be regenerated with ``energy-pipeline report``.
"""

from __future__ import annotations

import json
import logging

import duckdb
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from energy_pipeline.config import Paths  # noqa: E402

log = logging.getLogger(__name__)

TOL = 0.01
IDENTITIES = {
    "fossil = coal + oil + gas": (
        "fossil_fuel_consumption",
        "coal_consumption + oil_consumption + gas_consumption",
    ),
    "generation = sum of sources": (
        "electricity_generation",
        "coal_electricity + oil_electricity + gas_electricity + nuclear_electricity + hydro_electricity"
        " + wind_electricity + solar_electricity + biofuel_electricity"
        " + other_renewable_exc_biofuel_electricity",
    ),
    "demand = generation + net imports": (
        "electricity_demand",
        "electricity_generation + net_elec_imports",
    ),
    "primary = fossil + low-carbon": (
        "primary_energy_consumption",
        "fossil_fuel_consumption + low_carbon_consumption",
    ),
}


def _identity_checks(con: duckdb.DuckDBPyConnection) -> list[dict]:
    rows = []
    for name, (lhs, rhs) in IDENTITIES.items():
        checked, failing, median_gap = con.execute(
            f"""SELECT count(*),
                       count(*) FILTER (WHERE abs(({lhs}) - ({rhs})) > {TOL} * greatest(abs({lhs}), 1)),
                       median(100 * (({lhs}) - ({rhs})) / nullif({lhs}, 0))
                           FILTER (WHERE abs(({lhs}) - ({rhs})) > {TOL} * greatest(abs({lhs}), 1))
                FROM fct_energy_country_year
                WHERE {lhs} IS NOT NULL AND ({rhs}) IS NOT NULL"""
        ).fetchone()
        rows.append(
            {
                "check": name,
                "rows_checked": checked,
                "rows_outside_1pct": failing,
                "median_gap_pct_when_outside": None if median_gap is None else round(median_gap, 2),
            }
        )
    return rows


def _figure_rescaling(con: duckdb.DuckDBPyConnection, paths: Paths, old: str) -> None:
    data = con.execute(
        """SELECT metric, new_value / old_value AS ratio
           FROM fct_metric_revisions
           WHERE old_release = ? AND change_type = 'update' AND abs(old_value) > 1
             AND metric IN ('hydro_consumption', 'wind_consumption', 'solar_consumption',
                            'nuclear_consumption', 'coal_consumption', 'oil_consumption')
             AND new_value / old_value BETWEEN 0.8 AND 1.2""",
        [old],
    ).fetchall()
    fig, ax = plt.subplots(figsize=(8, 4))
    groups = {
        "hydro, wind, solar (primary energy)": {"hydro_consumption", "wind_consumption", "solar_consumption"},
        "nuclear (primary energy)": {"nuclear_consumption"},
        "coal, oil (primary energy)": {"coal_consumption", "oil_consumption"},
    }
    for label, metrics in groups.items():
        ax.hist([r for m, r in data if m in metrics], bins=160, range=(0.8, 1.2), alpha=0.75, label=label)
    ax.set_yscale("log")
    ax.set_xlabel("new value / old value (revised cells only)")
    ax.set_ylabel("revised country-years (log)")
    ax.set_title("A methodology change shows up as a spike, data revisions as a spread")
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(paths.reports / "figures" / "revision_ratios.png", dpi=150)
    plt.close(fig)


def _figure_revisions_by_decade(con: duckdb.DuckDBPyConnection, paths: Paths) -> list[dict]:
    rows = con.execute(
        """SELECT old_release, new_release, (year // 10) * 10 AS decade,
                  count(*) FILTER (WHERE change_type = 'update')
                      / count(*) FILTER (WHERE change_type IN ('update', 'unchanged')) AS share_updated
           FROM fct_metric_revisions
           WHERE metric IN ('coal_consumption', 'oil_consumption', 'gas_consumption')
             AND year >= 1960
           GROUP BY ALL ORDER BY 1, 3"""
    ).fetchall()
    fig, ax = plt.subplots(figsize=(8, 4))
    for old, new in sorted({(r[0], r[1]) for r in rows}):
        pts = [(r[2], 100 * r[3]) for r in rows if r[0] == old and r[1] == new]
        ax.plot([p[0] for p in pts], [p[1] for p in pts], marker="o", label=f"{old} → {new}")
    ax.set_xlabel("decade of the data")
    ax.set_ylabel("% of fossil-consumption values revised")
    ax.set_title("Recent years get revised; history mostly does not")
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(paths.reports / "figures" / "fossil_revisions_by_decade.png", dpi=150)
    plt.close(fig)
    return [
        {"old_release": str(o), "new_release": str(n), "decade": d, "share_updated": round(s, 4)}
        for o, n, d, s in rows
    ]


def _figure_regions(con: duckdb.DuckDBPyConnection, paths: Paths) -> None:
    rows = con.execute(
        """SELECT region, year, low_carbon_share_elec_pct FROM mart_region_year_balanced ORDER BY 1, 2"""
    ).fetchall()
    panel_sizes = dict(
        con.execute("SELECT region, max(countries) FROM mart_region_year_balanced GROUP BY 1").fetchall()
    )
    fig, ax = plt.subplots(figsize=(8, 4))
    for region in sorted({r[0] for r in rows}):
        pts = [(y, v) for reg, y, v in rows if reg == region and v is not None]
        n = panel_sizes[region]
        ax.plot([p[0] for p in pts], [p[1] for p in pts], label=f"{region} ({n} countries)")
    ax.set_ylabel("low-carbon share of electricity (%)")
    ax.set_title("Low-carbon share of electricity, balanced panel of countries")
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(paths.reports / "figures" / "low_carbon_share_by_region.png", dpi=150)
    plt.close(fig)


def write_reports(paths: Paths) -> dict:
    (paths.reports / "figures").mkdir(parents=True, exist_ok=True)
    # Same configuration as dbt's in-process connection, so `run` can reuse it.
    con = duckdb.connect(str(paths.warehouse))

    releases = [str(r[0]) for r in con.execute("SELECT release_date FROM dim_release ORDER BY 1").fetchall()]
    change_counts = con.execute(
        """SELECT old_release, new_release, change_type, count(*)
           FROM fct_metric_revisions GROUP BY ALL ORDER BY 1, 3"""
    ).fetchall()
    rescaled = con.execute(
        """SELECT old_release, new_release, metric, updated, median_ratio, p10_ratio, p90_ratio
           FROM mart_revision_summary WHERE looks_like_rescaling ORDER BY 1, 3"""
    ).fetchall()

    con.execute(
        f"COPY (SELECT * FROM mart_revision_summary ORDER BY 1, 2, 3) "
        f"TO '{paths.reports / 'revision_summary.csv'}' (HEADER)"
    )

    _figure_rescaling(con, paths, releases[0])
    by_decade = _figure_revisions_by_decade(con, paths)
    _figure_regions(con, paths)

    metrics = {
        "releases": releases,
        "cell_changes": [
            {"old_release": str(o), "new_release": str(n), "change_type": t, "cells": c}
            for o, n, t, c in change_counts
        ],
        "detected_rescaling": [
            {
                "old_release": str(o),
                "new_release": str(n),
                "metric": m,
                "updated_cells": u,
                "median_ratio": round(med, 4),
                "p10_ratio": round(p10, 4),
                "p90_ratio": round(p90, 4),
            }
            for o, n, m, u, med, p10, p90 in rescaled
        ],
        "fossil_revisions_by_decade": by_decade,
        "identity_checks_latest_release": _identity_checks(con),
        "countries": con.execute("SELECT count(*) FROM dim_country").fetchone()[0],
        "fact_rows": con.execute("SELECT count(*) FROM fct_energy_country_year").fetchone()[0],
    }
    (paths.reports / "metrics.json").write_text(json.dumps(metrics, indent=2))

    manifest = json.loads(paths.manifest.read_text())
    for entry in manifest.values():
        entry.pop("extra_columns", None)
    (paths.reports / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True))
    log.info("reports written to %s", paths.reports)
    return metrics
