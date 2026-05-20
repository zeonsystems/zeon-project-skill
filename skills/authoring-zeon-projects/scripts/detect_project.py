#!/usr/bin/env python3
"""Detect whether a directory is a Zeon project, an empty target, or something else.

Usage:
    python3 detect_project.py [<dir>]

If <dir> is omitted, uses the current working directory.

Output (stdout, one of):
    create        — the directory is empty or has no project.json (safe to scaffold).
    develop       — the directory has project.json AND at least one standard subfolder.
    project_json_only — has project.json but no subfolders (broken or in-progress create).
    foreign       — has files but no project.json (NOT a Zeon project; refuse).

Exit code:
    0 on success (any of the four above).
    2 on usage error.
"""

from __future__ import annotations

import sys
from pathlib import Path


STANDARD_SUBFOLDERS = (
    "canvas",
    "data",
    "docs",
    "objects",
    "scripts",
    "skills",
    "workflows",
    "worlds",
)


def classify(root: Path) -> str:
    if not root.is_dir():
        raise SystemExit(f"detect_project: not a directory: {root}")

    project_json = root / "project.json"
    has_project = project_json.is_file()

    present_subfolders = [name for name in STANDARD_SUBFOLDERS if (root / name).is_dir()]

    # Walk the directory's top level to see what else is there.
    visible_entries = [
        p for p in root.iterdir() if not p.name.startswith(".")
    ]

    if has_project:
        if present_subfolders:
            return "develop"
        return "project_json_only"

    # No project.json. Is the directory effectively empty?
    if not visible_entries:
        return "create"

    # There are files but no project.json. Don't proceed.
    return "foreign"


def main(argv: list[str]) -> int:
    if len(argv) > 2:
        print("usage: detect_project.py [<dir>]", file=sys.stderr)
        return 2

    target = Path(argv[1]) if len(argv) == 2 else Path.cwd()
    target = target.resolve()
    print(classify(target))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
