"""Phase 11 golden path — one live chain across the monorepo.

simulated fleet event → CV finding → review queue → approval → gold update →
visible in Redshift AND Snowflake via activation-gateway → visible in cockpit
API surface → answerable by Ask PRISM.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_IMAGE = ROOT / "cv-service" / "fixtures" / "images" / "dent_sample.png"
GOLD_METRICS = ROOT / ".data" / "lakehouse" / "gold" / "asset_daily_metrics"
CV_GOLD = ROOT / ".data" / "lakehouse" / "gold" / "cv_findings"
ASSET_ID = "PRISM-AST-001"


def _request(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    body: bytes | None = None,
    timeout: float = 60.0,
) -> tuple[int, bytes]:
    req = urllib.request.Request(url, data=body, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.getcode() or 0, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def _json(
    method: str,
    url: str,
    *,
    token: str | None = None,
    payload: dict | None = None,
) -> tuple[int, object]:
    headers = {"content-type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = None if payload is None else json.dumps(payload).encode()
    code, raw = _request(method, url, headers=headers, body=body)
    if not raw:
        return code, {}
    try:
        return code, json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError:
        return code, raw.decode("utf-8", errors="replace")


def _print_token(role: str) -> str:
    proc = subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            "docker-compose.yml",
            "-f",
            "docker-compose.demo.yml",
            "exec",
            "-T",
            "control-plane",
            "python",
            "manage.py",
            "print_api_token",
            role,
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    lines = [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]
    # Last non-empty line is the bare token (logging may precede it).
    token = lines[-1]
    assert len(token) >= 32, f"unexpected token for {role}: {token!r}"
    return token


def _multipart_detect(cv_base: str, asset_id: str, frame_ref: str) -> dict:
    boundary = f"----prism{uuid.uuid4().hex}"
    file_bytes = FIXTURE_IMAGE.read_bytes()
    parts = [
        (
            f'--{boundary}\r\nContent-Disposition: form-data; name="asset_id"\r\n\r\n{asset_id}\r\n'
        ).encode(),
        (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="frame_ref"\r\n\r\n'
            f"{frame_ref}\r\n"
        ).encode(),
        (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="dent_sample.png"\r\n'
            f"Content-Type: image/png\r\n\r\n"
        ).encode()
        + file_bytes
        + b"\r\n",
        f"--{boundary}--\r\n".encode(),
    ]
    body = b"".join(parts)
    code, raw = _request(
        "POST",
        f"{cv_base}/v1/detect",
        headers={"content-type": f"multipart/form-data; boundary={boundary}"},
        body=body,
    )
    assert code == 200, raw[:500]
    return json.loads(raw.decode("utf-8"))


def _bump_gold_ping_count(asset_id: str) -> int:
    """Increment ping_count in lakehouse gold parquet — visible to both warehouses."""
    import duckdb

    GOLD_METRICS.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    src = str(GOLD_METRICS / "**/*.parquet")
    rows = con.execute(
        f"SELECT asset_id, ping_count FROM read_parquet('{src}') WHERE asset_id = ?",
        [asset_id],
    ).fetchall()
    assert rows, f"{asset_id} missing from gold metrics — run examples/demo/seed.py"
    before = int(rows[0][1])
    after = before + 7
    out = GOLD_METRICS / "part-000.parquet"
    # Rewrite full table with bumped row.
    con.execute(
        f"""
        COPY (
          SELECT
            asset_id,
            metric_date,
            CASE WHEN asset_id = '{asset_id}' THEN {after} ELSE ping_count END AS ping_count,
            avg_speed_mph,
            max_speed_mph,
            avg_fuel_level_pct,
            max_odometer_km,
            first_event_ts,
            last_event_ts
          FROM read_parquet('{src}')
        ) TO '{out}' (FORMAT PARQUET)
        """
    )
    # Drop any other parquet leftovers from fixture copy layout.
    for path in GOLD_METRICS.rglob("*.parquet"):
        if path.resolve() != out.resolve():
            path.unlink()
    return after


@pytest.mark.e2e
def test_golden_path_fleet_to_ask_prism(stack_urls: dict[str, str]) -> None:
    assert FIXTURE_IMAGE.is_file()

    # --- 1) Simulated fleet event → bronze via ingestion pipeline ---
    ingest = subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            "docker-compose.yml",
            "-f",
            "docker-compose.demo.yml",
            "exec",
            "-T",
            "ingestion",
            "python",
            "-c",
            (
                "from prism_ingestion.config import IngestConfig\n"
                "from prism_ingestion.pipeline import IngestPipeline\n"
                "cfg = IngestConfig.from_env()\n"
                "pipe = IngestPipeline.from_config(cfg)\n"
                "ok = pipe.process_one()\n"
                "print('accepted' if ok else 'rejected')\n"
                "print(pipe.stats.as_dict())\n"
            ),
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "accepted" in ingest.stdout or "rejected" in ingest.stdout, ingest.stdout

    # --- 2) CV finding (threshold 0.99 via docker-compose.demo.yml → review queue) ---
    frame_ref = f"frm_{uuid.uuid4().hex[:12]}"
    detect = _multipart_detect(stack_urls["cv"], ASSET_ID, frame_ref)
    assert detect["review_count"] >= 1, (
        f"expected review-queue findings (raise CV threshold); got {detect}"
    )
    finding = detect["review_queue"][0]["finding"]
    finding_id = finding["finding_id"]
    defect_class = finding["defect_class"]
    assert finding["asset_id"] == ASSET_ID

    # --- 3) Review queue → approval ---
    inspector = _print_token("inspector")
    code, sync_body = _json(
        "POST",
        f"{stack_urls['control']}/api/v1/review-queue/sync",
        token=inspector,
    )
    assert code == 200, sync_body

    code, queue = _json(
        "GET",
        f"{stack_urls['control']}/api/v1/review-queue",
        token=inspector,
    )
    assert code == 200, queue
    assert any(item.get("finding_id") == finding_id for item in queue), queue  # type: ignore[union-attr]

    code, decision = _json(
        "POST",
        f"{stack_urls['control']}/api/v1/review-queue/{finding_id}/decide",
        token=inspector,
        payload={"decision": "approve", "notes": "phase-11 golden path"},
    )
    assert code == 200, decision
    assert decision["gold_enqueued"] is True  # type: ignore[index]

    # --- 4) Gold table update (reviewed CV finding) ---
    gold_file = CV_GOLD / f"{finding_id}.json"
    for _ in range(30):
        if gold_file.is_file():
            break
        time.sleep(0.2)
    assert gold_file.is_file(), f"missing reviewed gold writeback: {gold_file}"
    gold_payload = json.loads(gold_file.read_text(encoding="utf-8"))
    assert gold_payload["reviewed"] is True
    assert gold_payload["finding_id"] == finding_id

    # --- 5) Warehouse gold bump → visible in Redshift AND Snowflake ---
    new_ping_count = _bump_gold_ping_count(ASSET_ID)
    # activation-gateway container sees the bind mount at /data, not the host path.
    gold_uri = "file:///data/lakehouse/gold/asset_daily_metrics"
    for warehouse, primary in (("redshift", True), ("snowflake", False)):
        code, body = _json(
            "POST",
            f"{stack_urls['activation']}/v1/activate",
            payload={
                "gold_table": "asset_daily_metrics",
                "warehouse": warehouse,
                "gold_uri": gold_uri,
                "set_primary": primary,
            },
        )
        assert code in {200, 201, 409}, (warehouse, code, body)

    results: dict[str, int] = {}
    sql = f"SELECT asset_id, ping_count FROM asset_daily_metrics WHERE asset_id = '{ASSET_ID}'"
    for warehouse in ("redshift", "snowflake"):
        code, body = _json(
            "POST",
            f"{stack_urls['activation']}/v1/query",
            payload={
                "table": "asset_daily_metrics",
                "warehouse": warehouse,
                "sql": sql,
            },
        )
        assert code == 200, (warehouse, body)
        rows = body["rows"]  # type: ignore[index]
        assert rows, (warehouse, body)
        # rows may be list[dict] or list[list]
        row0 = rows[0]
        if isinstance(row0, dict):
            ping = int(row0["ping_count"])
        else:
            # column order from SELECT
            ping = int(row0[1])
        results[warehouse] = ping
    assert results["redshift"] == new_ping_count
    assert results["snowflake"] == new_ping_count
    assert results["redshift"] == results["snowflake"]

    # --- 6) Visible in cockpit API surface (Vite proxies) ---
    viewer = _print_token("viewer")
    code, assets = _json(
        "GET",
        f"{stack_urls['cockpit']}/proxy/control/api/v1/assets",
        token=viewer,
    )
    assert code == 200, assets
    assert any(a.get("asset_id") == ASSET_ID for a in assets), assets  # type: ignore[union-attr]

    code, findings = _json(
        "GET",
        f"{stack_urls['cockpit']}/proxy/control/api/v1/findings",
        token=viewer,
    )
    assert code == 200, findings
    assert any(f.get("finding_id") == finding_id for f in findings), findings  # type: ignore[union-attr]

    code, telemetry = _json(
        "POST",
        f"{stack_urls['cockpit']}/proxy/activation/v1/query",
        payload={
            "table": "asset_daily_metrics",
            "warehouse": "auto",
            "sql": sql,
        },
    )
    assert code == 200, telemetry

    # --- 7) Answerable by Ask PRISM (grounded) ---
    question = (
        f"What defect class and finding id do we have for asset {ASSET_ID}? "
        f"Mention finding {finding_id} if present."
    )
    code, ask = _json(
        "POST",
        f"{stack_urls['copilot']}/v1/ask",
        payload={"question": question, "control_plane_token": viewer},
    )
    assert code == 200, ask
    assert ask["grounded"] is True, ask  # type: ignore[index]
    answer = str(ask["answer"])  # type: ignore[index]
    assert finding_id in answer or ASSET_ID in answer
    # Prefer strong signal when tools returned the finding.
    tools = ask.get("tools_used") or []  # type: ignore[union-attr]
    assert tools, ask
    assert (
        "query_cv_findings" in tools or "query_warehouse" in tools or "query_work_orders" in tools
    )

    # Keep defect_class in the report for humans reading failures.
    assert defect_class
    os.environ["PRISM_GOLDEN_FINDING_ID"] = finding_id


# --- Phase 19 — full chaos scenario: scenario-engine trips a breaker for real,
# a human acknowledges + resolves it via the API, the cockpit proxy reflects
# the state change, and Ask PRISM answers a grounded question about it. ---

CHAOS_SEED = 14
CHAOS_ASSET_ID = "PRISM-AST-001"
CHAOS_TICKS = 20


def _poll_breaker_state(
    incident_base: str, asset_id: str, *, want: str, timeout_s: float = 20.0
) -> dict:
    """Bounded poll — same 0.2s/30-try shape as the gold-file wait above."""
    deadline = time.monotonic() + timeout_s
    last: dict = {}
    while time.monotonic() < deadline:
        code, body = _json("GET", f"{incident_base}/breakers/{asset_id}")
        if code == 200:
            last = body  # type: ignore[assignment]
            if last.get("state") == want:
                return last
        time.sleep(0.3)
    raise AssertionError(f"breaker for {asset_id} never reached {want!r}: {last}")


@pytest.mark.e2e
def test_chaos_golden_path(stack_urls: dict[str, str]) -> None:
    """Phases 12+14+15+18+19, end to end, against the live compose stack.

    scenario-engine (fixed seed 14) -> ingestion's real two-layer validation
    -> incident-engine's OPA/Rego quarantine_rate policy actually trips
    PRISM-AST-001's breaker -> a human acknowledges + resolves it over the
    real API -> the cockpit's own proxy surface (same path the Breaker Board
    fetches) reflects the closed state -> Ask PRISM answers a grounded
    question about the resolved incident.
    """
    incident_base = stack_urls["incident"]

    # OPA is a real dependency container (Phase 18); its own healthcheck can
    # lag incident-engine's plain 200 OK, so wait for policy_engine.ready
    # specifically before driving any chaos through it.
    deadline = time.monotonic() + 20.0
    engine_ready = False
    while time.monotonic() < deadline:
        code, health = _json("GET", f"{incident_base}/health")
        if code == 200 and health.get("policy_engine", {}).get("ready"):  # type: ignore[union-attr]
            engine_ready = True
            break
        time.sleep(0.5)
    assert engine_ready, "incident-engine's OPA policy engine never became ready"

    # Sanity: this asset must not already have an open breaker from an
    # earlier test/run sharing the same live stack.
    code, before = _json("GET", f"{incident_base}/breakers/{CHAOS_ASSET_ID}")
    if code == 200 and before.get("state") != "closed":  # type: ignore[union-attr]
        pytest.skip(f"{CHAOS_ASSET_ID} breaker not closed before chaos run: {before}")

    # --- 1) Drive real chaos through the real pipeline (Phase 12 + 13) ---
    # Same admin endpoint the cockpit's ScenarioControls.vue calls -- reuses
    # IngestPipeline.process_one exactly, on an isolated pipeline instance so
    # this doesn't disturb the continuously-running live-mode pipeline.
    code, run_result = _json(
        "POST",
        f"{stack_urls['ingestion']}/v1/scenario-runs",
        payload={
            "seed": CHAOS_SEED,
            "ticks": CHAOS_TICKS,
            "rate_hz": 10.0,
            "scenario_id": "scn_phase19_chaos",
        },
    )
    assert code == 200, run_result
    assert run_result["rejected"] >= 3, run_result  # type: ignore[index]

    # --- 2) incident-engine's real OPA/Rego quarantine_rate policy trips it
    # (Phase 14 FSM + Phase 18 Rego -- not asserted/faked, polled for real) ---
    opened = _poll_breaker_state(incident_base, CHAOS_ASSET_ID, want="open")
    assert opened["trip_reason"] == "quarantine_rate", opened
    incident_id = opened["incident_id"]
    assert incident_id, opened

    code, incident = _json("GET", f"{incident_base}/incidents/{incident_id}")
    assert code == 200, incident
    assert incident["status"] == "open", incident  # type: ignore[index]
    assert incident["asset_id"] == CHAOS_ASSET_ID, incident  # type: ignore[index]

    # --- 3) A human acknowledges, then resolves, over the real API (Phase 14) ---
    code, ack = _json("POST", f"{incident_base}/incidents/{incident_id}/acknowledge")
    assert code == 200, ack
    assert ack["status"] == "acknowledged", ack  # type: ignore[index]

    code, resolved = _json("POST", f"{incident_base}/incidents/{incident_id}/resolve")
    assert code == 200, resolved
    assert resolved["status"] == "resolved", resolved  # type: ignore[index]

    # --- 4) Breaker closes immediately on manual resolve (store.py resolve()) ---
    code, after = _json("GET", f"{incident_base}/breakers/{CHAOS_ASSET_ID}")
    assert code == 200, after
    assert after["state"] == "closed", after  # type: ignore[index]
    assert after["incident_id"] is None, after  # type: ignore[index]

    # --- 5) Cockpit reflects it -- same /proxy/incident path BreakerBoard.vue
    # and ScenarioControls.vue actually fetch, not a re-implementation ---
    code, cockpit_breaker = _json(
        "GET", f"{stack_urls['cockpit']}/proxy/incident/breakers/{CHAOS_ASSET_ID}"
    )
    assert code == 200, cockpit_breaker
    assert cockpit_breaker["state"] == "closed", cockpit_breaker  # type: ignore[index]

    code, cockpit_incident = _json(
        "GET", f"{stack_urls['cockpit']}/proxy/incident/incidents/{incident_id}"
    )
    assert code == 200, cockpit_incident
    assert cockpit_incident["status"] == "resolved", cockpit_incident  # type: ignore[index]

    # --- 6) Ask PRISM answers grounded, from real incident-engine data
    # (Phase 15's query_breakers/query_incidents tools, ADR-004) ---
    viewer = _print_token("viewer")
    question = f"What happened to asset {CHAOS_ASSET_ID}? Is its circuit breaker open right now?"
    code, ask = _json(
        "POST",
        f"{stack_urls['copilot']}/v1/ask",
        payload={"question": question, "control_plane_token": viewer},
    )
    assert code == 200, ask
    assert ask["grounded"] is True, ask  # type: ignore[index]
    answer = str(ask["answer"])  # type: ignore[index]
    assert CHAOS_ASSET_ID in answer, ask
    tools = ask.get("tools_used") or []  # type: ignore[union-attr]
    assert "query_breakers" in tools or "query_incidents" in tools, ask
