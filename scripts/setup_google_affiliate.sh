#!/usr/bin/env bash
set -euo pipefail

project_id=""
topic_name=""
subscription_name=""
push_endpoint=""
oidc_service_account=""
dry_run=1
while (($#)); do
  case "$1" in
    --project-id) project_id="${2:?missing project id}"; shift 2 ;;
    --topic) topic_name="${2:?missing topic name}"; shift 2 ;;
    --subscription) subscription_name="${2:?missing subscription name}"; shift 2 ;;
    --push-endpoint) push_endpoint="${2:?missing push endpoint}"; shift 2 ;;
    --oidc-service-account) oidc_service_account="${2:?missing OIDC service account}"; shift 2 ;;
    --apply) dry_run=0; shift ;;
    --dry-run) dry_run=1; shift ;;
    *) printf 'Unknown argument: %s\n' "$1" >&2; exit 2 ;;
  esac
done
if [[ -z "$project_id" ]]; then printf '%s\n' 'Usage: setup_google_affiliate.sh --project-id PROJECT [--topic TOPIC --subscription SUBSCRIPTION --push-endpoint URL --oidc-service-account EMAIL] [--dry-run|--apply]' >&2; exit 2; fi
if [[ -n "$subscription_name" && ( -z "$topic_name" || -z "$push_endpoint" || -z "$oidc_service_account" ) ]]; then
  printf '%s\n' '--subscription requires --topic, --push-endpoint and --oidc-service-account.' >&2
  exit 2
fi

printf 'Project: %s\n' "$project_id"
if ((dry_run)); then printf '%s\n' 'Active account: not queried in dry-run (no credentials inspected).'; fi
printf '%s\n' 'Planned Google setup: enable androidpublisher.googleapis.com and pubsub.googleapis.com.'
if [[ -n "$topic_name" ]]; then printf 'Pub/Sub topic to verify/create: %s\n' "$topic_name"; fi
if [[ -n "$subscription_name" ]]; then printf 'Pub/Sub push subscription to verify/create: %s\n' "$subscription_name"; fi
printf '%s\n' 'This script never creates service-account keys and never enables affiliate runtime flags.'
if ((dry_run)); then printf '%s\n' 'DRY RUN: no external changes made.'; exit 0; fi
command -v gcloud >/dev/null || { printf '%s\n' 'gcloud is required for --apply.' >&2; exit 1; }
gcloud auth list --filter=status:ACTIVE --format='value(account)' --quiet
gcloud projects describe "$project_id" --format='value(projectId)' --quiet
gcloud services enable androidpublisher.googleapis.com pubsub.googleapis.com --project "$project_id"
if [[ -n "$topic_name" ]]; then
  if ! gcloud pubsub topics describe "$topic_name" --project "$project_id" --format='value(name)' --quiet >/dev/null 2>&1; then
    gcloud pubsub topics create "$topic_name" --project "$project_id"
  fi
fi
if [[ -n "$subscription_name" ]]; then
  if ! gcloud pubsub subscriptions describe "$subscription_name" --project "$project_id" --format='value(name)' --quiet >/dev/null 2>&1; then
    gcloud pubsub subscriptions create "$subscription_name" --project "$project_id" \
      --topic="$topic_name" --push-endpoint="$push_endpoint" \
      --push-auth-service-account="$oidc_service_account" \
      --push-auth-token-audience="$push_endpoint"
  fi
fi
printf '%s\n' 'APPLIED: APIs enabled. Create/approve the least-privilege service account and WIF binding manually after owner review.'
