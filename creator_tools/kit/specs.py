"""Render-Spezifikation des unpersonalisierten Creator-Kits.

Jeder Eintrag beschreibt ein fertiges Werbemittel: Template, Zielpfad, Größe,
Theme, Sprachen und die sprachabhängigen Text-Tokens. Die Produktfakten kommen
aus ``product_facts.json`` — hier stehen nur Formulierungen, keine Preise.

Gewählte Richtungen (siehe docs/influencer-design-directions.html):
* Promotion-Assets (Kit B) → **creator-energy** (entspricht der echten App-UI)
* Recruitment-Assets (Kit A) → **premium-tech** (entspricht der Website)
* Tutorial-/Blog-Assets → **clean-utility**
"""

GRAD = '<span class="grad-text">{}</span>'


def _g(s: str) -> str:
    return GRAD.format(s)


# ---------------------------------------------------------------------------
# Kit B — 10 Story-Vorlagen (1080×1920, Safe Areas oben 230 / unten 330)
# ---------------------------------------------------------------------------
STORIES = [
    dict(template="story/story-01-know-this-app.html", slug="story-01-know-this-app",
         theme="creator-energy", extra={"de": {}, "en": {}}),
    dict(template="story/story-statement.html", slug="story-02-save-media",
         theme="creator-energy",
         extra={
             "de": {"story_title": f"So speicherst du erlaubte Medien {_g('direkt auf deinem Gerät')}.",
                    "story_sub": "Ohne Umweg über irgendeine Cloud — Video, Audio oder Bild.",
                    "story_shot": "screenshot_queue.png", "story_cta": "Kostenlos testen"},
             "en": {"story_title": f"Save permitted media {_g('right on your device')}.",
                    "story_sub": "No detour through anyone's cloud — video, audio or image.",
                    "story_shot": "screenshot_queue.png", "story_cta": "Try it free"},
         }),
    dict(template="story/story-steps.html", slug="story-03-share-steps",
         theme="creator-energy",
         extra={
             "de": {"story_title": f"Teilen. {_g('DownloadThat')}. Fertig."},
             "en": {"story_title": f"Share. {_g('DownloadThat')}. Done."},
         }),
    dict(template="story/story-statement.html", slug="story-04-no-cloud",
         theme="creator-energy",
         extra={
             "de": {"story_title": f"Keine unnötige {_g('Cloud-Zwischenstation')}.",
                    "story_sub": "Alles läuft lokal auf deinem Handy. Nichts wird irgendwo hochgeladen.",
                    "story_shot": "", "story_cta": "Mehr in meiner Bio"},
             "en": {"story_title": f"No pointless {_g('cloud middleman')}.",
                    "story_sub": "Everything runs locally on your phone. Nothing gets uploaded anywhere.",
                    "story_shot": "", "story_cta": "More in my bio"},
         }),
    dict(template="story/story-statement.html", slug="story-05-testing",
         theme="creator-energy",
         extra={
             "de": {"story_title": f"Ich teste gerade {_g('DownloadThat')}.",
                    "story_sub": "Ehrliches Fazit kommt — bisher: Teilen, App wählen, gespeichert.",
                    "story_shot": "screenshot_main.png", "story_cta": "Fragen? Schreib mir"},
             "en": {"story_title": f"I'm testing {_g('DownloadThat')}.",
                    "story_sub": "Honest verdict coming — so far: share, pick the app, saved.",
                    "story_shot": "screenshot_main.png", "story_cta": "Questions? DM me"},
         }),
    dict(template="story/story-statement.html", slug="story-06-link-in-bio",
         theme="creator-energy",
         extra={
             "de": {"story_title": f"Link in meiner {_g('Bio')}.",
                    "story_sub": "DownloadThat kostenlos ausprobieren — 3 Downloads am Tag, volle Qualität.",
                    "story_shot": "", "story_cta": "→ Zur Bio"},
             "en": {"story_title": f"Link in my {_g('bio')}.",
                    "story_sub": "Try DownloadThat for free — 3 downloads a day, full quality.",
                    "story_shot": "", "story_cta": "→ To the bio"},
         }),
    dict(template="story/story-code.html", slug="story-07-my-code",
         theme="creator-energy",
         extra={
             "de": {"story_title": f"Mein {_g('Creator-Code')}."},
             "en": {"story_title": f"My {_g('creator code')}."},
         }),
    dict(template="story/story-statement.html", slug="story-08-try-free",
         theme="creator-energy",
         extra={
             "de": {"story_title": f"{_g('Kostenlos')} ausprobieren.",
                    "story_sub": "3 Downloads pro Tag, für immer — in voller HD/4K-Qualität. Ohne Konto.",
                    "story_shot": "screenshot_main.png", "story_cta": "Kostenlos testen"},
             "en": {"story_title": f"Try it {_g('for free')}.",
                    "story_sub": "3 downloads a day, forever — in full HD/4K quality. No account.",
                    "story_shot": "screenshot_main.png", "story_cta": "Try it free"},
         }),
    dict(template="story/story-statement.html", slug="story-09-pro-onetime",
         theme="creator-energy",
         extra={
             "de": {"story_title": f"Vollversion mit {_g('einmaliger Lizenz')}.",
                    "story_sub": "12 € einmal zahlen, für immer nutzen. Kein Abo, keine versteckten Kosten.",
                    "story_shot": "", "story_cta": "Details in meiner Bio"},
             "en": {"story_title": f"Full version, {_g('one-time license')}.",
                    "story_sub": "Pay €12 once, use it forever. No subscription, no hidden costs.",
                    "story_shot": "", "story_cta": "Details in my bio"},
         }),
    dict(template="story/story-checklist.html", slug="story-10-three-things",
         theme="creator-energy",
         extra={
             "de": {"story_title": f"Drei Dinge, die mir an {_g('DownloadThat')} gefallen:",
                    "item1": "Teilen-Menü statt Copy-Paste", "item1_sub": "Zwei Fingertipps vom Link zum Download",
                    "item2": "Alles bleibt auf dem Gerät", "item2_sub": "Kein Cloud-Upload, kein Konto, keine Werbung",
                    "item3": "Downloads überleben alles", "item3_sub": "App geschlossen? Der Download läuft weiter",
                    "story_foot": "Werbung · Persönliche Einschätzung"},
             "en": {"story_title": f"Three things I like about {_g('DownloadThat')}:",
                    "item1": "Share sheet instead of copy-paste", "item1_sub": "Two taps from link to download",
                    "item2": "Everything stays on the device", "item2_sub": "No cloud upload, no account, no ads",
                    "item3": "Downloads survive everything", "item3_sub": "Closed the app? The download keeps going",
                    "story_foot": "Ad · Personal opinion"},
         }),
]

