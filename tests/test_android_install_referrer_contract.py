from pathlib import Path

ROOT = Path(__file__).parents[1]

def test_install_referrer_is_play_only_and_disabled_by_default():
    gradle = (ROOT / "android/app/build.gradle").read_text(encoding="utf-8")
    assert "playImplementation 'com.android.installreferrer:installreferrer:2.2'" in gradle
    assert 'AFFILIATE_ATTRIBUTION_CLIENT_ENABLED", "false"' in gradle
    assert "implementation 'com.android.installreferrer" not in gradle

def test_repository_closes_connection_and_never_logs_referrer():
    source = (ROOT / "android/app/src/play/java/de/classydl/app/PlayInstallReferrerRepository.kt").read_text(encoding="utf-8")
    assert "endConnection()" in source
    assert "details.installReferrer" in source
    assert "Log.d" not in source
    assert "Log.i" not in source
