# e2e tests

Phase 11 golden-path lives here. Unit CI does not require the live stack.

```bash
make demo          # <5 min — demo compose + seed
make e2e           # PRISM_E2E=1 pytest tests/e2e
```

| Test | Chain |
|------|-------|
| `test_golden_path_fleet_to_ask_prism` | ingest → CV review → approve → gold → Redshift+Snowflake → cockpit proxies → Ask PRISM |

Unit CI collects these files only when pointed at `tests/e2e`; without `PRISM_E2E=1` the suite skips. The GitHub Actions `e2e` job runs `make demo` then this suite after lint/test/cockpit/terraform gates are green.
