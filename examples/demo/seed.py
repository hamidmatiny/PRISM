#!/usr/bin/env python3
"""Materialize demo gold + bootstrap control-plane entities.

Idempotent. Safe to re-run. Does not call paid APIs (ADR-001).
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_GOLD = ROOT / "activation-gateway" / "fixtures" / "gold" / "asset_daily_metrics"
DATA = ROOT / ".data"
GOLD_METRICS = DATA / "lakehouse" / "gold" / "asset_daily_metrics"
ASSETS = Path(__file__).resolve().parent / "assets.json"
WORK_ORDERS = Path(__file__).resolve().parent / "work_orders.json"


def _http_json(
    method: str,
    url: str,
    *,
    token: str | None = None,
    body: dict | None = None,
) -> tuple[int, object]:
    data = None if body is None else json.dumps(body).encode()
    headers = {"content-type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
            payload: object = json.loads(raw) if raw else {}
            return resp.getcode() or 0, payload
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload = raw.decode("utf-8", errors="replace")
        return exc.code, payload


def materialize_gold() -> None:
    GOLD_METRICS.mkdir(parents=True, exist_ok=True)
    for path in GOLD_METRICS.glob("**/*"):
        if path.is_file():
            path.unlink()
    for parquet in FIXTURE_GOLD.glob("**/*.parquet"):
        rel = parquet.relative_to(FIXTURE_GOLD)
        dest = GOLD_METRICS / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(parquet, dest)
    # Ensure review/findings dirs exist for the bind mount.
    for sub in (
        DATA / "cv-review-queue" / "pending",
        DATA / "cv-review-queue" / "decided",
        DATA / "lakehouse" / "gold" / "cv_findings",
        DATA / "cv-findings" / "published",
        DATA / "bronze",
        DATA / "activation",
        DATA / "otel",
    ):
        sub.mkdir(parents=True, exist_ok=True)
    print(f"gold metrics → {GOLD_METRICS}")


def activate_warehouses(activation_base: str, gold_uri: str | None = None) -> None:
    # Compose activation-gateway sees the bind mount at /data, not the host path.
    uri = gold_uri or "file:///data/lakehouse/gold/asset_daily_metrics"
    if not uri.startswith("file://"):
        uri = f"file://{uri}"
    for warehouse, primary in (("redshift", True), ("snowflake", False)):
        code, body = _http_json(
            "POST",
            f"{activation_base}/v1/activate",
            body={
                "gold_table": "asset_daily_metrics",
                "warehouse": warehouse,
                "gold_uri": uri,
                "set_primary": primary,
            },
        )
        if code not in {200, 201, 409}:
            raise SystemExit(f"activate {warehouse} failed: {code} {body}")
        print(f"activated asset_daily_metrics on {warehouse} ({code}) uri={uri}")


def bootstrap_control_plane(control_base: str, token: str) -> None:
    assets = json.loads(ASSETS.read_text(encoding="utf-8"))
    for asset in assets:
        code, body = _http_json(
            "POST",
            f"{control_base}/api/v1/assets",
            token=token,
            body=asset,
        )
        if code not in {200, 201, 409}:
            # Some deployments use PUT-only; fall back to list check.
            print(f"warn: create asset {asset['asset_id']}: {code} {body}")
    existing_wo = _http_json("GET", f"{control_base}/api/v1/work-orders", token=token)
    if existing_wo[0] != 200:
        raise SystemExit(f"list work-orders failed: {existing_wo}")
    have = {
        (w.get("asset_id"), w.get("title"))
        for w in existing_wo[1]  # type: ignore[union-attr]
        if isinstance(w, dict)
    }
    for wo in json.loads(WORK_ORDERS.read_text(encoding="utf-8")):
        key = (wo["asset_id"], wo["title"])
        if key in have:
            continue
        code, body = _http_json(
            "POST",
            f"{control_base}/api/v1/work-orders",
            token=token,
            body=wo,
        )
        if code not in {200, 201}:
            raise SystemExit(f"create work-order failed: {code} {body}")
        print(f"work-order → {wo['asset_id']}: {wo['title']}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--control-plane", default="http://127.0.0.1:9100")
    parser.add_argument("--activation", default="http://127.0.0.1:9103")
    parser.add_argument("--token", default="", help="control-plane Bearer (fleetadmin/inspector)")
    parser.add_argument(
        "--gold-uri",
        default="file:///data/lakehouse/gold/asset_daily_metrics",
        help="gold URI as seen by activation-gateway (compose default /data/...)",
    )
    parser.add_argument("--skip-http", action="store_true", help="only materialize gold files")
    args = parser.parse_args()

    materialize_gold()
    if args.skip_http:
        return 0

    code, _ = _http_json("GET", f"{args.activation}/health")
    if code != 200:
        print("activation-gateway not healthy — gold files only", file=sys.stderr)
        return 0
    activate_warehouses(args.activation, gold_uri=args.gold_uri)

    if not args.token:
        print("no --token; skipped control-plane bootstrap")
        return 0
    code, _ = _http_json("GET", f"{args.control_plane}/health")
    if code != 200:
        print("control-plane not healthy — skipped bootstrap", file=sys.stderr)
        return 0
    bootstrap_control_plane(args.control_plane, args.token)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