# ---------------------------------------------------------------------------
# Kit B — 10 Feed-Vorlagen (Basis 1080×1350; 3 Motive zusätzlich 1080×1080 + 1200×628)
# ---------------------------------------------------------------------------
FEEDS = [
    dict(template="feed/feed-01-product-intro.html", slug="feed-01-product-intro",
         theme="creator-energy", extra={"de": {}, "en": {}}, also_sizes=[(1080, 1080), (1200, 628)]),
    dict(template="feed/feed-feature.html", slug="feed-02-feature-playlists",
         theme="creator-energy",
         extra={
             "de": {"feat_kicker": "Feature-Fokus", "feat_title": f"Ganze Playlists. {_g('Ein Fingertipp')}.",
                    "feat_desc": "Playlist-Link einfügen und alle Videos daraus auf einmal herunterladen — statt jedes einzeln.",
                    "feat_icon": "∞", "feat_fact": "Playlist-Downloads sind Teil der Pro-Lizenz.",
                    "feat_foot": "Lade nur Inhalte herunter, für die du die erforderlichen Rechte oder die Erlaubnis besitzt."},
             "en": {"feat_kicker": "Feature focus", "feat_title": f"Whole playlists. {_g('One tap')}.",
                    "feat_desc": "Paste a playlist link and download every video in it at once — instead of one by one.",
                    "feat_icon": "∞", "feat_fact": "Playlist downloads are part of the Pro license.",
                    "feat_foot": "Only download content you have the necessary rights or permission for."},
         }),
    dict(template="blog/blog-steps.html", slug="feed-03-three-steps",
         theme="creator-energy", extra={"de": {}, "en": {}}),
    dict(template="feed/feed-feature.html", slug="feed-04-try-free",
         theme="creator-energy",
         extra={
             "de": {"feat_kicker": "Kostenlos testen", "feat_title": f"Erst {_g('ausprobieren')}, dann entscheiden.",
                    "feat_desc": "Die Free-Version bleibt für immer kostenlos: 3 Downloads pro Tag in voller HD/4K-Qualität — ohne Konto.",
                    "feat_icon": "0 €", "feat_fact": "Kein Abo. Keine Werbung. Kein Tracking.",
                    "feat_foot": "Funktioniert nicht mit DRM-Streaming-Diensten wie Spotify oder Netflix."},
             "en": {"feat_kicker": "Try it free", "feat_title": f"{_g('Try first')}, decide later.",
                    "feat_desc": "The free version stays free forever: 3 downloads a day in full HD/4K quality — no account.",
                    "feat_icon": "€0", "feat_fact": "No subscription. No ads. No tracking.",
                    "feat_foot": "Does not work with DRM streaming services like Spotify or Netflix."},
         }),
    dict(template="blog/blog-compare.html", slug="feed-05-free-vs-pro",
         theme="creator-energy", extra={"de": {}, "en": {}}),
    dict(template="cards/card-affiliate.html", slug="feed-06-creator-code",
         theme="creator-energy", extra={"de": {}, "en": {}}, also_sizes=[(1080, 1080)]),
    dict(template="feed/feed-announce.html", slug="feed-07-affiliate-link",
         theme="creator-energy",
         extra={
             "de": {"ann_badge": "Affiliate-Link", "ann_title": f"Über meinen Link {_g('kostenlos testen')}.",
                    "ann_desc": "Wenn du dir später die Pro-Lizenz holst, unterstützt du damit meinen Kanal — der Preis bleibt für dich gleich.",
                    "ann_cta": "Link in meiner Bio", "ann_shot": "screenshot_main.png",
                    "ann_foot": "Affiliate-Link: Bei einem Kauf über diesen Link erhalte ich eine Provision. Für dich ändert sich der Preis nicht."},
             "en": {"ann_badge": "Affiliate link", "ann_title": f"Use my link to {_g('try it free')}.",
                    "ann_desc": "If you grab the Pro license later, you support my channel — the price stays the same for you.",
                    "ann_cta": "Link in my bio", "ann_shot": "screenshot_main.png",
                    "ann_foot": "Affiliate link: I may earn a commission if you purchase through this link, at no additional cost to you."},
         }),
    dict(template="feed/feed-announce.html", slug="feed-08-app-update",
         theme="creator-energy",
         extra={
             "de": {"ann_badge": "App-Update", "ann_title": f"DownloadThat ist {_g('besser geworden')}.",
                    "ann_desc": "Die Download-Engine hält sich jetzt selbst aktuell — wenn sich große Seiten ändern, repariert sich die App im Hintergrund.",
                    "ann_cta": "Update ansehen", "ann_shot": "screenshot_settings.png",
                    "ann_foot": "Werbung · Details und Download über den Link in der Bio."},
             "en": {"ann_badge": "App update", "ann_title": f"DownloadThat just {_g('got better')}.",
                    "ann_desc": "The download engine now keeps itself up to date — when big sites change, the app repairs itself in the background.",
                    "ann_cta": "See what's new", "ann_shot": "screenshot_settings.png",
                    "ann_foot": "Ad · Details and download via the link in my bio."},
         }),
    dict(template="feed/feed-announce.html", slug="feed-09-tutorial-announce",
         theme="clean-utility",
         extra={
             "de": {"ann_badge": "Neues Tutorial", "ann_title": f"Schritt für Schritt: {_g('Medien direkt aufs Handy')}.",
                    "ann_desc": "Im neuen Video zeige ich den kompletten Ablauf — vom Teilen-Menü bis zur fertigen Datei in deinen Downloads.",
                    "ann_cta": "Jetzt ansehen", "ann_shot": "screenshot_queue.png",
                    "ann_foot": "Werbung · Lade nur Inhalte herunter, für die du die Rechte oder Erlaubnis besitzt."},
             "en": {"ann_badge": "New tutorial", "ann_title": f"Step by step: {_g('media straight to your phone')}.",
                    "ann_desc": "In the new video I walk through the whole flow — from the share sheet to the finished file in your downloads.",
                    "ann_cta": "Watch now", "ann_shot": "screenshot_queue.png",
                    "ann_foot": "Ad · Only download content you have the rights or permission for."},
         }),
    dict(template="feed/feed-recommend.html", slug="feed-10-personal-recommend",
         theme="creator-energy",
         extra={
             "de": {"quote_text": "Endlich eine Download-App, die sich nicht wie eine Falle anfühlt: keine Werbung, kein Konto, alles bleibt auf meinem Gerät."},
             "en": {"quote_text": "Finally a downloader that doesn't feel like a trap: no ads, no account, everything stays on my device."},
         }, also_sizes=[(1080, 1080)]),
]

