from __future__ import annotations

import argparse
from dataclasses import replace
import os
import shutil
import sys
import time
from pathlib import Path

from rich.console import Console
from rich.table import Table

from .app_config import AppConfig, load_or_create_config, resolve_paths
from .core import DownloadManager
from .history import list_history as history_list
from .history import retry_history_job
from .logging_setup import configure_logging
from .models import DownloadProfile, DownloadRequest, DownloadWorkflowError
from .profiles import interactive_profile_override, resolve_profile
from .queue_runner import QueueRunner
from .queue_store import QueueStore
from .scheduler_windows import install_scheduler, uninstall_scheduler
from .subscriptions import sync_due_subscriptions
from .utils import ensure_output_dir, safe_filename

NEW_COMMANDS = {"download", "queue", "profile", "sub", "history", "tui", "ui", "scrape", "web", "purge-data"}


def main() -> None:
    argv = sys.argv[1:]

    # When launched without arguments (e.g. double-clicking the windowed EXE),
    # default to the Easy Desktop UI instead of printing help to a non-existent console.
    if not argv and getattr(sys, "frozen", False):
        argv = ["ui"]

    if _should_use_legacy_mode(argv):
        _run_legacy_mode(argv)
        return

    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return

    paths = resolve_paths()
    config = load_or_create_config(paths)
    configure_logging(paths)

    store = QueueStore(paths.state_db)
    store.init()

    console = Console()
    _print_legal_warning(console)

    try:
        _dispatch_command(console, store, config, args)
    except ValueError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        sys.exit(1)
    except DownloadWorkflowError as exc:
        console.print(f"[bold red]Download failed:[/bold red] {exc}")
        _print_attempt_table(console, exc)
        sys.exit(1)
    except RuntimeError as exc:
        console.print(f"[bold red]Command failed:[/bold red] {exc}")
        sys.exit(1)


def _dispatch_command(
    console: Console,
    store: QueueStore,
    config: AppConfig,
    args: argparse.Namespace,
) -> None:
    if args.command == "download":
        _command_download(console, store, config, args)
        return
    if args.command == "queue":
        _command_queue(console, store, config, args)
        return
    if args.command == "profile":
        _command_profile(console, store, args)
        return
    if args.command == "sub":
        _command_subscriptions(console, store, args)
        return
    if args.command == "history":
        _command_history(console, store, args)
        return
    if args.command == "tui":
        _command_tui(store)
        return
    if args.command == "ui":
        _command_easy_ui(config, args)
        return
    if args.command == "scrape":
        _command_scrape(console, config, args)
        return
    if args.command == "web":
        _command_web(console, store, config, args)
        return
    if args.command == "purge-data":
        _command_purge_data(console, store, config, args)
        return
    raise ValueError(f"Unknown command: {args.command}")


def _command_purge_data(
    console: Console,
    store: QueueStore,
    config: AppConfig,
    args: argparse.Namespace,
) -> None:
    """DSAR / "delete my data": wipe locally-stored download history and the
    URLs it contains. Config (profiles/settings) is kept unless the user also
    passes --logs to clear the log file."""
    if not args.yes:
        console.print(
            "[bold yellow]This deletes all local download history, queued jobs, "
            "subscriptions, and their event log from the state database.[/bold yellow]"
        )
        confirm = input("Type 'purge' to confirm: ").strip().lower()
        if confirm != "purge":
            console.print("Aborted.")
            return
    counts = store.purge_user_data()
    total = sum(counts.values())
    console.print(f"[bold green]Purged {total} record(s):[/bold green] {counts}")
    if args.logs:
        from .app_config import resolve_paths

        log_file = resolve_paths().log_file
        try:
            if log_file.exists():
                log_file.write_text("", encoding="utf-8")
                console.print(f"Cleared log file: {log_file}")
        except OSError as exc:
            console.print(f"[yellow]Could not clear log file: {exc}[/yellow]")


def _command_download(
    console: Console,
    store: QueueStore,
    config: AppConfig,
    args: argparse.Namespace,
) -> None:
    headers = _parse_headers(args.header)
    _validate_download_args(args)

    output_dir = ensure_output_dir(_resolve_output_dir(args.output, config))
    manager = DownloadManager(logger=lambda m: console.print(f"[cyan]{m}[/cyan]"))

    if args.topic:
        profile = _resolve_runtime_profile(store, args)
        _run_topic_batch(console, manager, args, headers, output_dir, profile)
        return

    profile = _resolve_runtime_profile(store, args)
    effective_method = "yt-dlp" if args.playlist and args.method == "auto" else args.method
    request = _build_request(
        args=args,
        headers=headers,
        output_dir=output_dir,
        source=args.source.strip(),
        method=effective_method,
        filename=args.name,
        allow_playlist=args.playlist,
        max_items=args.max_items,
        profile=profile,
    )
    _run_single(console, manager, request)


