#!/usr/bin/env python3
"""Print a complete map of a Zeon project in one pass.

Usage:
    python3 inspect.py [<project_root>] [--json]

Output (text mode):
  - project.json manifest summary
  - every skill with its DERIVED parameter schema (from the function
    signature, exactly as the platform derives it)
  - every workflow: inputs, then the graph as an edge list
  - every world: instances (name, type, xyz)
  - every object: its anchors
  - every canvas and which workflow references it

Run this first in an unfamiliar project — it replaces reading dozens of
files to build the mental model. Pure stdlib; PyYAML optional (skill
descriptions/tags and object anchors are unavailable without it; worlds
and workflows are unaffected).
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path
from typing import Any, Optional

try:
    import yaml as _yaml  # type: ignore
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

ANNOTATION_TYPE_MAP = {
    "SkillObject": "object",
    "str": "string", "bool": "boolean", "int": "int", "float": "float",
    "list": "array", "List": "array", "tuple": "array", "Tuple": "array",
    "Sequence": "array",
    "dict": "object", "Dict": "object", "Mapping": "object",
}


def _try_yaml(path: Path) -> Optional[Any]:
    if not HAS_YAML:
        return None
    try:
        return _yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _try_json(path: Path) -> Optional[Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _annotation_base(node: ast.expr) -> Optional[str]:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Subscript):
        base = _annotation_base(node.value)
        if base in {"Optional", "Union"}:
            inner = node.slice
            elts = inner.elts if isinstance(inner, ast.Tuple) else [inner]
            for e in elts:
                if not (isinstance(e, ast.Constant) and e.value is None):
                    return _annotation_base(e)
        return base
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        for side in (node.left, node.right):
            if not (isinstance(side, ast.Constant) and side.value is None):
                return _annotation_base(side)
    return None


def _derive_param_type(annotation, default) -> str:
    """Mirror the platform's signature→type derivation."""
    if annotation is not None:
        base = _annotation_base(annotation)
        if base in ANNOTATION_TYPE_MAP:
            return ANNOTATION_TYPE_MAP[base]
    if default is not None:
        try:
            v = ast.literal_eval(default)
            return {bool: "boolean", int: "int", float: "float", str: "string",
                    list: "array", tuple: "array", dict: "object"}.get(type(v), "string")
        except (ValueError, SyntaxError):
            pass
    return "string"


def inspect_skills(root: Path) -> list[dict]:
    out = []
    skills_dir = root / "skills"
    if not skills_dir.is_dir():
        return out
    for d in sorted(p for p in skills_dir.iterdir() if p.is_dir() and not p.name.startswith(".")):
        if d.name == "__pycache__":
            continue
        entry: dict = {"skill_id": d.name, "parameters": [], "description": "", "tags": []}
        meta = _try_yaml(d / "metadata.yaml")
        if isinstance(meta, dict):
            entry["description"] = meta.get("description") or ""
            entry["tags"] = meta.get("tags") or []
        code = d / "robotic_code.py"
        if code.is_file():
            try:
                tree = ast.parse(code.read_text(encoding="utf-8"))
            except SyntaxError:
                entry["error"] = "syntax error in robotic_code.py"
                out.append(entry)
                continue
            fn_name = d.name.replace("-", "_")
            for node in tree.body:
                if isinstance(node, ast.FunctionDef) and node.name == fn_name:
                    a = node.args
                    pos = a.posonlyargs + a.args
                    defaults: list = [None] * (len(pos) - len(a.defaults)) + list(a.defaults)
                    for arg, dflt in zip(pos, defaults):
                        p = {
                            "name": arg.arg,
                            "type": _derive_param_type(arg.annotation, dflt),
                            "required": dflt is None,
                        }
                        if dflt is not None:
                            try:
                                p["default"] = ast.literal_eval(dflt)
                            except (ValueError, SyntaxError):
                                p["default"] = ast.unparse(dflt)
                                p["default_unresolved"] = True
                        entry["parameters"].append(p)
        out.append(entry)
    return out