# ---------------------------------------------------------------------------
# Kit B — YouTube (6 Thumbnails 1280×720 + Cover + Community + Endcard + Linkkarte)
# ---------------------------------------------------------------------------
THUMBS = [
    ("thumb-01-spart-zeit", "creator-energy",
     {"de": {"thumb_title": f"Diese Android-App<br>{_g('spart Zeit')}", "thumb_sub": "Video · Audio · Bilder — lokal gespeichert", "thumb_badge": "Im Test", "thumb_shot": "screenshot_main.png"},
      "en": {"thumb_title": f"This Android app<br>{_g('saves time')}", "thumb_sub": "Video · audio · images — saved locally", "thumb_badge": "Tested", "thumb_shot": "screenshot_main.png"}}),
    ("thumb-02-direkt-aufs-handy", "creator-energy",
     {"de": {"thumb_title": f"Videos {_g('direkt aufs')} Smartphone?", "thumb_sub": "So funktioniert der Teilen-Trick", "thumb_badge": "Anleitung", "thumb_shot": "screenshot_queue.png"}}),
    ("thumb-03-im-test", "premium-tech",
     {"de": {"thumb_title": f"DownloadThat<br>{_g('im Test')}", "thumb_sub": "Ehrliches Fazit nach einer Woche", "thumb_badge": "Review", "thumb_shot": "screenshot_main.png"}}),
    ("thumb-04-mehr-als-erwartet", "premium-tech",
     {"de": {"thumb_title": f"Diese App kann {_g('mehr als erwartet')}", "thumb_sub": "Playlists · MP3 · 4K — ohne Cloud", "thumb_badge": "Überraschung", "thumb_shot": "screenshot_queue.png"}}),
    ("thumb-05-teilen-speichern", "clean-utility",
     {"de": {"thumb_title": f"{_g('Teilen')} und direkt speichern", "thumb_sub": "Der 2-Tipps-Workflow für Android", "thumb_badge": "Tutorial", "thumb_shot": "screenshot_main.png"},
      "en": {"thumb_title": f"{_g('Share')} and save instantly", "thumb_sub": "The 2-tap workflow for Android", "thumb_badge": "Tutorial", "thumb_shot": "screenshot_main.png"}}),
    ("thumb-06-free-oder-lizenz", "clean-utility",
     {"de": {"thumb_title": f"Kostenlos oder Lizenz — {_g('was lohnt sich?')}", "thumb_sub": "Free vs. Pro ehrlich verglichen", "thumb_badge": "Vergleich", "thumb_shot": "screenshot_settings.png"}}),
]

