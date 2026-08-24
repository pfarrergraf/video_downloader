from scripts.check_public_claims import FORBIDDEN, find_violations


def test_active_public_sources_follow_security_claims_policy() -> None:
    assert find_violations() == []


def test_fixed_public_price_claim_detects_currency_before_or_after_amount() -> None:
    pattern = FORBIDDEN["fixed public price claim"]
    for sample in ("12 €", "12&nbsp;€", "$4.99", "4,99 EUR", "£ 9"):
        assert pattern.search(sample), f"fixed public price was not detected: {sample!r}"


def test_dynamic_local_play_price_copy_is_allowed() -> None:
    pattern = FORBIDDEN["fixed public price claim"]
    for sample in (
        "One-time purchase at your local Google Play price",
        "Einmalkauf zum lokalen Google-Play-Preis",
    ):
        assert pattern.search(sample) is None