def inspect_workflows(root: Path) -> list[dict]:
    out = []
    wdir = root / "workflows"
    if not wdir.is_dir():
        return out
    for path in sorted(wdir.glob("*.json")):
        wf = _try_json(path)
        if not isinstance(wf, dict):
            out.append({"file": path.name, "error": "invalid JSON"})
            continue
        nodes = {n.get("node_id"): n for n in wf.get("nodes", []) if isinstance(n, dict)}
        out.append({
            "file": path.name,
            "workflow_id": wf.get("workflow_id"),
            "name": wf.get("name"),
            "inputs": [
                {k: v for k, v in i.items()
                 if k in {"name", "type", "is_array", "isArray", "defaultValue", "description"}}
                for i in wf.get("inputs", []) if isinstance(i, dict)
            ],
            "nodes": [
                {"node_id": nid,
                 "type": n.get("type"),
                 **({"skill_id": n.get("skill_id")} if n.get("type") == "skill" else {}),
                 **({"parameters": n.get("parameters")} if n.get("type") == "skill" else {})}
                for nid, n in nodes.items()
            ],
            "edges": [
                {"from": e.get("from_node"), "to": e.get("to_node"),
                 "condition": (e.get("condition") or {}).get("type")}
                for e in wf.get("edges", []) if isinstance(e, dict)
            ],
            "canvas": (wf.get("canvas_ui") or {}).get("source_ref"),
        })
    return out


def inspect_worlds(root: Path) -> list[dict]:
    out = []
    wdir = root / "worlds"
    if not wdir.is_dir():
        return out
    for d in sorted(p for p in wdir.iterdir() if p.is_dir() and not p.name.startswith(".")):
        state = _try_json(d / "world_state.json")
        entry: dict = {"world_id": d.name, "instances": []}
        if isinstance(state, dict):
            entry["version"] = state.get("version")
            objs = state.get("objects")
            objs = objs if isinstance(objs, dict) else {}
            for key, obj in objs.items():
                if not isinstance(obj, dict):
                    continue
                meta = obj.get("metadata")
                meta = meta if isinstance(meta, dict) else {}
                geom = obj.get("geometry")
                geom = geom if isinstance(geom, dict) else {}
                inst = {"key": key}
                if meta.get("name"):
                    inst["name"] = meta["name"]
                if meta.get("type"):
                    inst["type"] = meta["type"]
                elif geom.get("type") and geom.get("type") != "articulated":
                    inst["primitive"] = geom["type"]
                mount = obj.get("mount")
                mount = mount if isinstance(mount, dict) else {}
                pose = mount.get("world_P_body_fixed")
                pose = pose if isinstance(pose, dict) else {}
                if isinstance(pose.get("xyz"), list):
                    try:
                        inst["xyz"] = [round(float(x), 3) for x in pose["xyz"]]
                    except (TypeError, ValueError):
                        pass
                entry["instances"].append(inst)
        if (d / "live_state.yaml").is_file():
            entry["has_live_state"] = True
        out.append(entry)
    return out


def inspect_objects(root: Path) -> list[dict]:
    out = []
    odir = root / "objects"
    if not odir.is_dir():
        return out
    for d in sorted(p for p in odir.iterdir() if p.is_dir() and not p.name.startswith(".")):
        model = _try_yaml(d / f"{d.name}.object_model.yaml")
        entry: dict = {"object": d.name, "anchors": []}
        if isinstance(model, dict):
            entry["anchors"] = sorted((model.get("anchors") or {}).keys())
            arts = model.get("articulations") or {}
            joints = set()
            for art in arts.values():
                if isinstance(art, dict):
                    joints |= set((art.get("joints") or {}).keys())
            if joints:
                entry["joints"] = sorted(joints)
        out.append(entry)
    return out


def run(root: Path) -> dict:
    project = _try_json(root / "project.json")
    if not isinstance(project, dict):
        project = {}
    return {
        "root": str(root),
        "project": {k: project.get(k) for k in
                    ("name", "description", "active_workflow", "active_world")},
        "skills": inspect_skills(root),
        "workflows": inspect_workflows(root),
        "worlds": inspect_worlds(root),
        "objects": inspect_objects(root),
        "canvases": sorted(p.name for p in (root / "canvas").glob("*.tsx"))
        if (root / "canvas").is_dir() else [],
        "input_presets": inspect_presets(root),
    }


