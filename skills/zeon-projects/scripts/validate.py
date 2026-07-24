#!/usr/bin/env python3
"""Validate a Zeon project's structure, cross-references, and runtime contracts.

Usage:
    python3 validate.py [<project_root>] [--json]

Defaults to the current working directory. Beyond parse/naming/required-field
checks, this validator mirrors the platform's *runtime* contracts so failures
that would otherwise surface mid-run on hardware become local errors:

  - workflow skill-node parameters are cross-checked against the skill
    function's actual signature (missing required param aborts a run;
    unknown keys are silently ignored by the executor)
  - imports and call sites in robotic_code.py are linted against the
    platform's curated execution-function API (references/execution-functions.json)
  - literal `arm` arguments must be exactly "left_arm"/"right_arm" (anything
    else silently selects the right arm at runtime)
  - anchors referenced by skill code must exist in object models
  - conditional/loop expressions are checked against the executor's actual
    tiny grammar; collection-loop sources must name a declared input
  - metadata.yaml is checked against the catalog's fatal rules (a failing
    file silently removes the skill from the catalog)

Pure stdlib; PyYAML used when available (YAML field checks are skipped
without it). Exit codes: 0 = no errors (warnings allowed), 1 = errors,
2 = usage error.
"""

from __future__ import annotations

import ast
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Optional

NAME_RE = re.compile(r"^[a-z_][a-z0-9_-]{0,63}$")
ID_RE = re.compile(r"^[a-z0-9_]+$")  # skill_id / workflow_id (in-file identifiers)
NODE_ID_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
INPUT_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
CANVAS_REF_RE = re.compile(r"^canvas/[a-z0-9_]+\.tsx$")
CANVAS_STEM_RE = re.compile(r"^[a-z0-9_]+$")
UUID_RE = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")

VALID_NODE_TYPES = {"start", "end", "skill", "loop", "conditional"}
VALID_EDGE_CONDITIONS = {
    "default", "on_success", "on_failure",
    "if_true", "if_false",
    "loop_continue", "loop_complete",
}
INPUT_TYPES = {"string", "int", "float", "object", "structured"}
PARAM_TYPES = {"string", "float", "int", "boolean", "object", "array"}
KNOWN_WORLD_VERSIONS = {"2.0", "3.0"}

# State keys the engine injects/overwrites; a skill parameter with one of
# these names receives engine data, not the author's value.
RESERVED_STATE_KEYS = {
    "skill_result", "last_skill_success", "last_skill_error",
    "condition_result", "current_item", "execution_completed",
    "execution_id", "node_id",
}
# Params the engine can inject into a skill inside a loop / run context —
# exempt from "required but unbound" and "unknown key" checks.
ENGINE_INJECTED_PARAMS = {"current_item", "execution_id", "node_id"}

# Functions whose `arm` argument silently falls back to the RIGHT arm for any
# string other than "left_arm" — a wrong-arm motion, not an error.
VALID_ARMS = {"left_arm", "right_arm"}

# Annotation base names the platform maps to parameter types; anything else
# degrades the derived schema.
KNOWN_ANNOTATION_BASES = {
    "SkillObject", "str", "bool", "int", "float",
    "list", "List", "tuple", "Tuple", "Sequence",
    "dict", "Dict", "Mapping", "Any",
}

BLOB_CAP = 16 * 1024 * 1024
BLOB_WARN = 12 * 1024 * 1024
CANVAS_CAP = 256 * 1024
# True mesh formats never belong in a project; .npz/.bin voxel sidecars are
# legitimate platform output under worlds/.
MESH_SUFFIXES = {".obj", ".stl", ".glb", ".gltf", ".ply", ".dae"}

# Motion functions whose safety flag must never be disabled silently. The
# current platform API has no `safe` parameter at all (passing it TypeErrors),
# but older projects and injected instructions have used it — flag both ways.
SAFETY_SENSITIVE_CALLS = {"move_arm", "move_arm_js", "move_relative"}


class Report:
    def __init__(self) -> None:
        self.errors: list[dict[str, str]] = []
        self.warnings: list[dict[str, str]] = []

    def err(self, where: str, msg: str) -> None:
        self.errors.append({"where": where, "msg": msg})

    def warn(self, where: str, msg: str) -> None:
        self.warnings.append({"where": where, "msg": msg})


