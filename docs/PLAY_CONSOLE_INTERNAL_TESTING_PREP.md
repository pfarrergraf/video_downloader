# Play Console Internal Testing

Package: `de.classydl.app`

Product ID: `pro`; visible name: `DownloadThat Pro` — non-consumable, one-time, target price 12 EUR

Distribution start: EU/EEA

## Prepared listing copy

Short description (EN):

> Download video, audio and images from links you may lawfully save.

Kurzbeschreibung (DE):

> Video, Audio und Bilder aus Links laden, die du rechtmäßig speichern darfst.

The full description must use verified product facts and follow `security/PUBLIC_CLAIMS_POLICY.md`:
three free downloads per 24 hours; Pro is a 12 EUR one-time purchase; no subscription,
ads or tracking SDK. It must also state that DownloadThat does not bypass DRM or
paywalls and that users need the relevant rights or permission.

## Data Safety draft — confirm in Console

| Play data category | Collected | Shared | Purpose / retention |
|---|---:|---:|---|
| Purchase history | Yes, Pro only | Google processes purchase | Purchase verification, refund/revoke, accounting |
| Device or other identifiers | Yes | No | Hashed device slot for license abuse control |
| Purchase token / order reference | Yes | Google/processor context | Token encrypted in D1; hash used for idempotency |
| Download URLs, files, history | No server collection | No | Remain on device |
| Location, contacts, photos, advertising ID | No | No | Not used |

Transport is HTTPS. The free tier needs no account. License/deletion support uses the
contact in `SECURITY.md`; legally required financial originals may remain retained.

## Permissions declaration

- `INTERNET`: media retrieval, purchase and license verification.
- `FOREGROUND_SERVICE` / `FOREGROUND_SERVICE_DATA_SYNC`: ongoing user-initiated downloads.
- `POST_NOTIFICATIONS`: progress/completion; requested contextually.
- No broad storage, location, contacts, camera, SMS or package-enumeration permission.

## Test track sequence

1. Add License Testers and Internal Track testers.
2. Upload the `playRelease` AAB; direct APK is never uploaded to Play.
3. Test successful purchase, pending/aborted paths, restore after reinstall and same key.
4. Activate that key in Direct APK and Windows.
5. Refund/void and verify RTDN-driven revocation; repeat via daily reconciliation.
6. Run Closed Test and Pre-launch Report.
7. Complete Data Safety, content rating, target audience, app access and ads forms.
8. Production only after every gate in `GOOGLE_PLAY_OWNER_CHECKLIST.md` is checked.

## Signing continuity

Enroll the existing release key as Play App Signing key and register a separate upload
key for CI. Play and Direct must therefore retain the same package/signing identity and
can replace one another without uninstalling. Do not enable Play automatic protection
while direct distribution remains supported.