def inspect_presets(root: Path) -> list[dict]:
    out = []
    idir = root / "inputs"
    if not idir.is_dir():
        return out
    for p in sorted(idir.glob("*.json")):
        entry: dict = {"id": p.stem}
        data = _try_json(p)
        if isinstance(data, dict):
            entry["label"] = data.get("_label")
            entry["keys"] = sorted(k for k in data if k != "_label")
        else:
            entry["error"] = "unparseable"
        out.append(entry)
    return out


def _fmt_params(params: list[dict]) -> str:
    bits = []
    for p in params:
        s = f"{p['name']}: {p['type']}"
        if not p["required"]:
            s += f" = {p.get('default')!r}"
        bits.append(s)
    return ", ".join(bits)


def print_text(data: dict) -> None:
    pj = data["project"]
    print(f"# {pj.get('name') or '(unnamed project)'}  —  {data['root']}")
    print(f"  active_workflow: {pj.get('active_workflow')}   active_world: {pj.get('active_world')}")

    print(f"\n## Skills ({len(data['skills'])})")
    for s in data["skills"]:
        print(f"  {s['skill_id']}({_fmt_params(s.get('parameters', []))})")
        if s.get("description"):
            print(f"      {s['description']}")

    print(f"\n## Workflows ({len(data['workflows'])})")
    for w in data["workflows"]:
        if w.get("error"):
            print(f"  {w['file']}  ERROR: {w['error']}")
            continue
        print(f"  {w.get('workflow_id') or w['file']}  ({w['file']})"
              + (f"  canvas={w['canvas']}" if w.get("canvas") else ""))
        for i in w.get("inputs", []):
            arr = "[]" if (i.get("is_array") or i.get("isArray")) else ""
            dv = f" = {i['defaultValue']!r}" if "defaultValue" in i else ""
            print(f"      input {i.get('name')}: {i.get('type')}{arr}{dv}")
        for e in w.get("edges", []):
            node = next((n for n in w["nodes"] if n["node_id"] == e["from"]), {})
            sid = f" [{node['skill_id']}]" if node.get("skill_id") else ""
            print(f"      {e['from']}{sid} --{e['condition']}--> {e['to']}")

    print(f"\n## Worlds ({len(data['worlds'])})")
    for wd in data["worlds"]:
        n_real = sum(1 for i in wd["instances"] if "type" in i)
        print(f"  {wd['world_id']}  (v{wd.get('version')}, {n_real} object instances"
              + (", live_state.yaml" if wd.get("has_live_state") else "") + ")")
        for i in wd["instances"]:
            if "type" in i:
                nm = i.get("name") or i["key"]
                xyz = f"  @ {i['xyz']}" if "xyz" in i else ""
                print(f"      {nm}  ({i['type']}){xyz}")

    print(f"\n## Objects ({len(data['objects'])})")
    yaml_note = "(PyYAML not installed)" if not HAS_YAML else "(yaml unreadable)"
    for o in data["objects"]:
        joints = f"  joints: {', '.join(o['joints'])}" if o.get("joints") else ""
        print(f"  {o['object']}  anchors: {', '.join(o['anchors']) or yaml_note}{joints}")

    if data["canvases"]:
        print(f"\n## Canvases ({len(data['canvases'])})")
        for c in data["canvases"]:
            print(f"  canvas/{c}")

    if data["input_presets"]:
        print(f"\n## Input presets ({len(data['input_presets'])})")
        for p in data["input_presets"]:
            if p.get("error"):
                print(f"  inputs/{p['id']}.json  ERROR: {p['error']}")
            else:
                print(f"  {p['id']}  ({p.get('label')})  keys: {', '.join(p.get('keys', []))}")


def main(argv: list[str]) -> int:
    args = [a for a in argv[1:] if a != "--json"]
    as_json = "--json" in argv[1:]
    if len(args) > 1:
        print("usage: inspect.py [<project_root>] [--json]", file=sys.stderr)
        return 2
    root = (Path(args[0]) if args else Path.cwd()).resolve()
    if not (root / "project.json").is_file():
        print(f"no project.json in {root}", file=sys.stderr)
        return 2
    data = run(root)
    if as_json:
        json.dump(data, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        print_text(data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