def _command_queue(
    console: Console,
    store: QueueStore,
    config: AppConfig,
    args: argparse.Namespace,
) -> None:
    subcmd = args.queue_command

    if subcmd == "add":
        headers = _parse_headers(args.header)
        profile = _resolve_runtime_profile(store, args)
        profile = _persist_overridden_profile_if_needed(store, profile, args)

        output_dir = _resolve_output_dir(args.output, config)
        job_id = store.add_job(
            source=args.source,
            profile_id=profile.id,
            mode="queue",
            priority=max(1, int(args.priority)),
            max_attempts=max(1, int(args.max_attempts)),
            output_dir=str(output_dir),
            method=args.method,
            user_agent=args.user_agent,
            referer=args.referer,
            headers=headers,
            cookies_from_browser=args.cookies_from_browser,
            allow_playlist=bool(args.playlist),
            max_items=args.max_items,
            timeout_seconds=args.timeout,
            ffmpeg_binary=args.ffmpeg_binary,
        )
        console.print(f"[bold green]Queued[/bold green] job #{job_id} using profile [bold]{profile.name}[/bold]")
        return

    if subcmd == "run":
        workers = args.workers if args.workers is not None else config.default_workers
        workers = max(1, min(int(workers), min(config.max_workers, 8)))
        if workers > 6:
            console.print("[yellow]Warning:[/yellow] High concurrency can stress sites. Use responsibly.")

        runner = QueueRunner(
            store=store,
            default_output_dir=_resolve_output_dir(None, config),
            logger=lambda message: store.append_event(None, "info", message),
        )
        summary = runner.run(workers=workers)
        console.print(f"Processed: {summary.processed}")
        console.print(f"Completed: [green]{summary.completed}[/green]")
        console.print(f"Failed: [red]{summary.failed}[/red]")
        return

    if subcmd == "list":
        rows = store.list_jobs(status=args.status, limit=args.limit)
        table = Table(title="Queue")
        table.add_column("ID")
        table.add_column("Status")
        table.add_column("Attempt")
        table.add_column("Priority")
        table.add_column("Source")
        table.add_column("Updated")
        for row in rows:
            table.add_row(
                str(row.id),
                row.status,
                f"{row.attempt}/{row.max_attempts}",
                str(row.priority),
                row.source,
                row.updated_at,
            )
        console.print(table)
        return

    if subcmd == "cancel":
        if store.mark_job_cancelled(args.job_id):
            console.print(f"[bold yellow]Cancelled[/bold yellow] job #{args.job_id}")
        else:
            console.print(f"No cancellable job found for id {args.job_id}")
        return

    if subcmd == "pause":
        if store.pause_job(args.job_id):
            console.print(f"[bold yellow]Paused[/bold yellow] job #{args.job_id}")
        else:
            console.print(f"No pending job found for id {args.job_id}")
        return

    if subcmd == "resume":
        if store.resume_job(args.job_id):
            console.print(f"[bold green]Resumed[/bold green] job #{args.job_id}")
        else:
            console.print(f"No paused job found for id {args.job_id}")
        return

    if subcmd == "reprioritize":
        if store.reprioritize_job(args.job_id, args.priority):
            console.print(f"[bold green]Updated[/bold green] job #{args.job_id} priority to {args.priority}")
        else:
            console.print(f"No pending/paused job found for id {args.job_id}")
        return

    raise ValueError(f"Unknown queue subcommand: {subcmd}")


def _command_profile(console: Console, store: QueueStore, args: argparse.Namespace) -> None:
    subcmd = args.profile_command
    if subcmd == "create":
        if store.get_profile_by_name(args.name):
            raise ValueError(f"Profile already exists: {args.name}")

        profile = DownloadProfile(
            id=None,
            name=args.name,
            format_selector=args.format_selector,
            output_template=args.output_template,
            audio_only=bool(args.audio_only),
            subtitle_langs=args.subtitle_langs,
            audio_langs=args.audio_langs,
            embed_subs=bool(args.embed_subs),
            workers_hint=max(1, min(8, int(args.workers_hint))),
            use_aria2=bool(args.use_aria2),
        )
        created = store.create_profile(profile)
        console.print(f"[bold green]Created[/bold green] profile [bold]{created.name}[/bold]")
        return

    if subcmd == "list":
        rows = store.list_profiles()
        table = Table(title="Profiles")
        table.add_column("Name")
        table.add_column("Format")
        table.add_column("Audio")
        table.add_column("Subs")
        table.add_column("Aria2")
        for row in rows:
            table.add_row(
                row.name,
                row.format_selector,
                "yes" if row.audio_only else "no",
                row.subtitle_langs or "-",
                "yes" if row.use_aria2 else "no",
            )
        console.print(table)
        return

    if subcmd == "show":
        row = store.get_profile_by_name(args.name)
        if row is None:
            raise ValueError(f"Profile not found: {args.name}")
        table = Table(title=f"Profile: {row.name}")
        table.add_column("Field")
        table.add_column("Value")
        table.add_row("format_selector", row.format_selector)
        table.add_row("output_template", row.output_template or "")
        table.add_row("audio_only", str(row.audio_only))
        table.add_row("subtitle_langs", row.subtitle_langs or "")
        table.add_row("audio_langs", row.audio_langs or "")
        table.add_row("embed_subs", str(row.embed_subs))
        table.add_row("workers_hint", str(row.workers_hint))
        table.add_row("use_aria2", str(row.use_aria2))
        console.print(table)
        return

    if subcmd == "delete":
        deleted = store.delete_profile(args.name)
        if not deleted:
            raise ValueError("Profile deletion failed (not found or protected profile).")
        console.print(f"[bold green]Deleted[/bold green] profile [bold]{args.name}[/bold]")
        return

    raise ValueError(f"Unknown profile subcommand: {subcmd}")


