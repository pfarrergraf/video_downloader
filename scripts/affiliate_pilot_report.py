#!/usr/bin/env python3
"""Evaluate redacted aggregate pilot data; never accepts buyer-level records."""

from __future__ import annotations

import argparse
import json
from decimal import Decimal
from pathlib import Path


def ratio(numerator: int, denominator: int) -> Decimal:
    return Decimal(numerator) / Decimal(denominator) if denominator else Decimal("0")


def evaluate(data: dict, *, max_refund_rate: Decimal = Decimal("0.15"), max_install_purchase_rate: Decimal = Decimal("0.25")) -> dict:
    allowed = {"clicks", "installs", "purchases", "voided_purchases", "pending_minor", "payable_minor", "paid_minor"}
    unknown = set(data) - allowed
    if unknown:
        raise ValueError(f"unsupported non-aggregate fields: {', '.join(sorted(unknown))}")
    values = {key: int(data.get(key, 0)) for key in allowed}
    if any(value < 0 for value in values.values()):
        raise ValueError("aggregate counters must be non-negative")
    refund_rate = ratio(values["voided_purchases"], values["purchases"])
    install_purchase_rate = ratio(values["purchases"], values["installs"])
    stop_reasons = []
    if refund_rate > max_refund_rate:
        stop_reasons.append("refund_rate_above_threshold")
    if install_purchase_rate > max_install_purchase_rate:
        stop_reasons.append("install_purchase_rate_above_threshold")
    return {
        "clicks": values["clicks"],
        "installs": values["installs"],
        "purchases": values["purchases"],
        "voided_purchases": values["voided_purchases"],
        "install_to_purchase_rate": str(install_purchase_rate.quantize(Decimal("0.0001"))),
        "void_rate": str(refund_rate.quantize(Decimal("0.0001"))),
        "pending_minor": values["pending_minor"],
        "payable_minor": values["payable_minor"],
        "paid_minor": values["paid_minor"],
        "stop": bool(stop_reasons),
        "stop_reasons": stop_reasons,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="JSON file containing only aggregate counters")
    parser.add_argument("--max-refund-rate", type=Decimal, default=Decimal("0.15"))
    parser.add_argument("--max-install-purchase-rate", type=Decimal, default=Decimal("0.25"))
    args = parser.parse_args()
    result = evaluate(json.loads(args.input.read_text(encoding="utf-8")), max_refund_rate=args.max_refund_rate, max_install_purchase_rate=args.max_install_purchase_rate)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
