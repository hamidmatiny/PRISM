"""Bounded, admin-triggered scenario batch (Phase 15 cockpit scenario controls).

Reuses the exact same validate -> bronze/DLQ -> incident-engine-report code
path as the continuously-running pipeline (``IngestPipeline.process_one``) --
this module does not reimplement any of that logic, it just drives it for a
fixed number of ticks against a fresh scenario-engine seed, on an isolated
``IngestPipeline`` instance so the admin-triggered batch's stats never mix
with the real, continuously-running pipeline's own ``/health`` numbers.
"""

from __future__ import annotations

import logging
import time
from dataclasses import replace
from typing import Any

import httpx

from prism_ingestion.config import IngestConfig
from prism_ingestion.pipeline import IngestPipeline

logger = logging.getLogger(__name__)

MAX_TICKS = 300
MIN_RATE_HZ = 0.5
MAX_RATE_HZ = 20.0


class ScenarioRunError(ValueError):
    """Bad request input, or the scenario-engine reset call itself failed."""


def run_scenario_batch(
    base_config: IngestConfig,
    *,
    seed: int,
    ticks: int = 30,
    rate_hz: float = 3.0,
    scenario_id: str | None = None,
) -> dict[str, Any]:
    if ticks < 1 or ticks > MAX_TICKS:
        raise ScenarioRunError(f"ticks must be between 1 and {MAX_TICKS}, got {ticks}")
    if rate_hz < MIN_RATE_HZ or rate_hz > MAX_RATE_HZ:
        raise ScenarioRunError(
            f"rate_hz must be between {MIN_RATE_HZ} and {MAX_RATE_HZ}, got {rate_hz}"
        )

    reset_body: dict[str, Any] = {"seed": seed}
    if scenario_id:
        reset_body["scenario_id"] = scenario_id
    reset_url = f"{base_config.scenario_url.rstrip('/')}/v1/reset"
    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.post(reset_url, json=reset_body)
            resp.raise_for_status()
            reset_info = resp.json()
    except Exception as exc:  # noqa: BLE001 — surfaced as a clear admin-facing error
        raise ScenarioRunError(f"scenario-engine reset failed: {exc}") from exc

    run_config = replace(base_config, source_mode="scenario", duration_seconds=0.0)
    run_pipeline = IngestPipeline.from_config(run_config)

    interval = 1.0 / rate_hz
    started = time.monotonic()
    for _ in range(ticks):
        tick_start = time.monotonic()
        run_pipeline.process_one()
        sleep_for = interval - (time.monotonic() - tick_start)
        if sleep_for > 0:
            time.sleep(sleep_for)
    elapsed_s = time.monotonic() - started

    stats = run_pipeline.stats.as_dict()
    logger.info(
        "Scenario batch complete seed=%s scenario_id=%s ticks=%s stats=%s",
        seed,
        reset_info.get("scenario_id"),
        ticks,
        stats,
    )
    return {
        "seed": seed,
        "scenario_id": reset_info.get("scenario_id"),
        "journal_path": reset_info.get("journal_path"),
        "ticks_requested": ticks,
        "elapsed_seconds": round(elapsed_s, 3),
        **stats,
    }
