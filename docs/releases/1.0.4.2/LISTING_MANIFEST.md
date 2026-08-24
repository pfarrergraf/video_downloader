# DownloadThat 1.0.4.2 listing manifest

## Approved claim model

- No advertising, subject to a final dependency/SDK scan.
- Three successful downloads per rolling 24 hours are free.
- Pro removes the app's daily download limit.
- One-time purchase at the local Google Play price; no subscription.
- Up to 4K when the source offers it.
- Supported links only, and only media the user has the right to save.

Reject universal source claims, `Skip the ad`, unqualified `No limits` or
`Unlimited`, `100% free`, fixed prices and entirely offline/local claims.

## Locale and asset policy

- App UI: 50 locales.
- Play listings: 86 locales mapped through a canonical locale matrix.
- Regional variants reuse their supported base UI language.
- The 20 Play languages without matching UI inherit default English imagery;
  never upload falsely localized UI captures.
- Phone, seven-inch and ten-inch screenshots are captured from the frozen UI
  commit. Marketing compositions and PSDs are not store screenshots.
- Every asset entry records type, locale, dimensions, source commit and SHA-256.

Current status: `BLOCKED` until UI/string freeze and real captures.
