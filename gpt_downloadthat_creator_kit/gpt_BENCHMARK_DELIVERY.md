# GPT DownloadThat Influencer Creator Kit

This branch is reserved for the GPT benchmark implementation. All benchmark-specific files and folders use a `gpt_` prefix.

## Verified product facts used

- DownloadThat is an Android-focused local media workflow for video, audio and images.
- Partner commission is EUR 2.00 to EUR 4.00 per confirmed sale according to the current tier.
- Sales are confirmed after a 30-day review and a renewed Stripe check.
- Payouts are monthly from EUR 50.00.
- No commission is granted for self-purchases, refunds, failed payments or disputes.
- Version 1 has no customer discount.

## Implemented benchmark deliverables

The generated artifact package contains:

- 44 rendered PNG creatives
- 10 vertical Story templates
- 10 Feed templates
- 6 YouTube thumbnails
- 3 Carousel slides
- 8 pitch-deck slides
- creator-code, affiliate-link and QR assets
- an A4 recruitment flyer in PNG and PDF
- 2 editable SVG masters
- 7 rendered H.264/AAC vertical MP4 templates
- a JSON-driven local creator-kit generator using `uv`
- German and English outreach, copy and video-script libraries
- an HTML preview, asset manifest and machine-readable QA report

## Reproduction command

```bash
uv run --project gpt_downloadthat_creator_kit/gpt_creator_tools \
  python gpt_downloadthat_creator_kit/gpt_creator_tools/gpt_generate_creator_kit.py \
  --repo-root . \
  --config gpt_downloadthat_creator_kit/gpt_creator_tools/gpt_config/gpt_example_creator.json
```

When run in this repository, the generator uses `store_assets/screenshot_main.png`. Its isolated fallback is explicitly presented as a product-flow visualisation rather than as a real screenshot.

## Compliance guardrails

- no invented discounts, testimonials, user counts or income guarantees
- no claim that every website is supported
- no DRM-bypass positioning
- visible affiliate disclosure
- users are instructed to save only content for which they have the required rights or permission
- no secrets or live payment credentials in generated assets

## Honest limitations

The rendered MP4 files contain a silent AAC compatibility track. Campaign-specific licensed music, creator voice or TTS must be added separately. The provided rendered visual set is primarily German; German and English copy libraries are included for additional export runs.
