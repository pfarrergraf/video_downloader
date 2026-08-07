from decimal import Decimal

from scripts.affiliate_funnel import calculate


def test_funnel_calculator_is_price_agnostic_and_deterministic():
    result = calculate(
        clicks=1000,
        play_store_conversion=Decimal("0.7"),
        install_rate=Decimal("1"),
        pro_conversion=Decimal("0.04"),
        price=Decimal("11.99"),
        google_fee=Decimal("0.15"),
        refund_rate=Decimal("0.05"),
        commission_rate=Decimal("0.30"),
    )
    assert result["expected_pro_sales"] == Decimal("28.000")
    assert result["gross_revenue"] == Decimal("335.72")
    assert result["net_revenue"] == Decimal("271.09")
    assert result["affiliate_cost"] == Decimal("81.33")
    assert result["profit_contribution"] == Decimal("189.77")


def test_funnel_rejects_invalid_rates_and_handles_zero_sales():
    try:
        calculate(
            clicks=0,
            play_store_conversion=Decimal("1.1"),
            install_rate=1,
            pro_conversion=0,
            price=1,
            google_fee=0,
            refund_rate=0,
            commission_rate=0,
        )
    except ValueError as error:
        assert "play_store_conversion" in str(error)
    else:
        raise AssertionError("invalid rate was accepted")

    result = calculate(
        clicks=0,
        play_store_conversion=0,
        install_rate=1,
        pro_conversion=1,
        price=10,
        google_fee=0,
        refund_rate=0,
        commission_rate=0.2,
        fixed_campaign_cost=10,
    )
    assert result["expected_pro_sales"] == 0
    assert result["cac"] is None
    assert result["break_even_pro_conversion"] is None
