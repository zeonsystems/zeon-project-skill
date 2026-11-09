#!/usr/bin/env python3
"""Regenerate references/execution-functions.json from a zeon platform checkout.

Usage:
    python3 gen_function_manifest.py <path-to-zeon-repo> [--write]

Reads the skill API v2 surface: the ``__all__`` built in
``services/execution/src/execution/skill_api/__init__.py`` (the names a skill
gets from ``from execution.skill_api import *`` in its ``modules.py``). That
``__all__`` is assembled from literal lists and from other modules' lists
(``*_world``, ``*CARRIED``, ``__all__ += [...]``); this script resolves those
references by AST, never by importing the platform.

Each name's definition is looked up first in the ``skill_api`` package, then
in ``execution_functions`` (the v1 verbs ``skill_api/carried.py`` re-exports
unchanged). For each exported name it records:

  - kind: "function" | "constant" | "class" | "reexport"
  - signature: ordered parameters with {name, kind, default?, annotation?}
    (kind: positional | keyword_only | vararg | kwarg)
  - doc: first line of the docstring
  - deprecated: true for the names ``skill_api/deprecated.py`` keeps for old
    projects (each logs a deprecation warning on first call)

It also records the v1 verbs ``execution_functions`` retired (they raise
``NotImplementedError``), so the validator can flag v1 skills that call them.

Run this whenever the platform's skill-facing API changes, diff the result,
and commit. The validator loads the manifest to lint imports and call sites.

Maintainer tool; requires a zeon platform checkout; not needed by skill users.
"""

from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
from pathlib import Path

V2_REL = "services/execution/src/execution/skill_api"
V1_REL = "services/execution/src/execution/execution_functions"
OUT_REL = Path(__file__).resolve().parent.parent.parent / "references" / "execution-functions.json"

# API families excluded from the public manifest (e.g. unannounced
# integrations) are listed one prefix per line in a git-ignored local file
# next to this script; names matching any prefix are dropped even though
# they are in __all__.
_EXCLUSIONS_FILE = Path(__file__).resolve().parent / "manifest-exclusions.txt"


def _excluded_prefixes() -> tuple[str, ...]:
    try:
        return tuple(
            line.strip() for line in _EXCLUSIONS_FILE.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        )
    except OSError:
        return ()


# Internal names (people, studies) that appear in platform docstrings; the
# manifest ships publicly, so the first doc line is scrubbed of them.
_SCRUB = ((re.compile(r"\bBas's\s+"), "the planner's "),)


def _doc(node: ast.AST) -> str:
    doc = ast.get_docstring(node) or ""
    line = doc.splitlines()[0] if doc else ""
    for pat, rep in _SCRUB:
        line = pat.sub(rep, line)
    return line


def _literal(node: ast.expr) -> str:
    try:
        return repr(ast.literal_eval(node))
    except (ValueError, SyntaxError):
        return ast.unparse(node)


def _param(name: str, kind: str, annotation, default) -> dict:
    p: dict = {"name": name, "kind": kind}
    if annotation is not None:
        p["annotation"] = ast.unparse(annotation)
    if default is not None:
        p["default"] = _literal(default)
    return p


def _signature(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> list[dict]:
    a = fn.args
    params: list[dict] = []
    pos = a.posonlyargs + a.args
    defaults: list = [None] * (len(pos) - len(a.defaults)) + list(a.defaults)
    for arg, d in zip(pos, defaults):
        params.append(_param(arg.arg, "positional", arg.annotation, d))
    if a.vararg:
        params.append(_param(a.vararg.arg, "vararg", a.vararg.annotation, None))
    for arg, d in zip(a.kwonlyargs, a.kw_defaults):
        params.append(_param(arg.arg, "keyword_only", arg.annotation, d))
    if a.kwarg:
        params.append(_param(a.kwarg.arg, "kwarg", a.kwarg.annotation, None))
    return params


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def _top_assign(tree: ast.Module, name: str) -> ast.expr | None:
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name) and tgt.id == name:
                    return node.value
    return None


def _names_list(expr: ast.expr | None, resolve) -> list[str]:
    """A list/tuple literal of strings, with ``*Name`` elements resolved."""
    out: list[str] = []
    if isinstance(expr, (ast.List, ast.Tuple)):
        for e in expr.elts:
            if isinstance(e, ast.Constant) and isinstance(e.value, str):
                out.append(e.value)
            elif isinstance(e, ast.Starred) and isinstance(e.value, ast.Name):
                out.extend(resolve(e.value.id))
    elif isinstance(expr, ast.ListComp) and isinstance(expr.generators[0].iter, ast.Name):
        out.extend(resolve(expr.generators[0].iter.id))
    elif isinstance(expr, ast.Name):
        out.extend(resolve(expr.id))
    return out


