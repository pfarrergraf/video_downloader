# Affiliate Privacy and Data Minimization

This is a technical design record, not legal advice or a completed GDPR review.
Legal basis, controller/processor roles, international transfers, retention duties,
data-subject workflows and affiliate contracts require qualified legal review before
any public affiliate pilot.

## Data flow

```text
partner link -> Pages redirect -> pseudonymous click -> Google Play referrer
-> Play app first start -> attribution API -> verified Play purchase
-> pending commission -> aggregate partner dashboard
```

The partner dashboard receives only own aggregate counters and monetary states. It
must never receive buyer name/email, Google account, purchase token, raw/full order
ID, IP, user-agent, app install ID, device information or a row-level purchase feed.

## Data inventory and retention proposal

| Data | Store | Purpose | Retention |
|---|---|---|---|
| affiliate ID/code/status | D1 | programme operation | contract term plus legal review period |
| campaign slug | D1 | link performance | contract term; delete/aggregate after end |
| click ID and times | D1 | attribution and fraud review | 90 days unless linked to a commission |
| hashed, peppered install ID | D1 | immutable one-install attribution | 90 days after attribution window; longer only if linked to financial record |
| referrer timestamps/version | D1 | plausibility/audit | 90 days unless financial linkage |
| token hash/order ID access-controlled | existing D1 | dedupe and purchase/void reconciliation | financial/legal retention policy; never dashboard |
| commission/audit/payout reference | D1/archive | accounting and dispute evidence | owner/legal-accounting retention policy |

Do not collect advertising IDs, Google account identity, raw IP address, raw user
agent, precise location, contact list or downloaded-content information. If a narrow
rate limit is later necessary, retain only a rotating salted hash and short window.

## Access and deletion

- Pages Function secrets are server-only. Android and the affiliate dashboard never
  receive Play API credentials or signing/pepper material.
- Admin views use role checks and query only the fields necessary for each action.
- Deletion must erase non-financial click/attribution data on schedule, then replace
  retained financial personal links with an irreversible reference where legally
  permitted. It must not destroy records required for bookkeeping or dispute defence.
- Export/erasure requests must be a documented human process before launch; do not
  create a self-service delete button that destroys active financial evidence.

## Logging

Log structured event names and opaque IDs only, for example
`affiliate.click.created`, `affiliate.install.attributed`,
`affiliate.purchase.attributed`, `affiliate.commission.voided`, and
`affiliate.fraud.flagged`. Redact purchase tokens, raw referrer strings, raw order
IDs, secrets and buyer identifiers before any console/error output.
