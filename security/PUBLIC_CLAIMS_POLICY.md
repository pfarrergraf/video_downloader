# Public Claims Policy

Status: **current and mandatory** · Effective: 2026-07-14

This policy converts the security, privacy and DRM analyses into release gates for
all public app, website, store and marketing copy. It overrides older creator,
affiliate, sideload and marketing documents.

## Canonical external description

English:

> DownloadThat is an Android media utility for saving video, audio and images
> from links you provide, where you have the right or permission to do so. Media
> processing happens on your device. License verification and updates use limited
> network services.

Deutsch:

> DownloadThat ist eine Android-Medien-App zum Speichern von Video, Audio und
> Bildern aus Links, die du selbst bereitstellst und rechtmäßig speichern darfst.
> Die Medienverarbeitung erfolgt auf deinem Gerät. Lizenzprüfung und Updates
> nutzen begrenzte Netzwerkdienste.

## Mandatory rules

- Never claim or imply support for all, almost all, most, arbitrary or every
  website, service, video or app. Compatibility changes and must be described
  factually for a tested source, never as universal coverage.
- Never use sideload-only or anti-store positioning. Google Play is primary; the
  signed direct APK is a secondary installation option.
- Never claim that the whole app is entirely offline, entirely local or uses no
  network/cloud service. Media processing is on-device, while source retrieval,
  license verification, Play Billing and updates require network services.
- It is acceptable to state that there are no advertising SDKs and no analytics
  tracking if that remains verified in code. The Free tier requires no account.
- Never promise DRM/TPM circumvention. The app must not enable
  `allow_unplayable_formats`, integrate decryption keys, Widevine/CENC tooling or
  external decryptors. Only content the user may lawfully save is in scope.
- Platform names may be used only for factual exclusion, interoperability testing
  or legal/security analysis; never to imply endorsement or download support.
- Public claims must be derived from current code and this policy. Historical
  affiliate/creator documents are evidence only and must not be copied, rendered
  or deployed.

## Examples that are explicitly prohibited

The following are quoted solely so automated and human reviewers know what to
reject: "from any site", "from almost any site", "works with most websites",
"von fast jeder Website", "MP3 from any video", "100% local", "everything runs
locally", "no Play Store needed" and equivalent translations.

## Enforcement

- `scripts/check_public_claims.py` scans every active public text source.
- `tests/test_public_claims_policy.py` makes the scanner a regression test.
- Security CI and the production website deployment run the scanner.
- The deployment fails if the retired `pro/website/assets/influencer/` directory
  exists, preventing historical affiliate assets from becoming public again.
- Any intentional policy change must update this file, the security evidence and
  tests in the same change.