def _command_subscriptions(console: Console, store: QueueStore, args: argparse.Namespace) -> None:
    subcmd = args.sub_command

    if subcmd == "add":
        profile = resolve_profile(store, args.profile)
        sub_id = store.add_subscription(
            source_url=args.source,
            profile_id=profile.id,
            interval_minutes=max(1, int(args.interval_minutes)),
        )
        console.print(
            f"[bold green]Subscription saved[/bold green] #{sub_id} for {args.source} (profile {profile.name})"
        )
        return

    if subcmd == "list":
        rows = store.list_subscriptions()
        table = Table(title="Subscriptions")
        table.add_column("ID")
        table.add_column("Source")
        table.add_column("Profile")
        table.add_column("Interval (min)")
        table.add_column("Last Checked")
        for row in rows:
            table.add_row(
                str(row.id),
                row.source_url,
                str(row.profile_id or "default"),
                str(row.interval_minutes),
                row.last_checked_at or "never",
            )
        console.print(table)
        return

    if subcmd == "run":
        summary = sync_due_subscriptions(store)
        console.print(f"Checked subscriptions: {summary.subscriptions_checked}")
        console.print(f"Jobs created: [green]{summary.jobs_created}[/green]")
        console.print(f"Errors: [red]{summary.errors}[/red]")
        return

    if subcmd == "install-scheduler":
        task_command = install_scheduler(interval_minutes=args.interval_minutes)
        console.print("[bold green]Scheduler installed[/bold green]")
        console.print(f"Task command: {task_command}")
        return

    if subcmd == "uninstall-scheduler":
        uninstall_scheduler()
        console.print("[bold green]Scheduler removed[/bold green]")
        return

    raise ValueError(f"Unknown sub subcommand: {subcmd}")


def _command_history(console: Console, store: QueueStore, args: argparse.Namespace) -> None:
    if args.history_command == "list":
        rows = history_list(store, status=args.status, limit=args.limit)
        table = Table(title="History")
        table.add_column("ID")
        table.add_column("Status")
        table.add_column("Source")
        table.add_column("Finished")
        table.add_column("Error")
        for row in rows:
            table.add_row(
                str(row.id),
                row.status,
                row.source,
                row.finished_at or "",
                row.error or "",
            )
        console.print(table)
        return

    if args.history_command == "retry":
        new_job_id = retry_history_job(store, args.job_id)
        if new_job_id is None:
            raise ValueError("Retry failed. Job must exist and be failed/cancelled.")
        console.print(f"[bold green]Retried[/bold green] as job #{new_job_id}")
        return

    raise ValueError(f"Unknown history subcommand: {args.history_command}")


def _command_tui(store: QueueStore) -> None:
    from .tui_app import run_tui

    run_tui(store)


def _command_easy_ui(config: AppConfig, args: argparse.Namespace) -> None:
    from .easy_ui import run_easy_ui

    output = args.output if args.output else config.default_output_dir
    run_easy_ui(
        default_output_dir=str(Path(output).expanduser().resolve()),
        initial_method=args.method,
        initial_cookies_from_browser=args.cookies_from_browser,
    )


def _command_web(
    console: Console,
    store: QueueStore,
    config: AppConfig,
    args: argparse.Namespace,
) -> None:
    from .web.server import run_server

    password = args.password or os.environ.get("CLASSYDL_WEB_PASSWORD", "")
    if not password:
        raise ValueError(
            "Refusing to start without a password. Pass --password or set CLASSYDL_WEB_PASSWORD."
        )

    output = args.output if args.output else config.default_output_dir
    output_dir = ensure_output_dir(Path(output).expanduser().resolve())
    workers = args.workers if args.workers else config.default_workers

    if args.host not in ("127.0.0.1", "localhost", "::1"):
        console.print(
            f"[bold yellow]⚠ Binding to {args.host} exposes this server (and its "
            "authenticated /api/scrape URL fetcher) to the network over plain HTTP. "
            "Only do this on a trusted network; prefer 127.0.0.1.[/bold yellow]"
        )

    console.print(f"[bold magenta]Starting Gothic web UI on http://{args.host}:{args.port}[/bold magenta]")
    run_server(
        store=store,
        output_dir=output_dir,
        password=password,
        host=args.host,
        port=args.port,
        workers=workers,
    )


def _command_scrape(
    console: Console,
    config: AppConfig,
    args: argparse.Namespace,
) -> None:
    from .scraper import SiteScraper, filter_items, parse_pick_spec, format_size

    media_types: set[str] | None = None
    if args.type:
        media_types = set(args.type)

    scraper = SiteScraper(
        timeout=args.timeout,
        logger=lambda m: console.print(f"[cyan]{m}[/cyan]"),
    )
    result = scraper.scrape(
        args.url,
        same_domain=args.same_domain,
        media_types=media_types,
        name_filter=args.filter,
        deep=args.deep,
    )

    if result.errors:
        for err in result.errors:
            console.print(f"[yellow]Warning:[/yellow] {err}")

    if not result.items:
        console.print("[bold red]No media found on this page.[/bold red]")
        return

    # Apply post-filter (type/name may also be applied at scrape time, but
    # user can re-filter interactively in the selection step).
    items = result.items

    # Show results table
    console.print(f"\n[bold]Page:[/bold] {result.page_title or result.page_url}")
    console.print(f"[bold]Found:[/bold] {len(items)} media items\n")

    _print_scrape_table(console, items, show_all=not args.brief)

    # Summary by type
    type_counts: dict[str, int] = {}
    for item in items:
        type_counts[item.media_type] = type_counts.get(item.media_type, 0) + 1
    summary_parts = [f"{t}: {c}" for t, c in sorted(type_counts.items())]
    console.print(f"\n[bold]Summary:[/bold] {', '.join(summary_parts)}")

    # Download mode
    if args.download:
        pick_spec = args.download
        indices = parse_pick_spec(pick_spec, len(items))
        if not indices:
            console.print("[bold red]No valid items selected.[/bold red]")
            return
        selected = [items[i] for i in indices]
        console.print(f"\n[bold green]Downloading {len(selected)} item(s)...[/bold green]")
        output_dir = ensure_output_dir(_resolve_output_dir(args.output, config))
        _scrape_download_batch(console, selected, output_dir, args)
        return

    # Interactive selection
    if args.interactive:
        _scrape_interactive(console, items, config, args)


