"""Bronze layer: download pinned releases, verify them, and land them as Parquet.

Each release is written once to ``data/bronze/<source>/release=<date>/data.parquet``
with lineage columns attached. Values are stored as text, exactly as published;
typing happens in the dbt staging models, so a bad cast never loses raw data.
"""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import duckdb

from energy_pipeline.config import Config, Contract, Paths, Release

log = logging.getLogger(__name__)


class ChecksumMismatchError(RuntimeError):
    """The downloaded bytes are not the ones the config pins."""


class ContractViolationError(RuntimeError):
    """A release is missing columns or has duplicate keys."""


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fetch(release: Release, cache_dir: Path) -> Path:
    """Download a release into the cache (once) and verify its checksum."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    target = cache_dir / f"{release.source}_{release.release}_{release.commit[:7]}.csv"
    if not target.exists():
        log.info("downloading %s %s", release.source, release.release)
        tmp = target.with_suffix(".part")
        with urllib.request.urlopen(release.url, timeout=120) as resp, tmp.open("wb") as out:
            shutil.copyfileobj(resp, out)
        tmp.replace(target)
    actual = sha256_of(target)
    if actual != release.sha256:
        raise ChecksumMismatchError(
            f"{release.source} {release.release}: expected sha256 {release.sha256}, got {actual}"
        )
    return target


def check_contract(con: duckdb.DuckDBPyConnection, csv_path: Path, contract: Contract) -> dict:
    """Fail on missing required columns or duplicate keys; report extra columns."""
    columns = [
        row[0]
        for row in con.execute(
            "DESCRIBE SELECT * FROM read_csv(?, all_varchar = true)", [str(csv_path)]
        ).fetchall()
    ]
    missing = sorted(set(contract.required) - set(columns))
    if missing:
        raise ContractViolationError(f"{csv_path.name}: missing required columns {missing}")

    key_cols = ", ".join(f'"{k}"' for k in contract.key)
    dupes = con.execute(
        f"""SELECT count(*) FROM (
                SELECT {key_cols} FROM read_csv(?, all_varchar = true)
                WHERE {" AND ".join(f'"{k}" IS NOT NULL' for k in contract.key)}
                GROUP BY ALL HAVING count(*) > 1)""",
        [str(csv_path)],
    ).fetchone()[0]
    if dupes:
        raise ContractViolationError(f"{csv_path.name}: {dupes} duplicate keys on {contract.key}")

    return {"columns": len(columns), "extra_columns": sorted(set(columns) - set(contract.required))}


def _load_manifest(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def land(release: Release, csv_path: Path, paths: Paths, con: duckdb.DuckDBPyConnection) -> int:
    """Write one release to bronze Parquet with lineage columns. Returns the row count."""
    out_dir = paths.bronze / release.source / f"release={release.release}"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "data.parquet"
    ingested_at = datetime.now(UTC).isoformat(timespec="seconds")
    con.execute(
        f"""COPY (
              SELECT *,
                     ? AS _release,
                     ? AS _source_commit,
                     ? AS _source_sha256,
                     ? AS _ingested_at
              FROM read_csv(?, all_varchar = true)
            ) TO '{out_file}' (FORMAT parquet, COMPRESSION zstd)""",
        [release.release, release.commit, release.sha256, ingested_at, str(csv_path)],
    )
    return con.execute(f"SELECT count(*) FROM '{out_file}'").fetchone()[0]


def ingest(config: Config, paths: Paths, force: bool = False) -> dict:
    """Ingest every configured release. Already-landed releases are skipped."""
    manifest = _load_manifest(paths.manifest)
    con = duckdb.connect()
    for release in config.releases:
        key = f"{release.source}/{release.release}"
        parquet = paths.bronze / release.source / f"release={release.release}" / "data.parquet"
        entry = manifest.get(key)
        if not force and entry and entry["sha256"] == release.sha256 and parquet.exists():
            log.info("skip %s (already landed)", key)
            continue
        csv_path = fetch(release, paths.cache)
        contract_info = check_contract(con, csv_path, config.contracts[release.source])
        rows = land(release, csv_path, paths, con)
        manifest[key] = {
            "source": release.source,
            "release": release.release,
            "commit": release.commit,
            "sha256": release.sha256,
            "url": release.url,
            "rows": rows,
            **contract_info,
        }
        log.info("landed %s: %d rows", key, rows)
    paths.manifest.parent.mkdir(parents=True, exist_ok=True)
    paths.manifest.write_text(json.dumps(manifest, indent=2, sort_keys=True))
    return manifest
