"""Dagster assets wrapping lakehouse, drift-monitor, and optional scenario reseed."""

import shutil

from dagster import AssetExecutionContext, MaterializeResult, asset

from prism_orchestration.clients import (
    assets_with_drift,
    get_drift_status,
    pull_next_events,
    reset_scenario,
)
from prism_orchestration.config import OrchestrationConfig

# 100% drift_signature for a focused reseed replay (still synthetic_scenario=true).
_DRIFT_RESEED_WEIGHTS: dict[str, float] = {
    "clean": 0.0,
    "sensor_corrupt": 0.0,
    "contract_violation": 0.0,
    "cv_low_confidence": 0.0,
    "cv_high_confidence": 0.0,
    "drift_signature": 1.0,
    "stalled_source": 0.0,
}


def _cfg() -> OrchestrationConfig:
    return OrchestrationConfig.from_env()


@asset(group_name="lakehouse")
def lakehouse_medallion(context: AssetExecutionContext) -> MaterializeResult:
    """Materialize bronze→silver→gold via existing ``run_medallion`` (no fork)."""
    cfg = _cfg()
    if shutil.which("java") is None:
        context.log.warning("Java not on PATH — skipping Spark medallion (ADR-005)")
        return MaterializeResult(
            metadata={
                "status": "skipped",
                "reason": "java_not_on_path",
                "bronze_root": str(cfg.bronze_root),
                "warehouse_root": str(cfg.warehouse_root),
            }
        )

    from prism_lakehouse.spark_session import build_local_spark
    from prism_lakehouse.transforms import run_medallion

    if not cfg.bronze_root.is_dir():
        return MaterializeResult(
            metadata={
                "status": "skipped",
                "reason": "bronze_root_missing",
                "bronze_root": str(cfg.bronze_root),
            }
        )

    try:
        spark = build_local_spark("prism-orchestration-medallion")
    except Exception as exc:  # noqa: BLE001
        text = f"{type(exc).__name__}: {exc}"
        if "JAVA_GATEWAY_EXITED" in text or type(exc).__name__ == "PySparkRuntimeError":
            return MaterializeResult(
                metadata={
                    "status": "skipped",
                    "reason": "jvm_unavailable",
                    "error": text,
                }
            )
        raise

    try:
        counts = run_medallion(
            spark,
            bronze_root=cfg.bronze_root,
            warehouse_root=cfg.warehouse_root,
        )
    finally:
        spark.stop()

    context.log.info("Medallion counts=%s", counts)
    return MaterializeResult(
        metadata={
            "status": "ok",
            "bronze_root": str(cfg.bronze_root),
            "warehouse_root": str(cfg.warehouse_root),
            "counts": counts,
            **{f"count.{k}": int(v) for k, v in counts.items()},
        }
    )


@asset(group_name="drift")
def drift_status_snapshot(context: AssetExecutionContext) -> MaterializeResult:
    """Poll drift-monitor ``/v1/status`` — never invents baseline_ready."""
    cfg = _cfg()
    try:
        status = get_drift_status(cfg.drift_monitor_url, timeout_s=cfg.http_timeout_s)
    except Exception as exc:  # noqa: BLE001 — honest skip, not fabricated ready
        context.log.warning("drift-monitor unreachable: %s", exc)
        return MaterializeResult(
            metadata={
                "status": "skipped",
                "reason": "drift_monitor_unreachable",
                "error": str(exc),
                "drift_monitor_url": cfg.drift_monitor_url,
            }
        )

    drifted = assets_with_drift(status)
    baseline_ready = bool(status.get("baseline_ready"))
    context.log.info(
        "drift snapshot baseline_ready=%s drifted_assets=%s",
        baseline_ready,
        [d["asset_id"] for d in drifted],
    )
    return MaterializeResult(
        metadata={
            "status": "ok",
            "baseline_ready": baseline_ready,
            "drifted_asset_count": len(drifted),
            "drifted_assets": drifted,
            "raw_status": status,
        }
    )


@asset(group_name="chaos")
def scenario_drift_reseed(context: AssetExecutionContext) -> MaterializeResult:
    """Optional drift→scenario reseed (flag-gated; no-op when off — ADR-005).

    Intentionally has no hard Dagster ``deps=`` on ``drift_status_snapshot`` so a
    flag-off materialization stays a pure no-op even when drift-monitor is down.
    When the flag is on, this asset re-polls ``/v1/status`` itself (same HTTP
    client) before deciding whether to reseed.
    """
    cfg = _cfg()
    if not cfg.drift_reseed_enabled:
        context.log.info("PRISM_DAGSTER_DRIFT_RESEED off — reseed is a deliberate no-op")
        return MaterializeResult(
            metadata={
                "status": "skipped",
                "reason": "flag_off",
                "flag": "PRISM_DAGSTER_DRIFT_RESEED",
                "reseed_attempted": False,
            }
        )

    try:
        status = get_drift_status(cfg.drift_monitor_url, timeout_s=cfg.http_timeout_s)
    except Exception as exc:  # noqa: BLE001
        return MaterializeResult(
            metadata={
                "status": "skipped",
                "reason": "drift_monitor_unreachable",
                "error": str(exc),
                "reseed_attempted": False,
            }
        )

    drifted = assets_with_drift(status)
    if not drifted:
        context.log.info("flag on but no drifted features — not inventing a reseed")
        return MaterializeResult(
            metadata={
                "status": "skipped",
                "reason": "no_drift_detected",
                "baseline_ready": bool(status.get("baseline_ready")),
                "reseed_attempted": False,
            }
        )

    scenario_id = f"{cfg.reseed_scenario_id_prefix}_{cfg.reseed_seed}"
    try:
        reset_info = reset_scenario(
            cfg.scenario_url,
            seed=cfg.reseed_seed,
            scenario_id=scenario_id,
            weights=_DRIFT_RESEED_WEIGHTS,
            timeout_s=cfg.http_timeout_s,
        )
        events = pull_next_events(
            cfg.scenario_url, ticks=cfg.reseed_ticks, timeout_s=cfg.http_timeout_s
        )
    except Exception as exc:  # noqa: BLE001 — do not pretend success
        return MaterializeResult(
            metadata={
                "status": "error",
                "reason": "scenario_engine_failed",
                "error": str(exc),
                "reseed_attempted": True,
                "drifted_assets": drifted,
            }
        )

    outcomes = [e.get("outcome") for e in events if not e.get("skip")]
    context.log.info(
        "reseed complete scenario_id=%s ticks=%s outcomes=%s",
        reset_info.get("scenario_id"),
        len(events),
        outcomes,
    )
    return MaterializeResult(
        metadata={
            "status": "ok",
            "reseed_attempted": True,
            "scenario_id": reset_info.get("scenario_id"),
            "seed": reset_info.get("seed"),
            "weights": reset_info.get("weights"),
            "ticks_pulled": len(events),
            "outcomes": outcomes,
            "drifted_assets": drifted,
            "events": events,
        }
    )