def _print_scrape_table(
    console: Console,
    items: list,
    *,
    show_all: bool = True,
) -> None:
    table = Table(title="Discovered Media")
    table.add_column("#", justify="right", style="dim")
    table.add_column("Type", style="bold")
    table.add_column("Filename")
    table.add_column("Source", style="dim")
    table.add_column("URL", overflow="fold")

    display = items if show_all else items[:50]
    for idx, item in enumerate(display, start=1):
        type_color = {"video": "red", "audio": "blue", "image": "green"}.get(item.media_type, "white")
        table.add_row(
            str(idx),
            f"[{type_color}]{item.media_type}[/{type_color}]",
            item.filename[:60],
            item.source_tag,
            item.url[:120],
        )
    if not show_all and len(items) > 50:
        table.add_row("...", "", f"({len(items) - 50} more)", "", "")
    console.print(table)


def _scrape_interactive(
    console: Console,
    items: list,
    config: AppConfig,
    args: argparse.Namespace,
) -> None:
    from .scraper import filter_items, parse_pick_spec

    console.print("\n[bold]Interactive Selection[/bold]")
    console.print("  Enter numbers: [cyan]1,3,5-8[/cyan]  or [cyan]all[/cyan]")
    console.print("  Filter by type: [cyan]type video[/cyan] / [cyan]type audio[/cyan] / [cyan]type image[/cyan]")
    console.print("  Filter by name: [cyan]name *thumb*[/cyan]")
    console.print("  Type [cyan]quit[/cyan] to exit\n")

    current = items
    while True:
        try:
            raw = console.input("[bold]Select> [/bold]").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not raw or raw.lower() in {"quit", "q", "exit"}:
            break

        # Type filter
        if raw.lower().startswith("type "):
            type_arg = raw[5:].strip().lower()
            if type_arg in {"video", "audio", "image"}:
                current = filter_items(items, media_types={type_arg})
                _print_scrape_table(console, current)
                console.print(f"Showing {len(current)} {type_arg} items")
                continue
            console.print("[yellow]Valid types: video, audio, image[/yellow]")
            continue

        # Name filter
        if raw.lower().startswith("name "):
            pattern = raw[5:].strip()
            current = filter_items(items, name_pattern=pattern)
            _print_scrape_table(console, current)
            console.print(f"Showing {len(current)} items matching '{pattern}'")
            continue

        # Reset
        if raw.lower() in {"reset", "show all", "list"}:
            current = items
            _print_scrape_table(console, current)
            continue

        # Selection to download
        try:
            indices = parse_pick_spec(raw, len(current))
        except (ValueError, IndexError):
            console.print("[yellow]Invalid selection. Use numbers like 1,3,5-8 or 'all'[/yellow]")
            continue

        if not indices:
            console.print("[yellow]No items matched.[/yellow]")
            continue

        selected = [current[i] for i in indices]
        console.print(f"[bold green]Downloading {len(selected)} item(s)...[/bold green]")
        output_dir = ensure_output_dir(_resolve_output_dir(args.output, config))
        _scrape_download_batch(console, selected, output_dir, args)
        break


def _scrape_download_batch(
    console: Console,
    items: list,
    output_dir: Path,
    args: argparse.Namespace,
) -> None:
    """Download scraped media items – media files directly, video pages via yt-dlp."""
    manager = DownloadManager(logger=lambda m: console.print(f"[cyan]{m}[/cyan]"))

    ok = 0
    failed_items: list[str] = []
    for i, item in enumerate(items, start=1):
        console.print(f"[{i}/{len(items)}] {item.media_type}: {item.filename}")
        audio_only = getattr(args, "audio_only", False)
        request = DownloadRequest(
            source_url=item.url,
            output_dir=output_dir,
            filename=safe_filename(item.filename.rsplit(".", 1)[0]) if "." in item.filename else None,
            method="auto",
            referer=item.referer,
            cookies_from_browser=getattr(args, "cookies_from_browser", None),
            timeout_seconds=getattr(args, "timeout", 30),
            audio_only=audio_only,
            format_selector="ba/b" if audio_only else "bv*+ba/b",
        )
        try:
            result = manager.download(request)
            console.print(f"  [green]OK[/green] → {result.file_path}")
            ok += 1
        except Exception as exc:
            console.print(f"  [red]FAIL[/red] {exc}")
            failed_items.append(item.url)

    console.print(f"\n[bold]Done:[/bold] {ok} downloaded, {len(failed_items)} failed")
    if failed_items:
        for url in failed_items[:5]:
            console.print(f"  [red]✗[/red] {url}")
        if len(failed_items) > 5:
            console.print(f"  ... and {len(failed_items) - 5} more")


def _resolve_runtime_profile(store: QueueStore, args: argparse.Namespace) -> DownloadProfile:
    profile = resolve_profile(store, args.profile)
    if getattr(args, "manual", False):
        profile = interactive_profile_override(profile)
    return _apply_profile_overrides(profile, args)


def _persist_overridden_profile_if_needed(
    store: QueueStore,
    profile: DownloadProfile,
    args: argparse.Namespace,
) -> DownloadProfile:
    if not _profile_overrides_requested(args):
        return profile

    # Keep queue jobs reproducible by storing an explicit immutable profile snapshot.
    name = f"adhoc_{time.time_ns()}"
    snapshot = replace(profile, id=None, name=name)
    created = store.create_profile(snapshot)
    return created


