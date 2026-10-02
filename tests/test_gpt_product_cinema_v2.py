from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "pro" / "website" / "gpt_hero_product_cinema_v2.html"
CSS = ROOT / "pro" / "website" / "assets" / "gpt_product_cinema_v2" / "gpt_product_cinema_v2.css"
JS = ROOT / "pro" / "website" / "assets" / "gpt_product_cinema_v2" / "gpt_product_cinema_v2.js"


def test_product_cinema_files_exist() -> None:
    assert HTML.is_file()
    assert CSS.is_file()
    assert JS.is_file()


def test_preview_references_only_local_component_assets() -> None:
    html = HTML.read_text(encoding="utf-8")
    assert "assets/gpt_product_cinema_v2/gpt_product_cinema_v2.css" in html
    assert "assets/gpt_product_cinema_v2/gpt_product_cinema_v2.js" in html
    assert "http://" not in html
    assert "https://" not in html


def test_product_story_has_all_five_states() -> None:
    html = HTML.read_text(encoding="utf-8")
    for state in ("source", "share", "format", "transfer", "success"):
        assert f'data-pc-scene="{state}"' in html
    assert html.count("data-pc-scene=") == 5


def test_component_is_namespaced_and_reduced_motion_safe() -> None:
    css = CSS.read_text(encoding="utf-8")
    js = JS.read_text(encoding="utf-8")
    assert "@media (prefers-reduced-motion:reduce)" in css
    assert "prefers-reduced-motion: reduce" in js
    assert "[data-pc-root]" in js
    assert ".pc-shell" in css
    assert ".hero " not in css
    assert ".btn " not in css


def test_preview_does_not_embed_checkout_or_affiliate_logic() -> None:
    combined = "\n".join(
        path.read_text(encoding="utf-8") for path in (HTML, CSS, JS)
    ).lower()
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


def test_legal_and_product_truth_are_visible_dom_text() -> None:
    html = HTML.read_text(encoding="utf-8")
    assert "Nur Inhalte speichern" in html
    assert "direkt auf deinem Android-Gerät" in html
    assert "kein unnötiger Cloud-Upload" in html
    assert "Gespeichert." in html
