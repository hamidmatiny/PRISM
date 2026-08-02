"""Load canonical expectations and project them to UC table-property maps."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

# Prefer packaged data (works when installed / in Docker); fall back to repo path.
_PACKAGE_EXPECTATIONS = Path(__file__).resolve().parent / "data" / "expectations.yaml"
_REPO_EXPECTATIONS = Path(__file__).resolve().parents[2] / "quality" / "expectations.yaml"

# UC property key prefix — auditable on the table, not buried in job code.
PROPERTY_PREFIX = "quality.expectation."


def expectations_path(path: Path | None = None) -> Path:
    if path is not None:
        return path
    if _PACKAGE_EXPECTATIONS.is_file():
        return _PACKAGE_EXPECTATIONS
    if _REPO_EXPECTATIONS.is_file():
        return _REPO_EXPECTATIONS
    raise FileNotFoundError("expectations.yaml not found in package data or lakehouse/quality/")


def load_expectations(path: Path | None = None) -> dict[str, Any]:
    target = expectations_path(path)
    with target.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict) or "tables" not in data:
        raise ValueError(f"Invalid expectations file: {target}")
    return data


def table_properties_for(table_key: str, path: Path | None = None) -> dict[str, str]:
    """Return Unity Catalog TBLPROPERTIES map for ``schema.table``."""
    data = load_expectations(path)
    table = data["tables"].get(table_key)
    if table is None:
        raise KeyError(f"Unknown table key: {table_key}")
    props: dict[str, str] = {
        "quality.expectations_source": "lakehouse/quality/expectations.yaml",
    }
    for item in table.get("expectations", []):
        name = item["name"]
        props[f"{PROPERTY_PREFIX}{name}"] = item["constraint"]
        props[f"{PROPERTY_PREFIX}{name}.action"] = item.get("action", "fail")
    return props


def all_table_keys(path: Path | None = None) -> list[str]:
    return sorted(load_expectations(path)["tables"].keys())
