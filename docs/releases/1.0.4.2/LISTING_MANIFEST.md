# DownloadThat 1.0.4.2 listing manifest

## Approved claim model

- Canonical source: `security/PUBLIC_CLAIMS_CATALOG.json`.
- No advertising, subject to the final dependency/SDK scan at candidate freeze.
- 3 successful downloads free per rolling 24 hours.
- Pro removes DownloadThat's daily app download limit.
- One-time purchase at the local Google Play price. No subscription.
- Up to 4K when the source offers it.
- Use supported links and only save media the user has the right to save.

Reject universal source claims, `Skip the ad`, unqualified `No limits` or
`Unlimited`, `100% free`, fixed prices and entirely offline/local claims.

## Locale and asset policy

- App UI: 50 locales, derived from the actual JSON files under
  `video_downloader/web/static/i18n`.
- Play listings: 86 locales observed in the live asset-sync run `32484439312`.
  `store_assets/play_locale_matrix.json` is the canonical mapping.
- Regional variants reuse their supported base UI language.
- The 20 Play languages without matching UI are `af`, `sq`, `hy-AM`, `az-AZ`,
  `eu-ES`, `be`, `my-MM`, `ca`, `gl-ES`, `ka-GE`, `is-IS`, `kk`, `km-KH`,
  `ky-KG`, `lo-LA`, `mk-MK`, `mn-MN`, `ne-NP`, `rm` and `si-LK`. They inherit
  default English imagery; never upload falsely localized UI captures.
- Phone, seven-inch and ten-inch screenshots are captured from the frozen UI
  commit. Marketing compositions and PSDs are not store screenshots.
- Every asset entry records type, locale, dimensions, source commit and SHA-256.

## Capture gate

Current status: `BLOCKED` until UI/string freeze and real captures from a debug
build of the exact frozen commit. Acceptance requires at least four real PNG
captures each for phone, 7-inch and 10-inch form factors, 16:9 or 9:16 and at
least 1080 px on the long edge. Device frames, generated UI, marketing
backgrounds, PII and notifications are prohibited. PSD and 1920x1080 campaign
compositions remain campaign material and must not enter screenshot directories.