def _load_json(path: Path, report: Report) -> Optional[Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        report.err(str(path), f"invalid JSON: {exc}")
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        report.err(str(path), f"cannot read: {exc}")
    return None


_YAML_WARNED = False


def _load_yaml(path: Path, report: Report) -> Optional[Any]:
    global _YAML_WARNED
    try:
        import yaml  # type: ignore
    except ImportError:
        if not _YAML_WARNED:
            report.warn(str(path), "PyYAML not installed; YAML field checks skipped")
            _YAML_WARNED = True
        return None
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        report.err(str(path), f"invalid YAML: {exc}")
    except OSError as exc:
        report.err(str(path), f"cannot read: {exc}")
    return None


def _item_dirs(parent: Path) -> list[Path]:
    if not parent.is_dir():
        return []
    return sorted(
        p for p in parent.iterdir()
        if p.is_dir() and not p.name.startswith(".") and p.name != "__pycache__"
    )


# ---------------------------------------------------------------------------
# Execution-function manifest
# ---------------------------------------------------------------------------

def load_manifest() -> dict:
    """Load the vendored platform API manifest; {} when unavailable."""
    path = Path(__file__).resolve().parent.parent / "references" / "execution-functions.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("functions", {})
    except (OSError, json.JSONDecodeError):
        return {}


def _manifest_params(entry: dict) -> Optional[dict]:
    """Split a manifest signature into a call-checking model."""
    sig = entry.get("signature")
    if sig is None:
        return None
    positional, kw_only = [], []
    has_vararg = has_kwarg = False
    for p in sig:
        if p["kind"] == "positional":
            positional.append(p)
        elif p["kind"] == "keyword_only":
            kw_only.append(p)
        elif p["kind"] == "vararg":
            has_vararg = True
        elif p["kind"] == "kwarg":
            has_kwarg = True
    return {
        "positional": positional,
        "kw_only": kw_only,
        "has_vararg": has_vararg,
        "has_kwarg": has_kwarg,
        "all_names": {p["name"] for p in positional + kw_only},
        "required": [p["name"] for p in positional + kw_only if "default" not in p],
    }


# ---------------------------------------------------------------------------
# project.json
# ---------------------------------------------------------------------------

def validate_project_json(root: Path, report: Report) -> dict:
    path = root / "project.json"
    if not path.is_file():
        report.err("project.json", "missing")
        return {}
    data = _load_json(path, report)
    if not isinstance(data, dict):
        if data is not None:
            report.err("project.json", "not a JSON object")
        return {}
    for field in ("name", "description", "created_at", "updated_at",
                  "archived", "active_workflow", "active_world"):
        if field not in data:
            report.warn("project.json", f"missing field: {field}")
    return data


def validate_active_refs(project: dict, workflow_ids: set[str],
                         world_names: set[str], report: Report) -> None:
    aw = project.get("active_workflow")
    if isinstance(aw, str) and aw and aw not in workflow_ids:
        report.err("project.json", f"active_workflow {aw!r} has no workflows/{aw}.json")
    wd = project.get("active_world")
    if isinstance(wd, str) and wd and wd not in world_names:
        report.err("project.json", f"active_world {wd!r} has no worlds/{wd}/ folder")


# ---------------------------------------------------------------------------
# skills/
# ---------------------------------------------------------------------------

def validate_skills(root: Path, report: Report, manifest: dict,
                    world_info: dict) -> tuple[int, dict[str, dict]]:
    """Validate all skills. Returns (count, {skill_id: signature model})."""
    signatures: dict[str, dict] = {}
    count = 0
    skills_root = root / "skills"

    utils_names = _module_top_level_names(skills_root / "utils.py", report)

    for skill_dir in _item_dirs(skills_root):
        count += 1
        name = skill_dir.name
        where = f"skills/{name}"

        if not NAME_RE.match(name):
            report.err(where, f"folder name violates {NAME_RE.pattern}")
            continue

        meta_path = skill_dir / "metadata.yaml"
        if not meta_path.is_file():
            report.err(f"{where}/metadata.yaml", "missing")
        else:
            meta = _load_yaml(meta_path, report)
            if isinstance(meta, dict):
                _check_skill_metadata(meta, name, f"{where}/metadata.yaml", report)

        modules_path = skill_dir / "modules.py"
        modules_names, modules_star = _parse_modules_shim(modules_path, report, skills_root)

        code_path = skill_dir / "robotic_code.py"
        if not code_path.is_file():
            report.err(f"{where}/robotic_code.py", "missing")
            continue
        sig = _check_robotic_code(
            code_path, name, report, manifest,
            modules_exists=modules_path.is_file(),
            modules_names=modules_names,
            modules_star=modules_star,
            utils_names=utils_names,
            world_info=world_info,
            project_root=root,
        )
        if sig is not None:
            signatures[name] = sig

    # Stray nested metadata.yaml files become phantom catalog entries.
    if skills_root.is_dir():
        for stray in skills_root.rglob("metadata.yaml"):
            rel = stray.relative_to(skills_root)
            if len(rel.parts) != 2:
                report.err(f"skills/{rel}",
                           "metadata.yaml outside skills/<id>/ — the catalog's recursive "
                           "scan turns this into a phantom/duplicate skill entry")

    return count, signatures


def _module_top_level_names(path: Path, report: Report) -> set[str]:
    if not path.is_file():
        return set()
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError as exc:
        report.err(str(path), f"syntax error: {exc}")
        return set()
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        report.err(str(path), f"cannot read: {exc}")
        return set()
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name):
                    names.add(tgt.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, ast.Import):
            names |= {(a.asname or a.name.split(".")[0]) for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            names |= {(a.asname or a.name) for a in node.names if a.name != "*"}
    return names


def _parse_modules_shim(path: Path, report: Report, skills_root: Path,
                        _seen: Optional[set[Path]] = None) -> tuple[set[str], bool]:
    """Names available via `from .modules import ...` and whether the shim
    star-imports the platform API (directly or through sibling chains)."""
    if not path.is_file():
        return set(), False
    seen = _seen if _seen is not None else set()
    resolved = path.resolve()
    if resolved in seen:
        return set(), False
    seen.add(resolved)
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError as exc:
        report.err(str(path), f"syntax error: {exc}")
        return set(), False
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        report.err(str(path), f"cannot read: {exc}")
        return set(), False
    names = _module_top_level_names(path, report)
    star = False
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            is_star = any(a.name == "*" for a in node.names)
            if "execution_functions" in mod and is_star:
                star = True
            elif mod.endswith(".modules") and is_star:
                sibling = mod.split(".")[0]
                sib_path = skills_root / sibling / "modules.py"
                if sib_path.is_file():
                    sib_names, sib_star = _parse_modules_shim(sib_path, report,
                                                              skills_root, seen)
                    names |= sib_names
                    star = star or sib_star
            elif not is_star:
                names |= {a.asname or a.name for a in node.names}
    return names, star


def _check_skill_metadata(meta: dict, folder: str, where: str, report: Report) -> None:
    skill_id = meta.get("skill_id")
    if not isinstance(skill_id, str) or not ID_RE.match(skill_id):
        report.err(where, f"skill_id missing or violates {ID_RE.pattern}")
    elif skill_id != folder:
        report.err(where, f"skill_id {skill_id!r} != folder name {folder!r}")

    version = meta.get("version")
    if not isinstance(version, str) or not VERSION_RE.match(version):
        report.err(where, "version missing or not semver (e.g. \"1.0.0\")")

    # Catalog-fatal: the catalog schema requires a string description; a
    # failing file silently drops the skill from the catalog.
    if not isinstance(meta.get("description"), str):
        report.err(where, "description missing or not a string (skill would be "
                          "silently dropped from the platform catalog)")

    params = meta.get("parameters")
    if isinstance(params, list):
        for i, p in enumerate(params):
            if not isinstance(p, dict):
                report.err(where, f"parameters[{i}] is not a mapping")
                continue
            pname = p.get("name")
            if not isinstance(pname, str) or not ID_RE.match(pname):
                report.err(where, f"parameters[{i}].name must be snake_case ({ID_RE.pattern})")
            if p.get("type") not in PARAM_TYPES:
                report.err(where, f"parameters[{i}].type invalid: {p.get('type')!r} "
                                  f"(expected one of {sorted(PARAM_TYPES)})")
            if not isinstance(p.get("description"), str):
                report.err(where, f"parameters[{i}].description missing (required by the "
                                  "catalog schema — its absence drops the skill)")

    for section in ("preconditions", "postconditions"):
        cond = meta.get(section)
        if isinstance(cond, dict):
            for key in cond:
                if key in RESERVED_STATE_KEYS:
                    report.warn(where, f"{section} key {key!r} collides with an "
                                       "engine-reserved state key")


def _annotation_base(node: ast.expr) -> Optional[str]:
    """Base name of an annotation, unwrapping Optional[X] / X | None / subscripts."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value.split("[")[0].split(".")[-1]
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


def _check_robotic_code(path: Path, folder: str, report: Report, manifest: dict,
                        *, modules_exists: bool, modules_names: set[str],
                        modules_star: bool, utils_names: set[str],
                        world_info: dict, project_root: Path) -> Optional[dict]:
    """Validate one robotic_code.py. Returns the skill's signature model."""
    where = str(path)
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError as exc:
        report.err(where, f"syntax error: {exc}")
        return None
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        report.err(where, f"cannot read: {exc}")
        return None

    expected_fn = folder.replace("-", "_")
    skill_fn: Optional[ast.FunctionDef] = None
    defined: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            defined.add(node.name)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            defined.add(node.id)
        elif isinstance(node, ast.arg):
            defined.add(node.arg)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == expected_fn:
            skill_fn = node

    if skill_fn is None:
        report.err(where, f"must define a top-level function {expected_fn}() "
                          "(the platform derives the skill's parameters from its signature)")

    # ---- imports -----------------------------------------------------------
    imported: set[str] = set()
    shadowed: set[str] = set()  # names bound locally or from non-platform modules
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            shadowed.add(node.name)
        elif isinstance(node, ast.Assign):
            shadowed |= {t.id for t in node.targets if isinstance(t, ast.Name)}
    star_platform = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {(a.asname or a.name).split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            is_star = any(a.name == "*" for a in node.names)
            from_shim = mod in {"modules", ".modules"} or mod.endswith(".modules") or (
                node.level == 1 and mod == "modules")
            from_platform = "execution_functions" in mod
            if from_shim and not modules_exists:
                report.err(where, f"imports from .modules but {folder}/modules.py does "
                                  "not exist (ImportError at load)")
            if is_star:
                if from_shim:
                    star_platform = star_platform or modules_star
                    imported |= modules_names
                elif from_platform:
                    star_platform = True
                continue
            for a in node.names:
                imported.add(a.asname or a.name)
                nm = a.name
                if from_shim:
                    if manifest and nm not in manifest and nm not in modules_names and not modules_star:
                        report.warn(where, f"imports {nm!r} from .modules but it is neither "
                                           "in the platform API manifest nor defined in "
                                           "modules.py — possible ImportError at load")
                elif from_platform:
                    if manifest and nm not in manifest:
                        report.warn(where, f"imports {nm!r} from execution.execution_functions "
                                           "— not in the curated skill-facing API (__all__); "
                                           "works only if the module defines it internally "
                                           "(unsupported surface)")
                elif mod == "utils" and utils_names:
                    if nm not in utils_names:
                        report.err(where, f"imports {nm!r} from utils but skills/utils.py "
                                          "does not define it (ImportError at load)")
                    shadowed.add(a.asname or a.name)
                else:
                    shadowed.add(a.asname or a.name)

    # ---- signature model + fidelity warnings --------------------------------
    sig_model: Optional[dict] = None
    if skill_fn is not None:
        a = skill_fn.args
        pos = a.posonlyargs + a.args
        defaults: list = [None] * (len(pos) - len(a.defaults)) + list(a.defaults)
        params = []
        for arg, dflt in zip(pos, defaults):
            params.append({"name": arg.arg, "annotation": arg.annotation,
                           "default": dflt})
        for arg, dflt in zip(a.kwonlyargs, a.kw_defaults):
            params.append({"name": arg.arg, "annotation": arg.annotation,
                           "default": dflt})
        sig_model = {
            "params": [p["name"] for p in params],
            "required": [p["name"] for p in params if p["default"] is None],
            "has_kwargs": a.kwarg is not None,
        }
        for p in params:
            pname = p["name"]
            if pname in RESERVED_STATE_KEYS and pname not in ENGINE_INJECTED_PARAMS:
                report.err(where, f"parameter {pname!r} collides with an engine-reserved "
                                  "state key — it would receive engine data, not your value")
            if p["default"] is not None:
                try:
                    ast.literal_eval(p["default"])
                except (ValueError, SyntaxError):
                    report.warn(where, f"parameter {pname!r} default is not a literal — "
                                       "the platform records default=None in the derived schema")
            if p["annotation"] is None:
                if p["default"] is None:
                    report.warn(where, f"parameter {pname!r} has no annotation and no "
                                       "default — the platform types it as 'string'")
            else:
                base = _annotation_base(p["annotation"])
                if base and base not in KNOWN_ANNOTATION_BASES:
                    report.warn(where, f"parameter {pname!r} annotation {base!r} is not in "
                                       "the platform's type map — the derived schema degrades")

        # Return-convention: a skill returning None breaks result logging.
        returns_dict = False
        for node in ast.walk(skill_fn):
            if isinstance(node, ast.Return) and node.value is not None:
                if isinstance(node.value, ast.Dict):
                    for k in node.value.keys:
                        if isinstance(k, ast.Constant) and k.value == "success":
                            returns_dict = True
                else:
                    returns_dict = True  # returns something non-literal; don't nag
        if not returns_dict:
            report.warn(where, f"{expected_fn}() never returns a dict with a 'success' "
                               "key (platform convention; note: routing is exception-"
                               "driven — raise to fail the node)")

    # ---- call-site lint ------------------------------------------------------
    import builtins as _builtins
    available = imported | defined | set(dir(_builtins))

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
            continue
        fn_name = node.func.id
        # A locally-defined or non-platform-imported name shadows the platform
        # function — don't lint the call against the platform signature.
        entry = manifest.get(fn_name) if fn_name not in shadowed else None
        model = _manifest_params(entry) if entry else None

        if fn_name not in available and not star_platform:
            report.warn(where, f"line {node.lineno}: call to {fn_name!r} which is neither "
                               "imported nor defined here — possible NameError at run time")
        elif fn_name not in available and star_platform and manifest and fn_name not in manifest:
            report.warn(where, f"line {node.lineno}: call to {fn_name!r} resolved only via "
                               "star-import, but it is not in the platform API manifest — "
                               "possible NameError at run time")

        if model:
            has_star_args = any(isinstance(x, ast.Starred) for x in node.args)
            has_star_kwargs = any(kw.arg is None for kw in node.keywords)
            kw_names = {kw.arg for kw in node.keywords if kw.arg}
            if not model["has_kwarg"] and not has_star_kwargs:
                for kw in kw_names:
                    if kw not in model["all_names"]:
                        report.err(where, f"line {node.lineno}: {fn_name}(..., {kw}=…) — "
                                          f"unknown keyword (API: {fn_name}"
                                          f"({', '.join(sorted(model['all_names']))})); "
                                          "TypeError at run time")
            if not model["has_vararg"] and not has_star_args:
                if len(node.args) > len(model["positional"]):
                    report.err(where, f"line {node.lineno}: {fn_name}() takes at most "
                                      f"{len(model['positional'])} positional args, got "
                                      f"{len(node.args)} — TypeError at run time")
            if not has_star_args and not has_star_kwargs:
                pos_bound = {p["name"] for p in model["positional"][:len(node.args)]}
                for dup in sorted(pos_bound & kw_names):
                    report.err(where, f"line {node.lineno}: {fn_name}() got multiple values "
                                      f"for argument {dup!r} — TypeError at run time")
                missing = [r for r in model["required"] if r not in pos_bound | kw_names]
                if missing:
                    report.err(where, f"line {node.lineno}: {fn_name}() missing required "
                                      f"argument(s): {', '.join(missing)} — TypeError at run time")

            # Arm-literal check: any string other than left_arm/right_arm
            # silently selects the RIGHT arm at run time.
            if any(p["name"] == "arm" for p in model["positional"]) or "arm" in model["all_names"]:
                arm_val = None
                for kw in node.keywords:
                    if kw.arg == "arm" and isinstance(kw.value, ast.Constant):
                        arm_val = kw.value.value
                arm_idx = next((i for i, p in enumerate(model["positional"]) if p["name"] == "arm"), None)
                if arm_val is None and arm_idx is not None and len(node.args) > arm_idx:
                    argnode = node.args[arm_idx]
                    if isinstance(argnode, ast.Constant):
                        arm_val = argnode.value
                if isinstance(arm_val, str) and arm_val not in VALID_ARMS:
                    report.err(where, f"line {node.lineno}: {fn_name}(arm={arm_val!r}) — arm "
                                      "must be exactly 'left_arm' or 'right_arm'; anything "
                                      "else silently moves the RIGHT arm")

        # Safety flag audit (legacy `safe=` has no effect on the current API
        # and TypeErrors; flag it regardless of manifest availability).
        if fn_name in SAFETY_SENSITIVE_CALLS:
            for kw in node.keywords:
                if kw.arg == "safe" and isinstance(kw.value, ast.Constant) and kw.value.value is False:
                    report.warn(where, f"line {node.lineno}: {fn_name}(..., safe=False) "
                                       "attempts to disable collision checking — the current "
                                       "API has no such flag (TypeError); remove it and "
                                       "confirm intent with the user")

        # Anchor / object-name cross-reference on literal calls.
        if fn_name in {"load_object_anchor", "get_object_pose", "update_object_joint_config"}:
            _check_object_literal_call(node, fn_name, where, report, world_info, project_root)

        # live_state access keys strictly by instance id — a display name
        # silently returns {} / creates a bogus entry.
        if fn_name in {"get_world_state", "set_world_state"}:
            first = None
            for kw in node.keywords:
                if kw.arg == "object_id" and isinstance(kw.value, ast.Constant):
                    first = kw.value.value
            if first is None and node.args and isinstance(node.args[0], ast.Constant):
                first = node.args[0].value
            if isinstance(first, str) and first in world_info.get("display_names", set()) \
                    and first not in world_info.get("instance_keys", set()):
                report.err(where, f"line {node.lineno}: {fn_name}({first!r}, …) passes a "
                                  "display name — live_state keys strictly by instance id; "
                                  "a name silently returns {} (and writes create a bogus "
                                  "entry). Pass the SkillObject.id / world instance key")

    return sig_model


def _check_object_literal_call(node: ast.Call, fn_name: str, where: str,
                               report: Report, world_info: dict,
                               project_root: Path) -> None:
    args = [a.value if isinstance(a, ast.Constant) else None for a in node.args]
    kwargs = {kw.arg: kw.value.value for kw in node.keywords
              if kw.arg and isinstance(kw.value, ast.Constant)}
    obj = kwargs.get("object_name") or (args[0] if args else None)
    if not isinstance(obj, str):
        return
    resolved = _resolve_object_type(obj, world_info, project_root)
    if resolved == "":  # known world instance, object model comes from mesh-db
        return
    if resolved is None:
        report.warn(where, f"line {node.lineno}: {fn_name}({obj!r}, …) — {obj!r} matches no "
                           "world instance name/key and no objects/ folder in this project "
                           "(may resolve from the mesh database at run time)")
        return
    obj_type = resolved
    if fn_name == "load_object_anchor":
        anchor = kwargs.get("anchor_name") or (args[1] if len(args) > 1 else None)
        if isinstance(anchor, str):
            anchors = _object_anchors(project_root, obj_type)
            if anchors is not None and anchor not in anchors:
                report.err(where, f"line {node.lineno}: anchor {anchor!r} not found in "
                                  f"objects/{obj_type}/{obj_type}.object_model.yaml "
                                  f"(has: {', '.join(sorted(anchors)) or 'none'})")


def _resolve_object_type(name: str, world_info: dict, root: Path) -> Optional[str]:
    """Resolve an instance name / key / type to an objects/<type> folder name.

    Returns the folder name, "" when the instance is known but its object
    model lives only in the mesh database (nothing to check locally), or
    None when the name is entirely unknown.
    """
    if (root / "objects" / name).is_dir():
        return name
    t = world_info.get("name_to_type", {}).get(name)
    if t and (root / "objects" / t).is_dir():
        return t
    if t:
        return ""
    return None


_ANCHOR_CACHE: dict[Path, Optional[set[str]]] = {}


def _object_anchors(root: Path, obj_type: str) -> Optional[set[str]]:
    path = root / "objects" / obj_type / f"{obj_type}.object_model.yaml"
    if path in _ANCHOR_CACHE:
        return _ANCHOR_CACHE[path]
    result: Optional[set[str]] = None
    if path.is_file():
        try:
            import yaml  # type: ignore
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("anchors"), dict):
                result = set(data["anchors"].keys())
        except Exception:
            result = None
    _ANCHOR_CACHE[path] = result
    return result


# ---------------------------------------------------------------------------
# workflows/
# ---------------------------------------------------------------------------

def validate_workflows(root: Path, report: Report,
                       skill_sigs: dict[str, dict]) -> tuple[int, set[str], set[str], set[str]]:
    workflows_dir = root / "workflows"
    workflow_ids: set[str] = set()
    id_to_file: dict[str, str] = {}
    canvas_refs: set[str] = set()
    all_input_names: set[str] = set()
    count = 0
    if not workflows_dir.is_dir():
        return 0, workflow_ids, canvas_refs, all_input_names

    for path in sorted(workflows_dir.glob("*.json")):
        count += 1
        where = f"workflows/{path.name}"
        wf = _load_json(path, report)
        if not isinstance(wf, dict):
            continue

        workflow_id = wf.get("workflow_id")
        if not isinstance(workflow_id, str) or not ID_RE.match(workflow_id):
            report.err(where, f"workflow_id missing or violates {ID_RE.pattern}")
        else:
            if workflow_id in id_to_file:
                report.err(where, f"duplicate workflow_id {workflow_id!r} (also in "
                                  f"{id_to_file[workflow_id]}) — GET-by-id becomes ambiguous")
            id_to_file[workflow_id] = path.name
            workflow_ids.add(workflow_id)
            if path.stem != workflow_id:
                report.err(where, f"workflow_id {workflow_id!r} != filename stem "
                                  f"{path.stem!r} — the platform persists to "
                                  f"<workflow_id>.json, leaving this file stale after "
                                  "any editor round-trip")

        if not wf.get("name"):
            report.err(where, "name is required")
        version = wf.get("version")
        if not isinstance(version, str) or not VERSION_RE.match(version):
            report.err(where, "version missing or not semver (e.g. \"1.0.0\")")
        for field in ("author", "created_at", "updated_at"):
            if field not in wf:
                report.warn(where, f"missing field: {field}")
        if "objects" not in wf:
            report.err(where, "missing field: objects (use [] when empty)")

        input_names, array_inputs = _check_inputs(wf.get("inputs"), where, report)
        all_input_names |= input_names

        nodes = wf.get("nodes")
        edges = wf.get("edges")
        if not isinstance(nodes, list) or len(nodes) < 2:
            report.err(where, "nodes must be a list with at least 2 nodes (start and end)")
            nodes = nodes if isinstance(nodes, list) else []
        if not isinstance(edges, list) or len(edges) < 1:
            report.err(where, "edges must be a list with at least 1 edge")
            edges = edges if isinstance(edges, list) else []

        _check_graph(nodes, edges, input_names, array_inputs, root, where,
                     report, skill_sigs)

        canvas_ui = wf.get("canvas_ui")
        if isinstance(canvas_ui, dict):
            ref = _check_canvas_ui(canvas_ui, root, where, report)
            if ref:
                canvas_refs.add(ref)

    return count, workflow_ids, canvas_refs, all_input_names


def validate_input_presets(root: Path, report: Report,
                           all_input_names: set[str]) -> int:
    """inputs/*.json presets. The platform silently skips malformed files —
    they just vanish from the canvas dropdown — so parse failures are local
    errors here."""
    inputs_dir = root / "inputs"
    if not inputs_dir.is_dir():
        return 0
    count = 0
    for path in sorted(inputs_dir.glob("*.json")):
        count += 1
        rel = f"inputs/{path.name}"
        data = _load_json(path, report)
        if data is None:
            continue
        if not isinstance(data, dict):
            report.err(rel, "preset must be a JSON object of input values "
                            "(the platform silently skips this file)")
            continue
        label = data.get("_label")
        if not isinstance(label, str) or not label.strip():
            report.warn(rel, "no _label — the preset has no display name in the canvas")
        if all_input_names:
            for key in data:
                if key == "_label":
                    continue
                if key not in all_input_names:
                    report.warn(rel, f"preset key {key!r} matches no declared workflow "
                                     "input in this project (typo?)")
    return count


def _check_inputs(inputs: Any, where: str, report: Report) -> tuple[set[str], set[str]]:
    names: set[str] = set()
    array_names: set[str] = set()
    if inputs is None:
        report.err(where, "missing field: inputs (use [] when empty)")
        return names, array_names
    if not isinstance(inputs, list):
        report.err(where, "inputs must be a list")
        return names, array_names
    for i, inp in enumerate(inputs):
        if not isinstance(inp, dict):
            report.err(where, f"inputs[{i}] is not an object")
            continue
        name = inp.get("name")
        if not isinstance(name, str) or not INPUT_NAME_RE.match(name):
            report.err(where, f"inputs[{i}].name invalid (must match {INPUT_NAME_RE.pattern})")
        else:
            if name in names:
                report.err(where, f"duplicate input name: {name!r}")
            names.add(name)
            if inp.get("is_array") or inp.get("isArray"):
                array_names.add(name)
        itype = inp.get("type")
        if itype == "boolean":
            report.warn(where, f"inputs[{i}].type 'boolean' is legacy — the current "
                               f"save API accepts {sorted(INPUT_TYPES)}")
        elif itype not in INPUT_TYPES:
            report.err(where, f"inputs[{i}].type invalid: {itype!r} "
                              f"(expected one of {sorted(INPUT_TYPES)})")
        dv = inp.get("defaultValue", inp.get("default_value"))
        if itype == "string" and isinstance(dv, str) and UUID_RE.search(dv):
            report.warn(where, f"inputs[{i}] ({name!r}): UUID-shaped defaultValue on a "
                               "string input — at run time any UUID-shaped string is "
                               "auto-treated as a world object reference and a lookup "
                               "miss aborts the skill")
    return names, array_names


_CONDITIONAL_FORBIDDEN = re.compile(r"(!=|<=|>=|<|>|\band\b|\bor\b|\bnot\b)")
_LOOP_OPS = ["<=", ">=", "==", "!=", "<", ">"]


def _check_graph(nodes: list, edges: list, input_names: set[str],
                 array_inputs: set[str], root: Path, where: str,
                 report: Report, skill_sigs: dict[str, dict]) -> None:
    node_ids: set[str] = set()
    types_by_id: dict[str, str] = {}

    for i, node in enumerate(nodes):
        if not isinstance(node, dict):
            report.err(where, f"nodes[{i}] is not an object")
            continue
        nid = node.get("node_id")
        ntype = node.get("type")
        if not isinstance(nid, str) or not nid:
            report.err(where, f"nodes[{i}].node_id missing")
        else:
            if nid in node_ids:
                report.err(where, f"duplicate node_id: {nid!r}")
            node_ids.add(nid)
            types_by_id[nid] = ntype if isinstance(ntype, str) else "<missing>"
            if not NODE_ID_RE.match(nid):
                if ntype == "loop":
                    report.err(where, f"loop node_id {nid!r} must match "
                                      f"{NODE_ID_RE.pattern} — loop ids are embedded in "
                                      "executor expressions; this id breaks the run at "
                                      "startup")
                else:
                    report.warn(where, f"node_id {nid!r} is not identifier-safe "
                                       f"({NODE_ID_RE.pattern})")
        if ntype not in VALID_NODE_TYPES:
            report.err(where, f"nodes[{i}].type invalid: {ntype!r} "
                              f"(expected one of {sorted(VALID_NODE_TYPES)})")
        if not node.get("label"):
            report.warn(where, f"nodes[{i}] ({nid!r}) has no label")
        if "retry" in node and ntype == "skill":
            report.warn(where, f"node {nid!r}: 'retry' on skill nodes is a runtime no-op — "
                               "the executor never reads it; build retry logic inside the "
                               "skill or as explicit graph structure")

        if ntype == "skill":
            _check_skill_node(node, nid, root, where, report, input_names, skill_sigs)
        if ntype == "conditional":
            cond = node.get("condition")
            if not isinstance(cond, dict):
                report.err(where, f"node {nid!r}: type=conditional but condition config missing")
            else:
                expr = str(cond.get("expression", "")).strip()
                if expr and expr.lower() not in {"true", "false"}:
                    if _CONDITIONAL_FORBIDDEN.search(expr):
                        report.err(where, f"node {nid!r}: conditional expressions support "
                                          "only 'var', 'var == value', or true/false — "
                                          f"{expr!r} becomes a state-key lookup and "
                                          "KeyErrors at run time")
                    else:
                        var = expr.split("==")[0].strip()
                        if var and var not in input_names:
                            report.warn(where, f"node {nid!r}: conditional variable {var!r} "
                                               "is not a declared input — it must be a key "
                                               "in the immediately preceding skill's "
                                               "returned dict")
        if ntype == "loop":
            loop = node.get("loop")
            if not isinstance(loop, dict):
                report.err(where, f"node {nid!r}: type=loop but loop config missing")
            else:
                ltype = loop.get("type")
                if ltype == "collection":
                    src = loop.get("source")
                    if not isinstance(src, str) or src not in input_names:
                        report.err(where, f"node {nid!r}: collection loop source {src!r} "
                                          "names no declared workflow input — at run time "
                                          "the collection is empty and the loop body "
                                          "silently runs zero times")
                    elif src not in array_inputs:
                        report.warn(where, f"node {nid!r}: collection loop source {src!r} "
                                           "is not an is_array input")
                elif ltype == "conditional":
                    expr = str(loop.get("expression", ""))
                    if re.search(r"\band\b|\bor\b", expr):
                        report.err(where, f"node {nid!r}: loop expressions support a single "
                                          "comparison — no 'and'/'or'")
                    elif not any(op in expr for op in _LOOP_OPS):
                        report.err(where, f"node {nid!r}: loop conditional expression needs "
                                          f"exactly one of {_LOOP_OPS}")

    edge_ids: set[str] = set()
    outgoing: dict[str, list] = {nid: [] for nid in node_ids}
    adjacency: dict[str, list[str]] = {nid: [] for nid in node_ids}
    for i, edge in enumerate(edges):
        if not isinstance(edge, dict):
            report.err(where, f"edges[{i}] is not an object")
            continue
        eid = edge.get("edge_id")
        if not isinstance(eid, str) or not eid:
            report.err(where, f"edges[{i}].edge_id missing")
        else:
            if eid in edge_ids:
                report.err(where, f"duplicate edge_id: {eid!r}")
            edge_ids.add(eid)
        fr, to = edge.get("from_node"), edge.get("to_node")
        if not isinstance(fr, str) or fr not in node_ids:
            report.err(where, f"edges[{i}].from_node references unknown node: {fr!r}")
        else:
            outgoing[fr].append(edge)
            if isinstance(to, str):
                adjacency[fr].append(to)
        if not isinstance(to, str) or to not in node_ids:
            report.err(where, f"edges[{i}].to_node references unknown node: {to!r}")
        cond = edge.get("condition")
        ctype = cond.get("type") if isinstance(cond, dict) else None
        if ctype not in VALID_EDGE_CONDITIONS:
            report.err(where, f"edges[{i}].condition.type invalid: {ctype!r} "
                              f"(expected one of {sorted(VALID_EDGE_CONDITIONS)})")
        elif ctype == "default" and types_by_id.get(fr) == "skill":
            report.warn(where, f"edges[{i}] ({fr}→{to}): 'default' edge out of a skill "
                               "node runs UNCONDITIONALLY — the workflow continues even "
                               "if the skill raises; use on_success unless that is "
                               "intended")

    starts = [nid for nid, t in types_by_id.items() if t == "start"]
    ends = [nid for nid, t in types_by_id.items() if t == "end"]
    if not starts:
        report.err(where, "at least one start node is required")
    elif len(starts) > 1:
        report.warn(where, f"{len(starts)} start nodes (convention is exactly 1)")
    if not ends:
        report.err(where, "at least one end node is required")

    for nid, t in types_by_id.items():
        n_out = len(outgoing.get(nid, []))
        if t == "conditional" and n_out != 2:
            report.err(where, f"conditional node {nid!r} must have exactly 2 outgoing edges (has {n_out})")
        if t == "loop" and n_out != 2:
            report.err(where, f"loop node {nid!r} must have exactly 2 outgoing edges (has {n_out})")

    if starts and node_ids:
        reachable: set[str] = set()
        frontier = list(starts)
        while frontier:
            cur = frontier.pop()
            if cur in reachable:
                continue
            reachable.add(cur)
            frontier.extend(n for n in adjacency.get(cur, []) if n in node_ids)
        for nid in sorted(node_ids - reachable):
            report.warn(where, f"node {nid!r} is unreachable from the start node")


def _check_skill_node(node: dict, nid: str, root: Path, where: str,
                      report: Report, input_names: set[str],
                      skill_sigs: dict[str, dict]) -> None:
    sid = node.get("skill_id")
    if not isinstance(sid, str) or not sid:
        report.err(where, f"node {nid!r}: type=skill but skill_id missing")
        return
    if not (root / "skills" / sid).is_dir():
        report.err(where, f"node {nid!r} references missing skill: {sid!r}")
        return
    params = node.get("parameters")
    if params is None:
        report.err(where, f"node {nid!r}: skill nodes need parameters ({{}} when none)")
        return
    if not isinstance(params, dict):
        report.err(where, f"node {nid!r}: parameters must be an object")
        return

    for pname, pval in params.items():
        if isinstance(pval, dict) and "$input" in pval:
            ref = pval["$input"]
            if ref not in input_names:
                report.err(where, f"node {nid!r} parameter {pname!r} binds "
                                  f"{{'$input': {ref!r}}} but no such input is declared")

    sig = skill_sigs.get(sid)
    if sig is None:
        return
    bound = set(params.keys())
    for req in sig["required"]:
        if req not in bound and req not in ENGINE_INJECTED_PARAMS:
            report.err(where, f"node {nid!r}: skill {sid!r} requires parameter {req!r} "
                              "but the node does not bind it — the run aborts at this "
                              "node with 'requires parameter'")
    if not sig["has_kwargs"]:
        for key in bound:
            if key not in sig["params"] and key not in ENGINE_INJECTED_PARAMS:
                report.warn(where, f"node {nid!r}: parameter {key!r} is not in "
                                   f"{sid}()'s signature — the executor silently drops "
                                   "it (typo?)")


def _check_canvas_ui(canvas_ui: dict, root: Path, where: str, report: Report) -> Optional[str]:
    if canvas_ui.get("kind") != "react":
        report.err(where, f"canvas_ui.kind must be 'react' (got {canvas_ui.get('kind')!r})")
    source_ref = canvas_ui.get("source_ref")
    ok_ref = None
    if not isinstance(source_ref, str) or not CANVAS_REF_RE.match(source_ref):
        report.err(where, f"canvas_ui.source_ref must match {CANVAS_REF_RE.pattern} "
                          f"(got {source_ref!r})")
    elif not (root / source_ref).is_file():
        report.err(where, f"canvas_ui.source_ref points to missing file: {source_ref}")
    else:
        ok_ref = source_ref
    if not isinstance(canvas_ui.get("enabled"), bool):
        report.err(where, "canvas_ui.enabled must be a boolean")
    version = canvas_ui.get("version")
    if not isinstance(version, int) or version < 1:
        report.err(where, "canvas_ui.version must be an integer >= 1")
    return ok_ref


# ---------------------------------------------------------------------------
# worlds/
# ---------------------------------------------------------------------------

def collect_world_info(root: Path) -> dict:
    """Map world-instance names/keys to object types, before validation."""
    name_to_type: dict[str, str] = {}
    instance_keys: set[str] = set()
    display_names: set[str] = set()
    for world_dir in _item_dirs(root / "worlds"):
        state = world_dir / "world_state.json"
        if not state.is_file():
            continue
        try:
            data = json.loads(state.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, UnicodeDecodeError, ValueError):
            continue
        objects = data.get("objects")
        if not isinstance(objects, dict):
            continue
        for key, entry in objects.items():
            if not isinstance(entry, dict):
                continue
            meta = entry.get("metadata") or {}
            otype = meta.get("type")
            if isinstance(otype, str):
                name_to_type[key] = otype
                instance_keys.add(key)
                oname = meta.get("name")
                if isinstance(oname, str):
                    name_to_type[oname] = otype
                    display_names.add(oname)
    return {
        "name_to_type": name_to_type,
        "instance_keys": instance_keys,
        "display_names": display_names,
    }


def validate_worlds(root: Path, report: Report) -> tuple[int, set[str]]:
    names: set[str] = set()
    count = 0
    for world_dir in _item_dirs(root / "worlds"):
        count += 1
        name = world_dir.name
        names.add(name)
        where = f"worlds/{name}"
        if not NAME_RE.match(name):
            report.err(where, f"folder name violates {NAME_RE.pattern}")
        state = world_dir / "world_state.json"
        if not state.is_file():
            report.err(f"{where}/world_state.json", "missing")
            continue
        data = _load_json(state, report)
        if not isinstance(data, dict):
            continue
        version = data.get("version")
        if str(version) not in KNOWN_WORLD_VERSIONS:
            report.warn(f"{where}/world_state.json",
                        f"unknown schema version {version!r} (known: {sorted(KNOWN_WORLD_VERSIONS)})")
        objects = data.get("objects")
        if not isinstance(objects, dict):
            report.err(f"{where}/world_state.json", "objects must be a dict keyed by instance name")
            continue
        for key, entry in objects.items():
            if not isinstance(entry, dict):
                continue
            geom = entry.get("geometry") or {}
            if geom.get("type") == "articulated":
                yaml_path = geom.get("yaml_path")
                if isinstance(yaml_path, str) and yaml_path.startswith("/"):
                    report.err(f"{where}/world_state.json",
                               f"instance {key!r}: geometry.yaml_path is an ABSOLUTE path "
                               f"({yaml_path!r}) baked in from another machine — must be "
                               "project-relative; the world fails to load anywhere else")
                elif isinstance(yaml_path, str) and not (root / yaml_path).is_file():
                    report.err(f"{where}/world_state.json",
                               f"instance {key!r}: geometry.yaml_path {yaml_path!r} does "
                               "not exist in the project — the world fails to load on a "
                               "fresh clone")
                otype = (entry.get("metadata") or {}).get("type")
                if isinstance(otype, str):
                    odir = root / "objects" / otype
                    if not (odir / f"{otype}.object_model.yaml").is_file():
                        report.warn(f"{where}/world_state.json",
                                    f"instance {key!r}: no objects/{otype}/ in this project "
                                    "(will rely on the mesh database at load time)")
    return count, names


# ---------------------------------------------------------------------------
# objects/
# ---------------------------------------------------------------------------

def validate_objects(root: Path, report: Report) -> int:
    count = 0
    for obj_dir in _item_dirs(root / "objects"):
        count += 1
        name = obj_dir.name
        where = f"objects/{name}"
        if not NAME_RE.match(name):
            report.err(where, f"folder name violates {NAME_RE.pattern}")
            continue

        urdf = obj_dir / f"{name}.urdf"
        link_names: set[str] = set()
        if not urdf.is_file():
            report.err(f"{where}/{name}.urdf", "missing")
        else:
            try:
                robot = ET.parse(urdf).getroot()
                if robot.tag != "robot":
                    report.err(str(urdf), f"root element must be <robot>, got <{robot.tag}>")
                elif robot.get("name") != name:
                    report.warn(str(urdf), f"<robot name={robot.get('name')!r}> != folder name {name!r}")
                link_names = {l.get("name", "") for l in robot.findall("link")}
            except ET.ParseError as exc:
                report.err(str(urdf), f"invalid XML: {exc}")

        model = obj_dir / f"{name}.object_model.yaml"
        if not model.is_file():
            report.err(f"{where}/{name}.object_model.yaml", "missing")
            continue
        data = _load_yaml(model, report)
        if not isinstance(data, dict):
            continue
        if "urdf" not in data:
            report.err(str(model), "missing 'urdf' field")
        if "default" not in (data.get("articulations") or {}):
            report.err(str(model), "articulations.default is required")
        anchors = data.get("anchors") or {}
        if "object" not in anchors:
            report.err(str(model), "an anchor named 'object' is required")
        for aname, anchor in anchors.items():
            if not isinstance(anchor, dict):
                report.err(str(model), f"anchor {aname!r} is not a mapping")
                continue
            parent = anchor.get("parent_link")
            if link_names and isinstance(parent, str) and parent not in link_names:
                report.err(str(model), f"anchor {aname!r}: parent_link {parent!r} is not a "
                                       f"URDF link (has: {', '.join(sorted(link_names))})")
            if link_names and aname in link_names:
                report.warn(str(model), f"anchor {aname!r} collides with a URDF link name")
            lta = anchor.get("link_T_anchor")
            if not isinstance(lta, dict) or "xyz" not in lta or "wxyz" not in lta:
                report.err(str(model), f"anchor {aname!r}: link_T_anchor needs xyz and wxyz")
            else:
                wxyz = lta.get("wxyz")
                if isinstance(wxyz, list) and len(wxyz) == 4:
                    norm2 = sum(float(x) * float(x) for x in wxyz if isinstance(x, (int, float)))
                    if norm2 < 1e-6:
                        report.err(str(model), f"anchor {aname!r}: wxyz is (near-)zero — "
                                               "placeholder quaternion, not a rotation")
    return count


# ---------------------------------------------------------------------------
# canvas/
# ---------------------------------------------------------------------------

def validate_canvases(root: Path, canvas_refs: set[str], report: Report) -> int:
    canvas_dir = root / "canvas"
    if not canvas_dir.is_dir():
        return 0
    count = 0
    for path in sorted(canvas_dir.glob("*.tsx")):
        count += 1
        rel = f"canvas/{path.name}"
        if not CANVAS_STEM_RE.match(path.stem):
            report.err(rel, f"filename stem must match {CANVAS_STEM_RE.pattern} — the "
                            "platform cannot list, fetch, or save this canvas")
        size = path.stat().st_size
        if size > CANVAS_CAP:
            report.err(rel, f"{size} bytes exceeds the 256 KiB canvas cap — editor save "
                            "rejects it")
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError, ValueError) as exc:
            report.err(rel, f"cannot read: {exc}")
            continue
        if "export default" not in content:
            report.err(rel, "must `export default` a React component")
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("import ") and " from " in stripped:
                m = re.search(r"""from\s+['"]([^'"]+)['"]""", stripped)
                mod = m.group(1) if m else ""
                if mod not in {"react", "react-dom"} and not mod.startswith("react-dom/") \
                        and not mod.startswith("react/"):
                    report.err(rel, f"import of {mod!r} — the sandbox vendors only react "
                                    "and react-dom; anything else throws at module "
                                    "evaluation and the canvas cannot load")
        if rel not in canvas_refs:
            report.warn(rel, "not referenced by any workflow's canvas_ui block")
    return count


