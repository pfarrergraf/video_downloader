from __future__ import annotations

from dataclasses import replace

from .models import DownloadProfile
from .queue_store import QueueStore


def resolve_profile(store: QueueStore, name: str | None) -> DownloadProfile:
    if name:
        profile = store.get_profile_by_name(name)
        if profile is None:
            raise ValueError(f"Profile not found: {name}")
        return profile

    profile = store.get_profile_by_name("default")
    if profile is None:
        profile = store.ensure_default_profile()
    return profile


def interactive_profile_override(base: DownloadProfile) -> DownloadProfile:
    try:
        format_selector = input(f"Format selector [{base.format_selector}]: ").strip() or base.format_selector
        template = input(
            f"Output template [{base.output_template or '%(title)s [%(id)s].%(ext)s'}]: "
        ).strip()
        audio_only = _bool_prompt("Audio only", base.audio_only)
        subtitle_langs = input(f"Subtitle langs [{base.subtitle_langs or 'none'}]: ").strip()
        embed_subs = _bool_prompt("Embed subtitles", base.embed_subs)
        use_aria2 = _bool_prompt("Use aria2 when available", base.use_aria2)
    except EOFError:
        return base

    return replace(
        base,
        format_selector=format_selector,
        output_template=template or base.output_template,
        audio_only=audio_only,
        subtitle_langs=subtitle_langs or base.subtitle_langs,
        embed_subs=embed_subs,
        use_aria2=use_aria2,
    )


def _bool_prompt(label: str, default: bool) -> bool:
    suffix = "Y/n" if default else "y/N"
    raw = input(f"{label}? ({suffix}): ").strip().lower()
    if not raw:
        return default
    return raw in {"y", "yes", "1", "true"}
