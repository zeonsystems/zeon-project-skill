#!/usr/bin/env python3
"""Validate a Zeon project's structure and cross-references.

Usage:
    python3 validate_project.py [<project_root>]

Defaults to the current working directory.

Output: JSON on stdout. Shape:

    {
      "ok": bool,
      "using": "library" | "embedded",   # whether protocol_schema was available
      "errors":   [{"where": "...", "msg": "..."}],
      "warnings": [{"where": "...", "msg": "..."}],
      "summary": {
        "skills":    int,
        "workflows": int,
        "worlds":    int,
        "objects":   int,
        "canvases":  int
      }
    }

Exit codes:
    0 = ok (no errors; warnings allowed).
    1 = errors found.
    2 = usage error / project root invalid.
"""

from __future__ import annotations

import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Optional


# ----------------------------------------------------------------------------
# Regex
# ----------------------------------------------------------------------------

NAME_RE = re.compile(r"^[a-z_][a-z0-9_-]{0,63}$")
SKILL_ID_RE = re.compile(r"^[a-z0-9_]+$")
WORKFLOW_ID_RE = re.compile(r"^[a-z0-9_]+$")
NODE_ID_RE = re.compile(r"^[a-z0-9_]+$")
EDGE_ID_RE = re.compile(r"^edge_\d+$")
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
INPUT_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
CANVAS_REF_RE = re.compile(r"^canvas/[a-z0-9_]+\.tsx$")

VALID_NODE_TYPES = {"start", "end", "skill", "loop", "conditional"}
# Edge condition types that the executor accepts on disk.
VALID_EDGE_CONDITIONS = {
    "default", "on_success", "on_failure",
    "if_true", "if_false",
    "loop_continue", "loop_complete",
}

PARAM_TYPES = {"string", "float", "int", "boolean", "object", "array"}
INPUT_TYPES = {"string", "int", "float", "object", "structured"}


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------


class Report:
    def __init__(self) -> None:
        self.errors: list[dict[str, str]] = []
        self.warnings: list[dict[str, str]] = []

    def err(self, where: str, msg: str) -> None:
        self.errors.append({"where": where, "msg": msg})

    def warn(self, where: str, msg: str) -> None:
        self.warnings.append({"where": where, "msg": msg})


def _load_json(path: Path, report: Report) -> Optional[dict]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        report.err(str(path), f"invalid JSON: {exc}")
    except OSError as exc:
        report.err(str(path), f"cannot read: {exc}")
    return None


def _load_yaml(path: Path, report: Report) -> Optional[dict]:
    try:
        import yaml  # type: ignore
    except ImportError:
        report.warn(str(path), "PyYAML not available; skipping YAML field checks")
        return None
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:  # type: ignore[attr-defined]
        report.err(str(path), f"invalid YAML: {exc}")
    except OSError as exc:
        report.err(str(path), f"cannot read: {exc}")
    return None


def _probe_protocol_schema() -> bool:
    try:
        import protocol_schema  # type: ignore  # noqa: F401
        return True
    except ImportError:
        return False


# ----------------------------------------------------------------------------
# Per-item validators
# ----------------------------------------------------------------------------


def _validate_project_json(root: Path, report: Report) -> dict:
    path = root / "project.json"
    if not path.is_file():
        report.err("project.json", "missing")
        return {}
    data = _load_json(path, report)
    if not isinstance(data, dict):
        report.err("project.json", "not a JSON object")
        return {}
    for field in ("name", "description", "active_workflow", "active_world"):
        if field not in data:
            report.warn("project.json", f"missing field: {field}")
    return data


def _validate_skills(root: Path, report: Report, use_pydantic: bool) -> int:
    skills_dir = root / "skills"
    if not skills_dir.is_dir():
        return 0
    count = 0
    for entry in sorted(skills_dir.iterdir()):
        if not entry.is_dir() or entry.name.startswith("."):
            continue
        count += 1
        skill_dir = entry
        skill_name = entry.name

        if not NAME_RE.match(skill_name):
            report.err(f"skills/{skill_name}", f"folder name violates {NAME_RE.pattern}")
            continue

        meta_path = skill_dir / "metadata.yaml"
        code_path = skill_dir / "robotic_code.py"
        modules_path = skill_dir / "modules.py"

        if not meta_path.is_file():
            report.err(f"skills/{skill_name}/metadata.yaml", "missing")
        else:
            meta = _load_yaml(meta_path, report)
            if isinstance(meta, dict):
                _validate_skill_metadata(meta, f"skills/{skill_name}/metadata.yaml", report, use_pydantic)

        if not code_path.is_file():
            report.err(f"skills/{skill_name}/robotic_code.py", "missing")
        else:
            import ast as _ast
            try:
                _ast.parse(code_path.read_text(encoding="utf-8"))
            except SyntaxError as exc:
                report.err(str(code_path), f"syntax error: {exc}")

        if not modules_path.is_file():
            report.warn(f"skills/{skill_name}/modules.py", "missing")
    return count


