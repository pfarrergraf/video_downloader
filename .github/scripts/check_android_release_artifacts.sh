#!/usr/bin/env bash
set -euo pipefail

apk="${1:?direct APK required}"
aab="${2:?play AAB required}"
test -f "$apk" && test -f "$aab"
test -n "${EXPECTED_APP_SIGNING_SHA256:-}" && test -n "${EXPECTED_UPLOAD_SHA256:-}"

normalize() { tr '[:lower:]' '[:upper:]' | tr -d ':'; }
apk_cert="$(apksigner verify --print-certs "$apk" | awk -F': ' '/Signer #1 certificate SHA-256 digest/{print $2; exit}' | normalize)"
expected_app="$(printf '%s' "$EXPECTED_APP_SIGNING_SHA256" | normalize)"
test "$apk_cert" = "$expected_app" || { echo "Direct APK signing certificate mismatch"; exit 1; }

aab_cert="$(keytool -printcert -jarfile "$aab" | awk -F': ' '/SHA256:/{print $2; exit}' | normalize)"
expected_upload="$(printf '%s' "$EXPECTED_UPLOAD_SHA256" | normalize)"
test "$aab_cert" = "$expected_upload" || { echo "Play AAB upload certificate mismatch"; exit 1; }

zipalign -c -P 16 4 "$apk"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
unzip -qq "$aab" 'base/lib/*' -d "$work"
while IFS= read -r -d '' lib; do
  while read -r alignment; do
    (( alignment >= 0x4000 )) || { echo "$lib has LOAD alignment $alignment"; exit 1; }
  done < <(readelf -lW "$lib" | awk '/ LOAD / {print $NF}')
done < <(find "$work" -type f -name '*.so' -print0)

if unzip -p "$aab" | strings | grep -Eqi 'buy\.stripe\.com|api\.stripe\.com|/api/create-checkout'; then
  echo "Play artifact contains a legacy Stripe endpoint"
  exit 1
fi
if unzip -p "$apk" 'classes*.dex' | strings | grep -Eqi 'com/android/billingclient|BillingClient'; then
  echo "Direct APK contains Play Billing classes"
  exit 1
fi
