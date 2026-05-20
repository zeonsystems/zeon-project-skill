#!/usr/bin/env python3
"""Emit the file map for a fresh Zeon project or a typed item.

Tries to import the official ``zeon_project_scaffold`` library; falls back to
embedded templates if not available. Output is JSON on stdout:

    [
      {"path": "skills/<name>/metadata.yaml", "content_b64": "..."},
      ...
    ]

A one-line stderr note indicates the source:

    using=library
    using=embedded

Usage:
    invoke_scaffold.py default            # full default project
    invoke_scaffold.py <kind> <name>      # one new item

    <kind> is one of: skill, workflow, world, object, canvas.
    For canvas, <name> is the workflow_id the canvas attaches to —
    the output file is ``canvas/<workflow_id>_screen.tsx``.

Exit codes:
    0 success
    2 usage error
    3 invalid name (per naming-rules.md)
    4 internal error
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path
from typing import Iterable, Iterator, Optional


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_DIR.parent
TEMPLATES_DIR = SKILL_ROOT / "templates"

# Mirrors `zeon_project_scaffold._scaffold._NAME_RE`.
NAME_RE = re.compile(r"^[a-z_][a-z0-9_-]{0,63}$")

ITEM_KINDS = ("skill", "workflow", "world", "object", "canvas")


def _emit(pairs: Iterable[tuple[str, bytes]]) -> None:
    out = [
        {"path": path, "content_b64": base64.b64encode(content).decode("ascii")}
        for path, content in pairs
    ]
    json.dump(out, sys.stdout, indent=2)
    sys.stdout.write("\n")


def _stderr(msg: str) -> None:
    sys.stderr.write(msg + "\n")


def _validate_name(name: str) -> None:
    if not NAME_RE.match(name):
        _stderr(f"invalid item name {name!r}: must match {NAME_RE.pattern}")
        raise SystemExit(3)


def _py_identifier(name: str) -> str:
    return name.replace("-", "_")


def _pascal_case(name: str) -> str:
    parts = re.split(r"[_\-]+", name)
    return "".join(p[:1].upper() + p[1:] for p in parts if p)


# ----------------------------------------------------------------------------
# Library probe + invocation
# ----------------------------------------------------------------------------


def _probe_library() -> Optional[object]:
    """Try to import ``zeon_project_scaffold._scaffold``. Returns the module on success.

    Set ``ZEON_FORCE_EMBEDDED=1`` to skip the probe entirely — useful for tests
    that want to exercise the embedded fallback even when the library is on disk.
    """
    if os.environ.get("ZEON_FORCE_EMBEDDED") == "1":
        return None

    # Direct import (already on PYTHONPATH).
    try:
        from zeon_project_scaffold import _scaffold  # type: ignore  # noqa: F401
        return _scaffold
    except ImportError:
        pass

    # Look in common locations.
    candidates: list[Path] = []

    zeon_repo = os.environ.get("ZEON_REPO")
    if zeon_repo:
        candidates.append(Path(zeon_repo) / "libraries/zeon_project_scaffold/src")

    for parent_name in ("~/code", "~/GitHub", "~/projects", "~/work"):
        parent = Path(parent_name).expanduser()
        if parent.is_dir():
            candidates.append(parent / "everything-prototype-containers/libraries/zeon_project_scaffold/src")
            candidates.append(parent / "ZeonSystems/everything-prototype-containers/libraries/zeon_project_scaffold/src")

    # Also probe neighbours of the cwd.
    cwd = Path.cwd().resolve()
    for ancestor in [cwd, *cwd.parents]:
        sibling = ancestor / "everything-prototype-containers/libraries/zeon_project_scaffold/src"
        if sibling.is_dir():
            candidates.append(sibling)

    for path in candidates:
        if not path.is_dir():
            continue
        sys.path.insert(0, str(path))
        try:
            from zeon_project_scaffold import _scaffold  # type: ignore  # noqa: F401
            return _scaffold
        except ImportError:
            sys.path.pop(0)
            continue

    return None


# ----------------------------------------------------------------------------
# Embedded templates (used when library unavailable)
# ----------------------------------------------------------------------------


def _read_template(name: str) -> str:
    return (TEMPLATES_DIR / name).read_text(encoding="utf-8")


def _format(content: str, **subs: str) -> str:
    """Replace `{key}` placeholders with values without invoking str.format
    (the JSON/YAML/Python templates contain literal braces).
    """
    for key, value in subs.items():
        content = content.replace("{" + key + "}", value)
    return content


def _now_iso() -> str:
    """Millisecond-precision UTC ISO-8601 timestamp with Z suffix.

    Matches `zeon_project_scaffold._scaffold._now_iso_ms()`.
    """
    return (
        dt.datetime.now(dt.timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def _emit_embedded_item(kind: str, name: str) -> Iterator[tuple[str, bytes]]:
    if kind == "skill":
        base = f"skills/{name}"
        py_name = _py_identifier(name)
        yield (
            f"{base}/metadata.yaml",
            _format(_read_template("skills/{name}/metadata.yaml"), name=name).encode(),
        )
        yield (
            f"{base}/robotic_code.py",
            _format(_read_template("skills/{name}/robotic_code.py"), name=name, py_name=py_name).encode(),
        )
        return

    if kind == "workflow":
        now = _now_iso()
        yield (
            f"workflows/{name}.json",
            _format(_read_template("workflows/{name}.json"), name=name, now=now).encode(),
        )
        return

    if kind == "world":
        yield (
            f"worlds/{name}/world_state.json",
            _format(_read_template("worlds/{name}/world_state.json"), name=name).encode(),
        )
        return

    if kind == "object":
        yield (
            f"objects/{name}/{name}.urdf",
            _format(_read_template("objects/{name}/{name}.urdf"), name=name).encode(),
        )
        yield (
            f"objects/{name}/{name}.object_model.yaml",
            _format(_read_template("objects/{name}/{name}.object_model.yaml"), name=name).encode(),
        )
        return

    if kind == "canvas":
        component = _pascal_case(name) + "Screen"
        yield (
            f"canvas/{name}_screen.tsx",
            _format(
                _read_template("canvas/{workflow_id}_screen.tsx"),
                workflow_id=name,
                component=component,
            ).encode(),
        )
        return

    raise SystemExit(f"unknown kind: {kind!r}")


def _emit_embedded_default_project() -> Iterator[tuple[str, bytes]]:
    """Walk the embedded ``templates/`` tree and yield every file, mirroring
    what ``zeon_project_scaffold._scaffold.iter_default_project_files`` does
    with its bundled ``templates/default/`` tree.

    Skips:
      - the meta ``templates/README.md`` (docs about the templates folder)
      - any path containing a ``{placeholder}`` segment (those are item
        templates used by :func:`_emit_embedded_item`, not part of the
        default project).
    """
    now = _now_iso()
    placeholder = re.compile(r"\{[a-z_]+\}")
    for path in sorted(TEMPLATES_DIR.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(TEMPLATES_DIR).as_posix()
        if rel == "README.md":
            continue
        if placeholder.search(rel):
            continue
        content = path.read_bytes()
        if rel == "project.json":
            content = _format(content.decode("utf-8"), now=now).encode()
        yield rel, content


# ----------------------------------------------------------------------------
# Primary path lookup (matches `zeon_project_scaffold._scaffold.primary_path_for`).
# Exposed for the skill flows that want to tell the user which file to open
# after a fresh item is created.
# ----------------------------------------------------------------------------


def primary_path_for(kind: str, name: str) -> str:
    _validate_name(name)
    if kind == "skill":
        return f"skills/{name}/robotic_code.py"
    if kind == "workflow":
        return f"workflows/{name}.json"
    if kind == "world":
        return f"worlds/{name}/world_state.json"
    if kind == "object":
        return f"objects/{name}/{name}.object_model.yaml"
    if kind == "canvas":
        return f"canvas/{name}_screen.tsx"
    raise SystemExit(f"unknown kind: {kind!r}")


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0] if __doc__ else None)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_default = sub.add_parser("default", help="emit the full default project file map")
    _ = p_default  # noqa: F841

    p_item = sub.add_parser("item", help="emit files for a typed item")
    p_item.add_argument("kind", choices=ITEM_KINDS)
    p_item.add_argument("name")

    # Backwards-compatible shorthand: invoke_scaffold.py <kind> <name>
    if argv and argv[0] in ITEM_KINDS:
        argv = ["item", *argv]
    elif argv and argv[0] == "default":
        pass
    elif not argv:
        parser.print_help(sys.stderr)
        return 2

    args = parser.parse_args(argv)

    library = _probe_library()
    use_library = library is not None
    _stderr(f"using={'library' if use_library else 'embedded'}")

    try:
        if args.cmd == "default":
            if use_library:
                raw_pairs = list(library.iter_default_project_files())  # type: ignore[attr-defined]
                # Filter Python bytecode-cache files the library accidentally
                # ships when the source tree has been imported.
                pairs = [
                    (path, content)
                    for path, content in raw_pairs
                    if "__pycache__" not in path.split("/")
                    and not path.endswith(".pyc")
                ]
            else:
                pairs = list(_emit_embedded_default_project())
        else:
            kind = args.kind
            name = args.name
            _validate_name(name)

            if use_library:
                pairs = list(library.item_template(kind, name))  # type: ignore[attr-defined]
            else:
                pairs = list(_emit_embedded_item(kind, name))
    except SystemExit:
        raise
    except Exception as exc:  # pragma: no cover
        _stderr(f"internal error: {exc}")
        return 4

    _emit(pairs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
