# GPT Product Cinema V2 — Integration Guide

## Goal

This branch contains one focused Hero direction rather than a collection of unrelated effects:

**Product Cinema** — a premium, restrained eight-second product story built around one spatial smartphone, one deterministic particle transition and one calm final CTA state.

## Preview

Open:

`pro/website/gpt_hero_product_cinema_v2.html`

Assets:

- `pro/website/assets/gpt_product_cinema_v2/gpt_product_cinema_v2.css`
- `pro/website/assets/gpt_product_cinema_v2/gpt_product_cinema_v2.js`

## What it implements

- responsive two-column desktop composition;
- mobile-first stacked composition;
- CSS 3D phone treatment with pointer tilt;
- five real interactive DOM states;
- automatic eight-second product sequence;
- deterministic Canvas particle morph into the DownloadThat arrow shape;
- replay control;
- keyboard-operable primary controls;
- `prefers-reduced-motion` fallback;
- pause/resume behaviour when the document is hidden;
- no framework and no build requirement;
- fully namespaced `.pc-*` CSS and `data-pc-*` JavaScript hooks.

## Product sequence

1. Source media is shown.
2. The user shares the link.
3. DownloadThat is selected.
4. Video, audio or images are selected.
5. Local processing is visualised.
6. The final state says that the file is saved directly on the device.

## Safety boundaries

This branch does **not** modify:

- `pro/website/index.html`;
- Stripe payment links;
- withdrawal logic;
- licensing logic;
- affiliate attribution;
- partner registration;
- Android permissions;
- application download behaviour.

The laboratory page only links to the existing `/download` route.

## Validation already performed

The implementation was rendered and interacted with in headless Chromium at:

- 1440 × 1000;
- 390 × 844.

Verified:

- final automatic state is `success`;
- desktop scroll width equals viewport width;
- mobile scroll width equals viewport width;
- German headline remains fully visible at 390 px;
- controls remain inside the viewport;
- mobile and desktop screenshots render without missing assets.

## Recommended master integration

Do not replace the existing Hero in one large unreviewed edit.

### Step 1 — merge the isolated preview

Merge this branch while keeping the production homepage unchanged. This makes the implementation and assets available for review without changing traffic.

### Step 2 — extract the component markup

Move the contents of `.pc-copy` and `.pc-cinema` into the existing `<section class="hero">` in `pro/website/index.html`.

Keep the current production navigation, pricing, checkout and footer unchanged.

### Step 3 — connect i18n

Replace fixed German strings with existing `data-i18n` keys or add dedicated keys under:

`website.hero_cinema.*`

Required keys:

- eyebrow;
- title line 1;
- title line 2;
- title line 3;
- lead;
- trust local;
- trust cloud;
- trust free;
- primary CTA;
- secondary CTA;
- legal notice;
- five timeline captions;
- format-choice labels;
- success labels.

English must be complete before other locale fallbacks are used. Arabic requires RTL visual testing. Japanese and Chinese require line-break testing.

### Step 4 — use real product assets

The current source card and share sheet are explicitly stylised demonstrations. Before production rollout, replace relevant screen regions with real, current product captures where available.

Do not present a fabricated Android system screen as a real screenshot.

### Step 5 — add a feature switch

Recommended temporary selection:

```html
<body data-hero-variant="classic">
```

Supported values during rollout:

- `classic`;
- `product-cinema`.

The classic Hero should remain available for immediate rollback until performance and conversion are verified.

### Step 6 — validate production routes

Test:

- `/`;
- `/download`;
- `#pricing`;
- language switching;
- checkout modal;
- affiliate query parameters;
- mobile navigation.

## Production acceptance criteria

- no horizontal overflow at widths from 320 px upward;
- headline and CTA are available before animation completion;
- animation failure does not hide product copy;
- reduced-motion mode shows the success state without continuous animation;
- no checkout or attribution regression;
- no unsupported product claims;
- LCP remains within the project target;
- keyboard focus remains visible;
- all essential information exists as DOM text.

## Rollback

Because the implementation is isolated and namespaced, rollback consists of restoring the original Hero markup and removing the Product Cinema CSS/JS references. No payment, licensing or backend migration is involved.
