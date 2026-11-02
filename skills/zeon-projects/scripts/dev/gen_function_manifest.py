#!/usr/bin/env python3
"""Regenerate the vendored skill API manifests from a zeon platform checkout.

Usage:
    python3 gen_function_manifest.py <path-to-zeon-repo> [--api v2|v1] [--static] [--write]

  --api v2 (default)  ``execution.skill_api``          -> references/skill-api.json
  --api v1            ``execution.execution_functions`` -> references/execution-functions.json (legacy)

For each name in the package's ``__all__`` the manifest records:

  - kind: "function" | "class" | "constant" | "reexport"
  - signature (functions): ordered parameters {name, kind, default?, annotation?}
    (kind: positional | keyword_only | vararg | kwarg)
  - doc: first line of the docstring
  - methods / fields (classes), bases / hint (exceptions)
  - deprecated / retired: set when the docstring says so (validate.py warns on a call)

Two ways to read the API:

  1. import (preferred): run this script with the platform's Python environment
     (the workspace venv; ZEON_PROFILE defaults to "simulation" for the
     import); it imports the package from the checkout given and
     introspects the real objects, re-exports included.
  2. static (fallback, or ``--static``): AST-parse the package sources; works
     with any Python 3.9+, no platform dependencies. Re-exported names are
     resolved from the v1 package when they come from there.

Run it whenever the platform's skill-facing API changes, diff the result, and
commit. The validator loads both manifests to lint imports and call sites in
skill code; each manifest carries the date of the platform checkout.

Maintainer tool: requires a zeon platform checkout; not needed by skill users.
"""

from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
from pathlib import Path

SRC_REL = "services/execution/src"
PACKAGES = {
    "v2": ("execution.skill_api", "skill-api.json"),
    "v1": ("execution.execution_functions", "execution-functions.json"),
}
REFS = Path(__file__).resolve().parent.parent.parent / "references"

# Names a v2 skill imports by name (not star-exported); recorded so the
# validator accepts `from execution.skill_api import deg` and can explain a
# star-import-only use of them.
V2_BY_NAME = ("Target", "Keep", "Hold", "Axis", "Region", "facing", "Tolerance", "FREE_YAW", "MoveResult",
              "Posture", "deg", "mm", "bind", "bind_set", "current")

# API families excluded from the public manifest (e.g. unannounced
# integrations) are listed one prefix per line in a git-ignored local file
# next to this script; names matching any prefix are dropped even though
# they are in __all__.
_EXCLUSIONS_FILE = Path(__file__).resolve().parent / "manifest-exclusions.txt"

# Constant values that identify a device (BLE names, serials) are redacted:
# the manifest ships publicly; the NAME of the constant is the API.
_REDACT_SUFFIXES = ("_BLE_NAME", "_SERIAL", "_MAC")


def _excluded_prefixes() -> tuple[str, ...]:
    try:
        return tuple(
            line.strip() for line in _EXCLUSIONS_FILE.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        )
    except OSError:
        return ()


def _clean(text: str) -> str:
    """Docstring markup to plain text: ``x`` -> `x`, :func:`~.mod.name` -> `name`."""
    text = re.sub(r":[a-z]+:`~?\.?([\w.]+)`", lambda m: "`" + m.group(1).split(".")[-1] + "`", text)
    text = text.replace("``", "`")
    return re.sub(r"\bBas's\b", "the planner's", text)  # internal names stay out of customer docs


def _first_line(doc: str | None) -> str:
    doc = (doc or "").strip()
    return _clean(doc.splitlines()[0].strip()) if doc else ""


def _flags(doc: str | None) -> dict:
    """deprecated / retired markers from the docstring's first paragraph."""
    head = (doc or "").strip().split("\n\n")[0]
    out: dict = {}
    if head.startswith("Deprecated"):
        out["deprecated"] = _clean(" ".join(head.split()))
    if "Retired: raises" in head:
        out["retired"] = True
    return out


# ---------------------------------------------------------------------------
# import mode
# ---------------------------------------------------------------------------

