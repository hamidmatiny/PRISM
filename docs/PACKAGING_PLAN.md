# Packaging plan (GHCR)

Publish container images **at tagged release time** (see [RELEASE_PLAN.md](./RELEASE_PLAN.md)).
Mid-phase `docker push` on arbitrary `main` commits is out of scope.
GHCR publish for a public repo is free and is **not** restricted by ADR-001
(ADR-001 forbids paid cloud apply / paid APIs / GPU in CI — not OSS registry pushes).

## Registry

| Item | Value |
|------|--------|
| Registry | `ghcr.io` |
| Namespace | `ghcr.io/hamidmatiny/prism` |
| Visibility | Public images OK for OSS; secrets never baked into layers |

## Image naming

```text
ghcr.io/hamidmatiny/prism/<service>:<tag>
```

### Core images (required at v1.0.0)

| Service | Image |
|---------|-------|
| `ingestion` | `ghcr.io/hamidmatiny/prism/ingestion` |
| `cv-service` | `ghcr.io/hamidmatiny/prism/cv-service` |
| `activation-gateway` | `ghcr.io/hamidmatiny/prism/activation-gateway` |
| `control-plane` | `ghcr.io/hamidmatiny/prism/control-plane` |
| `lakehouse` | `ghcr.io/hamidmatiny/prism/lakehouse` |

`control-plane-worker` reuses the control-plane image with a different command.

### Surface images (also published at v1.0.0 — phases 8–9 shipped before first tag)

| Service | Image |
|---------|-------|
| `cockpit` | `ghcr.io/hamidmatiny/prism/cockpit` |
| `ai-copilot` | `ghcr.io/hamidmatiny/prism/ai-copilot` |

### Internal-only (do not publish)

foundation-stub (nginx), LocalStack, embedded mock Redshift/Snowflake — ADR-001
local/CI helpers, not product runtime.

## Tagging strategy

| Tag | Meaning |
|-----|---------|
| `v1.0.0` | Immutable release tag matching git tag |
| `1.0.0` | Same semver without `v` prefix |
| `latest` | Points at newest **tagged** release on `main` |
| `sha-<gitsha>` | Provenance tag from the release commit |

Do **not** publish `:latest` from every phase commit on `main`.

## Release publish steps

```bash
VERSION=v1.0.0
SHA=$(git rev-parse --short HEAD)
OWNER=hamidmatiny
NS=ghcr.io/${OWNER}/prism

echo "$GHCR_TOKEN" | docker login ghcr.io -u "$OWNER" --password-stdin

for svc in ingestion cv-service activation-gateway control-plane lakehouse ai-copilot; do
  docker build -f "$svc/Dockerfile" -t "$NS/$svc:$VERSION" -t "$NS/$svc:1.0.0" \
    -t "$NS/$svc:latest" -t "$NS/$svc:sha-$SHA" \
    --label "org.opencontainers.image.source=https://github.com/${OWNER}/PRISM" \
    --label "org.opencontainers.image.version=$VERSION" \
    --label "org.opencontainers.image.revision=$(git rev-parse HEAD)" \
    .
  docker push "$NS/$svc:$VERSION"
  docker push "$NS/$svc:1.0.0"
  docker push "$NS/$svc:latest"
  docker push "$NS/$svc:sha-$SHA"
done

# cockpit (Vite static build; see cockpit/Dockerfile if present, else multi-stage)
docker build -f cockpit/Dockerfile -t "$NS/cockpit:$VERSION" ...
```

## Local build (no push)

```bash
docker compose build ingestion cv-service activation-gateway control-plane lakehouse ai-copilot
```
