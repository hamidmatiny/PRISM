# scenario-engine

Seeded, audited chaos **source** for PRISM (Phase 12). Samples per-asset
outcomes from a weighted distribution and feeds ingestion via
`PRISM_SOURCE_MODE=scenario`. Every emit is labeled `synthetic_scenario: true`
([ADR-005](../docs/adr/005-earned-evidence-policy.md)).

| | |
|---|---|
| **Port (host)** | **9107** |
| **Health** | `GET /health` |
| **Next event** | `GET /v1/next-event` |
| **Resume stalled asset** | `POST /v1/assets/{id}/resume` |
| **Journal** | `$PRISM_DATA_ROOT/scenario/journal/<scenario_id>.jsonl` |

## Outcomes

`clean`, `sensor_corrupt`, `contract_violation`, `cv_low_confidence`,
`cv_high_confidence`, `drift_signature`, `stalled_source` — weights in
`src/prism_scenario_engine/weights/default_weights.yaml`.

Ingestion remains the contract authority (validate → bronze / DLQ). This
service never writes bronze itself.

## Test it yourself

Replay identity (same seed → identical journals):

```bash
# From repo root
pip install -e contracts/telemetry-schema -e scenario-engine

rm -rf /tmp/prism-scn-a /tmp/prism-scn-b
PRISM_DATA_ROOT=/tmp/prism-scn-a PRISM_SCENARIO_SEED=42 PRISM_SCENARIO_ID=scn_42 \
  python -c "
from prism_scenario_engine.config import ScenarioConfig
from prism_scenario_engine.api import create_app
from fastapi.testclient import TestClient
c = TestClient(create_app(ScenarioConfig.from_env()))
for _ in range(40):
    c.get('/v1/next-event')
print(c.get('/health').json()['journal_path'])
"

PRISM_DATA_ROOT=/tmp/prism-scn-b PRISM_SCENARIO_SEED=42 PRISM_SCENARIO_ID=scn_42 \
  python -c "
from prism_scenario_engine.config import ScenarioConfig
from prism_scenario_engine.api import create_app
from fastapi.testclient import TestClient
c = TestClient(create_app(ScenarioConfig.from_env()))
for _ in range(40):
    c.get('/v1/next-event')
"

diff /tmp/prism-scn-a/scenario/journal/scn_42.jsonl \
     /tmp/prism-scn-b/scenario/journal/scn_42.jsonl \
  && echo "JOURNALS_IDENTICAL"
```

Compose (with ingestion in scenario mode):

```bash
PRISM_SOURCE_MODE=scenario docker compose up -d --build scenario-engine ingestion
curl -sS http://127.0.0.1:9107/health
curl -sS http://127.0.0.1:9107/v1/next-event | python -m json.tool
```
