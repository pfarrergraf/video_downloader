from pathlib import Path

from scripts.check_no_ad_sdk import find_ad_sdk_references, shipped_text_files


def test_gate_detects_known_advertising_sdk(tmp_path: Path) -> None:
    source = tmp_path / "build.gradle"
    source.write_text('implementation "com.google.android.gms:play-services-ads:1.0"', encoding="utf-8")
    findings = find_ad_sdk_references([source])
    assert [finding["sdk"] for finding in findings] == ["Google Mobile Ads"]


def test_current_shipped_sources_have_no_advertising_sdk_reference() -> None:
    files = shipped_text_files()
    assert files
    assert find_ad_sdk_references(files) == []
