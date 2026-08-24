# ADR-001: Google-managed refunds

Status: Accepted for 1.0.4.2

## Decision

DownloadThat has no in-app refund request, refund API, automatic refund, admin
refund queue or refund-based purchase cooldown. Google Play owns payment and
eligible-refund decisions. Pro is revoked only after an authenticated Google
refund, void or revocation is observed through RTDN or reconciliation.

## Consequences

- Transient Google, OAuth or network errors never revoke Pro.
- Historical finance and migration records remain audit records, not runtime
  authorization paths.
- Repository automation never initiates a real purchase or refund.
- Device testing uses an owner-controlled Play test order and records only a
  neutral test ID and redacted evidence reference.

The normative product wording, revoke flow and external verification gate are
defined in [Google Play refund policy](../../../GOOGLE_PLAY_REFUND_POLICY.md).
Play ownership restoration remains governed separately by the
[Google Play restore contract](../../../GOOGLE_PLAY_RESTORE_CONTRACT.md).

