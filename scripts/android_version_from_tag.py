"""Derive a monotone Google Play versionCode from a release tag."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re


TAG_RE = re.compile(r"^v(\d+)\.(\d+)\.(\d+)(?:\.(\d+))?$")
MAX_ANDROID_VERSION_CODE = 2_100_000_000


@dataclass(frozen=True)
class AndroidVersion:
    name: str
    code: int


def from_tag(tag: str) -> AndroidVersion:
    """Accept vMAJOR.MINOR.PATCH[.REVISION] and preserve numeric ordering."""

    match = TAG_RE.fullmatch(tag)
    if not match:
        raise ValueError(
            "release version must match vMAJOR.MINOR.PATCH[.REVISION]"
        )
    major, minor, patch = (int(value) for value in match.groups()[:3])
    revision = int(match.group(4) or 0)
    if any(value > 99 for value in (minor, patch, revision)):
        raise ValueError("MINOR, PATCH and REVISION must each be between 0 and 99")

    # Two decimal places per component. This deliberately moves the historical
    # 0.8.4 code 804 to 80400; 0.8.4.1 is 80401 and 0.8.5 is 80500, so both
    # hotfixes and subsequent normal releases remain strictly monotone.
    code = major * 1_000_000 + minor * 10_000 + patch * 100 + revision
    if not 1 <= code <= MAX_ANDROID_VERSION_CODE:
        raise ValueError(
            f"derived versionCode {code} is outside Android's supported range"
        )
    return AndroidVersion(name=tag.removeprefix("v"), code=code)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("tag")
    parser.add_argument("--github-env", type=Path)
    args = parser.parse_args()

    try:
        version = from_tag(args.tag)
    except ValueError as error:
        parser.error(str(error))

    if args.github_env:
        with args.github_env.open("a", encoding="utf-8", newline="\n") as env_file:
            env_file.write(f"VERSION_NAME={version.name}\n")
            env_file.write(f"VERSION_CODE={version.code}\n")
    print(f"versionName={version.name} versionCode={version.code}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
