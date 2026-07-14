"""Build an auditable monthly archive from original Google Play CSV reports.

The input CSV files are never modified.  This tool only reads them, creates a
machine-readable summary and hashes every file in the resulting evidence set.
It intentionally does not perform tax classification or bookkeeping entries.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path


THRESHOLDS = (Decimal("25000"), Decimal("100000"))
WARNING_LEVELS = (Decimal("0.80"), Decimal("0.90"), Decimal("0.95"), Decimal("1.00"))


def _normalized(value: str) -> str:
    return "".join(ch for ch in value.lower() if ch.isalnum())


def _decimal(value: object) -> Decimal:
    raw = str(value or "").strip().replace("\u00a0", "").replace(" ", "")
    if not raw:
        return Decimal("0")
    if raw.count(",") == 1 and raw.count(".") == 0:
        raw = raw.replace(",", ".")
    elif raw.count(",") and raw.count("."):
        raw = raw.replace(",", "")
    try:
        return Decimal(raw)
    except InvalidOperation:
        return Decimal("0")


def _pick(row: dict[str, str], *names: str) -> str:
    indexed = {_normalized(key): value for key, value in row.items() if key}
    for name in names:
        if _normalized(name) in indexed:
            return indexed[_normalized(name)]
    return ""


def _classify(row: dict[str, str]) -> str:
    kind = _pick(row, "transaction type", "transaction_type", "description", "event type").lower()
    if "refund" in kind or "chargeback" in kind:
        return "refund"
    if "fee" in kind or "commission" in kind:
        return "fee"
    if "tax" in kind or "vat" in kind:
        return "tax"
    if "payout" in kind or "disbursement" in kind:
        return "payout"
    return "sale"


def _amount(row: dict[str, str]) -> Decimal:
    return _decimal(
        _pick(
            row,
            "amount (merchant currency)",
            "merchant currency amount",
            "amount",
            "buyer currency amount",
            "charged amount",
        )
    )


def _currency(row: dict[str, str]) -> str:
    return _pick(row, "merchant currency", "currency", "buyer currency") or "UNKNOWN"


def parse_reports(paths: list[Path]) -> dict[str, object]:
    totals: dict[str, dict[str, Decimal]] = defaultdict(lambda: defaultdict(Decimal))
    payout_dates: set[str] = set()
    row_count = 0
    for path in paths:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            sample = handle.read(4096)
            handle.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
            except csv.Error:
                dialect = csv.excel
            for row in csv.DictReader(handle, dialect=dialect):
                row_count += 1
                kind = _classify(row)
                totals[_currency(row)][kind] += _amount(row)
                if kind == "payout":
                    payout_date = _pick(row, "payout date", "payment date", "transaction date", "date")
                    if payout_date:
                        payout_dates.add(payout_date)

    by_currency: dict[str, dict[str, str]] = {}
    for currency, values in sorted(totals.items()):
        gross = values["sale"]
        refunds = values["refund"]
        fees = values["fee"]
        taxes = values["tax"]
        explicit_payout = values["payout"]
        expected = explicit_payout or (gross + refunds + fees + taxes)
        by_currency[currency] = {
            "gross_sales": str(gross),
            "refunds": str(refunds),
            "fees": str(fees),
            "taxes": str(taxes),
            "reported_payout": str(explicit_payout),
            "expected_payout": str(expected),
        }
    return {"rows": row_count, "currencies": by_currency, "reported_payout_dates": sorted(payout_dates)}


def threshold_warnings(relevant_eur: Decimal) -> list[dict[str, str]]:
    warnings = []
    for threshold in THRESHOLDS:
        for level in WARNING_LEVELS:
            trigger = threshold * level
            if relevant_eur >= trigger:
                warnings.append(
                    {
                        "threshold_eur": str(threshold),
                        "level_percent": str(int(level * 100)),
                        "trigger_eur": str(trigger),
                    }
                )
    return warnings


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _prior_relevant_eur(prior_archive: Path | None, exclude_month: str) -> Decimal:
    if not prior_archive or not prior_archive.exists():
        return Decimal("0")
    total = Decimal("0")
    for path in prior_archive.rglob("summary.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("month") != exclude_month:
                total += _decimal(data["financials"]["currencies"].get("EUR", {}).get("gross_sales"))
        except (OSError, KeyError, TypeError, json.JSONDecodeError):
            continue
    return total


def build_archive(
    input_dir: Path,
    output_dir: Path,
    month: str,
    ytd_relevant_eur: Decimal,
    prior_archive: Path | None = None,
) -> Path:
    csv_files = sorted(input_dir.glob("*.csv"))
    if not csv_files:
        raise ValueError(f"no CSV reports found in {input_dir}")
    raw_dir = output_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    for source in csv_files:
        shutil.copy2(source, raw_dir / source.name)

    financials = parse_reports(csv_files)
    current_eur = _decimal(financials["currencies"].get("EUR", {}).get("gross_sales"))
    calculated_ytd = _prior_relevant_eur(prior_archive, month) + max(current_eur, Decimal("0"))
    effective_ytd = ytd_relevant_eur if ytd_relevant_eur > 0 else calculated_ytd
    summary = {
        "schema_version": 1,
        "month": month,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "Google Play original financial CSV reports",
        "financials": financials,
        "kleinunternehmer_monitor": {
            "relevant_ytd_eur": str(effective_ytd),
            "calculation": "owner_override" if ytd_relevant_eur > 0 else "sum_of_archived_and_current_eur_gross_sales",
            "warnings": threshold_warnings(effective_ytd),
            "automatic_tax_change": False,
        },
        "bank_reconciliation": {
            "status": "owner_confirmation_required",
            "expected_amounts": {
                currency: amounts["expected_payout"] for currency, amounts in financials["currencies"].items()
            },
            "reported_payout_dates": financials["reported_payout_dates"],
            "exception": "missing_bank_confirmation",
        },
    }
    summary_path = output_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    procedure = output_dir / "procedure.txt"
    procedure.write_text(
        "Original CSV files were copied byte-for-byte into raw/. summary.json was derived "
        "without modifying the originals. The manifest hashes all evidence files. A human "
        "must confirm the bank receipt and any tax treatment.\n",
        encoding="utf-8",
    )
    if summary["kleinunternehmer_monitor"]["warnings"]:
        (output_dir / "tax-advisor-package.txt").write_text(
            "Threshold warning reached. Review the attached originals and summary. Questions: "
            "Which turnover is relevant under current German VAT rules? When does a change of "
            "VAT treatment take effect? Are foreign-currency and platform-tax amounts mapped correctly?\n",
            encoding="utf-8",
        )

    manifest_path = output_dir / "SHA256SUMS"
    evidence = sorted(path for path in output_dir.rglob("*") if path.is_file() and path != manifest_path)
    manifest_path.write_text(
        "".join(f"{sha256(path)}  {path.relative_to(output_dir).as_posix()}\n" for path in evidence),
        encoding="utf-8",
    )
    return manifest_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--month", required=True, help="YYYY-MM")
    parser.add_argument("--ytd-relevant-eur", type=Decimal, default=Decimal("0"))
    parser.add_argument("--prior-archive", type=Path)
    args = parser.parse_args()
    build_archive(args.input, args.output, args.month, args.ytd_relevant_eur, args.prior_archive)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