CAROUSELS = {
    "carousel-how-it-works": dict(
        theme="creator-energy",
        slides=[
            {"de": dict(slide_num="", slide_title=f"Schluss mit {_g('Copy-Paste-Chaos')}.", slide_desc="So speicherst du erlaubte Videos, Audios und Bilder direkt auf deinem Android-Handy — in drei Schritten.", slide_shot="screenshot_main.png", slide_footer_left="Wischen →"),
             "en": dict(slide_num="", slide_title=f"No more {_g('copy-paste chaos')}.", slide_desc="Save permitted videos, audio and images right on your Android phone — in three steps.", slide_shot="screenshot_main.png", slide_footer_left="Swipe →")},
            {"de": dict(slide_num="1", slide_title="Teilen antippen.", slide_desc="Auf der Seite mit dem Inhalt — genau wie beim normalen Teilen an Freunde.", slide_shot="", slide_footer_left="Wischen →"),
             "en": dict(slide_num="1", slide_title="Tap share.", slide_desc="On the page with the content — exactly like sharing with friends.", slide_shot="", slide_footer_left="Swipe →")},
            {"de": dict(slide_num="2", slide_title="DownloadThat wählen.", slide_desc="Die App taucht im Android-Teilen-Menü auf und merkt sich deine Einstellungen.", slide_shot="", slide_footer_left="Wischen →"),
             "en": dict(slide_num="2", slide_title="Pick DownloadThat.", slide_desc="The app shows up in the Android share sheet and remembers your settings.", slide_shot="", slide_footer_left="Swipe →")},
            {"de": dict(slide_num="3", slide_title="Fertig — lokal gespeichert.", slide_desc="Video, MP3 oder Bild landet in deinen Downloads. Läuft im Hintergrund weiter, auch wenn du die App schließt.", slide_shot="screenshot_queue.png", slide_footer_left="Wischen →"),
             "en": dict(slide_num="3", slide_title="Done — saved locally.", slide_desc="The video, MP3 or image lands in your downloads. Keeps running in the background even if you close the app.", slide_shot="screenshot_queue.png", slide_footer_left="Swipe →")},
            {"de": dict(slide_num="", slide_title=f"Kostenlos {_g('ausprobieren')}.", slide_desc="3 Downloads pro Tag für immer kostenlos — volle Qualität. Link in meiner Bio. · Werbung", slide_shot="", slide_footer_left="Link in Bio"),
             "en": dict(slide_num="", slide_title=f"Try it {_g('for free')}.", slide_desc="3 downloads a day, free forever — full quality. Link in my bio. · Ad", slide_shot="", slide_footer_left="Link in bio")},
        ]),
    "carousel-five-reasons": dict(
        theme="creator-energy",
        slides=[
            {"de": dict(slide_num="", slide_title=f"5 Gründe für {_g('DownloadThat')}.", slide_desc="Eine ehrliche Liste — inklusive dem, was die App bewusst nicht kann.", slide_shot="screenshot_main.png", slide_footer_left="Wischen →"),
             "en": dict(slide_num="", slide_title=f"5 reasons for {_g('DownloadThat')}.", slide_desc="An honest list — including what the app deliberately doesn't do.", slide_shot="screenshot_main.png", slide_footer_left="Swipe →")},
            {"de": dict(slide_num="1+2", slide_title="Lokal & werbefrei.", slide_desc="Alles bleibt auf deinem Gerät: kein Cloud-Upload, kein Konto, keine Werbung, kein Tracking.", slide_shot="", slide_footer_left="Wischen →"),
             "en": dict(slide_num="1+2", slide_title="Local & ad-free.", slide_desc="Everything stays on your device: no cloud upload, no account, no ads, no tracking.", slide_shot="", slide_footer_left="Swipe →")},
            {"de": dict(slide_num="3+4", slide_title="Playlists & MP3.", slide_desc="Ganze Playlists auf einmal laden und aus jedem Video die Tonspur als MP3 ziehen — bis 4K.", slide_shot="", slide_footer_left="Wischen →"),
             "en": dict(slide_num="3+4", slide_title="Playlists & MP3.", slide_desc="Grab whole playlists at once and pull the audio track from any video as MP3 — up to 4K.", slide_shot="", slide_footer_left="Swipe →")},
            {"de": dict(slide_num="5", slide_title="Downloads, die überleben.", slide_desc="App geschlossen, Handy neu gestartet? Downloads setzen von selbst fort. Ehrlich: DRM-Dienste wie Netflix gehen nicht.", slide_shot="", slide_footer_left="Wischen →"),
             "en": dict(slide_num="5", slide_title="Downloads that survive.", slide_desc="Closed the app, restarted the phone? Downloads resume on their own. Honestly: DRM services like Netflix don't work.", slide_shot="", slide_footer_left="Swipe →")},
            {"de": dict(slide_num="", slide_title=f"Neugierig? {_g('Kostenlos testen')}.", slide_desc="Free-Version ohne Konto, 3 Downloads pro Tag. Mein Link steht in der Bio. · Werbung", slide_shot="", slide_footer_left="Link in Bio"),
             "en": dict(slide_num="", slide_title=f"Curious? {_g('Try it free')}.", slide_desc="Free version, no account, 3 downloads a day. My link is in the bio. · Ad", slide_shot="", slide_footer_left="Link in bio")},
        ]),
    "carousel-free-vs-pro": dict(
        theme="clean-utility",
        slides=[
            {"de": dict(slide_num="", slide_title=f"Free oder Pro — {_g('ehrlich erklärt')}.", slide_desc="Was die kostenlose Version wirklich kann und wofür sich die 12-€-Lizenz lohnt.", slide_shot="", slide_footer_left="Wischen →"),
             "en": dict(slide_num="", slide_title=f"Free or Pro — {_g('the honest version')}.", slide_desc="What the free tier really does and when the €12 license is worth it.", slide_shot="", slide_footer_left="Swipe →")},
            {"de": dict(slide_num="0 €", slide_title="Free: komplett nutzbar.", slide_desc="3 Downloads pro Tag in voller HD/4K-Qualität — für immer, ohne Konto, ohne Werbung.", slide_shot="screenshot_main.png", slide_footer_left="Wischen →"),
             "en": dict(slide_num="€0", slide_title="Free: fully usable.", slide_desc="3 downloads a day in full HD/4K quality — forever, no account, no ads.", slide_shot="screenshot_main.png", slide_footer_left="Swipe →")},
            {"de": dict(slide_num="12 €", slide_title="Pro: einmal zahlen.", slide_desc="Unbegrenzte Downloads, Playlist-Downloads und alle zukünftigen Updates. Kein Abo.", slide_shot="", slide_footer_left="Wischen →"),
             "en": dict(slide_num="€12", slide_title="Pro: pay once.", slide_desc="Unlimited downloads, playlist downloads and all future updates. No subscription.", slide_shot="", slide_footer_left="Swipe →")},
            {"de": dict(slide_num="?", slide_title="Für wen lohnt sich Pro?", slide_desc="Wenn du regelmäßig mehr als 3 Dateien am Tag sicherst oder ganze Playlists brauchst. Sonst: bleib bei Free.", slide_shot="", slide_footer_left="Wischen →"),
             "en": dict(slide_num="?", slide_title="Who is Pro for?", slide_desc="If you regularly save more than 3 files a day or need whole playlists. Otherwise: stick with Free.", slide_shot="", slide_footer_left="Swipe →")},
            {"de": dict(slide_num="", slide_title=f"Mein Fazit + {_g('Link in Bio')}.", slide_desc="Erst Free testen, dann entscheiden. Über meinen Link unterstützt du den Kanal — gleicher Preis. · Werbung", slide_shot="", slide_footer_left="Link in Bio"),
             "en": dict(slide_num="", slide_title=f"My verdict + {_g('link in bio')}.", slide_desc="Test Free first, then decide. Using my link supports the channel — same price. · Ad", slide_shot="", slide_footer_left="Link in bio")},
        ]),
}

