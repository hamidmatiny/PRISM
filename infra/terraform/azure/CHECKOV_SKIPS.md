# Checkov skip ledger (Azure Terraform)

Machine-readable skips live in [`.checkov.yml`](.checkov.yml) and as
`#checkov:skip=<ID>: <reason>` comments on the owning resources.

**Rule:** every skip here must have a written reason. Silent skips are not allowed.
**Rule:** CI must invoke checkov with `--config-file .checkov.yml` only — never also
pass `--skip-check` / `skip_check:` (CLI overrides wipe the YAML skip list).

Pinned version: see `../CHECKOV_VERSION`.

| Check ID | Resource(s) | Decision | Reason |
|----------|-------------|----------|--------|
| `CKV_TF_1` | local modules | suppress | Sources are `./modules/*`, not remote git refs with version pins. |
| `CKV_AZURE_44` / `CKV2_AZURE_1` | ADLS storage account | suppress | Customer-managed keys add Key Vault + identity cost to a **warm standby**. Microsoft-managed encryption is accepted for the DR mirror; CMK is a prod harden when DR is exercised regularly. |
| `CKV_AZURE_206` | ADLS replication type | suppress | **LRS** is intentional: primary durability stays on AWS multi-AZ / versioned S3. Paying GRS on the standby doubles storage bill for a rarely used mirror (see ADR-003). |
| `CKV_AZURE_158` | Databricks workspace | suppress | Private Link / no-public-IP networking is the prod harden path; warm-standby job clusters use `no_public_ip` on clusters while workspace API access remains for human operators. |
| `CKV2_AZURE_21` | storage containers | suppress | Diagnostic settings are apply-time ops wiring (Log Analytics workspace not in this scaffold). |
| `CKV_AZURE_33` / `CKV_AZURE_59` | storage account | suppress (belt) | HTTPS-only + public access disabled are set in HCL; retained as documented if graph checks still fire across modules. |
| `CKV_AZURE_43` | storage account name | suppress | Name is `${prefix}lakedr${random}` truncated to 24 chars, lowercase alphanumeric only. Checkov cannot evaluate `random_string` at static scan time. |
| `CKV_AZURE_244` | storage local users | suppress (belt) | `local_user_enabled = false` + Azure AD auth; retained if graph still flags. |
| `CKV2_AZURE_33` | storage private endpoint | suppress | Private Endpoint + DNS is a prod harden. Warm standby keeps `public_network_access_enabled = false` and relies on Databricks/job identity paths without the PE tax until DR drills justify it. |

## Local ↔ CI parity

```bash
# Same command CI runs (from repo root):
checkov -d infra/terraform/azure \
  --config-file infra/terraform/azure/.checkov.yml \
  --framework terraform \
  --compact --quiet
```

`make checkov-azure` and `make phase7-check` use this invocation. No azure
`terraform plan` in CI — azurerm plan requires a real subscription/SP (ADR-001).