def _v2_exports(pkg: Path) -> list[str]:
    init = _parse(pkg / "__init__.py")
    aliases: dict[str, tuple[str, str]] = {}  # local name -> (module stem, name there)
    for node in init.body:
        if isinstance(node, ast.ImportFrom) and node.level == 1 and node.module:
            for a in node.names:
                if a.name != "*":
                    aliases[a.asname or a.name] = (node.module, a.name)

    def resolve(local: str) -> list[str]:
        mod, name = aliases.get(local, (None, None))
        if mod is None or not (pkg / f"{mod}.py").is_file():
            return []
        return _names_list(_top_assign(_parse(pkg / f"{mod}.py"), name), lambda _n: [])

    exported: list[str] = []
    for node in init.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets):
            exported = _names_list(node.value, resolve)
        elif isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name) and node.target.id == "__all__":
            exported += [n for n in _names_list(node.value, resolve) if n not in exported]
    seen: set[str] = set()
    return [n for n in exported if not (n in seen or seen.add(n))]


def _collect_defs(pkg: Path, defs: dict[str, dict]) -> None:
    for py in sorted(pkg.glob("*.py")):
        tree = _parse(py)
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                defs.setdefault(node.name, {
                    "kind": "function",
                    "signature": _signature(node),
                    "doc": _doc(node),
                })
            elif isinstance(node, ast.ClassDef):
                defs.setdefault(node.name, {
                    "kind": "class",
                    "doc": _doc(node),
                })
            elif isinstance(node, ast.Assign):
                for tgt in node.targets:
                    if isinstance(tgt, ast.Name):
                        # Redact device-identifying constant values (BLE names,
                        # serials): the manifest ships publicly; the NAME of
                        # the constant is the API, its value is not.
                        redact = tgt.id.endswith(("_BLE_NAME", "_SERIAL", "_MAC"))
                        defs.setdefault(tgt.id, {
                            "kind": "constant",
                            "value": "<device-specific>" if redact else _literal(node.value),
                        })


def _retired_v1(v1: Path) -> list[str]:
    """Public v1 functions whose body raises the retired-motion NotImplementedError."""
    out: set[str] = set()
    for py in sorted(v1.glob("*.py")):
        for node in _parse(py).body:
            if isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
                for sub in ast.walk(node):
                    if (isinstance(sub, ast.Raise) and isinstance(sub.exc, ast.Call)
                            and isinstance(sub.exc.func, ast.Name) and sub.exc.func.id == "_motion_phase3"):
                        out.add(node.name)
                        break
    return sorted(out)


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    repo = Path(argv[1]).resolve()
    v2, v1 = repo / V2_REL, repo / V1_REL
    if not (v2 / "__init__.py").is_file():
        print(f"not a zeon checkout with skill API v2 (missing {v2 / '__init__.py'})", file=sys.stderr)
        return 2

    exported = _v2_exports(v2)
    if not exported:
        print("could not resolve skill_api.__all__", file=sys.stderr)
        return 2
    deprecated = set(_names_list(_top_assign(_parse(v2 / "deprecated.py"), "__all__"), lambda _n: []))

    defs: dict[str, dict] = {}
    _collect_defs(v2, defs)  # skill_api's own definitions win (is_sim_mode, pause_aware_sleep, capture_image)
    if v1.is_dir():
        _collect_defs(v1, defs)  # then the v1 verbs carried.py re-exports

    # Provenance stamp: the DATE of the platform checkout, never its commit sha
    # or branch. This file ships in a public repo; internal VCS identifiers do
    # not belong in it.
    try:
        stamp = subprocess.run(
            ["git", "-C", str(repo), "log", "-1", "--format=%cs"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
    except Exception:
        stamp = "unknown"

    functions: dict[str, dict] = {}
    excluded = _excluded_prefixes()
    for name in exported:
        if excluded and name.startswith(excluded):
            continue
        entry = dict(defs.get(name, {"kind": "reexport"}))
        if name in deprecated:
            entry["deprecated"] = True
        functions[name] = entry

    manifest = {
        "source": f"execution.skill_api (skill API v2), platform source dated {stamp}",
        "note": ("Skill-facing API: the star export of execution.skill_api (__all__). "
                 "Regenerate with scripts/dev/gen_function_manifest.py."),
        "v1_retired": _retired_v1(v1) if v1.is_dir() else [],
        "functions": functions,
    }
    out = json.dumps(manifest, indent=2, sort_keys=False) + "\n"
    if "--write" in argv:
        OUT_REL.write_text(out, encoding="utf-8")
        n_re = sum(1 for e in functions.values() if e["kind"] == "reexport")
        print(f"wrote {OUT_REL} ({len(functions)} names, {n_re} re-exports, "
              f"{len(manifest['v1_retired'])} retired v1 verbs)")
    else:
        sys.stdout.write(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
