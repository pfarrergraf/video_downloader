#!/usr/bin/env bash
set -euo pipefail
project_id=""
confirmation=""
while (($#)); do
  case "$1" in
    --project-id) project_id="${2:?missing project id}"; shift 2 ;;
    --confirm) confirmation="${2:?missing confirmation}"; shift 2 ;;
    *) printf 'Unknown argument: %s\n' "$1" >&2; exit 2 ;;
  esac
done
if [[ -z "$project_id" ]]; then printf '%s\n' 'Usage: revoke_setup_access.sh --project-id PROJECT [--confirm PROJECT]' >&2; exit 2; fi
printf 'Would review IAM bindings in project %s and remove only owner-approved temporary bindings.\n' "$project_id"
if [[ "$confirmation" != "$project_id" ]]; then printf '%s\n' 'DRY RUN: no access removed. Re-run with --confirm PROJECT after reviewing audit output.'; exit 0; fi
printf '%s\n' 'Refusing automatic broad revocation. Use the exact binding/member from audit output and remove it with a separately reviewed gcloud command.' >&2
exit 3
