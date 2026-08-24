"""Select the first usable revision for one Android release line."""

from __future__ import annotations

import argparse
from pathlib import Path

from android_version_from_tag import AndroidVersion, TAG_RE, from_tag


def select_candidate(tag: str, highest_play_version_code: int) -> tuple[str, AndroidVersion]:
    """Keep a free requested tag, otherwise advance only its revision."""

    requested = from_tag(tag)
    if requested.code > highest_play_version_code:
        return tag, requested

    match = TAG_RE.fullmatch(tag)
    if match is None:
        raise ValueError("invalid release tag")
    major, minor, patch = (int(value) for value in match.groups()[:3])
    base_code = major * 1_000_000 + minor * 10_000 + patch * 100
    next_revision = highest_play_version_code - base_code + 1
    if not 0 <= next_revision <= 99:
        raise ValueError(
            f"no free revision remains on v{major}.{minor}.{patch}; "
            "choose a new release line explicitly"
        )
    selected_tag = f"v{major}.{minor}.{patch}.{next_revision}"
    return selected_tag, from_tag(selected_tag)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("tag")
    parser.add_argument("highest_play_version_code", type=int)
    parser.add_argument("--github-env", type=Path)
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args()
    try:
        tag, version = select_candidate(args.tag, args.highest_play_version_code)
    except ValueError as error:
        parser.error(str(error))

    values = {
        "release_tag": tag,
        "version_name": version.name,
        "version_code": str(version.code),
    }
    if args.github_env:
        with args.github_env.open("a", encoding="utf-8", newline="\n") as env_file:
            env_file.write(f"RELEASE_TAG={tag}\n")
            env_file.write(f"VERSION_NAME={version.name}\n")
            env_file.write(f"VERSION_CODE={version.code}\n")
    if args.github_output:
        with args.github_output.open("a", encoding="utf-8", newline="\n") as output_file:
            for key, value in values.items():
                output_file.write(f"{key}={value}\n")
    print(f"releaseTag={tag} versionName={version.name} versionCode={version.code}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
