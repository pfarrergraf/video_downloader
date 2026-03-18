from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from video_downloader.conversion import collect_convertible_files, convert_file_to_mp4


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Convert downloaded videos such as .webm into high-quality .mp4 files.")
    parser.add_argument("paths", nargs="+", help="One or more video files or folders to convert")
    parser.add_argument("-o", "--output-dir", help="Optional destination directory for the converted MP4 files")
    parser.add_argument("--recursive", action="store_true", help="Recurse into subfolders when a folder is provided")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing MP4 files")
    parser.add_argument("--delete-source", action="store_true", help="Delete the source file after a successful conversion")
    parser.add_argument("--ffmpeg-binary", default="ffmpeg", help="ffmpeg executable name or path")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else None

    try:
        sources = collect_convertible_files([Path(item) for item in args.paths], recursive=args.recursive)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if not sources:
        print("No convertible video files found.", file=sys.stderr)
        return 2

    converted = 0
    failed = 0
    for source in sources:
        try:
            target = convert_file_to_mp4(
                source,
                output_dir=output_dir,
                ffmpeg_binary=args.ffmpeg_binary,
                overwrite=args.overwrite,
                delete_source=args.delete_source,
            )
            converted += 1
            print(f"OK   {source} -> {target}")
        except Exception as exc:
            failed += 1
            print(f"FAIL {source}: {exc}", file=sys.stderr)

    print(f"Converted: {converted}, failed: {failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
