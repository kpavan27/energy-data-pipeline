"""Synthetic fixtures: small CSV releases served from disk via file:// URLs,
so the whole pipeline runs in tests without network access."""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path

import pytest
import yaml

from energy_pipeline.config import Config, Contract, Paths, Release, load_config

MEASURES = yaml.safe_load((Path(__file__).parents[1] / "dbt" / "dbt_project.yml").read_text())["vars"][
    "energy_measures"
]


def energy_row(iso: str, country: str, year: int, scale: float = 1.0) -> dict:
    """A country-year whose components add up exactly, so identity tests pass."""
    coal, oil, gas = 10.0, 20.0, 30.0
    nuclear, hydro, wind, solar, bio, other = 5.0 * scale, 8.0 * scale, 3.0 * scale, 2.0 * scale, 1.0, 1.0
    renew = hydro + wind + solar + bio + other
    fossil = coal + oil + gas
    elec = {
        "coal": 4.0,
        "oil": 1.0,
        "gas": 5.0,
        "nuclear": 3.0,
        "hydro": 6.0,
        "wind": 2.0,
        "solar": 1.0,
        "biofuel": 0.5,
        "other": 0.5,
    }
    gen = sum(elec.values())
    row = {
        "country": country,
        "year": year,
        "iso_code": iso,
        "population": 1_000_000,
        "gdp": 1e10,
        "primary_energy_consumption": fossil + nuclear + renew,
        "fossil_fuel_consumption": fossil,
        "coal_consumption": coal,
        "oil_consumption": oil,
        "gas_consumption": gas,
        "low_carbon_consumption": nuclear + renew,
        "nuclear_consumption": nuclear,
        "renewables_consumption": renew,
        "hydro_consumption": hydro,
        "wind_consumption": wind,
        "solar_consumption": solar,
        "biofuel_consumption": bio,
        "other_renewable_consumption": other,
        "electricity_generation": gen,
        "electricity_demand": gen + 1.0,
        "net_elec_imports": 1.0,
        "coal_electricity": elec["coal"],
        "oil_electricity": elec["oil"],
        "gas_electricity": elec["gas"],
        "nuclear_electricity": elec["nuclear"],
        "hydro_electricity": elec["hydro"],
        "wind_electricity": elec["wind"],
        "solar_electricity": elec["solar"],
        "biofuel_electricity": elec["biofuel"],
        "other_renewable_exc_biofuel_electricity": elec["other"],
        "low_carbon_electricity": elec["nuclear"]
        + elec["hydro"]
        + elec["wind"]
        + elec["solar"]
        + elec["biofuel"]
        + elec["other"],
        "renewables_electricity": elec["hydro"]
        + elec["wind"]
        + elec["solar"]
        + elec["biofuel"]
        + elec["other"],
        "greenhouse_gas_emissions": 50.0,
    }
    assert set(MEASURES) <= set(row)
    return row


def write_csv(path: Path, rows: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def fixture_sources(tmp_path: Path) -> tuple[Config, Paths]:
    """Two energy releases with one update, one insert and one delete, plus CO2 and codes.

    Release B rescales hydro, wind, solar and nuclear in every row (a methodology
    change), revises one coal value, adds a year for Ireland and drops a year for France.
    """
    src = tmp_path / "upstream"
    years = range(2000, 2004)
    rel_a = [energy_row("IRL", "Ireland", y) for y in years] + [energy_row("FRA", "France", y) for y in years]
    rel_a.append({**energy_row("IRL", "World", 2000), "iso_code": "OWID_WRL"})  # aggregate, dropped
    rel_b = [energy_row("IRL", "Ireland", y, scale=0.94) for y in [*years, 2004]]
    rel_b += [energy_row("FRA", "France", y, scale=0.94) for y in years if y != 2000]
    rel_b[0] = {
        **rel_b[0],
        "coal_consumption": 11.0,
        "fossil_fuel_consumption": 61.0,
        "primary_energy_consumption": rel_b[0]["primary_energy_consumption"] + 1.0,
    }

    files = {
        ("energy", "2024-01-01"): write_csv(src / "energy_a.csv", rel_a),
        ("energy", "2025-01-01"): write_csv(src / "energy_b.csv", rel_b),
        ("co2", "2025-01-01"): write_csv(
            src / "co2.csv",
            [
                {
                    "country": c,
                    "year": y,
                    "iso_code": i,
                    "co2": 30.0,
                    "co2_including_luc": 31.0,
                    "population": 1e6,
                }
                for i, c in [("IRL", "Ireland"), ("FRA", "France")]
                for y in years
            ],
        ),
        ("country_codes", "2025-01-01"): write_csv(
            src / "cc.csv",
            [
                {
                    "ISO3166-1-Alpha-3": "IRL",
                    "CLDR display name": "Ireland",
                    "Region Name": "Europe",
                    "Sub-region Name": "Northern Europe",
                },
                {
                    "ISO3166-1-Alpha-3": "FRA",
                    "CLDR display name": "France",
                    "Region Name": "Europe",
                    "Sub-region Name": "Western Europe",
                },
            ],
        ),
    }
    releases = [
        Release(source=s, release=r, commit=f"{i:040d}", sha256=sha256(p), url=p.as_uri())
        for i, ((s, r), p) in enumerate(files.items())
    ]
    contracts = load_config().contracts
    config = Config(
        releases=releases,
        contracts={
            **contracts,
            "energy": Contract(key=contracts["energy"].key, required=contracts["energy"].required),
        },
    )
    return config, Paths(tmp_path / "project")
