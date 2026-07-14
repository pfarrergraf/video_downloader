from scripts.check_public_claims import find_violations


def test_active_public_sources_follow_security_claims_policy() -> None:
    assert find_violations() == []
