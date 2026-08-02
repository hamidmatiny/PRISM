"""Structural validation of UC bootstrap + Lakeflow expectation wiring (CI / ADR-001)."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
sys.path.insert(0, str(ROOT / "src"))

from prism_lakehouse.expectations import PROPERTY_PREFIX, load_expectations  # noqa: E402

BOOTSTRAP = Path(__file__).resolve().parent / "bootstrap.sql"
LAKEFLOW_YML = ROOT / "lakeflow" / "prism_medallion.yml"
LAKEFLOW_NOTEBOOK = ROOT / "lakeflow" / "medallion_notebook.py"
JOB_JSON = ROOT / "jobs" / "databricks_job_medallion.json"


def _fail(msg: str) -> None:
    print(f"FAIL: {msg}", file=sys.stderr)
    raise SystemExit(1)


def main() -> int:
    data = load_expectations()
    if not BOOTSTRAP.is_file():
        _fail("bootstrap.sql missing — run render_bootstrap.py")

    sql = BOOTSTRAP.read_text(encoding="utf-8")
    if "CREATE CATALOG" not in sql:
        _fail("bootstrap.sql missing CREATE CATALOG")
    if "GRANT " not in sql:
        _fail("bootstrap.sql missing GRANT statements")
    if "SET TBLPROPERTIES" not in sql:
        _fail("bootstrap.sql missing SET TBLPROPERTIES")

    # Every expectation must appear as a UC table property key in bootstrap SQL.
    for table_key, table in data["tables"].items():
        schema, name = table_key.split(".", 1)
        fq = f"{data['catalog']}.{schema}.{name}"
        if fq not in sql and f"{schema}.{name}" not in sql:
            _fail(f"table {fq} not referenced in bootstrap.sql")
        for item in table["expectations"]:
            prop = f"{PROPERTY_PREFIX}{item['name']}"
            if prop not in sql:
                _fail(f"missing TBLPROPERTIES key {prop} for {table_key}")
            # Constraint text is SQL-string-escaped (single quotes doubled).
            escaped = item["constraint"].replace("'", "''")
            if escaped not in sql and item["constraint"] not in sql:
                _fail(f"constraint for {prop} not present in bootstrap.sql")

    # Lakeflow YAML expectation_keys must match the YAML manifest exactly.
    lakeflow = yaml.safe_load(LAKEFLOW_YML.read_text(encoding="utf-8"))
    for entry in lakeflow["tables"]:
        table_key = entry["name"]
        expected = {e["name"] for e in data["tables"][table_key]["expectations"]}
        got = set(entry["expectation_keys"])
        if expected != got:
            _fail(f"Lakeflow keys for {table_key} mismatch: {got ^ expected}")
        if entry.get("expectations_source") != "unity_catalog_table_properties":
            _fail(f"{table_key} must source expectations from UC table properties")

    # Notebook @dp.expect* keys must match the manifest (no rogue / missing keys).
    notebook = LAKEFLOW_NOTEBOOK.read_text(encoding="utf-8")
    all_manifest_keys = {e["name"] for t in data["tables"].values() for e in t["expectations"]}
    used_in_expects: set[str] = set()
    for block in re.findall(r"@dp\.expect_all(?:_or_drop)?\(\s*\{([^}]+)\}", notebook, re.S):
        used_in_expects.update(re.findall(r'"([a-z0-9_]+)"\s*:', block))
    used_in_expects.update(re.findall(r'@dp\.expect_or_drop\(\s*"([a-z0-9_]+)"', notebook))
    unknown = used_in_expects - all_manifest_keys
    if unknown:
        _fail(f"notebook expectation keys not in manifest: {sorted(unknown)}")
    missing = all_manifest_keys - used_in_expects
    if missing:
        _fail(f"manifest expectation keys missing from Lakeflow notebook: {sorted(missing)}")

    job = json.loads(JOB_JSON.read_text(encoding="utf-8"))
    if "tasks" not in job or not job["tasks"]:
        _fail("databricks job JSON missing tasks")
    if job.get("tags", {}).get("cost_safety") != "manual-apply-only":
        _fail("databricks job must be tagged cost_safety=manual-apply-only")

    # Refuse accidental apply instructions in CI-facing scripts.
    if "terraform apply" in sql.lower():
        _fail("bootstrap.sql must not reference terraform apply")

    print("OK: Unity Catalog bootstrap + Lakeflow expectation wiring is structurally valid")
    print(f"  tables={len(data['tables'])} property_prefix={PROPERTY_PREFIX}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