def _validate_skill_metadata(meta: dict, where: str, report: Report, use_pydantic: bool) -> None:
    skill_id = meta.get("skill_id")
    version = meta.get("version")
    description = meta.get("description")

    if not isinstance(skill_id, str) or not SKILL_ID_RE.match(skill_id):
        report.err(where, f"skill_id missing or violates {SKILL_ID_RE.pattern}")
    if not isinstance(version, str) or not VERSION_RE.match(version):
        report.err(where, f"version missing or violates {VERSION_RE.pattern}")
    if not isinstance(description, str):
        report.err(where, "description missing or not a string")

    params = meta.get("parameters")
    if params is not None:
        if not isinstance(params, list):
            report.err(where, "parameters must be a list")
        else:
            for i, param in enumerate(params):
                if not isinstance(param, dict):
                    report.err(where, f"parameters[{i}] not an object")
                    continue
                pname = param.get("name")
                ptype = param.get("type")
                preq = param.get("required", True)
                pdef = param.get("default")
                if not isinstance(pname, str) or not SKILL_ID_RE.match(pname):
                    report.err(where, f"parameters[{i}].name invalid")
                if ptype not in PARAM_TYPES:
                    report.err(where, f"parameters[{i}].type invalid: {ptype!r}")
                if preq and pdef is not None:
                    report.err(where, f"parameters[{i}] required=true but has default")

    if use_pydantic:
        try:
            from protocol_schema import SkillMetadata  # type: ignore
            SkillMetadata.model_validate(meta)
        except Exception as exc:  # pragma: no cover
            report.err(where, f"Pydantic SkillMetadata.model_validate failed: {exc}")


def _validate_workflows(root: Path, report: Report) -> tuple[int, set[str]]:
    workflows_dir = root / "workflows"
    if not workflows_dir.is_dir():
        return 0, set()
    workflow_ids: set[str] = set()
    count = 0
    for path in sorted(workflows_dir.glob("*.json")):
        count += 1
        wf = _load_json(path, report)
        if not isinstance(wf, dict):
            continue

        where = f"workflows/{path.name}"
        workflow_id = wf.get("workflow_id")
        if not isinstance(workflow_id, str) or not WORKFLOW_ID_RE.match(workflow_id):
            report.err(where, f"workflow_id missing or violates {WORKFLOW_ID_RE.pattern}")
        else:
            workflow_ids.add(workflow_id)
            if path.stem != workflow_id:
                report.warn(where, f"workflow_id {workflow_id!r} != filename stem {path.stem!r}")

        version = wf.get("version")
        if not isinstance(version, str) or not VERSION_RE.match(version):
            report.err(where, f"version missing or violates {VERSION_RE.pattern}")

        for field in ("name", "author", "created_at", "updated_at"):
            if field not in wf:
                report.err(where, f"missing field: {field}")

        if "objects" not in wf:
            report.err(where, "missing field: objects (use [] if no legacy objects)")

        nodes = wf.get("nodes")
        edges = wf.get("edges")
        if not isinstance(nodes, list) or len(nodes) < 2:
            report.err(where, "nodes must be a list of length >= 2")
        if not isinstance(edges, list) or len(edges) < 1:
            report.err(where, "edges must be a list of length >= 1")

        if isinstance(nodes, list) and isinstance(edges, list):
            _validate_workflow_graph(nodes, edges, where, report)

        # Cross-ref skills.
        skills_dir = root / "skills"
        if isinstance(nodes, list):
            for node in nodes:
                if not isinstance(node, dict):
                    continue
                if node.get("type") == "skill":
                    sid = node.get("skill_id")
                    if isinstance(sid, str) and not (skills_dir / sid).is_dir():
                        report.err(where, f"node {node.get('node_id')!r} references missing skill: {sid!r}")

        # Canvas cross-ref.
        canvas_ui = wf.get("canvas_ui")
        if isinstance(canvas_ui, dict):
            _validate_canvas_ui(canvas_ui, root, where, report)

    return count, workflow_ids