def _profile_overrides_requested(args: argparse.Namespace) -> bool:
    return any(
        [
            getattr(args, "manual", False),
            getattr(args, "audio_only", None) is True,
            getattr(args, "embed_subs", None) is True,
            getattr(args, "use_aria2", None) is True,
            getattr(args, "subtitle_langs", None),
            getattr(args, "audio_langs", None),
            getattr(args, "output_template", None),
            getattr(args, "format_selector", None) is not None,
        ]
    )


def _apply_profile_overrides(profile: DownloadProfile, args: argparse.Namespace) -> DownloadProfile:
    format_selector = getattr(args, "format_selector", None)
    output_template = getattr(args, "output_template", None)
    subtitle_langs = getattr(args, "subtitle_langs", None)
    audio_langs = getattr(args, "audio_langs", None)
    audio_only = getattr(args, "audio_only", None)
    embed_subs = getattr(args, "embed_subs", None)
    use_aria2 = getattr(args, "use_aria2", None)

    return replace(
        profile,
        format_selector=format_selector if format_selector is not None else profile.format_selector,
        output_template=output_template if output_template is not None else profile.output_template,
        audio_only=audio_only if audio_only is not None else profile.audio_only,
        subtitle_langs=subtitle_langs if subtitle_langs is not None else profile.subtitle_langs,
        audio_langs=audio_langs if audio_langs is not None else profile.audio_langs,
        embed_subs=embed_subs if embed_subs is not None else profile.embed_subs,
        use_aria2=use_aria2 if use_aria2 is not None else profile.use_aria2,
    )


