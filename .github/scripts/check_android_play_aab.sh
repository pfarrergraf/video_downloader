#!/usr/bin/env bash
set -euo pipefail

aab="${1:?play AAB required}"
test -f "$aab"
test -n "${EXPECTED_UPLOAD_SHA256:-}"

normalize() { tr '[:lower:]' '[:upper:]' | tr -d ':'; }
aab_cert="$(keytool -printcert -jarfile "$aab" | awk -F': ' '/SHA256:/{print $2; exit}' | normalize)"
expected_upload="$(printf '%s' "$EXPECTED_UPLOAD_SHA256" | normalize)"
test "$aab_cert" = "$expected_upload" || { echo "Play AAB upload certificate mismatch"; exit 1; }

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
