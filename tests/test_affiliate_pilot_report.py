from decimal import Decimal

from scripts.affiliate_pilot_report import evaluate


def test_pilot_report_uses_aggregate_counters_and_stop_thresholds():
    result = evaluate({"clicks": 100, "installs": 40, "purchases": 8, "voided_purchases": 1, "paid_minor": 500})
    assert result["install_to_purchase_rate"] == "0.2000"
    assert result["void_rate"] == "0.1250"
    assert result["stop"] is False

    stopped = evaluate({"installs": 10, "purchases": 4, "voided_purchases": 2}, max_refund_rate=Decimal("0.15"))
    assert stopped["stop"] is True
    assert "refund_rate_above_threshold" in stopped["stop_reasons"]


def test_pilot_report_rejects_buyer_level_fields():
    try:
        evaluate({"clicks": 1, "purchase_token": "secret"})
    except ValueError as error:
        assert "unsupported" in str(error)
    else:
        raise AssertionError("buyer-level field was accepted")
