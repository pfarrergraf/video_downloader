from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "pro" / "website" / "gpt_hero_product_cinema_v3.html"
PREVIEW = ROOT / "pro" / "website" / "gpt_product_cinema_v3_preview.html"
ASSETS = ROOT / "pro" / "website" / "assets" / "gpt_product_cinema_v3"
CSS_FILES = (
    ASSETS / "gpt_product_cinema_v3_base.css",
    ASSETS / "gpt_product_cinema_v3_stage.css",
    ASSETS / "gpt_product_cinema_v3_motion.css",
)
JS = ASSETS / "gpt_product_cinema_v3.js"


def test_v3_files_exist() -> None:
    assert HTML.is_file()
    assert PREVIEW.is_file()
    assert JS.is_file()
    assert all(path.is_file() for path in CSS_FILES)


def test_v3_story_contains_all_six_states() -> None:
    html = HTML.read_text(encoding="utf-8")
    states = ("source", "share", "format", "stream", "inside", "success")
    for state in states:
        assert f'data-pc3-view="{state}"' in html
    assert html.count("data-pc3-view=") == len(states)


def test_both_requested_animation_systems_exist() -> None:
    html = HTML.read_text(encoding="utf-8")
    js = JS.read_text(encoding="utf-8")
    css = "\n".join(path.read_text(encoding="utf-8") for path in CSS_FILES)
    assert "data-pc3-stream" in html
    assert "arrowPoints" in js
    assert "pc3-source--video" in css
    assert "pc3-source--audio" in css
    assert "pc3-source--image" in css
    assert 'data-pc3-phase="inside"' in css
    assert "pc3-glass-flare" in css
    assert "pc3-portal" in css


def test_accessibility_and_motion_controls_exist() -> None:
    html = HTML.read_text(encoding="utf-8")
    js = JS.read_text(encoding="utf-8")
    css = "\n".join(path.read_text(encoding="utf-8") for path in CSS_FILES)
    assert 'aria-live="polite"' in html
    assert 'data-pc3-motion' in html
    assert 'data-pc3-stepthrough' in html
    assert "prefers-reduced-motion" in css
    assert "prefers-reduced-motion: reduce" in js
    assert "visibilitychange" in js


def test_v3_does_not_embed_payment_or_android_permission_logic() -> None:
    files = (HTML, PREVIEW, JS, *CSS_FILES)
    combined = "\n".join(path.read_text(encoding="utf-8") for path in files).lower()
    forbidden = (
        "buy.stripe.com",
        "client_reference_id",
        "withdrawal-modal",
        "affiliate_code",
        "stripe_payment_link",
        "android.permission",
    )
    for token in forbidden:
        assert token not in combined
