#!/usr/bin/env bash
set -euo pipefail

: "${CLOUDFLARE_API_TOKEN:?CLOUDFLARE_API_TOKEN is required}"
: "${CLOUDFLARE_ACCOUNT_ID:?CLOUDFLARE_ACCOUNT_ID is required}"
: "${TESTER_GRANTS_ADMIN_EMAIL:?TESTER_GRANTS_ADMIN_EMAIL is required}"

API_ROOT="https://api.cloudflare.com/client/v4/accounts/${CLOUDFLARE_ACCOUNT_ID}/access"
APP_NAME="DownloadThat Mobile Tester Admin"
POLICY_NAME="Allow DownloadThat admin"
ADMIN_EMAIL="$(printf '%s' "$TESTER_GRANTS_ADMIN_EMAIL" | tr '[:upper:]' '[:lower:]')"

cf_request() {
  local method="$1"
  local path="$2"
  local data="${3:-}"
  local args=(
    --fail-with-body
    --silent
    --show-error
    --request "$method"
    --header "Authorization: Bearer $CLOUDFLARE_API_TOKEN"
    --header "Content-Type: application/json"
  )
  if [ -n "$data" ]; then
    args+=(--data "$data")
  fi
  curl "${args[@]}" "${API_ROOT}${path}"
}

require_success() {
  local json="$1"
  local what="$2"
  if ! jq -e '.success == true' >/dev/null <<<"$json"; then
    echo "Cloudflare API failed while ${what}:" >&2
    jq -c '{errors, messages}' <<<"$json" >&2 || true
    exit 1
  fi
}

echo "Checking Zero Trust organization..."
org_json="$(cf_request GET '/organizations')"
require_success "$org_json" "reading the Zero Trust organization"
auth_domain="$(jq -r '.result.auth_domain // empty' <<<"$org_json")"

if [ -z "$auth_domain" ]; then
  suffix="$(printf '%s' "$CLOUDFLARE_ACCOUNT_ID" | cut -c1-8)"
  auth_domain="downloadthat-${suffix}.cloudflareaccess.com"
  org_payload="$(jq -nc \
    --arg auth_domain "$auth_domain" \
    --arg name 'DownloadThat' \
    '{auth_domain:$auth_domain,name:$name,session_duration:"24h"}')"
  echo "Creating Zero Trust organization..."
  org_json="$(cf_request POST '/organizations' "$org_payload")"
  require_success "$org_json" "creating the Zero Trust organization"
  auth_domain="$(jq -r '.result.auth_domain' <<<"$org_json")"
fi

# Existing organizations may predate Cloudflare's built-in IdP default. Ensure
# that at least one browser login method exists. Exact-email policy below still
# determines authorization; this step only ensures there is a way to authenticate.
echo "Checking Access identity providers..."
idp_json="$(cf_request GET '/identity_providers')"
require_success "$idp_json" "listing Access identity providers"
login_idp_count="$(jq '[.result[] | select(.type == "cloudflare" or .type == "onetimepin")] | length' <<<"$idp_json")"
if [ "$login_idp_count" -eq 0 ]; then
  echo "Adding one-time PIN identity provider..."
  idp_payload='{"name":"One-time PIN login","type":"onetimepin","config":{}}'
  idp_create="$(cf_request POST '/identity_providers' "$idp_payload")"
  require_success "$idp_create" "creating the one-time PIN identity provider"
fi

echo "Checking Access application..."
apps_json="$(cf_request GET '/apps?per_page=100')"
require_success "$apps_json" "listing Access applications"
app_id="$(jq -r --arg name "$APP_NAME" '.result[] | select(.name == $name) | .id' <<<"$apps_json" | head -n 1)"

app_payload="$(jq -nc \
  --arg name "$APP_NAME" \
  '{
    name:$name,
    type:"self_hosted",
    session_duration:"30m",
    app_launcher_visible:false,
    destinations:[
      {type:"public",uri:"downloadthat.app/admin/mobile/*"},
      {type:"public",uri:"downloadthat.app/api/admin/mobile-tester-grant"}
    ]
  }')"

if [ -z "$app_id" ]; then
  echo "Creating Access application..."
  app_json="$(cf_request POST '/apps' "$app_payload")"
  require_success "$app_json" "creating the Access application"
else
  echo "Updating Access application..."
  app_json="$(cf_request PUT "/apps/${app_id}" "$app_payload")"
  require_success "$app_json" "updating the Access application"
fi

app_id="$(jq -r '.result.id' <<<"$app_json")"
aud="$(jq -r '.result.aud // empty' <<<"$app_json")"
if [ -z "$app_id" ] || [ -z "$aud" ]; then
  echo "Cloudflare Access application returned no id/aud" >&2
  exit 1
fi

echo "Checking exact-email Access policy..."
policies_json="$(cf_request GET "/apps/${app_id}/policies")"
require_success "$policies_json" "listing Access application policies"
policy_id="$(jq -r --arg name "$POLICY_NAME" '.result[] | select(.name == $name) | .id' <<<"$policies_json" | head -n 1)"

policy_payload="$(jq -nc \
  --arg name "$POLICY_NAME" \
  --arg email "$ADMIN_EMAIL" \
  '{
    name:$name,
    decision:"allow",
    precedence:1,
    session_duration:"30m",
    include:[{email:{email:$email}}]
  }')"

if [ -z "$policy_id" ]; then
  echo "Creating exact-email Access policy..."
  policy_json="$(cf_request POST "/apps/${app_id}/policies" "$policy_payload")"
  require_success "$policy_json" "creating the Access policy"
else
  echo "Updating exact-email Access policy..."
  policy_json="$(cf_request PUT "/apps/${app_id}/policies/${policy_id}" "$policy_payload")"
  require_success "$policy_json" "updating the Access policy"
fi

team_domain="https://${auth_domain#https://}"
team_domain="${team_domain%/}"

echo "Cloudflare Access ready for ${ADMIN_EMAIL}."
echo "Team domain: ${team_domain}"
echo "Application audience: ${aud}"

if [ -n "${GITHUB_OUTPUT:-}" ]; then
  {
    echo "team_domain=${team_domain}"
    echo "aud=${aud}"
    echo "admin_email=${ADMIN_EMAIL}"
  } >> "$GITHUB_OUTPUT"
fi