def _import_entries(repo: Path, package: str) -> tuple[list[str], dict, dict]:
    import importlib
    import inspect
    import os

    # The execution package reads a startup profile at import; the sim one
    # needs no hardware.
    os.environ.setdefault("ZEON_PROFILE", "simulation")
    sys.path.insert(0, str(repo / SRC_REL))
    mod = importlib.import_module(package)
    exported = list(mod.__all__)

    kind_map = {
        inspect.Parameter.POSITIONAL_ONLY: "positional",
        inspect.Parameter.POSITIONAL_OR_KEYWORD: "positional",
        inspect.Parameter.VAR_POSITIONAL: "vararg",
        inspect.Parameter.KEYWORD_ONLY: "keyword_only",
        inspect.Parameter.VAR_KEYWORD: "kwarg",
    }

    def ann(a) -> str | None:
        if a is inspect.Parameter.empty:
            return None
        return a if isinstance(a, str) else inspect.formatannotation(a)

    def sig_of(fn) -> list[dict] | None:
        try:
            sig = inspect.signature(fn)
        except (TypeError, ValueError):
            return None
        params = []
        for p in sig.parameters.values():
            e: dict = {"name": p.name, "kind": kind_map[p.kind]}
            a = ann(p.annotation)
            if a is not None:
                e["annotation"] = a
            if p.default is not inspect.Parameter.empty:
                e["default"] = repr(p.default)
            params.append(e)
        return params

    def describe(name: str, obj) -> dict:
        if inspect.isclass(obj):
            e: dict = {"kind": "class", "doc": _first_line(obj.__doc__)}
            if issubclass(obj, BaseException):
                e["bases"] = [b.__name__ for b in obj.__bases__]
                hint = getattr(obj, "hint_default", "")
                if hint:
                    e["hint"] = hint
                return e
            methods = {}
            for m, v in vars(obj).items():
                if m.startswith("_"):
                    continue
                if isinstance(v, property):
                    methods[m] = {"property": True, "doc": _first_line(v.__doc__)}
                elif isinstance(v, (classmethod, staticmethod)) or inspect.isfunction(v):
                    fn = v.__func__ if isinstance(v, (classmethod, staticmethod)) else v
                    sig = sig_of(fn)
                    if sig and sig[0]["name"] in ("self", "cls"):
                        sig = sig[1:]
                    methods[m] = {"signature": sig or [], "doc": _first_line(fn.__doc__)}
            fields = getattr(obj, "__dataclass_fields__", None)
            if fields:
                e["fields"] = list(fields)
            if methods:
                e["methods"] = methods
            e.update(_flags(obj.__doc__))
            return e
        if callable(obj):
            e = {"kind": "function", "signature": sig_of(obj) or [], "doc": _first_line(obj.__doc__)}
            e.update(_flags(obj.__doc__))
            return e
        value = "<device-specific>" if name.endswith(_REDACT_SUFFIXES) else repr(obj)
        return {"kind": "constant", "value": value}

    entries = {n: describe(n, getattr(mod, n)) for n in exported if hasattr(mod, n)}
    by_name = {}
    if package == PACKAGES["v2"][0]:
        for n in V2_BY_NAME:
            obj = getattr(mod, n, None)
            if obj is not None:
                by_name[n] = {k: v for k, v in describe(n, obj).items() if k in ("kind", "doc", "signature", "value")}
    return exported, entries, by_name


# ---------------------------------------------------------------------------
# static mode
# ---------------------------------------------------------------------------

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


def _signature(fn: ast.FunctionDef | ast.AsyncFunctionDef, drop_self: bool = False) -> list[dict]:
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
    if drop_self and params and params[0]["name"] in ("self", "cls"):
        params = params[1:]
    return params


def _static_defs(pkg: Path) -> dict[str, dict]:
    defs: dict[str, dict] = {}
    for py in sorted(pkg.glob("*.py")):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                doc = ast.get_docstring(node)
                e = {"kind": "function", "signature": _signature(node), "doc": _first_line(doc)}
                e.update(_flags(doc))
                defs.setdefault(node.name, e)
            elif isinstance(node, ast.ClassDef):
                doc = ast.get_docstring(node)
                e = {"kind": "class", "doc": _first_line(doc)}
                methods = {}
                for sub in node.body:
                    if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)) and not sub.name.startswith("_"):
                        is_prop = any(isinstance(d, ast.Name) and d.id == "property" for d in sub.decorator_list)
                        sdoc = _first_line(ast.get_docstring(sub))
                        methods[sub.name] = ({"property": True, "doc": sdoc} if is_prop
                                             else {"signature": _signature(sub, drop_self=True), "doc": sdoc})
                if methods:
                    e["methods"] = methods
                e.update(_flags(doc))
                defs.setdefault(node.name, e)
            elif isinstance(node, ast.Assign):
                for tgt in node.targets:
                    if isinstance(tgt, ast.Name) and not tgt.id.startswith("_"):
                        redact = tgt.id.endswith(_REDACT_SUFFIXES)
                        defs.setdefault(tgt.id, {
                            "kind": "constant",
                            "value": "<device-specific>" if redact else _literal(node.value),
                        })
    return defs


def _module_lists(pkg: Path) -> dict[str, list[str]]:
    """Literal list/tuple assignments per module (``__all__``, ``CARRIED``, ...)."""
    out: dict[str, list[str]] = {}
    for py in sorted(pkg.glob("*.py")):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, ast.Assign) and isinstance(node.value, (ast.List, ast.Tuple)):
                for tgt in node.targets:
                    if isinstance(tgt, ast.Name):
                        try:
                            out[f"{py.stem}.{tgt.id}"] = list(ast.literal_eval(node.value))
                        except (ValueError, SyntaxError):
                            pass
    return out


