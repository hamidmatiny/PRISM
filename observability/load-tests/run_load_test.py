#!/usr/bin/env python3
"""Basic load test: activation-gateway + control-plane (cockpit API surface).

Usage (stack healthy on default ports):
  TOKEN=$(docker compose exec -T control-plane python manage.py print_api_token viewer)
  python observability/load-tests/run_load_test.py --token "$TOKEN"

Writes JSON summary to observability/load-tests/last-run.json and prints a table.
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path


@dataclass
class EndpointResult:
    name: str
    latencies_ms: list[float] = field(default_factory=list)
    errors: int = 0
    status_codes: dict[int, int] = field(default_factory=dict)

    def record(self, ms: float, code: int) -> None:
        self.latencies_ms.append(ms)
        self.status_codes[code] = self.status_codes.get(code, 0) + 1
        if code >= 400:
            self.errors += 1

    def summary(self) -> dict:
        xs = sorted(self.latencies_ms)
        n = len(xs)
        if n == 0:
            return {
                "name": self.name,
                "requests": 0,
                "errors": self.errors,
                "error_rate": 1.0,
            }
        p95_idx = min(n - 1, max(0, int(round(0.95 * (n - 1)))))
        return {
            "name": self.name,
            "requests": n,
            "errors": self.errors,
            "error_rate": self.errors / n,
            "latency_ms": {
                "p50": statistics.median(xs),
                "p95": xs[p95_idx],
                "mean": statistics.fmean(xs),
                "max": xs[-1],
            },
            "status_codes": dict(sorted(self.status_codes.items())),
        }


def _request(
    method: str, url: str, headers: dict[str, str], body: bytes | None
) -> tuple[int, float]:
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp.read()
            code = resp.getcode() or 0
    except urllib.error.HTTPError as exc:
        code = exc.code
    except Exception:  # noqa: BLE001
        return 599, (time.perf_counter() - t0) * 1000
    return code, (time.perf_counter() - t0) * 1000


def main() -> int:
    parser = argparse.ArgumentParser(description="PRISM Phase 10 basic load test")
    parser.add_argument("--activation-base", default="http://127.0.0.1:9103")
    parser.add_argument("--control-plane-base", default="http://127.0.0.1:9100")
    parser.add_argument("--cockpit-base", default="http://127.0.0.1:9101")
    parser.add_argument("--token", default="", help="control-plane Bearer token")
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--requests", type=int, default=40, help="per endpoint")
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parent / "last-run.json",
    )
    args = parser.parse_args()

    auth = {"Authorization": f"Bearer {args.token}"} if args.token else {}
    # Ensure routing exists so /v1/query warehouse=auto is deterministic.
    activate_body = json.dumps(
        {
            "gold_table": "asset_daily_metrics",
            "warehouse": "redshift",
            "gold_uri": "file:///app/activation-gateway/fixtures/gold/asset_daily_metrics",
            "set_primary": True,
        }
    ).encode()
    act_code, _ = _request(
        "POST",
        f"{args.activation_base}/v1/activate",
        {"content-type": "application/json"},
        activate_body,
    )
    if act_code not in {200, 201, 409}:
        print(f"warn: activate returned {act_code} — query load may error")

    query_body = json.dumps(
        {
            "table": "asset_daily_metrics",
            "warehouse": "auto",
            "sql": "SELECT asset_id, ping_count FROM asset_daily_metrics LIMIT 5",
        }
    ).encode()

    endpoints: list[tuple[str, str, str, dict[str, str], bytes | None]] = [
        ("activation.health", "GET", f"{args.activation_base}/health", {}, None),
        (
            "activation.query",
            "POST",
            f"{args.activation_base}/v1/query",
            {"content-type": "application/json"},
            query_body,
        ),
        ("control_plane.health", "GET", f"{args.control_plane_base}/health", {}, None),
        (
            "control_plane.me",
            "GET",
            f"{args.control_plane_base}/api/v1/me",
            dict(auth),
            None,
        ),
        (
            "control_plane.work_orders",
            "GET",
            f"{args.control_plane_base}/api/v1/work-orders",
            dict(auth),
            None,
        ),
        (
            "cockpit.proxy.control_health",
            "GET",
            f"{args.cockpit_base}/proxy/control/health",
            {},
            None,
        ),
    ]

    results = {name: EndpointResult(name=name) for name, *_ in endpoints}

    def one(name: str, method: str, url: str, headers: dict[str, str], body: bytes | None) -> None:
        code, ms = _request(method, url, headers, body)
        results[name].record(ms, code)

    t_start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futs = []
        for name, method, url, headers, body in endpoints:
            for _ in range(args.requests):
                futs.append(pool.submit(one, name, method, url, headers, body))
        for fut in as_completed(futs):
            fut.result()
    wall_s = time.perf_counter() - t_start

    payload = {
        "started_at": datetime.now(UTC).isoformat(),
        "concurrency": args.concurrency,
        "requests_per_endpoint": args.requests,
        "wall_seconds": round(wall_s, 3),
        "endpoints": [results[name].summary() for name, *_ in endpoints],
    }
    args.out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    print(f"wall_s={wall_s:.2f} concurrency={args.concurrency} n={args.requests}")
    print(f"{'endpoint':36} {'n':>5} {'err%':>6} {'p50':>8} {'p95':>8} {'mean':>8}")
    for s in payload["endpoints"]:
        lat = s.get("latency_ms", {})
        print(
            f"{s['name']:36} {s['requests']:5d} {100 * s['error_rate']:5.1f}% "
            f"{lat.get('p50', 0):8.1f} {lat.get('p95', 0):8.1f} {lat.get('mean', 0):8.1f}"
        )
    print(f"wrote {args.out}")
    # Fail if auth endpoints error when token provided, or any health fails hard.
    hard = [s for s in payload["endpoints"] if s["error_rate"] > 0.05]
    if hard and args.token:
        return 1
    if any(s["name"].endswith(".health") and s["error_rate"] > 0 for s in payload["endpoints"]):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
