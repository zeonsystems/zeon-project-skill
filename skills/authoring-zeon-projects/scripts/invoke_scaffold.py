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

    <kind> is one of: skill, workflow, world, object.

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

ITEM_KINDS = ("skill", "workflow", "world", "object")


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


# ----------------------------------------------------------------------------
# Library probe + invocation
# ----------------------------------------------------------------------------


def _probe_library() -> Optional[object]:
    """Try to import ``zeon_project_scaffold._scaffold``. Returns the module on success."""
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
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


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
        yield (
            f"{base}/modules.py",
            _read_template("skills/{name}/modules.py").encode(),
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

    raise SystemExit(f"unknown kind: {kind!r}")


def _emit_embedded_default_project() -> Iterator[tuple[str, bytes]]:
    yield "project.json", _read_template("project.json").encode()
    # Empty stubs for the standard subfolders. The skill prompts the user to
    # populate them.
    for folder in ("canvas", "data", "docs", "objects", "scripts", "skills", "workflows", "worlds"):
        yield f"{folder}/.gitkeep", b""
    yield "canvas/README.md", _read_template("canvas/README.md").encode()


# ----------------------------------------------------------------------------
# ExecutionGraph -> Workflow format converter
# ----------------------------------------------------------------------------
#
# The bundled scaffold library currently emits workflow files in the older
# ExecutionGraph shape (graph_id, node_type, string condition, e<n> edge ids).
# The gateway loader expects the on-disk Workflow shape (workflow_id, type,
# nested condition, edge_<n>). This function converts in-place so any workflow
# file emitted by the library lands on disk in the format the runtime accepts.


_CONDITION_STRING_TO_OBJECT = {
    "unconditional": {"type": "default"},
    "on_success": {"type": "on_success"},
    "on_failure": {"type": "on_failure"},
    "if_true": {"type": "if_true"},
    "if_false": {"type": "if_false"},
    "loop_body": {"type": "loop_continue"},
    "loop_exit": {"type": "loop_complete"},
    "retry_body": {"type": "on_success"},
    "retry_exhausted": {"type": "on_failure"},
}


def _convert_workflow_eg_to_disk(data: dict, fallback_id: str) -> dict:
    """Rewrite an ExecutionGraph-shaped workflow dict to the on-disk Workflow shape.

    Idempotent: if `data` already looks like Workflow (workflow_id, type, etc.),
    only the missing required fields are added.
    """
    out: dict = {}

    workflow_id = data.get("workflow_id") or data.get("graph_id") or fallback_id
    if not isinstance(workflow_id, str) or not workflow_id:
        workflow_id = fallback_id
    out["workflow_id"] = workflow_id
    out["name"] = data.get("name", workflow_id)
    if "description" in data:
        out["description"] = data["description"]
    out["version"] = data.get("version", "1.0.0")
    out["author"] = data.get("author", "user")
    now = _now_iso()
    out["created_at"] = data.get("created_at", now)
    out["updated_at"] = data.get("updated_at", now)
    out["simulation_validated"] = bool(data.get("simulation_validated", False))
    out["simulation_result"] = data.get("simulation_result")
    out["last_simulation_timestamp"] = data.get("last_simulation_timestamp")
    out["objects"] = data.get("objects") if isinstance(data.get("objects"), list) else []
    if "inputs" in data:
        out["inputs"] = data["inputs"]
    if "canvas_ui" in data:
        out["canvas_ui"] = data["canvas_ui"]

    nodes_out: list[dict] = []
    for node in data.get("nodes", []):
        if not isinstance(node, dict):
            continue
        n: dict = {}
        n["node_id"] = node.get("node_id")
        n["type"] = node.get("type") or node.get("node_type")
        meta = node.get("metadata") or {}
        if isinstance(meta, dict) and "label" in meta:
            n["label"] = meta["label"]
        elif "label" in node:
            n["label"] = node["label"]
        else:
            n["label"] = n["node_id"] or ""
        for key in ("description", "skill_id", "parameters", "retry", "loop", "condition"):
            if key in node and node[key] is not None:
                n[key] = node[key]
        nodes_out.append(n)
    out["nodes"] = nodes_out

    edges_out: list[dict] = []
    for i, edge in enumerate(data.get("edges", [])):
        if not isinstance(edge, dict):
            continue
        e: dict = {}
        eid = edge.get("edge_id")
        if not (isinstance(eid, str) and re.match(r"^edge_\d+$", eid)):
            e["edge_id"] = f"edge_{i}"
        else:
            e["edge_id"] = eid
        e["from_node"] = edge.get("from_node")
        e["to_node"] = edge.get("to_node")
        cond = edge.get("condition")
        if isinstance(cond, dict):
            e["condition"] = cond
        elif isinstance(cond, str):
            e["condition"] = _CONDITION_STRING_TO_OBJECT.get(cond, {"type": cond})
        else:
            e["condition"] = {"type": "on_success"}
        edges_out.append(e)
    out["edges"] = edges_out

    return out


def _maybe_convert_library_workflow(path: str, content: bytes) -> bytes:
    """If `path` is a workflow JSON, convert ExecutionGraph shape -> on-disk Workflow shape."""
    if not path.startswith("workflows/") or not path.endswith(".json"):
        return content
    try:
        data = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return content
    if not isinstance(data, dict):
        return content
    fallback_id = Path(path).stem
    converted = _convert_workflow_eg_to_disk(data, fallback_id)
    return (json.dumps(converted, indent=2) + "\n").encode("utf-8")


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
                pairs = []
                converted_any = False
                dropped_legacy = False
                for path, content in raw_pairs:
                    # `inputs/` is deprecated and absent from current projects;
                    # filter it out so the library's stale tree matches today's
                    # 8-folder layout.
                    if path == "inputs" or path.startswith("inputs/"):
                        dropped_legacy = True
                        continue
                    new_content = _maybe_convert_library_workflow(path, content)
                    if new_content is not content:
                        converted_any = True
                    pairs.append((path, new_content))
                # Ensure the optional standard folders exist (the library tree
                # doesn't include them today, but `project.json` consumers
                # expect them present).
                present_top = {p.split("/", 1)[0] for p, _ in pairs}
                for folder in ("data", "docs", "scripts"):
                    if folder not in present_top:
                        pairs.append((f"{folder}/.gitkeep", b""))
                if converted_any:
                    _stderr("note=converted library workflow file(s) to canonical on-disk format")
                if dropped_legacy:
                    _stderr("note=dropped legacy inputs/ folder from library output")
            else:
                pairs = list(_emit_embedded_default_project())
        else:
            kind = args.kind
            name = args.name
            _validate_name(name)

            if use_library:
                pairs = list(
                    library.item_template(kind, name)  # type: ignore[attr-defined]
                )
                # The library's workflow template uses the older ExecutionGraph
                # shape (graph_id/node_type/string-condition) — substitute with
                # the canonical on-disk Workflow format from our embedded
                # template. See templates/README.md for context.
                if kind == "workflow":
                    pairs = list(_emit_embedded_item(kind, name))
                    _stderr("note=overrode library workflow template with embedded (canonical on-disk format)")
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
