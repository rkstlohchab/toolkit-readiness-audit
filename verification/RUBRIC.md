# Grading rubric (blind audit + human spot-check)

The sample (`verification/sample.json`) is 3 apps per category = 30 apps, drawn with a fixed seed **before** any
verification loop ran (Pass-1 sha256 is stored alongside it). Each sampled app is graded on 6 fields, for every pass.
Truth labels come from primary vendor docs read during the audit. Each label stores its quote + URL in `audit.json`.

| Field | Correct when… |
|---|---|
| **auth** | The listed methods include every method a third-party toolkit would use (OAuth2 if offered to third parties, otherwise the key/token path) **and** no listed method is false. Missing a minor legacy/alternate method is still correct. |
| **access** | The single `access` label matches truth. Tie-break rules: KYC alone is not "approval"; one-off free credits = `trial`; a free tier with real API access = `free` even if quotas are low; sales-provisioned trials = `gated`; free sandbox + production review = `approval` only when the review blocks *any* real customer use (Plaid, Google Ads, Meta), else `free`. |
| **api** | The listed API styles include the primary documented style and none are false. |
| **mcp** | Binary: does a vendor-published MCP server that exposes the product's data/actions exist (GA, beta or partner alpha)? Docs-only MCPs and third-party servers do not count. |
| **verdict** | Matches truth under the definitions in `agent/schema.py`, given the true access/auth/API facts. |
| **evidence** | Every cited URL for auth/access/api (and mcp, if official) is live and actually supports the claim it is cited for. |

Accuracy = correct field-judgments / (30 apps × 6 fields). Reported per field and overall, for Pass 1, Pass 2 and Final.
Because the sample was frozen before the loops ran, Pass 1 → Pass 2 on the sample measures what the automated loops
fixed on their own; corrections the audit itself triggers are only counted in Final and are reported separately.
