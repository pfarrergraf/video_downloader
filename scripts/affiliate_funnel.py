#!/usr/bin/env python3
"""Deterministic, price-agnostic unit-economics calculator for the Play pilot."""

from __future__ import annotations

import argparse
import json
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


ZERO = Decimal("0")


def decimal(value: object, name: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if not result.is_finite():
        raise ValueError(f"{name} must be finite")
    return result


def rate(value: object, name: str) -> Decimal:
    result = decimal(value, name)
    if result < ZERO or result > Decimal("1"):
        raise ValueError(f"{name} must be between 0 and 1")
    return result


def money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calculate(
    *,
    clicks: int,
    play_store_conversion: object,
    install_rate: object,
    pro_conversion: object,
    price: object,
    google_fee: object,
    refund_rate: object,
    commission_rate: object,
    fixed_campaign_cost: object = 0,
) -> dict[str, Decimal | int | None]:
    if isinstance(clicks, bool) or int(clicks) != clicks or clicks < 0:
        raise ValueError("clicks must be a non-negative integer")
    store = rate(play_store_conversion, "play_store_conversion")
    install = rate(install_rate, "install_rate")
    pro = rate(pro_conversion, "pro_conversion")
    fee = rate(google_fee, "google_fee")
    refunds = rate(refund_rate, "refund_rate")
    commission = rate(commission_rate, "commission_rate")
    price_value = decimal(price, "price")
    campaign_cost = decimal(fixed_campaign_cost, "fixed_campaign_cost")
    if price_value < ZERO or campaign_cost < ZERO:
        raise ValueError("price and fixed_campaign_cost must be non-negative")

    expected_sales = Decimal(clicks) * store * install * pro
    gross = expected_sales * price_value
    net = gross * (Decimal("1") - fee) * (Decimal("1") - refunds)
    affiliate_cost = net * commission
    contribution = net - affiliate_cost
    cac = affiliate_cost / expected_sales if expected_sales else None
    denominator = Decimal(clicks) * price_value * (Decimal("1") - fee) * (Decimal("1") - refunds) * (Decimal("1") - commission)
    break_even = campaign_cost / denominator if denominator else None
    return {
        "clicks": clicks,
        "expected_pro_sales": expected_sales,
        "gross_revenue": money(gross),
        "net_revenue": money(net),
        "affiliate_cost": money(affiliate_cost),
        "cac": money(cac) if cac is not None else None,
        "profit_contribution": money(contribution),
        "break_even_pro_conversion": break_even,
    }


def serializable(result: dict[str, Decimal | int | None]) -> dict[str, object]:
    output: dict[str, object] = {}
    for key, value in result.items():
        if isinstance(value, Decimal):
            output[key] = float(money(value)) if key != "break_even_pro_conversion" else float(value)
        else:
            output[key] = value
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clicks", type=int, required=True)
    parser.add_argument("--play-store-conversion", required=True, type=Decimal)
    parser.add_argument("--install-rate", required=True, type=Decimal)
    parser.add_argument("--pro-conversion", required=True, type=Decimal)
    parser.add_argument("--price", required=True, type=Decimal, help="price in the local currency")
    parser.add_argument("--google-fee", required=True, type=Decimal)
    parser.add_argument("--refund-rate", required=True, type=Decimal)
    parser.add_argument("--commission-rate", required=True, type=Decimal)
    parser.add_argument("--fixed-campaign-cost", default=Decimal("0"), type=Decimal)
    args = parser.parse_args()
    print(json.dumps(serializable(calculate(**vars(args))), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
