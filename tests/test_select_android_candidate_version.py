from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from select_android_candidate_version import select_candidate


def test_keeps_requested_revision_when_it_is_free():
    tag, version = select_candidate("v1.0.4.2", 1_000_401)
    assert tag == "v1.0.4.2"
    assert version.name == "1.0.4.2"
    assert version.code == 1_000_402


def test_advances_to_smallest_free_revision_when_requested_is_occupied():
    tag, version = select_candidate("v1.0.4.2", 1_000_407)
    assert tag == "v1.0.4.8"
    assert version.code == 1_000_408


def test_does_not_silently_cross_release_lines():
    try:
        select_candidate("v1.0.4.2", 1_000_500)
    except ValueError as error:
        assert "choose a new release line explicitly" in str(error)
    else:
        raise AssertionError("expected release-line exhaustion to fail")
