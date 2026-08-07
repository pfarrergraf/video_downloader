#!/usr/bin/env bash
set -euo pipefail

project_id=""
dry_run=1
while (($#)); do
  case "$1" in
    --project-id) project_id="${2:?missing project id}"; shift 2 ;;
    --apply) dry_run=0; shift ;;
    --dry-run) dry_run=1; shift ;;
    *) printf 'Unknown argument: %s\n' "$1" >&2; exit 2 ;;
  esac
done
if [[ -z "$project_id" ]]; then printf '%s\n' 'Usage: setup_google_affiliate.sh --project-id PROJECT [--dry-run|--apply]' >&2; exit 2; fi

printf 'Project: %s\n' "$project_id"
printf '%s\n' 'Planned Google setup: enable androidpublisher.googleapis.com and pubsub.googleapis.com, then review WIF/Pub/Sub permissions.'
printf '%s\n' 'This script never creates service-account keys and never enables affiliate runtime flags.'
if ((dry_run)); then printf '%s\n' 'DRY RUN: no external changes made.'; exit 0; fi
command -v gcloud >/dev/null || { printf '%s\n' 'gcloud is required for --apply.' >&2; exit 1; }
gcloud services enable androidpublisher.googleapis.com pubsub.googleapis.com --project "$project_id"
printf '%s\n' 'APPLIED: APIs enabled. Create/approve the least-privilege service account and WIF binding manually after owner review.'
