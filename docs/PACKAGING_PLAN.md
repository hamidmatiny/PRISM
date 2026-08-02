# Packaging plan (GHCR)

**Plan only.** Do not publish images until a deliberate tagged release
(see [RELEASE_PLAN.md](./RELEASE_PLAN.md)). Mid-phase `docker push` is out of scope.

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

| Service | Image | Publish at |
|---------|-------|------------|
| `ingestion` | `…/prism/ingestion` | **v1.0.0** |
| `cv-service` | `…/prism/cv-service` | **v1.0.0** |
| `activation-gateway` | `…/prism/activation-gateway` | **v1.0.0** |
| `control-plane` | `…/prism/control-plane` | **v1.0.0** |
| `lakehouse` | `…/prism/lakehouse` | **v1.0.0** (batch/job image) |
| `control-plane-worker` | same image as control-plane, different command | n/a (reuse) |
| foundation-stub | **internal-only** (nginx static) | do not publish |
| LocalStack / mock warehouses | **internal-only** | do not publish |

Later tracks:

| Service | First publish track |
|---------|---------------------|
| `cockpit` | v1.2.0 |
| `ai-copilot` | v1.2.0 |

## Tagging strategy (tied to RELEASE_PLAN)

| Tag | Meaning |
|-----|---------|
| `v1.0.0` | Immutable release tag matching git tag |
| `1.0.0` | Same semver without `v` prefix (optional convenience) |
| `1.0` | Rolling minor pointer (optional) |
| `latest` | Points at newest **tagged** release on `main` (never at arbitrary phase commits) |
| `sha-<gitsha>` | Optional provenance tag from release workflow |

Do **not** publish `:latest` from every phase commit on `main`.

## What is worth publishing vs internal-only

**Publish** — anything an operator would pull to run the product loop:
ingestion, cv-service, activation-gateway, control-plane, lakehouse job image.

**Internal-only** — compose helpers and emulators (foundation stub, LocalStack,
embedded mock Redshift/Snowflake). Those exist for ADR-001 local/CI paths and
are not product runtime.

## Release workflow (future, not implemented here)

1. Human cuts `vX.Y.Z` after RELEASE_PLAN gate.
2. CI release job builds listed Dockerfiles with `docker/build-push-action`.
3. Labels: `org.opencontainers.image.source`, revision, version.
4. Sign/attest optional later (Phase 10 hardening).

## Local build today (no push)

```bash
docker compose build ingestion cv-service activation-gateway control-plane lakehouse
```