def _resolve_output_dir(raw_output: str | None, config: AppConfig) -> Path:
    chosen = raw_output if raw_output else config.default_output_dir
    return Path(chosen).expanduser().resolve()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="classydl",
        description="Classy Downloader: queue-driven universal media downloader",
    )
    subparsers = parser.add_subparsers(dest="command")

    download_parser = subparsers.add_parser("download", help="Download now")
    download_parser.add_argument("source", nargs="?", help="URL or ytsearch expression")
    _add_common_download_options(download_parser)
    download_parser.add_argument(
        "--topic",
        action="append",
        default=[],
        help="Search topic for batch mode; repeat this option for multiple topics",
    )
    download_parser.add_argument(
        "--search-count",
        type=int,
        default=5,
        help="Number of results per topic in batch mode (default: 5)",
    )

    queue_parser = subparsers.add_parser("queue", help="Queue operations")
    queue_subparsers = queue_parser.add_subparsers(dest="queue_command", required=True)

    queue_add = queue_subparsers.add_parser("add", help="Add source to queue")
    queue_add.add_argument("source", help="Video URL or search expression")
    _add_common_download_options(queue_add)
    queue_add.add_argument("--priority", type=int, default=100, help="Lower means sooner")
    queue_add.add_argument("--max-attempts", type=int, default=3, help="Retry attempts per job")

    queue_run = queue_subparsers.add_parser("run", help="Process queued jobs")
    queue_run.add_argument("--workers", type=int, help="Parallel worker count (max 8)")

    queue_list = queue_subparsers.add_parser("list", help="List queued jobs")
    queue_list.add_argument(
        "--status",
        choices=["pending", "paused", "in_progress", "completed", "failed", "cancelled"],
        help="Filter by status",
    )
    queue_list.add_argument("--limit", type=int, default=200)

    queue_cancel = queue_subparsers.add_parser("cancel", help="Cancel pending/in-progress job")
    queue_cancel.add_argument("job_id", type=int)

    queue_pause = queue_subparsers.add_parser("pause", help="Pause a pending job")
    queue_pause.add_argument("job_id", type=int)

    queue_resume = queue_subparsers.add_parser("resume", help="Resume a paused job")
    queue_resume.add_argument("job_id", type=int)

    queue_reprioritize = queue_subparsers.add_parser(
        "reprioritize",
        help="Set priority for pending/paused job (lower runs sooner)",
    )
    queue_reprioritize.add_argument("job_id", type=int)
    queue_reprioritize.add_argument("--priority", type=int, required=True)

    profile_parser = subparsers.add_parser("profile", help="Profile management")
    profile_subparsers = profile_parser.add_subparsers(dest="profile_command", required=True)

    profile_create = profile_subparsers.add_parser("create", help="Create profile")
    profile_create.add_argument("name")
    profile_create.add_argument("-f", "--format", dest="format_selector", default="bv*+ba/b")
    profile_create.add_argument("--output-template")
    profile_create.add_argument("--audio-only", action="store_true")
    profile_create.add_argument("--subtitle-langs")
    profile_create.add_argument("--audio-langs")
    profile_create.add_argument("--embed-subs", action="store_true")
    profile_create.add_argument("--workers-hint", type=int, default=3)
    profile_create.add_argument("--use-aria2", action="store_true")

    profile_list = profile_subparsers.add_parser("list", help="List profiles")
    _ = profile_list

    profile_show = profile_subparsers.add_parser("show", help="Show profile")
    profile_show.add_argument("name")

    profile_delete = profile_subparsers.add_parser("delete", help="Delete profile")
    profile_delete.add_argument("name")

    sub_parser = subparsers.add_parser("sub", help="Subscription automation")
    sub_subparsers = sub_parser.add_subparsers(dest="sub_command", required=True)

    sub_add = sub_subparsers.add_parser("add", help="Create/update subscription")
    sub_add.add_argument("source", help="Channel or playlist URL")
    sub_add.add_argument("--interval-minutes", type=int, default=60)
    sub_add.add_argument("--profile", help="Profile name")

    sub_list = sub_subparsers.add_parser("list", help="List subscriptions")
    _ = sub_list

    sub_run = sub_subparsers.add_parser("run", help="Poll due subscriptions")
    _ = sub_run

    sub_install = sub_subparsers.add_parser("install-scheduler", help="Install Windows scheduler")
    sub_install.add_argument("--interval-minutes", type=int, default=30)

    sub_uninstall = sub_subparsers.add_parser("uninstall-scheduler", help="Remove scheduler")
    _ = sub_uninstall

    history_parser = subparsers.add_parser("history", help="Download history")
    history_subparsers = history_parser.add_subparsers(dest="history_command", required=True)

    history_list_parser = history_subparsers.add_parser("list", help="List completed/failed/cancelled jobs")
    history_list_parser.add_argument("--status", choices=["completed", "failed", "cancelled"])
    history_list_parser.add_argument("--limit", type=int, default=200)

    history_retry = history_subparsers.add_parser("retry", help="Retry a failed/cancelled job")
    history_retry.add_argument("job_id", type=int)

    subparsers.add_parser("tui", help="Launch Textual dashboard")

    ui_parser = subparsers.add_parser("ui", help="Launch easy desktop UI")
    ui_parser.add_argument("-o", "--output", help="Default output directory for the UI")
    ui_parser.add_argument(
        "-m",
        "--method",
        choices=["auto", "yt-dlp", "ffmpeg", "direct"],
        default="auto",
        help="Default method in the UI (default: auto)",
    )
    ui_parser.add_argument("--cookies-from-browser", help="Default cookies browser for the UI")

    # ── scrape command ──────────────────────────────────────────────────
    scrape_parser = subparsers.add_parser(
        "scrape",
        help="Scrape a website for videos, audio, and images",
    )
    scrape_parser.add_argument("url", help="Website URL to scrape")
    scrape_parser.add_argument(
        "-t",
        "--type",
        action="append",
        choices=["video", "audio", "image"],
        help="Filter by media type (repeat for multiple: -t video -t audio)",
    )
    scrape_parser.add_argument(
        "--filter",
        help="Wildcard filter for filenames (e.g. '*thumb*', '*.mp4')",
    )
    scrape_parser.add_argument(
        "--download",
        metavar="SPEC",
        help="Download items: 'all', '1,3,5-8', or specific indices",
    )
    scrape_parser.add_argument(
        "-i",
        "--interactive",
        action="store_true",
        help="Interactive mode: view results then pick what to download",
    )
    scrape_parser.add_argument(
        "--same-domain",
        action="store_true",
        help="Only include media from the same domain",
    )
    scrape_parser.add_argument(
        "--deep",
        action="store_true",
        help="Follow links to sub-pages and scrape those too",
    )
    scrape_parser.add_argument(
        "--brief",
        action="store_true",
        help="Show only first 50 results in the table",
    )
    scrape_parser.add_argument("-o", "--output", help="Output directory for downloads")
    scrape_parser.add_argument("--timeout", type=int, default=30, help="HTTP timeout in seconds")
    scrape_parser.add_argument("--cookies-from-browser", help="Browser for cookie extraction")
    scrape_parser.add_argument(
        "--audio-only",
        action="store_true",
        help="Extract audio only as high-quality MP3 (320 kbit/s)",
    )

    # ── web command ─────────────────────────────────────────────────────
    web_parser = subparsers.add_parser(
        "web",
        help="Launch the browser-based Gothic UI (reachable from phone/any device)",
    )
    web_parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Bind address (default: 127.0.0.1, loopback only). Pass 0.0.0.0 "
        "to expose it on the local network - only do this on a trusted network.",
    )
    web_parser.add_argument("--port", type=int, default=8420, help="Bind port (default: 8420)")
    web_parser.add_argument(
        "--password",
        help="Password required to access the site (or set CLASSYDL_WEB_PASSWORD)",
    )
    web_parser.add_argument("--workers", type=int, help="Concurrent download workers (default: config)")
    web_parser.add_argument("-o", "--output", help="Output directory for web downloads")

    # ── purge-data command (DSAR / "delete my data") ────────────────────
    purge_parser = subparsers.add_parser(
        "purge-data",
        help="Delete all locally-stored download history, jobs, and URLs (GDPR/DSAR)",
    )
    purge_parser.add_argument(
        "-y", "--yes", action="store_true", help="Skip the interactive confirmation prompt"
    )
    purge_parser.add_argument(
        "--logs", action="store_true", help="Also clear the application log file"
    )

    return parser


def _add_common_download_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("-o", "--output", help="Output directory")
    parser.add_argument("-n", "--name", help="Output filename without extension")
    parser.add_argument(
        "-m",
        "--method",
        choices=["auto", "yt-dlp", "ffmpeg", "direct"],
        default="auto",
        help="Download method (default: auto)",
    )
    parser.add_argument(
        "-f",
        "--format",
        dest="format_selector",
        help="yt-dlp format selector override",
    )
    parser.add_argument("--user-agent", help="Custom User-Agent header")
    parser.add_argument("--referer", help="Custom Referer header")
    parser.add_argument(
        "-H",
        "--header",
        action="append",
        default=[],
        help="Extra header in KEY:VALUE format; can be used multiple times",
    )
    parser.add_argument("--cookies-from-browser", help="Browser name for yt-dlp cookie extraction")
    parser.add_argument("--playlist", action="store_true", help="Allow playlist processing")
    parser.add_argument("--max-items", type=int, help="Cap total downloaded items")
    parser.add_argument("--timeout", type=int, default=30, help="HTTP timeout in seconds")
    parser.add_argument("--ffmpeg-binary", default="ffmpeg", help="ffmpeg executable name or path")
    parser.add_argument("--profile", help="Profile name to apply (default: default)")
    parser.add_argument("--manual", action="store_true", help="Interactively override profile fields")
    parser.add_argument("--output-template", help="yt-dlp output template override")
    parser.add_argument("--audio-only", action="store_true", default=None, help="Extract audio only as high-quality MP3 (320 kbit/s)")
    parser.add_argument("--subtitle-langs", help="Subtitle languages, e.g. en.*,de")
    parser.add_argument("--audio-langs", help="Preferred audio language list")
    parser.add_argument(
        "--embed-subs",
        action="store_true",
        default=None,
        help="Embed subtitles when possible",
    )
    parser.add_argument("--use-aria2", action="store_true", default=None, help="Use aria2 when available")