def _validate_workflow_graph(nodes: list, edges: list, where: str, report: Report) -> None:
    node_ids: set[str] = set()
    types_by_id: dict[str, str] = {}
    for i, node in enumerate(nodes):
        if not isinstance(node, dict):
            report.err(where, f"nodes[{i}] not an object")
            continue
        nid = node.get("node_id")
        ntype = node.get("type")
        if not isinstance(nid, str) or not NODE_ID_RE.match(nid):
            report.err(where, f"nodes[{i}].node_id invalid")
        else:
            if nid in node_ids:
                report.err(where, f"duplicate node_id: {nid}")
            node_ids.add(nid)
            types_by_id[nid] = ntype if isinstance(ntype, str) else "<missing>"
        if ntype not in VALID_NODE_TYPES:
            report.err(where, f"nodes[{i}].type invalid: {ntype!r}")
        if ntype == "skill" and not node.get("skill_id"):
            report.err(where, f"nodes[{i}] type=skill but skill_id missing")
        if ntype == "conditional" and not isinstance(node.get("condition"), dict):
            report.err(where, f"nodes[{i}] type=conditional but condition missing")
        if ntype == "loop" and not isinstance(node.get("loop"), dict):
            report.err(where, f"nodes[{i}] type=loop but loop config missing")

    edge_ids: set[str] = set()
    outgoing: dict[str, list[dict]] = {nid: [] for nid in node_ids}
    for i, edge in enumerate(edges):
        if not isinstance(edge, dict):
            report.err(where, f"edges[{i}] not an object")
            continue
        eid = edge.get("edge_id")
        if not isinstance(eid, str) or not EDGE_ID_RE.match(eid):
            report.err(where, f"edges[{i}].edge_id violates {EDGE_ID_RE.pattern} (got {eid!r})")
        else:
            if eid in edge_ids:
                report.err(where, f"duplicate edge_id: {eid}")
            edge_ids.add(eid)
        fr = edge.get("from_node")
        to = edge.get("to_node")
        if fr not in node_ids:
            report.err(where, f"edges[{i}].from_node references unknown node: {fr!r}")
        else:
            outgoing[fr].append(edge)
        if to not in node_ids:
            report.err(where, f"edges[{i}].to_node references unknown node: {to!r}")
        cond = edge.get("condition")
        if not isinstance(cond, dict) or cond.get("type") not in VALID_EDGE_CONDITIONS:
            report.err(where, f"edges[{i}].condition invalid (must be object with type in {sorted(VALID_EDGE_CONDITIONS)})")

    # Structural rules.
    starts = [nid for nid, t in types_by_id.items() if t == "start"]
    ends = [nid for nid, t in types_by_id.items() if t == "end"]
    if len(starts) != 1:
        report.err(where, f"expected exactly 1 start node, got {len(starts)}")
    if len(ends) < 1:
        report.err(where, "expected at least 1 end node")

    # Conditional has exactly 2 outgoing.
    for nid, t in types_by_id.items():
        if t == "conditional" and len(outgoing.get(nid, [])) != 2:
            report.err(where, f"conditional node {nid!r} must have exactly 2 outgoing edges")
        if t == "loop" and len(outgoing.get(nid, [])) != 2:
            report.err(where, f"loop node {nid!r} must have exactly 2 outgoing edges")


def _validate_canvas_ui(canvas_ui: dict, root: Path, where: str, report: Report) -> None:
    kind = canvas_ui.get("kind")
    source_ref = canvas_ui.get("source_ref")
    if kind != "react":
        report.err(where, f"canvas_ui.kind must be 'react' (got {kind!r})")
    if not isinstance(source_ref, str) or not CANVAS_REF_RE.match(source_ref):
        report.err(where, f"canvas_ui.source_ref violates {CANVAS_REF_RE.pattern} (got {source_ref!r})")
    elif not (root / source_ref).is_file():
        report.err(where, f"canvas_ui.source_ref points to missing file: {source_ref}")
    if not isinstance(canvas_ui.get("enabled"), bool):
        report.err(where, "canvas_ui.enabled must be boolean")
    if not isinstance(canvas_ui.get("version"), int) or canvas_ui.get("version", 0) < 1:
        report.err(where, "canvas_ui.version must be integer >= 1")


def _validate_worlds(root: Path, report: Report) -> tuple[int, set[str]]:
    worlds_dir = root / "worlds"
    if not worlds_dir.is_dir():
        return 0, set()
    names: set[str] = set()
    count = 0
    for entry in sorted(worlds_dir.iterdir()):
        if not entry.is_dir() or entry.name.startswith("."):
            continue
        count += 1
        names.add(entry.name)
        if not NAME_RE.match(entry.name):
            report.err(f"worlds/{entry.name}", f"folder name violates {NAME_RE.pattern}")
        state = entry / "world_state.json"
        if not state.is_file():
            report.err(f"worlds/{entry.name}/world_state.json", "missing")
            continue
        data = _load_json(state, report)
        if not isinstance(data, dict):
            continue
        if data.get("version") != "2.0":
            report.warn(f"worlds/{entry.name}/world_state.json", f"unexpected version (expected '2.0', got {data.get('version')!r})")
        if not isinstance(data.get("objects"), dict):
            report.err(f"worlds/{entry.name}/world_state.json", "objects must be a dict")
    return count, names


