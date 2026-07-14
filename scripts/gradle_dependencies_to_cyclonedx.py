"""Convert a Gradle dependency report into a minimal CycloneDX 1.6 SBOM."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


PATTERN = re.compile(r"(?:\+---|\\---)\s+([^:\s]+):([^:\s]+):([^\s]+)")


def main() -> int:
    source, target = map(Path, sys.argv[1:3])
    components = {}
    for group, name, version in PATTERN.findall(source.read_text(encoding="utf-8", errors="replace")):
        version = version.rstrip(" (*)")
        key = (group, name, version)
        components[key] = {
            "type": "library",
            "group": group,
            "name": name,
            "version": version,
            "purl": f"pkg:maven/{group}/{name}@{version}",
        }
    document = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "version": 1,
        "metadata": {"component": {"type": "application", "name": "DownloadThat-Android"}},
        "components": list(components.values()),
    }
    target.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
