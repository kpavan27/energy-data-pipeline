"""Load the pinned source configuration and resolve project paths."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Release:
    source: str
    release: str
    commit: str
    sha256: str
    url: str


@dataclass(frozen=True)
class Contract:
    key: list[str]
    required: list[str]


@dataclass(frozen=True)
class Paths:
    root: Path

    @property
    def data(self) -> Path:
        return self.root / "data"

    @property
    def cache(self) -> Path:
        return self.data / "cache"

    @property
    def bronze(self) -> Path:
        return self.data / "bronze"

    @property
    def manifest(self) -> Path:
        return self.bronze / "_manifest.json"

    @property
    def warehouse(self) -> Path:
        return self.data / "warehouse.duckdb"

    @property
    def reports(self) -> Path:
        return self.root / "reports"

    @property
    def dbt_project(self) -> Path:
        # The dbt project ships with the code; only data paths follow ``root``.
        return PROJECT_ROOT / "dbt"


@dataclass(frozen=True)
class Config:
    releases: list[Release]
    contracts: dict[str, Contract]

    def releases_for(self, source: str) -> list[Release]:
        return [r for r in self.releases if r.source == source]


def load_config(path: Path | None = None) -> Config:
    path = path or PROJECT_ROOT / "configs" / "sources.yaml"
    raw = yaml.safe_load(path.read_text())
    releases = [
        Release(
            source=name,
            release=str(item["release"]),
            commit=item["commit"],
            sha256=item["sha256"],
            url=spec["url_template"].format(commit=item["commit"]),
        )
        for name, spec in raw["sources"].items()
        for item in spec["releases"]
    ]
    contracts = {
        name: Contract(key=list(c["key"]), required=list(c["required"]))
        for name, c in raw["contracts"].items()
    }
    return Config(releases=releases, contracts=contracts)