def _should_use_legacy_mode(argv: list[str]) -> bool:
    if not argv:
        return False
    first = argv[0].strip()
    first_lower = first.lower()
    if first_lower in NEW_COMMANDS:
        return False
    if first_lower in {"-h", "--help"}:
        return False
    if first.startswith("-"):
        return True
    return first_lower not in NEW_COMMANDS


def _run_legacy_mode(argv: list[str]) -> None:
    # Safety shim: if legacy mode was selected unexpectedly, still route known
    # modern commands correctly.
    if argv:
        first = argv[0].strip().lower()
        if first in {"ui", "tui"}:
            parser = _build_parser()
            args = parser.parse_args([first, *argv[1:]])

            paths = resolve_paths()
            config = load_or_create_config(paths)
            configure_logging(paths)

            store = QueueStore(paths.state_db)
            store.init()

            console = Console()
            _print_legal_warning(console)
            _dispatch_command(console, store, config, args)
            return

    parser = _build_legacy_parser()
    args = parser.parse_args(argv)

    console = Console()
    _print_legal_warning(console)

    headers = _parse_headers(args.header)
    _validate_legacy_args(parser, args)
    output_dir = ensure_output_dir(Path(args.output).expanduser().resolve())

    manager = DownloadManager(logger=lambda m: console.print(f"[cyan]{m}[/cyan]"))

    profile = DownloadProfile(
        id=None,
        name="legacy",
        format_selector=args.format_selector,
        output_template=args.output_template,
        audio_only=bool(args.audio_only),
        subtitle_langs=args.subtitle_langs,
        audio_langs=args.audio_langs,
        embed_subs=bool(args.embed_subs),
        use_aria2=bool(args.use_aria2),
    )
    if args.topic:
        _run_topic_batch(console, manager, args, headers, output_dir, profile)
        return

    request = _build_request(
        args=args,
        headers=headers,
        output_dir=output_dir,
        source=args.url.strip(),
        method="yt-dlp" if args.playlist and args.method == "auto" else args.method,
        filename=args.name,
        allow_playlist=args.playlist,
        max_items=args.max_items,
        profile=profile,
    )
    _run_single(console, manager, request)


def _build_legacy_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="classydl",
        description="High-class but simple multi-strategy video downloader",
    )
    parser.add_argument("url", nargs="?", help="Video page URL or direct media URL")
    parser.add_argument("-o", "--output", default="downloads", help="Output directory (default: downloads)")
    parser.add_argument("-n", "--name", help="Output filename without extension")
    parser.add_argument(
        "-m",
        "--method",
        choices=["auto", "yt-dlp", "ffmpeg", "direct"],
        default="auto",
        help="Download method (default: auto)",
    )
    parser.add_argument("-f", "--format", dest="format_selector", default="bv*+ba/b")
    parser.add_argument("--user-agent", help="Custom User-Agent header")
    parser.add_argument("--referer", help="Custom Referer header")
    parser.add_argument("-H", "--header", action="append", default=[])
    parser.add_argument("--cookies-from-browser", help="Browser name for yt-dlp cookie extraction")
    parser.add_argument("--playlist", action="store_true")
    parser.add_argument("--max-items", type=int)
    parser.add_argument("--topic", action="append", default=[])
    parser.add_argument("--search-count", type=int, default=5)
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--ffmpeg-binary", default="ffmpeg")
    parser.add_argument("--output-template")
    parser.add_argument("--audio-only", action="store_true")
    parser.add_argument("--subtitle-langs")
    parser.add_argument("--audio-langs")
    parser.add_argument("--embed-subs", action="store_true")
    parser.add_argument("--use-aria2", action="store_true")
    return parser


def _parse_headers(values: list[str]) -> dict[str, str]:
    headers: dict[str, str] = {}
    for raw in values:
        if ":" not in raw:
            raise ValueError(f"Invalid header format: {raw!r}. Use KEY:VALUE.")
        key, value = raw.split(":", 1)
        if not key.strip():
            raise ValueError(f"Invalid header format: {raw!r}. Header name cannot be empty.")
        headers[key.strip()] = value.strip()
    return headers


def _validate_download_args(args: argparse.Namespace) -> None:
    if not args.source and not args.topic:
        raise ValueError("Provide a source URL or at least one --topic.")
    if args.source and args.topic:
        raise ValueError("Use either source mode or --topic batch mode, not both together.")
    if args.max_items is not None and args.max_items <= 0:
        raise ValueError("--max-items must be greater than 0.")
    if args.search_count <= 0:
        raise ValueError("--search-count must be greater than 0.")
    if args.playlist and args.method in {"direct", "ffmpeg"}:
        raise ValueError("--playlist requires method auto or yt-dlp.")
    if args.topic and args.method in {"direct", "ffmpeg"}:
        raise ValueError("--topic batch mode requires method auto or yt-dlp.")
    if args.topic and args.name:
        raise ValueError("--name is not supported in --topic batch mode.")