def _static_all(pkg: Path) -> list[str]:
    """``__all__`` of the package's __init__: a literal, or (v2) built from the
    submodules' lists via names imported into __init__."""
    init = pkg / "__init__.py"
    tree = ast.parse(init.read_text(encoding="utf-8"))
    lists = _module_lists(pkg)
    alias: dict[str, list[str]] = {}
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.level == 1 and node.module:
            for a in node.names:
                key = f"{node.module}.{a.name}"
                if key in lists:
                    alias[a.asname or a.name] = lists[key]

    def expand(expr: ast.expr) -> list[str]:
        names: list[str] = []
        for elt in getattr(expr, "elts", []):
            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                names.append(elt.value)
            elif isinstance(elt, ast.Starred) and isinstance(elt.value, ast.Name):
                names.extend(alias.get(elt.value.id, []))
        return names

    exported: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets):
            exported = expand(node.value)
        elif isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name) and node.target.id == "__all__":
            # `__all__ += [n for n in _camera if n not in __all__]`
            if isinstance(node.value, ast.ListComp):
                src = node.value.generators[0].iter
                if isinstance(src, ast.Name):
                    exported += [n for n in alias.get(src.id, []) if n not in exported]
            else:
                exported += expand(node.value)
    return exported


def _static_entries(repo: Path, package: str) -> tuple[list[str], dict, dict]:
    pkg = repo / SRC_REL / package.replace(".", "/")
    exported = _static_all(pkg)
    defs = _static_defs(pkg)
    v1_pkg = repo / SRC_REL / PACKAGES["v1"][0].replace(".", "/")
    v1_defs = _static_defs(v1_pkg) if v1_pkg != pkg and v1_pkg.is_dir() else {}
    entries = {}
    for n in exported:
        if n in defs:
            entries[n] = defs[n]
        elif n in v1_defs:
            entries[n] = v1_defs[n]
    by_name = {}
    if package == PACKAGES["v2"][0]:
        for n in V2_BY_NAME:
            if n in defs:
                by_name[n] = {k: v for k, v in defs[n].items() if k in ("kind", "doc", "signature", "value")}
            else:
                by_name[n] = {"kind": "reexport"}
    return exported, entries, by_name


# ---------------------------------------------------------------------------

def main(argv: list[str]) -> int:
    api = "v2"
    rest = list(argv[1:])
    if "--api" in rest:
        i = rest.index("--api")
        api = rest[i + 1] if i + 1 < len(rest) else ""
        del rest[i:i + 2]
    args = [a for a in rest if not a.startswith("--")]
    if not args or api not in PACKAGES:
        print(__doc__, file=sys.stderr)
        return 2
    repo = Path(args[0]).resolve()
    package, out_name = PACKAGES[api]
    pkg_dir = repo / SRC_REL / package.replace(".", "/")
    if not (pkg_dir / "__init__.py").is_file():
        print(f"not a zeon checkout (missing {pkg_dir / '__init__.py'})", file=sys.stderr)
        return 2

    mode = "static"
    if "--static" not in rest:
        try:
            exported, entries, by_name = _import_entries(repo, package)
            mode = "import"
        except Exception as exc:  # noqa: BLE001 -- any import failure falls back to the static reader
            print(f"import of {package} failed ({type(exc).__name__}: {exc}); reading the sources statically",
                  file=sys.stderr)
    if mode == "static":
        exported, entries, by_name = _static_entries(repo, package)
    if not exported:
        print("could not find __all__", file=sys.stderr)
        return 2

    # Provenance stamp: the DATE of the platform checkout, never its commit sha
    # or branch. This file ships in a public repo; internal VCS identifiers do
    # not belong in it.
    try:
        stamp = subprocess.run(
            ["git", "-C", str(repo), "log", "-1", "--format=%cs"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
    except Exception:  # noqa: BLE001
        stamp = "unknown"

    functions = {}
    excluded = _excluded_prefixes()
    for name in exported:
        if excluded and name.startswith(excluded):
            continue
        functions[name] = entries.get(name, {"kind": "reexport"})

    if api == "v2":
        note = ("Skill API v2 (`from execution.skill_api import *`): __all__ is the API. "
                "importable_by_name: not star-exported, import them by name. "
                "Regenerate with scripts/dev/gen_function_manifest.py.")
    else:
        note = ("Skill API v1 (legacy; `from execution.execution_functions import *`). Entries marked "
                "retired raise on the current platform: port the skill to v2 (skill-api.json). "
                "Regenerate with scripts/dev/gen_function_manifest.py --api v1.")
    manifest = {
        "api": api,
        "source": f"{package}, platform source dated {stamp}",
        "note": note,
        "functions": functions,
    }
    if by_name:
        manifest["importable_by_name"] = by_name
    out = json.dumps(manifest, indent=2, sort_keys=False) + "\n"
    if "--write" in rest:
        path = REFS / out_name
        path.write_text(out, encoding="utf-8")
        print(f"wrote {path} ({len(functions)} names of {len(exported)} in __all__, {mode} read)")
    else:
        sys.stdout.write(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
