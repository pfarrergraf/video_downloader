from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEBSITE = ROOT / "pro" / "website"
INDEX = WEBSITE / "index.html"
CSS = WEBSITE / "assets" / "home" / "hero-product-cinema.css"
JS = WEBSITE / "assets" / "home" / "hero-product-cinema.js"

# The lab/QA preview must keep working unmodified.
LAB_HTML = WEBSITE / "gpt_hero_product_cinema_v3.html"
LAB_PREVIEW = WEBSITE / "gpt_product_cinema_v3_preview.html"
LAB_ASSETS = WEBSITE / "assets" / "gpt_product_cinema_v3"


def _index_html() -> str:
    return INDEX.read_text(encoding="utf-8")


def test_production_files_exist() -> None:
    assert INDEX.is_file()
    assert CSS.is_file()
    assert JS.is_file()


def test_homepage_loads_production_cinema_assets() -> None:
    html = _index_html()
    assert 'href="assets/home/hero-product-cinema.css"' in html
    assert 'src="assets/home/hero-product-cinema.js"' in html


def test_no_lab_naming_leaks_into_production_homepage() -> None:
    html = _index_html()
    assert "gpt_" not in html
    assert "fable_" not in html
    assert "product cinema v3" not in html.lower()


def test_homepage_has_only_one_navigation() -> None:
    html = _index_html()
    # The lab nav (.pc3-nav) must not be reintroduced alongside the real one.
    assert html.count('<header class="nav">') == 1
    assert "pc3-nav" not in html


def test_all_six_cinema_scenes_present() -> None:
    html = _index_html()
    states = ("source", "share", "format", "stream", "inside", "success")
    for state in states:
        assert f'data-pc3-view="{state}"' in html
    assert html.count("data-pc3-view=") == len(states)


def test_headline_lead_and_cta_are_dom_text_not_js_generated() -> None:
    # Headline/lead are visually hidden (product feedback: the animation should
    # carry the hero) but must stay real DOM text on a real <h1> — not removed
    # outright, and never something JS has to generate — so the page keeps an
    # accessible/SEO title. The secondary "See Pro pricing" CTA was dropped
    # from the hero entirely (redundant with the pricing section below).
    html = _index_html()
    assert "<h1" in html
    assert 'data-i18n="website.hero_cinema.title_line_1"' in html
    assert 'data-i18n="website.hero_cinema.title_line_2"' in html
    assert 'data-i18n="website.hero_cinema.title_line_3"' in html
    assert 'data-i18n="website.hero_cinema.lead"' in html
    assert 'data-i18n="website.hero.cta_primary"' in html
    assert 'href="/download"' in html


def test_reduced_motion_hooks_exist() -> None:
    # No manual Replay/Step-through/Motion/Sound buttons by design (per
    # product feedback - too much UI clutter): the story loops on its own
    # forever, and prefers-reduced-motion is honored automatically instead
    # of via a manual toggle the visitor has to find and click.
    css = CSS.read_text(encoding="utf-8")
    js = JS.read_text(encoding="utf-8")
    html = _index_html()
    assert "prefers-reduced-motion" in css
    assert "prefers-reduced-motion: reduce" in js
    assert "data-pc3-motion" not in html
    assert "data-pc3-replay" not in html
    assert "data-pc3-stepthrough" not in html
    assert "data-pc3-sound" not in html


def test_inactive_scenes_are_removed_from_accessibility_tree_by_script() -> None:
    js = JS.read_text(encoding="utf-8")
    assert "aria-hidden" in js
    assert ".inert" in js or "v.inert" in js


def test_animation_pauses_when_tab_is_hidden() -> None:
    js = JS.read_text(encoding="utf-8")
    assert "visibilitychange" in js
    assert "document.hidden" in js


def test_cinema_assets_do_not_contain_payment_or_affiliate_logic() -> None:
    combined = (CSS.read_text(encoding="utf-8") + "\n" + JS.read_text(encoding="utf-8")).lower()
    forbidden = (
        "buy.stripe.com",
        "client_reference_id",
        "withdrawal-modal",
        "affiliate_code",
        "stripe_payment_link",
        "android.permission",
    )
    for token in forbidden:
        assert token not in combined, f"unexpected token {token!r} in cinema assets"


def test_cinema_assets_have_no_external_urls() -> None:
    for path in (CSS, JS):
        text = path.read_text(encoding="utf-8")
        for match in re.finditer(r"url\(([^)]+)\)", text):
            url = match.group(1).strip("'\" ")
            assert url.startswith("data:") or not url.startswith(("http://", "https://", "//")), (
                f"{path} references an external URL: {url!r}"
            )
        assert "fonts.googleapis.com" not in text
        assert "fonts.gstatic.com" not in text


def test_homepage_has_no_external_script_or_style_hosts() -> None:
    html = _index_html()
    for tag, attr in (("link", "href"), ("script", "src")):
        for match in re.finditer(rf'<{tag}[^>]*\s{attr}="([^"]+)"', html):
            url = match.group(1)
            if tag == "link" and 'rel="canonical"' in match.group(0):
                continue
            assert not url.startswith(("http://", "https://", "//")), (
                f"index.html loads an external resource: <{tag} {attr}={url!r}>"
            )


def test_homepage_routes_pro_to_google_play_options_without_legacy_checkout() -> None:
    html = _index_html()
    assert 'id="buy-license-btn"' in html
    assert 'href="/download/android"' in html
    assert 'id="withdrawal-modal"' not in html
    assert "buy.stripe.com" not in html
    assert "client_reference_id" not in html


def test_lab_fragment_remains_but_public_dev_preview_is_removed() -> None:
    assert LAB_HTML.is_file()
    assert not LAB_PREVIEW.exists()
    assert LAB_ASSETS.is_dir()
    lab_html = LAB_HTML.read_text(encoding="utf-8")
    assert "PRODUCT CINEMA V3" in lab_html
    assert 'data-pc3-view="success"' in lab_html


def test_new_hero_cinema_i18n_keys_are_wired_up() -> None:
    # The in-phone scenes are intentionally near-textless (icons + motion only,
    # per product feedback); each scene's step_* copy survives only as an
    # aria-label for screen readers, except the source-scene CTA (share_cta),
    # which was deliberately given a visible label. Per further product
    # feedback, the eyebrow, trust chip, legal note, secondary CTA and
    # Windows link were dropped from the hero entirely (kept, still
    # translated, elsewhere on the site: legal note in the FAQ, Windows link
    # in the footer). eyebrow/legal/trust_local/trust_cloud/format_title/
    # stream_title/inside_title/success_title/success_body are unused by
    # design now; their i18n entries are left in place across all locales in
    # case this direction changes again, but nothing requires them to appear
    # in the markup. format_images is likewise unused now — the app's share
    # flow only ever offers Video/Audio (there is no Images toggle anywhere
    # in video_downloader/web/static/index.html), so showing an "Images"
    # choice in the animation would misrepresent what the app actually does.
    # replay/stepthrough/motion_toggle_label/sound_toggle_label are unused
    # too now: there are no manual controls at all (per product feedback -
    # too much UI clutter), the story just loops on its own forever.
    html = _index_html()
    required_keys = (
        "title_line_1", "title_line_2", "title_line_3", "lead",
        "step_source", "step_share", "step_format", "step_stream", "step_inside", "step_success",
        "share_title", "share_cta", "format_video", "format_audio",
    )
    for key in required_keys:
        assert f"website.hero_cinema.{key}" in html, f"missing data-i18n wiring for {key}"