# ---------------------------------------------------------------------------
# Kit A — Deck (8 Slides, 1920×1080 + Portrait-Ableitung 1080×1350)
# ---------------------------------------------------------------------------
_PHONE = '<div class="phone"><img src="__STORE_ASSETS__/{}" alt=""></div>'
_TIER_TABLE = """<table>
<tr><th>{h1}</th><th>{h2}</th></tr>
<tr><td>1 – 10</td><td><b>2,00 €</b></td></tr>
<tr><td>11 – 50</td><td><b>2,50 €</b></td></tr>
<tr><td>51 – 100</td><td><b>3,00 €</b></td></tr>
<tr><td>101 – 500</td><td><b>3,50 €</b></td></tr>
<tr><td>{ab} 501</td><td><b>4,00 €</b></td></tr>
</table>"""

DECK = [
    {"de": dict(slide_kicker="DownloadThat in einem Satz",
                slide_title=f"Medien von fast jeder Seite — {_g('direkt aufs Handy')}.",
                slide_content="Eine Android-App, die Videos, Audio und Bilder direkt auf dem Gerät speichert — <b>ohne Cloud, ohne Werbung, ohne Konto</b>. Free-Version für immer kostenlos, Pro-Lizenz einmalig 12&nbsp;€.",
                slide_side=_PHONE.format("screenshot_main.png")),
     "en": dict(slide_kicker="DownloadThat in one sentence",
                slide_title=f"Media from almost any site — {_g('straight to the phone')}.",
                slide_content="An Android app that saves videos, audio and images right on the device — <b>no cloud, no ads, no account</b>. Free tier free forever, Pro license €12 one-time.",
                slide_side=_PHONE.format("screenshot_main.png"))},
    {"de": dict(slide_kicker="Das Problem",
                slide_title=f"Speichern auf Android ist {_g('unnötig kompliziert')}.",
                slide_content="<ul class=\"checks\"><li>Links kopieren, dubiose Download-Seiten, Werbe-Popups</li><li>Cloud-Umwege für eine einzige Datei</li><li>Apps, die mitten im Download abbrechen</li><li>Kryptische Fehlermeldungen</li></ul>",
                slide_side='<div class="bigicon">?</div>'),
     "en": dict(slide_kicker="The problem",
                slide_title=f"Saving things on Android is {_g('needlessly painful')}.",
                slide_content="<ul class=\"checks\"><li>Copying links into sketchy download sites full of ads</li><li>Cloud detours for a single file</li><li>Apps that die mid-download</li><li>Cryptic error messages</li></ul>",
                slide_side='<div class="bigicon">?</div>')},
    {"de": dict(slide_kicker="Die Lösung",
                slide_title=f"Teilen → DownloadThat → {_g('gespeichert')}.",
                slide_content="<ul class=\"checks\"><li><b>1.</b> Teilen antippen — in YouTube, Insta &amp; Co.</li><li><b>2.</b> DownloadThat im Teilen-Menü wählen</li><li><b>3.</b> Fertig — Video, MP3 oder Bild, lokal gespeichert</li></ul>Downloads laufen im Hintergrund weiter und setzen nach Abbrüchen selbst fort.",
                slide_side=_PHONE.format("screenshot_queue.png")),
     "en": dict(slide_kicker="The solution",
                slide_title=f"Share → DownloadThat → {_g('saved')}.",
                slide_content="<ul class=\"checks\"><li><b>1.</b> Tap share — in YouTube, Insta &amp; co.</li><li><b>2.</b> Pick DownloadThat in the share sheet</li><li><b>3.</b> Done — video, MP3 or image, saved locally</li></ul>Downloads keep running in the background and resume on their own after interruptions.",
                slide_side=_PHONE.format("screenshot_queue.png"))},
    {"de": dict(slide_kicker="Produkt",
                slide_title=f"Ehrlicher Umfang, {_g('klare Grenzen')}.",
                slide_content="<ul class=\"checks\"><li>Video, Audio (MP3) &amp; Bilder, bis 4K</li><li>Ganze Playlists auf einmal</li><li>100&nbsp;% lokal — kein Cloud-Upload, kein Tracking</li><li>Deutsch &amp; Englisch, hell &amp; dunkel</li></ul><b>Bewusst nicht:</b> keine DRM-Streaming-Dienste (Netflix, Spotify), kein iOS.",
                slide_side=_PHONE.format("screenshot_settings.png")),
     "en": dict(slide_kicker="Product",
                slide_title=f"Honest scope, {_g('clear limits')}.",
                slide_content="<ul class=\"checks\"><li>Video, audio (MP3) &amp; images, up to 4K</li><li>Whole playlists at once</li><li>100% on-device — no cloud upload, no tracking</li><li>German &amp; English, light &amp; dark</li></ul><b>Deliberately not:</b> no DRM streaming services (Netflix, Spotify), no iOS.",
                slide_side=_PHONE.format("screenshot_settings.png"))},
    {"de": dict(slide_kicker="Für deinen Kanal",
                slide_title=f"Content, der sich {_g('von selbst erzählt')}.",
                slide_content="<ul class=\"checks\"><li>15-Sekunden-Demo: Teilen-Trick als Short/Reel</li><li>Ehrliches Review mit Free-vs-Pro-Fazit</li><li>Tutorial: „Medien direkt aufs Handy“</li><li>„3 Dinge, die mir gefallen“-Story-Serie</li></ul>Skripte, Hooks und fertige Vorlagen liefern wir mit.",
                slide_side='<div class="bigicon">▶</div>'),
     "en": dict(slide_kicker="For your channel",
                slide_title=f"Content that {_g('explains itself')}.",
                slide_content="<ul class=\"checks\"><li>15-second demo: the share trick as a Short/Reel</li><li>Honest review with a Free-vs-Pro verdict</li><li>Tutorial: “media straight to your phone”</li><li>“3 things I like” story series</li></ul>We ship scripts, hooks and ready-made templates.",
                slide_side='<div class="bigicon">▶</div>')},
    {"de": dict(slide_kicker="Affiliate-Modell",
                slide_title=f"Transparent gestaffelt, {_g('fair abgerechnet')}.",
                slide_content=_TIER_TABLE.format(h1="Bestätigte Verkäufe", h2="Provision je Verkauf", ab="ab")
                + '<div style="font-size:21px;margin-top:18px;line-height:1.4;">180 Tage Attribution · Code hat Vorrang · Auszahlung monatlich ab 50&nbsp;€ · 30 Tage Prüfzeit · keine Einkommensgarantie</div>',
                slide_side='<div class="bigicon">€</div>'),
     "en": dict(slide_kicker="Affiliate model",
                slide_title=f"Transparent tiers, {_g('fair accounting')}.",
                slide_content=_TIER_TABLE.format(h1="Confirmed sales", h2="Commission per sale", ab="from")
                + '<div style="font-size:21px;margin-top:18px;line-height:1.4;">180-day attribution · code takes priority · monthly payout from €50 · 30-day review · no income guarantee</div>',
                slide_side='<div class="bigicon">€</div>')},
    {"de": dict(slide_kicker="Werbematerial",
                slide_title=f"Du bekommst ein {_g('fertiges Creator-Kit')}.",
                slide_content="<ul class=\"checks\"><li>Story-, Reel-, Feed- &amp; Carousel-Vorlagen (DE/EN)</li><li>YouTube-Thumbnails, Endcards &amp; Beschreibungstexte</li><li>Fertige Videovorlagen (MP4) mit Untertiteln</li><li>Personalisierte Code-, Link- &amp; QR-Karten</li><li>Skripte, Hooks &amp; Caption-Bibliothek</li></ul>",
                slide_side='<div class="bigicon">✓</div>'),
     "en": dict(slide_kicker="Creatives",
                slide_title=f"You get a {_g('ready-made creator kit')}.",
                slide_content="<ul class=\"checks\"><li>Story, reel, feed &amp; carousel templates (DE/EN)</li><li>YouTube thumbnails, endcards &amp; description copy</li><li>Finished video templates (MP4) with subtitles</li><li>Personalized code, link &amp; QR cards</li><li>Scripts, hooks &amp; caption library</li></ul>",
                slide_side='<div class="bigicon">✓</div>')},
    {"de": dict(slide_kicker="Nächster Schritt",
                slide_title=f"{_g('Partner werden')} — in zwei Minuten.",
                slide_content="Registrierung ist geöffnet, Login per Magic-Link ohne Passwort. Die Auszahlungsfunktion wird separat freigeschaltet — wer jetzt startet, ist vom ersten Tag an dabei.<br><br><b>downloadthat.pages.dev/partner.html</b>",
                slide_side='<div class="qr-frame">__QR__</div>'),
     "en": dict(slide_kicker="Next step",
                slide_title=f"{_g('Become a partner')} — in two minutes.",
                slide_content="Registration is open, login via magic link, no password. Payouts are enabled separately — join now and you're in from day one.<br><br><b>downloadthat.pages.dev/partner.html</b>",
                slide_side='<div class="qr-frame">__QR__</div>')},
]

