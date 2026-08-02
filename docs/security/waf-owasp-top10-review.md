# WAF vs OWASP Top 10 baseline (Phase 10)

Web ACL: `infra/terraform/aws/modules/alb_waf/main.tf` (`aws_wafv2_web_acl.this`),
REGIONAL, associated with the public ALB. Logging to
`aws-waf-logs-{prefix}` (365d, CMK).

## Managed rule groups (enabled)

| Priority | Rule group | Primary OWASP coverage |
|----------|------------|------------------------|
| 1 | `AWSManagedRulesCommonRuleSet` | A03 Injection (partial), A05 Security Misconfiguration, XSS (A03/A07) |
| 2 | `AWSManagedRulesKnownBadInputsRuleSet` | A03 / Log4Shell-class / bad payloads |
| 3 | `AWSManagedRulesAnonymousIpList` | A01 Broken Access / anon VPN-Tor noise |
| 4 | `AWSManagedRulesSQLiRuleSet` | **A03 Injection (SQLi)** — added Phase 10 |
| 5 | `AWSManagedRulesAmazonIpReputationList` | Bot / known-bad reputations |

## OWASP Top 10 (2021) mapping

| # | Risk | Edge (WAF/ALB) | App / platform control |
|---|------|----------------|------------------------|
| A01 | Broken Access Control | Anonymous IP + reputation lists | Django RBAC + API tokens (control-plane) |
| A02 | Cryptographic Failures | HTTPS listener TLS1.3 policy; HTTP→HTTPS redirect | Secrets CMK; S3 SSE |
| A03 | Injection | Common + **SQLi** + KnownBadInputs | Activation SQL guard; Django ORM/Ninja; parameterized tools |
| A04 | Insecure Design | Path-based routing only to known TGs | Contract-first APIs; ADR non-fabrication |
| A05 | Security Misconfiguration | drop_invalid_header_fields; WAF default | Compose/dev tokens not for prod |
| A06 | Vulnerable Components | (not a WAF concern) | CI deps; pinned images |
| A07 | Identification / Auth Failures | Reputation / anon IP | Bearer tokens; bootstrap password rotation (SM) |
| A08 | Software / Data Integrity | — | Gold write paths IAM-scoped; audit log |
| A09 | Security Logging Failures | WAF sampled + CW logs; ALB access logs | control-plane audit app |
| A10 | SSRF | CommonRuleSet SSRF parts | Copilot/tool allowlists to internal URLs only |

## Residual gaps (accepted)

- No Bot Control paid managed group (cost; ADR-001).
- No geo-match block (product is multi-region friendly).
- XSS body inspection can false-positive JSON APIs — monitor WAF metrics before
  tightening overrides; CommonRuleSet size limits may need `SizeRestrictions_BODY`
  count overrides at apply-time for large activate payloads.

## Verdict

Baseline **meets OWASP Top 10 edge coverage** for an ALB+API fleet when combined
with app authz and SQL guards. Phase 10 added SQLi + Amazon IP reputation to
close the Phase 6 Common/KnownBad/Anonymous-only gap.