def _validate_legacy_args(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    if not args.url and not args.topic:
        parser.error("Provide either a URL or at least one --topic.")
    if args.url and args.topic:
        parser.error("Use either URL mode or --topic batch mode, not both together.")
    if args.max_items is not None and args.max_items <= 0:
        parser.error("--max-items must be greater than 0.")
    if args.search_count <= 0:
        parser.error("--search-count must be greater than 0.")
    if args.playlist and args.method in {"direct", "ffmpeg"}:
        parser.error("--playlist requires method auto or yt-dlp.")
    if args.topic and args.method in {"direct", "ffmpeg"}:
        parser.error("--topic batch mode requires method auto or yt-dlp.")
    if args.topic and args.name:
        parser.error("--name is not supported in --topic batch mode; filenames are derived per video.")


def _build_request(
    args: argparse.Namespace,
    headers: dict[str, str],
    output_dir: Path,
    source: str,
    method: str,
    filename: str | None,
    allow_playlist: bool,
    max_items: int | None,
    profile: DownloadProfile,
) -> DownloadRequest:
    external_downloader: str | None = None
    external_downloader_args: str | None = None
    if profile.use_aria2 and shutil.which("aria2c"):
        external_downloader = "aria2c"
        external_downloader_args = "-x 16 -k 1M -s 16"

    # When audio_only is active, prefer best-audio format selector unless
    # the user explicitly overrode the format via profile or CLI flag.
    effective_format = profile.format_selector
    if profile.audio_only and effective_format == "bv*+ba/b":
        effective_format = "ba/b"

    return DownloadRequest(
        source_url=source,
        output_dir=output_dir,
        filename=filename,
        method=method,
        format_selector=effective_format,
        user_agent=args.user_agent,
        referer=args.referer,
        headers=headers,
        cookies_from_browser=args.cookies_from_browser,
        timeout_seconds=args.timeout,
        ffmpeg_binary=args.ffmpeg_binary,
        allow_playlist=allow_playlist,
        max_items=max_items,
        output_template=profile.output_template,
        audio_only=profile.audio_only,
        subtitle_langs=profile.subtitle_langs,
        audio_langs=profile.audio_langs,
        embed_subs=profile.embed_subs,
        external_downloader=external_downloader,
        external_downloader_args=external_downloader_args,
        profile_name=profile.name,
    )


def _run_single(console: Console, manager: DownloadManager, request: DownloadRequest) -> None:
    result = manager.download(request)

    files = result.downloaded_files or [result.file_path]
    console.print("[bold green]Download completed[/bold green]")
    console.print(f"Method: [green]{result.method}[/green]")
    console.print(f"Source: {result.source_url}")
    if len(files) == 1:
        console.print(f"File: [bold]{files[0]}[/bold]")
    else:
        console.print(f"Files downloaded: [bold]{len(files)}[/bold]")
        for file_path in files[:10]:
            console.print(f"- {file_path}")
        if len(files) > 10:
            console.print(f"... and {len(files) - 10} more")
    if result.details:
        console.print(f"[yellow]Note:[/yellow] {result.details}")


def _run_topic_batch(
    console: Console,
    manager: DownloadManager,
    args: argparse.Namespace,
    headers: dict[str, str],
    output_dir: Path,
    profile: DownloadProfile,
) -> None:
    table = Table(title="Batch Topic Results")
    table.add_column("Topic")
    table.add_column("Status")
    table.add_column("Items")
    table.add_column("Details")

    failures = 0
    total_files = 0
    for topic in args.topic:
        source = f"ytsearch{args.search_count}:{topic}"
        topic_dir = ensure_output_dir(output_dir / safe_filename(topic))
        request = _build_request(
            args=args,
            headers=headers,
            output_dir=topic_dir,
            source=source,
            method="yt-dlp",
            filename=None,
            allow_playlist=True,
            max_items=args.max_items if args.max_items is not None else args.search_count,
            profile=profile,
        )

        console.print(f"[cyan]Batch topic:[/cyan] {topic}")
        try:
            result = manager.download(request)
            files = result.downloaded_files or [result.file_path]
            total_files += len(files)
            detail = result.details if result.details else str(topic_dir)
            table.add_row(topic, "ok", str(len(files)), detail)
        except DownloadWorkflowError as exc:
            failures += 1
            table.add_row(topic, "failed", "0", str(exc))
            _print_attempt_table(console, exc)

    console.print(table)
    console.print(f"Topics processed: {len(args.topic)}")
    console.print(f"Files downloaded: {total_files}")
    if failures:
        console.print(f"[bold red]Failed topics: {failures}[/bold red]")
        sys.exit(1)
    console.print("[bold green]Batch download completed[/bold green]")


def _print_attempt_table(console: Console, exc: DownloadWorkflowError) -> None:
    if not exc.attempts:
        return
    table = Table(title="Attempt Summary")
    table.add_column("Method")
    table.add_column("Source URL")
    table.add_column("Status")
    table.add_column("Message")
    for attempt in exc.attempts:
        status = "ok" if attempt.success else "failed"
        table.add_row(attempt.method, attempt.source_url, status, attempt.message)
    console.print(table)


def _print_legal_warning(console: Console) -> None:
    console.print(
        "[yellow]Legal notice:[/yellow] Download only content you have rights/permission to access. "
        "This tool does not bypass DRM-protected platforms."
    )


if __name__ == "__main__":
    main()