# ---------------------------------------------------------------------------
# Blog / Newsletter (clean-utility)
# ---------------------------------------------------------------------------
BLOG = [
    dict(template="blog/blog-banner.html", slug="blog-01-header", w=1200, h=628, theme="clean-utility",
         extra={"de": dict(banner_tag="Werbung", banner_title=f"Medien von fast jeder Seite — {_g('direkt aufs Handy')}.",
                           banner_sub="DownloadThat für Android: Video, Audio & Bilder, 100 % lokal gespeichert.",
                           banner_cta="", banner_shot="screenshot_main.png", banner_qr=""),
                "en": dict(banner_tag="Ad", banner_title=f"Media from almost any site — {_g('straight to your phone')}.",
                           banner_sub="DownloadThat for Android: video, audio & images, saved 100% locally.",
                           banner_cta="", banner_shot="screenshot_main.png", banner_qr="")}),
    dict(template="feed/feed-01-product-intro.html", slug="blog-02-product-card", w=1000, h=1250,
         theme="clean-utility", extra={"de": {}, "en": {}}),
    dict(template="blog/blog-banner.html", slug="blog-03-cta-banner", w=1200, h=400, theme="clean-utility",
         extra={"de": dict(banner_tag="Werbung", banner_title=f"{_g('Kostenlos testen')} — ohne Konto.",
                           banner_sub="3 Downloads pro Tag für immer kostenlos. Pro: 12 € einmalig, kein Abo.",
                           banner_cta="DownloadThat herunterladen", banner_shot="", banner_qr=""),
                "en": dict(banner_tag="Ad", banner_title=f"{_g('Try it free')} — no account.",
                           banner_sub="3 downloads a day, free forever. Pro: €12 one-time, no subscription.",
                           banner_cta="Get DownloadThat", banner_shot="", banner_qr="")}),
    dict(template="blog/blog-banner.html", slug="blog-04-qr-banner", w=1200, h=628, theme="clean-utility",
         extra={"de": dict(banner_tag="Werbung", banner_title=f"Scannen und {_g('ausprobieren')}.",
                           banner_sub="QR-Code öffnet die Download-Seite — Installation direkt vom Browser, kein Play Store nötig.",
                           banner_cta="", banner_shot="", banner_qr="yes"),
                "en": dict(banner_tag="Ad", banner_title=f"Scan and {_g('try it')}.",
                           banner_sub="The QR code opens the download page — install straight from the browser, no Play Store needed.",
                           banner_cta="", banner_shot="", banner_qr="yes")}),
    dict(template="blog/blog-compare.html", slug="blog-05-compare", w=1200, h=900,
         theme="clean-utility", extra={"de": {}, "en": {}}),
    dict(template="blog/blog-steps.html", slug="blog-06-steps", w=1200, h=1200,
         theme="clean-utility", extra={"de": {}, "en": {}}),
]
