# Affiliate Marketing Plan — Play-first MVP

This plan promotes the official Google Play version. It must follow
`security/PUBLIC_CLAIMS_POLICY.md` and `docs/MARKETING_LEGAL_GUARDRAILS.md`:
lawful use only, no claims of universal source support, DRM bypass, or unsupported
privacy/security guarantees.

## Channel priority

| Channel | Reach | Conversion | Cost | Fraud risk | MVP recommendation |
|---|---|---|---|---|---|
| Android/productivity micro-creators | medium | high | low-medium | medium | Start here: clear demo and tracked Play link. |
| App/Android bloggers | medium | medium-high | low | low-medium | Review/tutorial partnerships after product proof. |
| Creator workflow/newsletters | medium | medium | low | medium | Use one campaign slug per placement. |
| Tech/news sites | high | low-medium | medium-high | low | Later, after pilot conversion data. |
| TikTok/Instagram broad creators | high | variable | medium | high | Pilot only with explicit disclosure and fraud hold. |
| Coupon/deal sites | high | low quality | medium | high | Exclude from MVP. |

Start with 3–5 vetted partners. Give each a single link and one optional campaign
slug, a lawful-use creative brief, disclosure guidance reviewed by counsel, and a
plain statement that purchases/refunds are handled through Google Play.

## Commission models

| Model | Strength | Risk | MVP fit |
|---|---|---|---|
| A. fixed amount per confirmed sale | simple forecasts and payouts | can exceed margin in low-price regions | Preferred only after floor analysis. |
| B. percentage of actual attributable net revenue | aligns payout with local price, fee/refund outcome | needs trustworthy finance input | Preferred long-term default. |
| C. hybrid | protects a small partner minimum | complexity | defer. |
| D. tiered monthly revenue/sales | rewards scale | incentives/edge cases | defer until pilot reconciliation is stable. |

Recommendation: use a documented **fixed minor-unit policy** for the first pilot
unless a trusted net-revenue field is added to server-verified Play purchase data.
The backend supports percentage policy only when `amount_minor` is present; it
otherwise creates no percentage commission rather than guessing a regional price.
If percentage data is approved later, use
`commission = floor(NET_REVENUE_MINOR * COMMISSION_RATE)` only after the 30-day
hold. Store the policy version with each commission; never recompute historical
earnings from a new rate.

Illustrative calculator (not a price or fee claim):

The reproducible CLI calculator is `uv run python scripts/affiliate_funnel.py`.
It accepts all rates as decimals from `0` to `1` and never embeds a current Play
price. Example:

```powershell
uv run python scripts/affiliate_funnel.py --clicks 1000 --play-store-conversion 0.70 --install-rate 1 --pro-conversion 0.04 --price 11.99 --google-fee 0.15 --refund-rate 0.05 --commission-rate 0.30
```

```text
gross = clicks * play_store_conversion * install_rate * pro_conversion * PRO_PRICE
net = gross * (1 - GOOGLE_FEE) * (1 - REFUND_RATE)
affiliate_cost = net * COMMISSION_RATE
contribution = net - affiliate_cost
CAC = affiliate_cost / confirmed_pro_sales
break_even_pro_conversion = fixed_campaign_cost /
  (clicks * PRO_PRICE * (1-GOOGLE_FEE) * (1-REFUND_RATE) * (1-COMMISSION_RATE))
```

Example inputs: 1,000 clicks, 70% store-to-install, 4% install-to-Pro,
`PRO_PRICE=11.99`, `GOOGLE_FEE=0.15`, `REFUND_RATE=0.05`, `COMMISSION_RATE=0.30`.
That yields 28 expected Pro sales, gross EUR335.72, estimated net EUR271.09,
affiliate cost EUR81.33 and contribution EUR189.77 when rounded only at the final
display step. Replace every input from real Play/finance data before making a
commercial decision.

## Funnel metrics and pilot rules

Track aggregated click, attributed-install, verified-purchase, void/refund and
payable-commission counts per affiliate/campaign. Do not optimize on buyer-level
profiles. Freeze a campaign for human review on obvious anomalies: burst clicks,
identical click reuse, implausible timestamps, extreme install-to-purchase ratios,
or elevated refund/void rate. These are review triggers, not automated accusations.
