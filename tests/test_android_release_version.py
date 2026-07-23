"""Release-version ordering guards for Google Play uploads."""

import pytest

from scripts.android_version_from_tag import from_tag


def test_requested_hotfix_version_is_monotone() -> None:
    hotfix = from_tag("v0.8.4.1")
    assert hotfix.name == "0.8.4.1"
    assert hotfix.code == 80401
    assert hotfix.code > 804  # existing v0.8.4 release metadata


def test_next_normal_release_remains_above_hotfix() -> None:
    assert from_tag("v0.8.5").code == 80500
    assert from_tag("v0.8.5").code > from_tag("v0.8.4.99").code


@pytest.mark.parametrize(
    "tag",
    ("0.8.4.1", "v0.8", "v0.8.4.beta", "v0.100.0", "v0.8.4.100"),
)
def test_invalid_or_ambiguous_versions_are_rejected(tag: str) -> None:
    with pytest.raises(ValueError):
        from_tag(tag)
