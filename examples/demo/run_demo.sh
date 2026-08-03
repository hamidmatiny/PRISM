#!/usr/bin/env bash
# Stand up the full PRISM demo stack with realistic data in under five minutes.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

START=$(date +%s)
# Local budget 5 minutes; CI may set DEMO_DEADLINE_SECONDS=600 for cold image pulls.
BUDGET="${DEMO_DEADLINE_SECONDS:-300}"
DEADLINE=$((START + BUDGET))

compose() {
  docker compose -f docker-compose.yml -f docker-compose.demo.yml "$@"
}

echo "==> [demo] materialize gold (offline)"
python3 examples/demo/seed.py --skip-http

echo "==> [demo] compose up (demo overrides: CV threshold 0.99)"
compose up -d --build \
  otel-collector ingestion cv-service activation-gateway \
  control-plane control-plane-worker ai-copilot cockpit

wait_http() {
  local url="$1" name="$2"
  while true; do
    now=$(date +%s)
    if (( now > DEADLINE )); then
      echo "ERROR: timed out waiting for $name ($url) after ${BUDGET}s" >&2
      compose ps >&2 || true
      exit 1
    fi
    if curl -sf "$url" >/dev/null 2>&1; then
      echo "    healthy: $name"
      return 0
    fi
    sleep 2
  done
}

echo "==> [demo] wait for health"
wait_http "http://127.0.0.1:9105/health" "ingestion"
wait_http "http://127.0.0.1:9102/health" "cv-service"
wait_http "http://127.0.0.1:9103/health" "activation-gateway"
wait_http "http://127.0.0.1:9100/health" "control-plane"
wait_http "http://127.0.0.1:9104/health" "ai-copilot"
wait_http "http://127.0.0.1:9107/health" "scenario-engine"
wait_http "http://127.0.0.1:9108/health" "incident-engine"
# cockpit is Vite — any HTTP response is fine
while ! curl -sf -o /dev/null "http://127.0.0.1:9101/" 2>/dev/null; do
  now=$(date +%s)
  if (( now > DEADLINE )); then
    echo "ERROR: timed out waiting for cockpit" >&2
    exit 1
  fi
  sleep 2
done
echo "    healthy: cockpit"

# bootstrap_rbac usernames: viewer, inspector, fleetadmin (role name is fleet-admin)
ADMIN_TOKEN="$(compose exec -T control-plane python manage.py print_api_token fleetadmin | tr -d '\r' | tail -n1)"
VIEWER_TOKEN="$(compose exec -T control-plane python manage.py print_api_token viewer | tr -d '\r' | tail -n1)"

echo "==> [demo] seed HTTP (activate WH + bootstrap assets/WOs)"
python3 examples/demo/seed.py --token "$ADMIN_TOKEN"

ELAPSED=$(( $(date +%s) - START ))
echo
echo "PRISM demo ready in ${ELAPSED}s (budget ${BUDGET}s)"
echo "  Cockpit:     http://127.0.0.1:9101"
echo "  Control:     http://127.0.0.1:9100"
echo "  Activation:  http://127.0.0.1:9103"
echo "  Ask PRISM:   http://127.0.0.1:9104"
echo "  Viewer token (paste into cockpit):"
echo "  $VIEWER_TOKEN"
echo
echo "Next: open docs/DEMO_SCRIPT.md or run:"
echo "  PRISM_E2E=1 pytest -q tests/e2e"
if (( ELAPSED > BUDGET )); then
  echo "ERROR: demo exceeded ${BUDGET}s budget" >&2
  exit 1
fi
