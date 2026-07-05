from __future__ import annotations

import argparse
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from tkinter import END, StringVar, Tk, Toplevel, messagebox
from tkinter import filedialog
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
import yt_dlp

if __package__ in {None, ""}:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from video_downloader.app_config import load_or_create_config, resolve_paths
    from video_downloader.conversion import CONVERTIBLE_VIDEO_EXTENSIONS, convert_file_to_mp4
    from video_downloader.core import DownloadManager
    from video_downloader.models import DownloadRequest, DownloadWorkflowError
    from video_downloader.scraper import SiteScraper, ScrapedMedia, classify_url
    from video_downloader.utils import (
        ensure_output_dir,
        extract_media_candidates,
        is_direct_media_url,
        is_manifest_url,
    )
else:
    from .app_config import load_or_create_config, resolve_paths
    from .conversion import CONVERTIBLE_VIDEO_EXTENSIONS, convert_file_to_mp4
    from .core import DownloadManager
    from .models import DownloadRequest, DownloadWorkflowError
    from .scraper import SiteScraper, ScrapedMedia, classify_url
    from .utils import ensure_output_dir, extract_media_candidates, is_direct_media_url, is_manifest_url

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)
MAX_DISCOVERED_LINKS = 1200
VIDEO_HINTS = (
    "/watch",
    "/video",
    "view_video",
    "/reel",
    "/clip",
    "/playlist",
)


@dataclass(slots=True)
class LinkEntry:
    url: str
    referer: str | None = None


def run_easy_ui(
    default_output_dir: str,
    initial_method: str = "auto",
    initial_cookies_from_browser: str | None = None,
) -> None:
    app = EasyUiApp(
        default_output_dir=default_output_dir,
        initial_method=initial_method,
        initial_cookies_from_browser=initial_cookies_from_browser,
    )
    app.run()


