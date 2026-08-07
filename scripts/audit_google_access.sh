#!/usr/bin/env bash
set -euo pipefail
project_id=""
while (($#)); do
  case "$1" in
    --project-id) project_id="${2:?missing project id}"; shift 2 ;;
    *) printf 'Unknown argument: %s\n' "$1" >&2; exit 2 ;;
  esac
done
if [[ -z "$project_id" ]]; then printf '%s\n' 'Usage: audit_google_access.sh --project-id PROJECT' >&2; exit 2; fi
command -v gcloud >/dev/null || { printf '%s\n' 'gcloud is required.' >&2; exit 1; }
gcloud projects get-iam-policy "$project_id" --flatten='bindings[].members' --format='table(bindings.role,bindings.members)' --filter='bindings.role:(roles/pubsub.publisher OR roles/pubsub.subscriber OR roles/iam.workloadIdentityUser OR roles/androidpublisher)'
printf '%s\n' 'Audit is read-only; compare the result with the least-privilege matrix in docs/GOOGLE_AFFILIATE_API_SETUP.md.'
