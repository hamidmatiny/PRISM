# ADR 006 — Dagster for asset-graph orchestration

**Status:** Accepted  
**Date:** 2026-08  
**Phases:** 17 (`orchestration/`)

## Context

PRISM now has three independently useful pieces that still get driven as
separate scripts / Compose services:

1. Lakehouse bronze → silver → gold materialization (`prism_lakehouse.run_medallion`)
2. Drift-monitor status / baseline readiness (`drift-monitor` HTTP, Phase 16)
3. Optional chaos replay from scenario-engine when drift is observed (Phase 12
   source + Phase 16 foreshadow)

Calling those ad hoc (Makefile targets, one-off curl, cockpit scenario batch)
works for demos but does not encode the dependency graph: gold depends on
bronze transforms; a drift-triggered reseed is optional and must never block
lakehouse or drift polling when the flag is off.

Lakehouse work is **asset-shaped** (tables / partitions with upstream
dependencies), not task-shaped (imperative “run script A then B”). That is the
same reason Argus chose Dagster over Airflow for lakehouse materialization —
the decision transfers because the shape of the problem transferred, not
because “Argus has it.”

## Decision

1. **Introduce Dagster** under `orchestration/` as the local asset-graph
   orchestrator for:
   - `lakehouse_medallion` — wraps existing `run_medallion` (no fork of Spark
     transforms)
   - `drift_status_snapshot` — polls `GET /v1/status` on drift-monitor
   - `scenario_drift_reseed` — optional, flag-gated edge: when
     `PRISM_DAGSTER_DRIFT_RESEED=1` **and** the snapshot shows at least one
     drifted feature on an asset, reset scenario-engine with
     `drift_signature`-heavy weights and pull a small replay batch
2. **ADR-005 applies to materialization claims.** Assets report skipped /
   not-materialized honestly when Spark/JVM is unavailable, when drift-monitor
   is unreachable, or when the reseed flag is off / no drift is present. No
   fabricated “success.”
3. **ADR-001:** Dagster runs locally / in Compose only. No cloud Dagster+, no
   paid schedulers, no terraform apply. CI materializes definitions in-process
   with pytest (and skips Spark-backed materialization without a JVM the same
   way `test_medallion_local_spark` does).
4. **Optional edge is non-blocking.** Reseed failures never fail the lakehouse
   asset; the reseed asset itself records `ok: false` with an error string
   rather than pretending it ran.

## Alternatives considered

| Option | Why not |
|--------|---------|
| Keep Makefile-only wiring | No dependency graph; easy to invent “success” in docs |
| Airflow / Prefect | Heavier ops surface for a local portfolio path; lakehouse is asset-shaped |
| Embed orchestration inside ingestion | Wrong layer; couples emit loop to batch materialization |

## Consequences

- New top-level `orchestration/` package + optional Compose service on **:9112**.
- Scenario-engine `POST /v1/reset` accepts optional per-run `weights` so the
  reseed edge can request `drift_signature` replay without restarting the
  container (still synthetic-labeled; ADR-005).
- Foundation / ADR index require ADR-006.
