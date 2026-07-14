from __future__ import annotations

import hashlib
import json
from decimal import Decimal

from scripts.google_play_finance import build_archive, threshold_warnings


def test_monthly_archive_preserves_originals_and_summarizes(tmp_path) -> None:
    source = tmp_path / "source"
    output = tmp_path / "archive"
    source.mkdir()
    original = (
        "Transaction Type,Amount (Merchant Currency),Merchant Currency\n"
        "Charge,12.00,EUR\nRefund,-12.00,EUR\nGoogle fee,-1.80,EUR\nTax,-1.91,EUR\n"
    ).encode()
    (source / "earnings.csv").write_bytes(original)

    manifest = build_archive(source, output, "2026-07", Decimal("24000"))

    assert (output / "raw" / "earnings.csv").read_bytes() == original
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    eur = summary["financials"]["currencies"]["EUR"]
    assert eur["gross_sales"] == "12.00"
    assert eur["refunds"] == "-12.00"
    assert eur["fees"] == "-1.80"
    assert eur["taxes"] == "-1.91"
    assert summary["bank_reconciliation"]["status"] == "owner_confirmation_required"
    assert (output / "tax-advisor-package.txt").is_file()
    line = next(line for line in manifest.read_text().splitlines() if line.endswith("raw/earnings.csv"))
    assert line.startswith(hashlib.sha256(original).hexdigest())


def test_threshold_monitor_emits_80_90_95_and_100_percent() -> None:
    levels = threshold_warnings(Decimal("25000"))
    assert [item["level_percent"] for item in levels if item["threshold_eur"] == "25000"] == [
        "80",
        "90",
        "95",
        "100",
    ]
    assert not [item for item in levels if item["threshold_eur"] == "100000"]


def test_ytd_is_calculated_from_prior_archives_without_double_counting_current_month(tmp_path) -> None:
    source = tmp_path / "source"
    prior = tmp_path / "prior"
    output = tmp_path / "output"
    source.mkdir()
    prior.mkdir()
    (source / "sales.csv").write_text(
        "Transaction Type,Amount,Merchant Currency\nCharge,100,EUR\n", encoding="utf-8"
    )
    (prior / "june").mkdir()
    (prior / "june" / "summary.json").write_text(
        json.dumps({"month": "2026-06", "financials": {"currencies": {"EUR": {"gross_sales": "200"}}}}),
        encoding="utf-8",
    )
    (prior / "july").mkdir()
    (prior / "july" / "summary.json").write_text(
        json.dumps({"month": "2026-07", "financials": {"currencies": {"EUR": {"gross_sales": "999"}}}}),
        encoding="utf-8",
    )
    build_archive(source, output, "2026-07", Decimal("0"), prior)
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert summary["kleinunternehmer_monitor"]["relevant_ytd_eur"] == "300"
