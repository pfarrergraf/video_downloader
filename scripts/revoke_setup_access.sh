#!/usr/bin/env bash
set -euo pipefail
project_id=""
confirmation=""
service_account=""
member=""
role="roles/iam.workloadIdentityUser"
while (($#)); do
  case "$1" in
    --project-id) project_id="${2:?missing project id}"; shift 2 ;;
    --confirm) confirmation="${2:?missing confirmation}"; shift 2 ;;
    --service-account) service_account="${2:?missing service account email}"; shift 2 ;;
    --member) member="${2:?missing WIF member}"; shift 2 ;;
    --role) role="${2:?missing IAM role}"; shift 2 ;;
    *) printf 'Unknown argument: %s\n' "$1" >&2; exit 2 ;;
  esac
done
if [[ -z "$project_id" ]]; then printf '%s\n' 'Usage: revoke_setup_access.sh --project-id PROJECT [--confirm PROJECT]' >&2; exit 2; fi
printf 'Would review IAM bindings in project %s and remove only owner-approved temporary bindings.\n' "$project_id"
if [[ "$confirmation" != "$project_id" ]]; then printf '%s\n' 'DRY RUN: no access removed. Re-run with --confirm PROJECT after reviewing audit output.'; exit 0; fi
if [[ -z "$service_account" || -z "$member" ]]; then
  printf '%s\n' '--confirm requires --service-account and --member; no broad revocation is supported.' >&2
  exit 2
fi
if [[ "$role" != "roles/iam/workloadIdentityUser" && "$role" != "roles/iam.serviceAccountTokenCreator" ]]; then
  printf '%s\n' 'Only setup-only WIF roles may be removed by this script.' >&2
  exit 2
fi
if [[ "$member" != principalSet://iam.googleapis.com/* && "$member" != principal://iam.googleapis.com/* ]]; then
  printf '%s\n' 'Refusing a non-WIF member; provide the exact principalSet/principal from the audit.' >&2
  exit 2
fi
command -v gcloud >/dev/null || { printf '%s\n' 'gcloud is required for --confirm.' >&2; exit 1; }
printf 'Removing only %s from service account %s for member %s.\n' "$role" "$service_account" "$member"
gcloud iam service-accounts remove-iam-policy-binding "$service_account" --project "$project_id" --member "$member" --role "$role" --quiet
printf '%s\n' 'APPLIED: setup-only WIF binding removed; runtime service accounts/topics were not touched.'
