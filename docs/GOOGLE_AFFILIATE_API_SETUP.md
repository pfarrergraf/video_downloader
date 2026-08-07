# Google Affiliate API Setup and Access Plan

Status: plan only. No API, project, IAM binding, Pub/Sub resource, credential, or
Play Console setting has been changed by this document.

## Required APIs and access

| API | Why | Access | Runtime? | Setup-only? | Later removable? |
|---|---|---|---:|---:|---:|
| Google Play Developer API | verify one-time purchase; voided reconciliation; existing refund flow | `androidpublisher` OAuth scope plus Play Console app permissions | yes | no | only if backend stops |
| Cloud Pub/Sub API | existing RTDN topic/subscription | topic publisher is Google Play; subscription administration is setup | yes | yes | no while RTDN exists |
| Play Install Referrer client library | Android reads Play-delivered referrer | app dependency only; no Cloud credential | yes | no | yes with feature removal |
| Play Integrity API | optional future fraud signal | none for MVP | no | no | n/a |

The official getting-started guide requires a Cloud project, enabling the Play
Developer API, and a service account granted only needed Play Console permissions.
For purchase/void/refund operations it names **View financial data, orders, and
cancellation survey responses** and **Manage orders and subscriptions**. Confirm the
current labels in the owner UI before saving because Console wording can change.
Source: [Google Play Developer API getting started](https://developers.google.com/android-publisher/getting_started).

## Benjamin — precise one-time steps

1. Open [Google Cloud Console](https://console.cloud.google.com/) using the owner
   Google account. Select the existing DownloadThat Cloud project if one already
   owns the existing finance/RTDN resources; otherwise stop and record the chosen
   project ID before creation. Do not create a duplicate project by default.
2. Open **APIs & Services → Library**, search **Google Play Android Developer API**,
   select it, and verify its project before pressing **Enable**.
3. Open Play Console, select DownloadThat, then **Users and permissions**. Invite
   the exact service-account email as an app-scoped user. Grant only the two
   permissions above; do not grant release, app-signing, account-admin, or broad
   financial-report access unless a separately documented job needs it.
4. In Play Console configure RTDN to publish to the intended Pub/Sub topic. Record
   only resource names (not credentials) in a private owner handoff.
5. Review the proposed commission policy, affiliate agreement/privacy text,
   marketing disclosures, payout tax/accounting treatment and pilot partners with
   the appropriate business/legal advisers.
6. After Codex's dry-run output is reviewed, approve each explicit create/apply
   command. Test with a License Tester/Internal Track account; capture evidence
   outside the repository without buyer/payment details.

## Codex / script responsibilities after approval

- `gcloud auth list` and `gcloud config get-value project` preflight only.
- Verify or enable the two required APIs, show the changed resource set first.
- Create/update the named Pub/Sub push subscription idempotently with an HTTPS
  endpoint and configured OIDC audience/service account.
- Generate no service-account JSON key by default. Configure GitHub Actions setup
  access through a narrowly scoped Workload Identity Federation pool/provider,
  restricted to the DownloadThat repository and protected branch/environment.
- Produce an audit report of enabled services, service accounts, relevant IAM
  bindings, Pub/Sub topic/subscription and local credential locations (names only).

## Runtime versus setup access

| Type | Identity | Minimum purpose | Removal |
|---|---|---|---|
| Setup/CI | GitHub OIDC → WIF → temporary service-account impersonation | provision/audit approved GCP resources | remove WIF provider/binding after setup unless CI uses it |
| Pub/Sub push | dedicated Google service account | sign delivery JWT for `/api/play/rtdn` | retain while subscription is active |
| Pages runtime | dedicated Play API service account | purchase/void status and current refund feature | retain only while Worker needs direct Play API calls |

WIF is preferred for GitHub and interactive setup because it avoids a long-lived
JSON key. The current Cloudflare Worker implementation signs a service-account JWT
from a Cloudflare secret. A Worker cannot simply reuse GitHub OIDC/WIF at runtime;
keep the existing minimal runtime identity or approve a separately designed keyless
broker before changing a working Play backend. See [Workload Identity Federation](https://cloud.google.com/iam/docs/workload-identity-federation).

## Planned safe scripts

`scripts/setup_google_affiliate.sh --dry-run` must require explicit `--project-id`,
never infer a production target, print account/project/API deltas, and refuse to
grant Owner, edit unrelated IAM, delete resources or create keys. With `--apply`, it
can enable explicitly listed APIs and create only declared topic/subscription names.

`scripts/audit_google_access.sh` is read-only. It lists enabled APIs, service
accounts, relevant IAM bindings, Pub/Sub resources and *names* of matching local
environment variables. It must redact values.

`scripts/revoke_setup_access.sh --dry-run` removes only an explicit WIF provider or
binding after checking it is not the configured runtime identity. It must never
delete the RTDN push service account, the Pages runtime account, production topic,
or subscription without a separate owner-confirmed command.

Pub/Sub push delivery contains a signed JWT in `Authorization`; the Pages endpoint
must validate issuer, audience, service-account email and signature, and return a
2xx only after durable processing. Sources: [Pub/Sub push subscriptions](https://cloud.google.com/pubsub/docs/push), [push authentication](https://cloud.google.com/pubsub/docs/authenticate-push-subscriptions).
