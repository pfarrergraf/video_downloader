from __future__ import annotations

from dataclasses import dataclass
import json
import subprocess
import sys
from typing import Iterable

from .queue_store import QueueStore


@dataclass(slots=True)
class RemoteItem:
    item_id: str
    url: str
    title: str | None = None


@dataclass(slots=True)
class SubscriptionSyncSummary:
    subscriptions_checked: int = 0
    jobs_created: int = 0
    errors: int = 0


def fetch_remote_items(source_url: str) -> list[RemoteItem]:
    cmd = [
        sys.executable,
        "-m",
        "yt_dlp",
        "--flat-playlist",
        "--dump-single-json",
        "--no-warnings",
        source_url,
    ]
    run = subprocess.run(cmd, capture_output=True, text=True)
    if run.returncode != 0:
        message = _tail(run.stderr, 12) or _tail(run.stdout, 12) or "yt-dlp metadata request failed"
        raise RuntimeError(message)

    try:
        payload = json.loads(run.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid metadata payload for subscription source: {source_url}") from exc

    entries = payload.get("entries") or []
    items: list[RemoteItem] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        item_id = str(entry.get("id") or entry.get("url") or "").strip()
        raw_url = entry.get("webpage_url") or entry.get("url")
        if isinstance(raw_url, str):
            item_url = _normalize_item_url(raw_url, item_id, source_url)
        else:
            item_url = _normalize_item_url("", item_id, source_url)

        if not item_url:
            continue
        stable_id = item_id or item_url
        title = str(entry.get("title")) if entry.get("title") is not None else None
        items.append(RemoteItem(item_id=stable_id, url=item_url, title=title))

    return items


def sync_due_subscriptions(store: QueueStore) -> SubscriptionSyncSummary:
    summary = SubscriptionSyncSummary()
    default_profile = store.ensure_default_profile()

    for subscription in store.due_subscriptions():
        summary.subscriptions_checked += 1
        try:
            items = fetch_remote_items(subscription.source_url)
        except Exception as exc:
            summary.errors += 1
            store.append_event(None, "error", f"Subscription poll failed ({subscription.source_url}): {exc}")
            store.mark_subscription_checked(subscription.id)
            continue

        for item in items:
            if store.has_seen_item(subscription.id, item.item_id):
                continue

            job_id = store.add_job(
                source=item.url,
                profile_id=subscription.profile_id or default_profile.id,
                mode="subscription",
                priority=90,
                max_attempts=3,
                allow_playlist=False,
            )
            store.mark_seen_item(subscription.id, item.item_id)
            summary.jobs_created += 1
            title_info = f" ({item.title})" if item.title else ""
            store.append_event(job_id, "info", f"Created from subscription: {subscription.source_url}{title_info}")

        store.mark_subscription_checked(subscription.id)

    return summary


def _normalize_item_url(raw_url: str, item_id: str, source_url: str) -> str:
    value = raw_url.strip()
    if value.startswith("http://") or value.startswith("https://"):
        return value
    if not item_id:
        return ""
    if "youtube.com" in source_url or "youtu.be" in source_url:
        return f"https://www.youtube.com/watch?v={item_id}"
    return value


def _tail(text: str, count: int) -> str:
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        return ""
    return "\n".join(lines[-count:])
