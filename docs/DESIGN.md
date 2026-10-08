# Design notes

## Why releases, not "latest"

Most pipelines read the newest file and overwrite yesterday's tables. That throws away the one thing needed to explain a changed number: what it used to be. Here, each release is an immutable bronze partition keyed by its publication date, and the warehouse holds all of them. Change capture then becomes a join, not a forensic exercise.

## Layers

| Layer | Where | Contents | Guarantees |
|---|---|---|---|
| Bronze | `data/bronze/<source>/release=<date>/data.parquet` | Every column as published (text) plus lineage | Bytes match the pinned SHA-256; contract columns present; no duplicate keys |
| Staging | dbt views | Typed columns, countries only, latest CO2 and codes | Unique (release, country, year); years in range |
| Intermediate | `int_energy_long` | release × country × year × metric | Nulls dropped, so a vanished value becomes a delete |
| Marts | dbt tables | Dimensions, facts, CDC, summaries | Identity checks, share ranges, referential integrity, panel balance |

## Decisions and trade-offs

**Text in bronze, types in staging.** Type inference on a 130-column CSV is fragile: one stray string turns a numeric column into text, or the reverse. Landing text keeps ingestion lossless; `try_cast` in staging makes typing explicit and reviewable.

**Contract: fail on missing, tolerate extra.** A removed column breaks downstream models, so ingestion stops. An added column is common and harmless, so it is recorded in the manifest (`extra_columns`) and ingestion continues.

**Checksums over timestamps.** Idempotency is keyed on the SHA-256, not on file modification times, so a re-download of identical bytes is a no-op and a silently changed upstream file is an error.

**Change thresholds.** A cell counts as updated when `|new - old| > 1e-9 + 1e-6 * |old|`. Without the tolerance, float formatting differences between releases would show up as thousands of spurious updates.

**Telling a method change from data revisions.** A methodology change multiplies many values by the same factor; genuine revisions vary in size and direction. `mart_revision_summary` flags a metric when at least 100 values changed, the 10th–90th percentile band of new/old ratios is narrower than 0.01, and the median ratio is more than 0.5% away from 1. The thresholds are deliberately conservative and live in one SQL file.

**Shares from sums.** Regional shares are recomputed from summed TWh. Averaging country shares would weight Iceland like China.

**Balanced panels for trends.** Country coverage grows over time, which inflates or deflates regional aggregates. Trend views use a fixed set of countries; the unbalanced mart keeps a `countries_with_electricity_mix` column so the coverage is visible.

**Warn vs error.** Identities that the source guarantees (fossil = coal + oil + gas) fail the build. A known, documented property of the source (primary energy is not fully explained by fossil + low-carbon) only warns, so it is visible without blocking.

## Mapping to AWS

The pipeline runs locally on DuckDB, but the layers map directly onto a managed setup. This is a design sketch, not something implemented in this repo.

| Here | On AWS |
|---|---|
| `ingest.py` writing Parquet partitions | Lambda or Glue Python shell job writing to `s3://…/bronze/<source>/release=<date>/` |
| `_manifest.json` | DynamoDB table or Glue Data Catalog partition metadata |
| dbt + DuckDB | dbt with the Athena adapter (or Redshift), same models |
| `dbt build` data tests | Same tests; failures stop a Step Functions state machine |
| Weekly CI schedule | EventBridge rule triggering the state machine |
| `reports/` | Athena views feeding QuickSight |

## Known limitations

- Three releases make two comparison pairs. Rules tuned on two pairs may need adjustment as more releases are added.
- OWID itself compiles data from the Energy Institute, Ember, EIA and others. A revision here can come from any of them; the pipeline detects and characterises revisions, it does not attribute them.
- The rescaling rule detects a uniform multiplicative change. A method change that varies by country would be classified as ordinary revisions.