# ---------------------------------------------------------------------------
# project-wide file checks
# ---------------------------------------------------------------------------

def validate_files(root: Path, report: Report) -> None:
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel_parts = path.relative_to(root).parts
        if rel_parts and rel_parts[0] in {".zeon", ".git", "__pycache__"}:
            continue
        rel = "/".join(rel_parts)
        size = path.stat().st_size
        if size >= BLOB_CAP:
            if rel_parts[0] == "data":
                # Run-artifact push skips oversized files instead of failing.
                report.warn(rel, f"{size} bytes ≥ the 16 MB blob cap — this artifact "
                                 "will be silently skipped by the run-end sync")
            else:
                report.err(rel, f"{size} bytes ≥ the 16 MB sync blob cap — every future "
                                "commit/push of this project will fail")
        elif size >= BLOB_WARN and rel_parts[0] != "data":
            report.warn(rel, f"{size} bytes is close to the 16 MB sync blob cap")
        if path.suffix.lower() in MESH_SUFFIXES and rel_parts[0] not in {"data", "worlds"}:
            report.warn(rel, "mesh-like binary in the project tree — meshes belong in "
                             "the mesh database, not in project files")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def run(root: Path) -> dict:
    report = Report()
    manifest = load_manifest()
    if not manifest:
        report.warn("validate.py", "execution-function manifest not found — API call-site "
                                   "checks skipped")
    world_info = collect_world_info(root)
    project = validate_project_json(root, report)
    n_skills, skill_sigs = validate_skills(root, report, manifest, world_info)
    n_workflows, workflow_ids, canvas_refs, all_input_names = validate_workflows(
        root, report, skill_sigs)
    n_worlds, world_names = validate_worlds(root, report)
    n_objects = validate_objects(root, report)
    n_canvases = validate_canvases(root, canvas_refs, report)
    n_presets = validate_input_presets(root, report, all_input_names)
    validate_files(root, report)
    validate_active_refs(project, workflow_ids, world_names, report)
    return {
        "ok": not report.errors,
        "errors": report.errors,
        "warnings": report.warnings,
        "summary": {
            "skills": n_skills,
            "workflows": n_workflows,
            "worlds": n_worlds,
            "objects": n_objects,
            "canvases": n_canvases,
            "input_presets": n_presets,
        },
    }


def main(argv: list[str]) -> int:
    args = [a for a in argv[1:] if a != "--json"]
    as_json = "--json" in argv[1:]
    if len(args) > 1:
        print("usage: validate.py [<project_root>] [--json]", file=sys.stderr)
        return 2
    root = (Path(args[0]) if args else Path.cwd()).resolve()
    if not root.is_dir():
        print(f"not a directory: {root}", file=sys.stderr)
        return 2

    result = run(root)

    if as_json:
        json.dump(result, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        s = result["summary"]
        print(f"{root}")
        extras = f", {s['input_presets']} input presets" if s.get("input_presets") else ""
        print(f"  {s['skills']} skills, {s['workflows']} workflows, {s['worlds']} worlds, "
              f"{s['objects']} objects, {s['canvases']} canvases{extras}")
        for e in result["errors"]:
            print(f"  ERROR    {e['where']}: {e['msg']}")
        for w in result["warnings"]:
            print(f"  warning  {w['where']}: {w['msg']}")
        print(f"  {'OK' if result['ok'] else 'FAILED'} — "
              f"{len(result['errors'])} error(s), {len(result['warnings'])} warning(s)")

    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