def _validate_objects(root: Path, report: Report) -> int:
    objects_dir = root / "objects"
    if not objects_dir.is_dir():
        return 0
    count = 0
    for entry in sorted(objects_dir.iterdir()):
        if not entry.is_dir() or entry.name.startswith("."):
            continue
        count += 1
        if not NAME_RE.match(entry.name):
            report.err(f"objects/{entry.name}", f"folder name violates {NAME_RE.pattern}")
            continue
        urdf = entry / f"{entry.name}.urdf"
        yaml_ = entry / f"{entry.name}.object_model.yaml"
        if not urdf.is_file():
            report.err(f"objects/{entry.name}/{entry.name}.urdf", "missing")
        else:
            try:
                tree = ET.parse(urdf)
                robot = tree.getroot()
                if robot.tag != "robot":
                    report.err(str(urdf), f"root element must be <robot>, got <{robot.tag}>")
                elif robot.get("name") != entry.name:
                    report.warn(str(urdf), f"<robot name='{robot.get('name')}'> does not match folder name '{entry.name}'")
            except ET.ParseError as exc:
                report.err(str(urdf), f"invalid XML: {exc}")
        if not yaml_.is_file():
            report.err(f"objects/{entry.name}/{entry.name}.object_model.yaml", "missing")
        else:
            data = _load_yaml(yaml_, report)
            if isinstance(data, dict):
                if "urdf" not in data:
                    report.err(str(yaml_), "missing 'urdf' field")
                if "anchors" not in data or "object" not in (data.get("anchors") or {}):
                    report.err(str(yaml_), "anchors.object is required")
                if "articulations" not in data or "default" not in (data.get("articulations") or {}):
                    report.err(str(yaml_), "articulations.default is required")
    return count


def _validate_canvases(root: Path, report: Report) -> int:
    canvas_dir = root / "canvas"
    if not canvas_dir.is_dir():
        return 0
    count = 0
    for path in sorted(canvas_dir.glob("*.tsx")):
        count += 1
        content = path.read_text(encoding="utf-8")
        if "export default" not in content:
            report.err(str(path), "TSX file must `export default` a component")
        # Crude check for non-react imports.
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("import ") and "from " in stripped:
                # Allow `from "react"` only.
                if "from \"react\"" not in stripped and "from 'react'" not in stripped:
                    report.warn(str(path), f"only `react` may be imported (line: {stripped})")
    return count


def _validate_active_refs(project: dict, workflow_ids: set[str], world_names: set[str], report: Report) -> None:
    aw = project.get("active_workflow")
    if isinstance(aw, str) and aw != "":
        if aw not in workflow_ids:
            report.err("project.json", f"active_workflow {aw!r} points to missing workflows/{aw}.json")
    aw2 = project.get("active_world")
    if isinstance(aw2, str) and aw2 != "":
        if aw2 not in world_names:
            report.err("project.json", f"active_world {aw2!r} points to missing worlds/{aw2}/")


def main(argv: list[str]) -> int:
    if len(argv) > 2:
        print("usage: validate_project.py [<project_root>]", file=sys.stderr)
        return 2
    root = Path(argv[1]) if len(argv) == 2 else Path.cwd()
    root = root.resolve()
    if not root.is_dir():
        print(f"not a directory: {root}", file=sys.stderr)
        return 2

    report = Report()
    use_pydantic = _probe_protocol_schema()

    project = _validate_project_json(root, report)
    skill_count = _validate_skills(root, report, use_pydantic)
    workflow_count, workflow_ids = _validate_workflows(root, report)
    world_count, world_names = _validate_worlds(root, report)
    object_count = _validate_objects(root, report)
    canvas_count = _validate_canvases(root, report)

    _validate_active_refs(project, workflow_ids, world_names, report)

    output = {
        "ok": len(report.errors) == 0,
        "using": "library" if use_pydantic else "embedded",
        "errors": report.errors,
        "warnings": report.warnings,
        "summary": {
            "skills": skill_count,
            "workflows": workflow_count,
            "worlds": world_count,
            "objects": object_count,
            "canvases": canvas_count,
        },
    }
    json.dump(output, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0 if output["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
