"""Generate the public, URL-free DownloadThat compatibility test catalog."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "compatibility" / "catalog.json"


GROUPS: dict[str, list[str]] = {
    "baseline": [
        "youtube.com", "vimeo.com", "twitter.com", "facebook.com", "bilibili.com",
        "tiktok.com", "soundcloud.com", "twitch.tv", "vk.com", "tv.nrk.no",
        "rutube.ru", "nicovideo.jp", "cbc.ca", "www3.nhk.or.jp", "music.163.com",
        "slideslive.com", "redbull.com", "pbs.org", "imgur.com", "bbc.co.uk",
        "instagram.com", "rtve.es", "radio.nrk.no", "loom.com", "gamejolt.com",
        "dailymotion.com", "bbc.com", "v.qq.com", "weverse.io", "rumble.com",
        "ok.ru", "france.tv", "bandlab.com", "yandex.ru", "sbs.com.au",
        "reddit.com", "mxplayer.in", "mewatch.sg", "cbsnews.com", "archive.org",
        "rctiplus.com", "nhk.or.jp", "bilibili.tv", "svtplay.se", "ruv.is",
        "raiplay.it", "npo.nl", "my.mail.ru", "mlb.com", "lbry.tv",
        "abc.net.au", "viu.com", "vidio.com", "tvw.org", "tvpot.daum.net",
        "tunein.com", "tmz.com", "svt.se", "startv.com.tr", "smotrim.ru",
        "polskieradio.pl", "newgrounds.com", "globalplayer.com", "dr.dk", "tver.jp",
        "thisoldhouse.com", "teamcoco.com", "sonyliv.com", "rts.ch", "odysee.com",
        "nytimes.com", "nrk.no", "web.archive.org", "likee.video", "la7.it",
        "imdb.com", "ign.com", "heise.de", "gettr.com", "espn.com",
        "cda.pl", "linkedin.com", "abema.tv", "abcnews.go.com", "theguardian.com",
        "washingtonpost.com", "nbcnews.com", "spiegel.de", "msn.com", "aol.com",
        "vice.com", "kick.com", "bitchute.com", "c-span.org", "nba.com",
        "nzherald.co.nz", "c.brightcove.com", "ctvnews.ca", "ina.fr", "vod.tvp.pl",
    ],
    "drm_subscription": [
        "netflix.com", "primevideo.com", "disneyplus.com", "spotify.com",
        "music.apple.com", "deezer.com", "tidal.com", "qobuz.com",
        "discoveryplus.com", "tubitv.com", "pluto.tv", "hotstar.com",
        "patreon.com", "nebula.tv", "medici.tv", "hoichoi.tv",
        "shahid.mbc.net", "gem.cbc.ca", "nbc.com", "wetv.vip",
        "ondemandkorea.com", "mediasetinfinity.mediaset.it", "subscription.packtpub.com", "magellantv.com",
        "americastestkitchen.com", "watch.nba.com", "nfhsnetwork.com", "jiosaavn.com",
        "music.youtube.com", "watch.thechosen.tv",
    ],
    "adult": [
        "pornhub.com", "xhamster.com", "xvideos.com", "xnxx.com", "youporn.com",
        "redgifs.com", "spankbang.com", "eporner.com", "beeg.com", "tnaflix.com",
        "empflix.com", "scrolller.com", "thisvid.com", "playvids.com", "nuvid.com",
        "slutload.com", "zenporn.com", "pornflip.com", "iwara.tv", "xvideos.es",
        "picarto.tv", "drtuber.com", "pr0gramm.com", "video.fc2.com",
        "mellow-fan.com",
    ],
    "alternative": [
        "mixch.tv", "twitcasting.tv", "rokfin.com", "dumpert.nl", "banbye.com",
        "subsplash.com", "prankcast.com", "gdcvault.com", "npr.org", "17.live",
        "weibo.com", "vkvideo.ru", "video.vice.com", "onf.ca", "nfb.ca",
        "rtl.lu", "bfmtv.com", "rtp.pt", "hungama.com", "lrt.lt",
        "areena.yle.fi", "rtbf.be", "mojevideo.sk", "rudo.video", "rtvcplay.co",
    ],
    "dach": [
        "zdf.de", "ardmediathek.de", "ndr.de", "tagesschau.de", "tlc.de",
        "n-joy.de", "3sat.de", "www1.wdr.de", "videocampus.sachsen.de",
        "canalalpha.ch", "on.orf.at", "moviepilot.de", "hearthis.at",
        "playsuisse.ch", "sr-mediathek.de", "bpb.de", "live.rbg.tum.de", "southpark.de",
        "mx3.ch", "germanupa.de",
    ],
}

EXPECTED_COUNTS = {
    "baseline": 100,
    "drm_subscription": 30,
    "adult": 25,
    "alternative": 25,
    "dach": 20,
}


def build_catalog() -> dict[str, object]:
    sites: list[dict[str, object]] = []
    seen: set[str] = set()
    for category, domains in GROUPS.items():
        expected = EXPECTED_COUNTS[category]
        if len(domains) != expected:
            raise ValueError(f"{category}: expected {expected} domains, got {len(domains)}")
        for rank, domain in enumerate(domains, start=1):
            if domain in seen:
                raise ValueError(f"duplicate domain: {domain}")
            seen.add(domain)
            sites.append(
                {
                    "domain": domain,
                    "category": category,
                    "category_rank": rank,
                    "required_urls": 3,
                    "private_evidence": category == "adult",
                    "expected_access": (
                        "protected_or_preview" if category == "drm_subscription" else "public"
                    ),
                }
            )
    if len(sites) != 200:
        raise ValueError(f"expected 200 domains, got {len(sites)}")
    return {
        "schema_version": 1,
        "selection_snapshot": "2026-08-21",
        "selection_basis": [
            "DACH and global media relevance",
            "current category traffic rankings",
            "yt-dlp extractor coverage",
            "explicit DRM/subscription negative controls",
        ],
        "counts": EXPECTED_COUNTS,
        "sites": sites,
    }


def main() -> int:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(build_catalog(), indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT}: 200 domains")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