class EasyUiApp:
    def __init__(
        self,
        default_output_dir: str,
        initial_method: str = "auto",
        initial_cookies_from_browser: str | None = None,
    ) -> None:
        self.root = Tk()
        self.root.title("ClassyDL Easy UI")
        self.root.geometry("1060x760")

        self.default_output_dir = default_output_dir
        self.manager = DownloadManager(logger=self._log_threadsafe)
        self.busy = False

        self.url_var = StringVar()
        self.site_var = StringVar()
        self.output_var = StringVar(value=default_output_dir)
        self.method_var = StringVar(value=initial_method if initial_method in {"auto", "yt-dlp", "ffmpeg", "direct"} else "auto")
        self.cookies_var = StringVar(value=initial_cookies_from_browser or "")
        self.max_items_var = StringVar()
        self.filter_var = StringVar()
        self.same_domain_var = StringVar(value="1")
        self.video_only_var = StringVar(value="0")
        self.playlist_var = StringVar(value="0")
        self.audio_only_var = StringVar(value="0")
        self.auto_convert_var = StringVar(value="0")
        self.type_filter_var = StringVar(value="all")
        self.deep_scrape_var = StringVar(value="0")
        self.workers_var = StringVar(value="3")

        self.link_entries: list[LinkEntry] = []
        self.scraped_items: list[ScrapedMedia] = []
        self.visible_entries: list[LinkEntry] = []
        self.visible_scraped: list[ScrapedMedia] = []
        self.download_button_refs: list[ttk.Button] = []

        self._build_ui()

    def run(self) -> None:
        self.root.mainloop()

    def _build_ui(self) -> None:
        root = self.root
        root.columnconfigure(0, weight=1)
        root.rowconfigure(2, weight=1)
        root.rowconfigure(3, weight=1)

        quick_frame = ttk.LabelFrame(root, text="Quick Download")
        quick_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=(10, 5))
        quick_frame.columnconfigure(1, weight=1)
        quick_frame.columnconfigure(4, weight=1)

        ttk.Label(quick_frame, text="Link").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        url_entry = ttk.Entry(quick_frame, textvariable=self.url_var)
        url_entry.grid(row=0, column=1, columnspan=3, padx=5, pady=5, sticky="ew")
        url_entry.focus_set()

        paste_btn = ttk.Button(quick_frame, text="Paste Clipboard", command=self._paste_clipboard_to_link)
        paste_btn.grid(row=0, column=4, padx=5, pady=5, sticky="ew")

        ttk.Label(quick_frame, text="Method").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        method_combo = ttk.Combobox(
            quick_frame,
            textvariable=self.method_var,
            values=("auto", "yt-dlp", "ffmpeg", "direct"),
            state="readonly",
            width=12,
        )
        method_combo.grid(row=1, column=1, padx=5, pady=5, sticky="w")

        ttk.Checkbutton(
            quick_frame,
            text="Playlist mode",
            variable=self.playlist_var,
            onvalue="1",
            offvalue="0",
        ).grid(row=1, column=2, padx=5, pady=5, sticky="w")

        ttk.Checkbutton(
            quick_frame,
            text="Audio only (MP3 320k)",
            variable=self.audio_only_var,
            onvalue="1",
            offvalue="0",
        ).grid(row=3, column=0, columnspan=2, padx=5, pady=5, sticky="w")

        ttk.Checkbutton(
            quick_frame,
            text="Auto-convert video to MP4",
            variable=self.auto_convert_var,
            onvalue="1",
            offvalue="0",
        ).grid(row=3, column=2, columnspan=2, padx=5, pady=5, sticky="w")

        ttk.Label(quick_frame, text="Max items").grid(row=1, column=3, padx=5, pady=5, sticky="e")
        ttk.Entry(quick_frame, textvariable=self.max_items_var, width=8).grid(
            row=1, column=4, padx=5, pady=5, sticky="w"
        )

        ttk.Label(quick_frame, text="Workers").grid(row=1, column=5, padx=(15, 2), pady=5, sticky="e")
        ttk.Spinbox(
            quick_frame,
            textvariable=self.workers_var,
            from_=1,
            to=8,
            width=4,
        ).grid(row=1, column=6, padx=(0, 5), pady=5, sticky="w")

        ttk.Label(quick_frame, text="Cookies browser").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        ttk.Entry(quick_frame, textvariable=self.cookies_var).grid(
            row=2, column=1, columnspan=2, padx=5, pady=5, sticky="ew"
        )
        ttk.Label(quick_frame, text="Output folder").grid(row=2, column=3, padx=5, pady=5, sticky="e")
        output_entry = ttk.Entry(quick_frame, textvariable=self.output_var)
        output_entry.grid(row=2, column=4, padx=5, pady=5, sticky="ew")

        browse_btn = ttk.Button(quick_frame, text="Browse", command=self._pick_output_directory)
        browse_btn.grid(row=2, column=5, padx=5, pady=5, sticky="ew")

        download_link_btn = ttk.Button(
            quick_frame,
            text="Download Link",
            command=self._download_link_now,
        )
        download_link_btn.grid(row=3, column=4, padx=5, pady=6, sticky="ew")
        self.download_button_refs.append(download_link_btn)

        help_btn = ttk.Button(
            quick_frame,
            text="ℹ Anleitung",
            command=self._show_help,
            width=12,
        )
        help_btn.grid(row=3, column=5, padx=5, pady=6, sticky="ew")

        # Progress bar row — shows "X / Y Lieder" while a playlist downloads
        self._progress_bar = ttk.Progressbar(
            quick_frame, orient="horizontal", mode="determinate", maximum=100, value=0
        )
        self._progress_bar.grid(row=4, column=0, columnspan=5, padx=5, pady=(2, 6), sticky="ew")
        self._track_label = ttk.Label(quick_frame, text="", foreground="#555555")
        self._track_label.grid(row=4, column=5, columnspan=2, padx=5, pady=(2, 6), sticky="w")

        site_frame = ttk.LabelFrame(root, text="Site Scraper – Find Videos, Audio & Images")
        site_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        site_frame.columnconfigure(1, weight=1)
        site_frame.columnconfigure(4, weight=1)

        ttk.Label(site_frame, text="Website").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        ttk.Entry(site_frame, textvariable=self.site_var).grid(
            row=0, column=1, columnspan=3, padx=5, pady=5, sticky="ew"
        )

        use_link_btn = ttk.Button(site_frame, text="Use Link Above", command=self._copy_link_to_site)
        use_link_btn.grid(row=0, column=4, padx=5, pady=5, sticky="ew")

        scan_btn = ttk.Button(site_frame, text="Scrape Website", command=self._scan_site_links)
        scan_btn.grid(row=0, column=5, padx=5, pady=5, sticky="ew")

        ttk.Checkbutton(
            site_frame,
            text="Same domain only",
            variable=self.same_domain_var,
            onvalue="1",
            offvalue="0",
        ).grid(row=1, column=0, padx=5, pady=5, sticky="w")

        ttk.Checkbutton(
            site_frame,
            text="Deep scrape (follow links)",
            variable=self.deep_scrape_var,
            onvalue="1",
            offvalue="0",
        ).grid(row=1, column=1, padx=5, pady=5, sticky="w")

        ttk.Label(site_frame, text="Type").grid(row=1, column=2, padx=5, pady=5, sticky="e")
        type_combo = ttk.Combobox(
            site_frame,
            textvariable=self.type_filter_var,
            values=("all", "video", "audio", "image"),
            state="readonly",
            width=10,
        )
        type_combo.grid(row=1, column=3, padx=5, pady=5, sticky="w")
        type_combo.bind("<<ComboboxSelected>>", self._on_type_filter_changed)

        ttk.Label(site_frame, text="Filter").grid(row=2, column=0, padx=5, pady=5, sticky="e")
        filter_entry = ttk.Entry(site_frame, textvariable=self.filter_var)
        filter_entry.grid(row=2, column=1, columnspan=2, padx=5, pady=5, sticky="ew")
        filter_entry.bind("<KeyRelease>", self._on_filter_changed)

        link_frame = ttk.Frame(root)
        link_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=5)
        link_frame.columnconfigure(0, weight=1)
        link_frame.rowconfigure(0, weight=1)

        self.link_list = tk_list = ttk.Treeview(
            link_frame,
            columns=("type", "filename", "url"),
            show="headings",
            selectmode="extended",
        )
        tk_list.heading("type", text="Type")
        tk_list.heading("filename", text="Filename")
        tk_list.heading("url", text="URL")
        tk_list.column("type", anchor="w", width=60, stretch=False)
        tk_list.column("filename", anchor="w", width=280, stretch=False)
        tk_list.column("url", anchor="w", stretch=True, width=680)
        tk_list.grid(row=0, column=0, sticky="nsew")

        scroll = ttk.Scrollbar(link_frame, orient="vertical", command=tk_list.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        tk_list.configure(yscrollcommand=scroll.set)

        actions = ttk.Frame(root)
        actions.grid(row=3, column=0, sticky="ew", padx=10, pady=(0, 4))

        select_all_btn = ttk.Button(actions, text="Select All", command=self._select_all_links)
        select_all_btn.grid(row=0, column=0, padx=4, pady=4)
        clear_sel_btn = ttk.Button(actions, text="Clear Selection", command=self._clear_selection)
        clear_sel_btn.grid(row=0, column=1, padx=4, pady=4)

        sel_videos_btn = ttk.Button(actions, text="All Videos", command=lambda: self._select_by_type("video"))
        sel_videos_btn.grid(row=0, column=2, padx=4, pady=4)
        sel_audio_btn = ttk.Button(actions, text="All Audio", command=lambda: self._select_by_type("audio"))
        sel_audio_btn.grid(row=0, column=3, padx=4, pady=4)
        sel_images_btn = ttk.Button(actions, text="All Images", command=lambda: self._select_by_type("image"))
        sel_images_btn.grid(row=0, column=4, padx=4, pady=4)

        download_selected_btn = ttk.Button(
            actions,
            text="Download Selected",
            command=self._download_selected_links,
        )
        download_selected_btn.grid(row=0, column=5, padx=4, pady=4)
        self.download_button_refs.append(download_selected_btn)

        download_all_btn = ttk.Button(
            actions,
            text="Download All Found",
            command=self._download_all_links,
        )
        download_all_btn.grid(row=0, column=6, padx=4, pady=4)
        self.download_button_refs.append(download_all_btn)

        self.status_label = ttk.Label(actions, text="Ready")
        self.status_label.grid(row=0, column=7, padx=8, pady=4, sticky="w")

        log_frame = ttk.LabelFrame(root, text="Activity")
        log_frame.grid(row=4, column=0, sticky="nsew", padx=10, pady=(0, 10))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        root.rowconfigure(4, weight=1)

        self.log_text = ScrolledText(log_frame, wrap="word", height=12, state="disabled")
        self.log_text.grid(row=0, column=0, sticky="nsew")

    def _paste_clipboard_to_link(self) -> None:
        try:
            text = self.root.clipboard_get().strip()
        except Exception:
            self._log("Clipboard does not contain text.")
            return
        if not text:
            self._log("Clipboard is empty.")
            return
        self.url_var.set(text)
        if not self.site_var.get().strip():
            self.site_var.set(text)
        self._log("Pasted clipboard into link input.")

    def _copy_link_to_site(self) -> None:
        link = self.url_var.get().strip()
        if not link:
            self._log("Link input is empty.")
            return
        self.site_var.set(link)
        self._log("Copied link input into website scanner.")

    def _pick_output_directory(self) -> None:
        selected = filedialog.askdirectory(initialdir=self.output_var.get() or self.default_output_dir)
        if selected:
            self.output_var.set(selected)

    def _scan_site_links(self) -> None:
        if self.busy:
            self._log("Wait for current download batch to finish.")
            return
        site_url = self.site_var.get().strip() or self.url_var.get().strip()
        if not site_url:
            messagebox.showwarning("Missing URL", "Enter a website URL first.")
            return
        if not _looks_like_http_url(site_url):
            messagebox.showwarning("Invalid URL", "Website URL must start with http:// or https://")
            return

        same_domain_only = self.same_domain_var.get() == "1"
        deep = self.deep_scrape_var.get() == "1"
        self.status_label.configure(text="Scraping site...")
        self._log(f"Scraping media from {site_url}")

        thread = threading.Thread(
            target=self._scan_site_links_worker,
            args=(site_url, same_domain_only, deep),
            daemon=True,
        )
        thread.start()

    def _scan_site_links_worker(
        self,
        site_url: str,
        same_domain_only: bool,
        deep: bool,
    ) -> None:
        try:
            scraper = SiteScraper(logger=self._log_threadsafe)
            result = scraper.scrape(
                site_url,
                same_domain=same_domain_only,
                deep=deep,
            )
            if result.errors:
                for err in result.errors:
                    self._log_threadsafe(f"Warning: {err}")
            # Convert ScrapedMedia to our internal lists
            items = result.items
            entries = [LinkEntry(url=item.url, referer=item.referer) for item in items]
        except Exception as exc:
            self.root.after(0, lambda: self._finish_scan_error(str(exc)))
            return
        self.root.after(0, lambda: self._finish_scan_success_scrape(entries, items))

    def _finish_scan_error(self, message: str) -> None:
        self.status_label.configure(text="Scan failed")
        self._log(f"Scan failed: {message}")
        messagebox.showerror("Scan failed", message)

    def _finish_scan_success(self, entries: list[LinkEntry]) -> None:
        self.link_entries = entries
        self.scraped_items = []
        self._refresh_link_list(entries)
        self.status_label.configure(text=f"Found {len(entries)} links")
        self._log(f"Scan complete. Found {len(entries)} candidate links.")

    def _finish_scan_success_scrape(self, entries: list[LinkEntry], items: list[ScrapedMedia]) -> None:
        self.link_entries = entries
        self.scraped_items = items
        self._apply_filters()
        type_counts: dict[str, int] = {}
        for item in items:
            type_counts[item.media_type] = type_counts.get(item.media_type, 0) + 1
        summary = ", ".join(f"{t}: {c}" for t, c in sorted(type_counts.items()))
        self.status_label.configure(text=f"Found {len(items)} media ({summary})")
        self._log(f"Scrape complete. Found {len(items)} media items ({summary}).")

    def _refresh_link_list(self, entries: list[LinkEntry], scraped: list[ScrapedMedia] | None = None) -> None:
        self.visible_entries = entries
        self.visible_scraped = scraped or []
        tree = self.link_list
        for item in tree.get_children():
            tree.delete(item)
        if scraped and len(scraped) == len(entries):
            for idx, (entry, media) in enumerate(zip(entries, scraped)):
                tree.insert("", END, iid=str(idx), values=(media.media_type, media.filename[:60], entry.url))
        else:
            for idx, entry in enumerate(entries):
                mtype = classify_url(entry.url)
                fname = entry.url.rsplit("/", 1)[-1][:60] if "/" in entry.url else entry.url[:60]
                tree.insert("", END, iid=str(idx), values=(mtype, fname, entry.url))

    def _on_filter_changed(self, _event=None) -> None:
        self._apply_filters()

    def _on_type_filter_changed(self, _event=None) -> None:
        self._apply_filters()

    def _apply_filters(self) -> None:
        """Re-filter scraped items by text filter and type combo."""
        raw_text = self.filter_var.get().strip().lower()
        type_val = self.type_filter_var.get().strip().lower()

        if self.scraped_items:
            filtered_items: list[ScrapedMedia] = []
            filtered_entries: list[LinkEntry] = []
            for item, entry in zip(self.scraped_items, self.link_entries):
                if type_val and type_val != "all" and item.media_type != type_val:
                    continue
                if raw_text and raw_text not in item.url.lower() and raw_text not in item.filename.lower():
                    continue
                filtered_items.append(item)
                filtered_entries.append(entry)
            self._refresh_link_list(filtered_entries, filtered_items)
            self.status_label.configure(text=f"Showing {len(filtered_items)} of {len(self.scraped_items)} items")
        else:
            if not raw_text:
                self._refresh_link_list(self.link_entries)
                return
            filtered = [entry for entry in self.link_entries if raw_text in entry.url.lower()]
            self._refresh_link_list(filtered)
            self.status_label.configure(text=f"Showing {len(filtered)} filtered links")

    def _select_all_links(self) -> None:
        items = self.link_list.get_children()
        self.link_list.selection_set(items)

    def _clear_selection(self) -> None:
        self.link_list.selection_remove(self.link_list.selection())

    def _select_by_type(self, media_type: str) -> None:
        """Select all visible items of a given media type."""
        self.link_list.selection_remove(self.link_list.selection())
        items = self.link_list.get_children()
        to_select: list[str] = []
        for item_id in items:
            values = self.link_list.item(item_id, "values")
            if values and values[0] == media_type:
                to_select.append(item_id)
        if to_select:
            self.link_list.selection_set(to_select)
            self._log(f"Selected {len(to_select)} {media_type} items.")
        else:
            self._log(f"No {media_type} items found in current view.")

    def _download_link_now(self) -> None:
        url = self.url_var.get().strip()
        if not url:
            messagebox.showwarning("Missing URL", "Enter a link first.")
            return
        if not _looks_like_http_url(url):
            messagebox.showwarning("Invalid URL", "Link must start with http:// or https://")
            return
        allow_playlist = self.playlist_var.get() == "1"
        if allow_playlist:
            # Extract all playlist entries first so we can download them in
            # parallel and show accurate "X / Y Lieder" progress.
            self.busy = True
            self._set_download_buttons_enabled(False)
            self.status_label.configure(text="Extracting playlist…")
            self._log("Extracting playlist items…")
            self._reset_progress()
            cookies = self.cookies_var.get().strip() or None
            thread = threading.Thread(
                target=self._extract_and_start_playlist,
                args=(url, cookies),
                daemon=True,
            )
            thread.start()
        else:
            self._start_download_batch([LinkEntry(url=url, referer=None)])

    def _extract_and_start_playlist(self, url: str, cookies_from_browser: str | None) -> None:
        """Run in background thread: extract playlist URLs then start batch."""
        try:
            entries = _extract_playlist_entries(url, cookies_from_browser)
        except Exception as exc:
            self.root.after(0, lambda: self._finish_extract_error(str(exc)))
            return
        self.root.after(0, lambda: self._finish_extract_success(entries))

    def _finish_extract_error(self, message: str) -> None:
        self.busy = False
        self._set_download_buttons_enabled(True)
        self.status_label.configure(text="Extraction failed")
        self._log(f"Playlist extraction failed: {message}")
        messagebox.showerror("Playlist extraction failed", message)

    def _finish_extract_success(self, entries: list[LinkEntry]) -> None:
        count = len(entries)
        self.busy = False
        self._log(f"Playlist contains {count} item(s). Starting parallel download…")
        self._start_download_batch(entries)

    def _download_selected_links(self) -> None:
        selected_ids = self.link_list.selection()
        if not selected_ids:
            messagebox.showwarning("No selection", "Select one or more links first.")
            return
        entries: list[LinkEntry] = []
        for item_id in selected_ids:
            try:
                index = int(item_id)
            except ValueError:
                continue
            if 0 <= index < len(self.visible_entries):
                entries.append(self.visible_entries[index])
        if not entries:
            messagebox.showwarning("No selection", "Could not read selected links.")
            return
        self._start_download_batch(entries)

    def _download_all_links(self) -> None:
        if not self.visible_entries:
            messagebox.showwarning("No links", "Scan a website first.")
            return
        self._start_download_batch(list(self.visible_entries))

    def _start_download_batch(self, entries: list[LinkEntry]) -> None:
        if self.busy:
            self._log("Download is already running.")
            return
        try:
            output_dir = ensure_output_dir(Path(self.output_var.get().strip()).expanduser().resolve())
        except Exception as exc:
            messagebox.showerror("Output path error", str(exc))
            return

        max_items = _parse_optional_positive_int(self.max_items_var.get().strip())
        if self.max_items_var.get().strip() and max_items is None:
            messagebox.showwarning("Invalid max-items", "Max items must be an integer greater than 0.")
            return

        workers = max(1, min(8, int(self.workers_var.get().strip() or "3")))
        cookies = self.cookies_var.get().strip() or None
        method = self.method_var.get().strip() or "auto"
        allow_playlist = self.playlist_var.get() == "1"
        audio_only = self.audio_only_var.get() == "1"
        auto_convert = self.auto_convert_var.get() == "1"

        self.busy = True
        self._set_download_buttons_enabled(False)
        self.status_label.configure(text=f"Downloading {len(entries)} item(s)…")
        self._log(f"Starting batch download for {len(entries)} link(s) with {workers} worker(s).")
        self._reset_progress()

        thread = threading.Thread(
            target=self._download_batch_worker,
            args=(entries, output_dir, method, allow_playlist, max_items, cookies, audio_only, auto_convert, workers),
            daemon=True,
        )
        thread.start()

    def _download_batch_worker(
        self,
        entries: list[LinkEntry],
        output_dir: Path,
        method: str,
        allow_playlist: bool,
        max_items: int | None,
        cookies_from_browser: str | None,
        audio_only: bool = False,
        auto_convert: bool = False,
        workers: int = 3,
    ) -> None:
        total = len(entries)
        ok_count = 0
        failed: list[str] = []
        converted_count = 0
        conversion_failures: list[str] = []
        completed = 0
        lock = threading.Lock()

        def download_one(idx_entry: tuple[int, LinkEntry]) -> None:
            nonlocal ok_count, converted_count, completed
            i, entry = idx_entry
            label = "audio" if audio_only else "media"
            self._log_threadsafe(f"[{i}/{total}] Downloading {label}: {entry.url}")
            # Each worker gets its own DownloadManager to avoid shared state.
            manager = DownloadManager(logger=self._log_threadsafe)
            request = DownloadRequest(
                source_url=entry.url,
                output_dir=output_dir,
                method=method,
                format_selector="ba/b" if audio_only else "bv*+ba/b",
                allow_playlist=allow_playlist,
                max_items=max_items,
                cookies_from_browser=cookies_from_browser,
                referer=entry.referer,
                audio_only=audio_only,
                # item_progress_callback fires for yt-dlp-internal playlist items
                # (e.g. when allow_playlist=True on a single-URL batch call).
                item_progress_callback=self._update_progress_threadsafe,
            )
            try:
                result = manager.download(request)
                files = result.downloaded_files or [result.file_path]
                if auto_convert and not audio_only:
                    cvt, cvt_errs = self._convert_files_to_mp4(files)
                    with lock:
                        converted_count += cvt
                        conversion_failures.extend(cvt_errs)
                self._log_threadsafe(f"Success: {entry.url} ({len(files)} file(s))")
                with lock:
                    ok_count += 1
                    completed += 1
                    self._update_progress_threadsafe(completed, total)
            except DownloadWorkflowError as exc:
                self._log_threadsafe(f"Failed: {entry.url} :: {exc}")
                with lock:
                    failed.append(entry.url)
                    completed += 1
                    self._update_progress_threadsafe(completed, total)
            except Exception as exc:
                self._log_threadsafe(f"Failed: {entry.url} :: {exc}")
                with lock:
                    failed.append(entry.url)
                    completed += 1
                    self._update_progress_threadsafe(completed, total)

        safe_workers = max(1, min(8, workers))
        with ThreadPoolExecutor(max_workers=safe_workers, thread_name_prefix="easydl") as pool:
            futures = [pool.submit(download_one, (i, e)) for i, e in enumerate(entries, start=1)]
            for fut in futures:
                fut.result()  # propagate any unexpected exceptions

        self.root.after(
            0,
            lambda: self._finish_download_batch(
                ok_count,
                failed,
                total,
                converted_count,
                conversion_failures,
            ),
        )

    def _convert_files_to_mp4(self, files: list[Path]) -> tuple[int, list[str]]:
        converted = 0
        failures: list[str] = []
        seen: set[Path] = set()

        for file_path in files:
            resolved = file_path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)

            suffix = resolved.suffix.lower()
            if suffix not in CONVERTIBLE_VIDEO_EXTENSIONS:
                continue

            try:
                converted_path = convert_file_to_mp4(resolved)
            except FileExistsError:
                target_name = f"{resolved.stem}.mp4"
                self._log_threadsafe(f"Skipped MP4 conversion for {resolved.name}: {target_name} already exists.")
                continue
            except Exception as exc:
                message = f"{resolved.name}: {exc}"
                self._log_threadsafe(f"MP4 conversion failed for {resolved.name}: {exc}")
                failures.append(message)
                continue

            converted += 1
            self._log_threadsafe(f"Converted to MP4: {converted_path}")

        return converted, failures

    def _finish_download_batch(
        self,
        ok_count: int,
        failed: list[str],
        total: int,
        converted_count: int = 0,
        conversion_failures: list[str] | None = None,
    ) -> None:
        self.busy = False
        self._set_download_buttons_enabled(True)
        fail_count = len(failed)
        conversion_failures = conversion_failures or []
        status_text = f"Done: {ok_count} ok / {fail_count} failed"
        if converted_count or conversion_failures:
            status_text += f" / {converted_count} MP4"
        self.status_label.configure(text=status_text)
        self._log(
            f"Batch complete: {ok_count} success, {fail_count} failed, "
            f"{converted_count} converted to MP4, {len(conversion_failures)} conversion failures."
        )

        if fail_count == 0 and not conversion_failures:
            details = f"Downloaded {ok_count}/{total} link(s) successfully."
            if converted_count:
                details += f"\nConverted to MP4: {converted_count}"
            messagebox.showinfo("Finished", details)
            return

        preview = "\n".join(failed[:5])
        if fail_count > 5:
            preview += f"\n... and {fail_count - 5} more."
        conversion_preview = "\n".join(conversion_failures[:5])
        if len(conversion_failures) > 5:
            conversion_preview += f"\n... and {len(conversion_failures) - 5} more."
        message = (
            f"Downloaded {ok_count}/{total}.\n"
            f"Failed downloads: {fail_count}\n"
            f"Converted to MP4: {converted_count}\n"
            f"Failed conversions: {len(conversion_failures)}"
        )
        if preview:
            message += f"\n\nDownload failures:\n{preview}"
        if conversion_preview:
            message += f"\n\nConversion failures:\n{conversion_preview}"
        messagebox.showwarning(
            "Finished with failures",
            message,
        )

    def _set_download_buttons_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        for button in self.download_button_refs:
            button.configure(state=state)

    # ------------------------------------------------------------------
    # Progress bar helpers
    # ------------------------------------------------------------------

    def _reset_progress(self) -> None:
        """Reset progress bar and track label to initial state (main thread)."""
        self._progress_bar.configure(maximum=100, value=0)
        self._track_label.configure(text="")

    def _update_progress(self, current: int, total: int) -> None:
        """Update progress bar and label (must be called from main thread)."""
        if total > 0:
            self._progress_bar.configure(maximum=total, value=current)
            self._track_label.configure(text=f"{current} / {total} Lieder")
        else:
            self._progress_bar.configure(value=0)
            self._track_label.configure(text="")

    def _update_progress_threadsafe(self, current: int, total: int) -> None:
        """Thread-safe wrapper — schedules progress update on the main thread."""
        self.root.after(0, lambda: self._update_progress(current, total))

    # ------------------------------------------------------------------
    # Help window
    # ------------------------------------------------------------------

    def _show_help(self) -> None:
        HelpWindow(self.root)

    def _log(self, message: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert(END, message + "\n")
        self.log_text.see(END)
        self.log_text.configure(state="disabled")

    def _log_threadsafe(self, message: str) -> None:
        self.root.after(0, lambda: self._log(message))


# ---------------------------------------------------------------------------
# Help window
# ---------------------------------------------------------------------------

_HELP_TEXT = """\
╔══════════════════════════════════════════════════════════════════╗
║         ClassyDL – Schritt-für-Schritt-Anleitung                ║
╚══════════════════════════════════════════════════════════════════╝

Diese Anleitung erklärt, wie Sie ein Lied, ein Video oder eine
ganze Playlist herunterladen können – auch wenn Sie das noch nie
gemacht haben.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎵  EIN EINZELNES LIED ODER VIDEO HERUNTERLADEN
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Schritt 1 – YouTube öffnen und Lied suchen
  ▶  Öffnen Sie YouTube in Ihrem Browser (z. B. Chrome oder Firefox)
     oder in der YouTube-App auf Ihrem Smartphone oder Tablet.
  🔍 Geben Sie den Lied- oder Videotitel in die Suchleiste ein,
     z. B. „Beethoven Mondscheinsonate", und drücken Sie Enter.
  ▶  Klicken Sie auf das gewünschte Video in der Ergebnisliste.

Schritt 2 – Den Link kopieren
  ┌─────────────────────────────────────────────────────────────┐
  │  💻 AM PC (Browser):                                        │
  │     • Klicken Sie einmal oben in die Adressleiste.          │
  │       Der Link wird blau markiert.                          │
  │     • Drücken Sie gleichzeitig  Strg  +  C                  │
  │       (oder rechte Maustaste → „Kopieren").                  │
  ├─────────────────────────────────────────────────────────────┤
  │  📱 AUF DEM SMARTPHONE / TABLET:                            │
  │     • Tippen Sie unter dem Video auf das Symbol  📤 Teilen  │
  │     • Wählen Sie dann „Link kopieren"                       │
  │     • Der Link ist jetzt unsichtbar gespeichert             │
  │       (in der sog. Zwischenablage).                         │
  └─────────────────────────────────────────────────────────────┘

Schritt 3 – Zurück zu ClassyDL wechseln
  📲 Wechseln Sie zurück zu dieser App (ClassyDL).
     Falls die App minimiert war, klicken Sie unten in der Taskleiste
     auf das ClassyDL-Symbol.

Schritt 4 – Den Link einfügen
  ┌─────────────────────────────────────────────────────────────┐
  │  Möglichkeit A – Schaltfläche nutzen (empfohlen):           │
  │     Klicken Sie auf die Schaltfläche  [ Paste Clipboard ]   │
  │     → Der Link wird automatisch in das Feld eingefügt. ✅   │
  ├─────────────────────────────────────────────────────────────┤
  │  Möglichkeit B – Manuell einfügen:                          │
  │     • Klicken Sie einmal in das Feld neben dem Wort „Link". │
  │     💻 AM PC: Drücken Sie  Strg  +  V                       │
  │     📱 AUF DEM SMARTPHONE:                                  │
  │        Halten Sie das Feld etwas länger gedrückt            │
  │        → Ein kleines Menü erscheint                         │
  │        → Tippen Sie auf  „Einfügen"  📋                     │
  └─────────────────────────────────────────────────────────────┘

Schritt 5 – Optionen wählen (falls gewünscht)
  ⚙️  Nur die Musik ohne Video herunterladen?
       → Setzen Sie ein Häkchen bei  [✓ Audio only (MP3 320k)]

Schritt 6 – Download starten
  ▶️  Klicken Sie auf die Schaltfläche  [ Download Link ]
      • Der Fortschrittsbalken füllt sich und zeigt an,
        wie weit der Download ist.
      • Wenn alles fertig ist, erscheint ein kleines Fenster:
        „Finished – Downloaded 1/1 link(s) successfully."


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎶  EINE GANZE PLAYLIST HERUNTERLADEN (z. B. 61 Lieder auf einmal)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Schritt 1 – Playlist auf YouTube öffnen
  ▶  Suchen Sie auf YouTube nach einer Playlist oder öffnen Sie eine,
     die Sie bereits kennen (z. B. eine eigene gespeicherte Playlist).
  ▶  Klicken Sie auf den Playlist-Titel (NICHT auf ein einzelnes Video),
     sodass Sie die Übersichtsseite der Playlist sehen.

Schritt 2 – Playlist-Link kopieren (wie oben in Schritt 2 beschrieben)
  💡 Tipp: Der Link einer Playlist enthält meist den Text „playlist"
     oder „list=PL…", z. B.:
     https://www.youtube.com/watch?v=…&list=PLxxx…

Schritt 3 – Link in ClassyDL einfügen (wie Schritt 4 oben)

Schritt 4 – Playlist-Modus aktivieren
  ☑  Setzen Sie ein Häkchen bei  [✓ Playlist mode]
     Dadurch werden ALLE Lieder der Playlist heruntergeladen.

Schritt 5 – Workers (parallele Downloads) einstellen
  🔢 Im Feld „Workers" steht standardmäßig „3".
     Das bedeutet: 3 Lieder werden gleichzeitig heruntergeladen.
     → Mehr Workers = schneller, aber mehr Internetbelastung.
     → Belassen Sie es bei 3, wenn Sie unsicher sind.

Schritt 6 – Download starten
  ▶️  Klicken Sie auf  [ Download Link ]
      • Die App liest zunächst die Playlist aus (kurze Wartezeit).
      • Dann startet der Download.
      • Der Fortschrittsbalken und die Anzeige  „X / Y Lieder"
        zeigen Ihnen, wie viele Lieder bereits fertig sind.
        Beispiel: „18 / 61 Lieder" = 18 von 61 Liedern heruntergeladen.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
❓  HÄUFIGE FRAGEN
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

F: Wo finde ich meine heruntergeladenen Dateien?
A: Das Feld „Output folder" zeigt den Speicherort.
   Mit der Schaltfläche [ Browse ] können Sie einen anderen
   Ordner auswählen. Standard ist Ihr Musik- bzw. Videoordner.

F: Was ist der Unterschied zwischen „Audio only" und normalem Download?
A: „Audio only" speichert nur den Ton als MP3-Datei (ideal für Musik).
   Ohne dieses Häkchen wird das komplette Video heruntergeladen.

F: Was tun, wenn der Download fehlschlägt?
A: • Überprüfen Sie Ihre Internetverbindung.
   • Vergewissern Sie sich, dass der Link vollständig kopiert wurde.
   • Manche Videos sind durch Altersbeschränkungen gesperrt –
     versuchen Sie es mit dem Feld „Cookies browser"
     (z. B. „chrome" eingeben, falls Sie in Chrome eingeloggt sind).

F: Kann ich mehrere einzelne Links gleichzeitig herunterladen?
A: Ja! Nutzen Sie den Bereich „Site Scraper" weiter unten,
   um von einer Webseite mehrere Links auf einmal zu finden
   und dann mit „Download Selected" oder „Download All Found"
   herunterzuladen. Auch hier laufen bis zu X Worker parallel.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""


class HelpWindow:
    """Separate Tkinter-Fenster mit einer scrollbaren Schritt-für-Schritt-Anleitung."""

    def __init__(self, parent: Tk) -> None:
        win = Toplevel(parent)
        win.title("ClassyDL – Anleitung")
        win.geometry("740x600")
        win.resizable(True, True)
        win.columnconfigure(0, weight=1)
        win.rowconfigure(0, weight=1)

        text = ScrolledText(win, wrap="word", font=("Consolas", 10), state="normal")
        text.grid(row=0, column=0, sticky="nsew", padx=10, pady=(10, 5))
        text.insert("1.0", _HELP_TEXT)
        text.configure(state="disabled")

        close_btn = ttk.Button(win, text="Schließen", command=win.destroy)
        close_btn.grid(row=1, column=0, pady=(0, 10))

        win.grab_set()
        win.focus_set()


def _extract_playlist_entries(url: str, cookies_from_browser: str | None = None) -> list[LinkEntry]:
    """Use yt-dlp's flat-playlist extraction to get individual item URLs.

    Returns a list of LinkEntry objects (one per playlist item).  Falls back to
    a single-entry list containing the original URL if the URL is not a playlist
    or if extraction fails, so callers can always treat the result as a batch.
    """
    ydl_opts: dict[str, object] = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,  # don't download, just list entries
        "skip_download": True,
    }
    if cookies_from_browser:
        ydl_opts["cookiesfrombrowser"] = (cookies_from_browser, None, None, None)

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    if not info:
        return [LinkEntry(url=url)]

    entries_raw = info.get("entries")
    if not entries_raw:
        # Single video, not a playlist
        return [LinkEntry(url=url)]

    result: list[LinkEntry] = []
    for entry in entries_raw:
        if not entry:
            continue
        item_url: str | None = (
            entry.get("url")
            or entry.get("webpage_url")
        )
        if not item_url:
            # Reconstruct URL from id if possible
            eid = entry.get("id")
            ie_key = str(entry.get("ie_key") or "").lower()
            if eid and ("youtube" in ie_key or "youtube" in url.lower()):
                item_url = f"https://www.youtube.com/watch?v={eid}"
        if item_url:
            result.append(LinkEntry(url=item_url))

    return result if result else [LinkEntry(url=url)]



    headers = {"User-Agent": DEFAULT_USER_AGENT}
    with requests.get(site_url, headers=headers, timeout=30, allow_redirects=True) as response:
        response.raise_for_status()
        content_type = response.headers.get("Content-Type", "").lower()
        if "html" not in content_type:
            raise RuntimeError("Website response is not HTML.")
        base_url = response.url
        html = response.text

    soup = BeautifulSoup(html, "html.parser")
    links: list[LinkEntry] = []

    for tag in soup.find_all(["a", "link", "video", "source"]):
        href = tag.get("href") or tag.get("src")
        if not href:
            continue
        absolute = urljoin(base_url, href.strip())
        links.append(LinkEntry(url=absolute, referer=base_url))

    for media_url in extract_media_candidates(base_url, html):
        links.append(LinkEntry(url=media_url, referer=base_url))

    unique = _dedupe_links(links)
    filtered = _filter_links(
        unique,
        root_url=base_url,
        same_domain_only=same_domain_only,
        likely_video_only=likely_video_only,
    )
    ranked = sorted(filtered, key=lambda entry: _link_rank(entry.url))
    return ranked[:MAX_DISCOVERED_LINKS]


def _dedupe_links(entries: list[LinkEntry]) -> list[LinkEntry]:
    out: list[LinkEntry] = []
    seen: set[str] = set()
    for entry in entries:
        cleaned = _canonicalize_url(entry.url)
        if not cleaned:
            continue
        if cleaned in seen:
            continue
        seen.add(cleaned)
        out.append(LinkEntry(url=cleaned, referer=entry.referer))
    return out


def _filter_links(
    entries: list[LinkEntry],
    root_url: str,
    same_domain_only: bool,
    likely_video_only: bool,
) -> list[LinkEntry]:
    root_host = _normalized_host(root_url)
    filtered: list[LinkEntry] = []
    for entry in entries:
        parsed = urlparse(entry.url)
        if parsed.scheme not in {"http", "https"}:
            continue
        if same_domain_only and root_host and not _same_site(root_host, parsed.netloc.lower()):
            continue
        if likely_video_only and not _looks_like_video_link(entry.url):
            continue
        filtered.append(entry)
    return filtered


def _same_site(root_host: str, candidate_host: str) -> bool:
    if candidate_host == root_host:
        return True
    if candidate_host.endswith("." + root_host):
        return True
    if root_host.endswith("." + candidate_host):
        return True
    return False


def _looks_like_video_link(url: str) -> bool:
    lower = url.lower()
    if is_direct_media_url(url) or is_manifest_url(url):
        return True
    return any(token in lower for token in VIDEO_HINTS)


def _link_rank(url: str) -> tuple[int, int]:
    lower = url.lower()
    if is_direct_media_url(url) or is_manifest_url(url):
        return (0, len(url))
    if any(token in lower for token in VIDEO_HINTS):
        return (1, len(url))
    return (2, len(url))


def _canonicalize_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return ""
    cleaned = parsed._replace(fragment="")
    return cleaned.geturl()


def _normalized_host(url: str) -> str:
    return urlparse(url).netloc.lower()


def _looks_like_http_url(value: str) -> bool:
    return value.startswith("http://") or value.startswith("https://")


def _parse_optional_positive_int(value: str) -> int | None:
    if not value:
        return None
    try:
        parsed = int(value)
    except ValueError:
        return None
    return parsed if parsed > 0 else None


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Launch the ClassyDL easy desktop UI.")
    parser.add_argument("-o", "--output", help="Default output directory for the UI")
    parser.add_argument(
        "-m",
        "--method",
        choices=["auto", "yt-dlp", "ffmpeg", "direct"],
        default="auto",
        help="Default download method shown in the UI",
    )
    parser.add_argument("--cookies-from-browser", help="Default cookies browser for yt-dlp downloads")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    config = load_or_create_config(resolve_paths())
    output_dir = args.output if args.output else config.default_output_dir
    run_easy_ui(
        default_output_dir=str(Path(output_dir).expanduser().resolve()),
        initial_method=args.method,
        initial_cookies_from_browser=args.cookies_from_browser,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
