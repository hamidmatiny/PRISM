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

### v1.1.0 additions (phases 12/14 shipped services, published starting v1.1.0)

| Service | Image |
|---------|-------|
| `scenario-engine` | `ghcr.io/hamidmatiny/prism/scenario-engine` |
| `incident-engine` | `ghcr.io/hamidmatiny/prism/incident-engine` |

These existed on `main` since Phase 12/14 but were not in the GHCR publish
matrix until this release — `release-packages.yml`'s matrix is now 9 services,
not 7.

### v1.2.0 additions (phase 16 shipped service)

| Service | Image |
|---------|-------|
| `drift-monitor` | `ghcr.io/hamidmatiny/prism/drift-monitor` |

Added to the GHCR publish matrix in the same commit that shipped the service
(Phase 16) rather than as a later fix — the v1.1.0 gap above is exactly why.

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

Automated by [`.github/workflows/release-packages.yml`](../.github/workflows/release-packages.yml):

1. Push an annotated tag `vX.Y.Z` (or re-run **Release packages** via `workflow_dispatch` with that tag).
2. The workflow builds each Dockerfile with Buildx and pushes
   `:vX.Y.Z`, `:X.Y.Z`, `:latest`, and `:sha-<short>` to GHCR.
3. OCI labels: `org.opencontainers.image.{source,version,revision,title}`.

Manual local push (requires a PAT with `write:packages`):

```bash
VERSION=v1.0.0
# … docker build / docker push as in the workflow matrix …
```

## Local build (no push)

```bash
docker compose build ingestion cv-service activation-gateway control-plane lakehouse ai-copilot
```
