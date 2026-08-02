# prism-otel

Shared OpenTelemetry setup for PRISM ECS-bound services.

| Env | Default | Notes |
|-----|---------|-------|
| `OTEL_SERVICE_NAME` | (required via code) | Service name in traces |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | unset | e.g. `http://otel-collector:4318` |
| `OTEL_SDK_DISABLED` | `false` | Set `true` to no-op (CI default when unset endpoint) |
| `OTEL_RESOURCE_ATTRIBUTES` | — | Optional `deployment.environment=local` |

When no OTLP endpoint is configured, setup is a **no-op** so unit tests stay offline (ADR-001).
