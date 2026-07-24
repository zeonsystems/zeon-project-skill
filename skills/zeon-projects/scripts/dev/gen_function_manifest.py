#!/usr/bin/env python3
"""Regenerate references/execution-functions.json from a zeon platform checkout.

Usage:
    python3 gen_function_manifest.py <path-to-zeon-repo> [--write]

Reads the curated ``__all__`` from
``services/execution/src/execution/execution_functions/__init__.py`` and
AST-parses every module in that package to extract, for each exported name:

  - kind: "function" | "constant" | "class"
  - signature: ordered parameters with {name, kind, default?, annotation?}
    (kind: positional | keyword_only | vararg | kwarg)
  - doc: first line of the docstring

Run this whenever the platform's skill-facing API changes, diff the result,
and commit. The validator loads the manifest to lint imports and call sites
in skill code; the manifest carries the source commit for provenance.

Maintainer tool — requires a zeon platform checkout; not needed by skill users.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

PKG_REL = "services/execution/src/execution/execution_functions"
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


def _literal(node: ast.expr) -> str:
    try:
        return repr(ast.literal_eval(node))
    except (ValueError, SyntaxError):
        return ast.unparse(node)


def _strip_module(entry: dict) -> dict:
    """Drop the internal module-split field — the public manifest documents
    the API surface, not how the platform organizes its source."""
    return {k: v for k, v in entry.items() if k != "module"}


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


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    repo = Path(argv[1]).resolve()
    pkg = repo / PKG_REL
    init = pkg / "__init__.py"
    if not init.is_file():
        print(f"not a zeon checkout (missing {init})", file=sys.stderr)
        return 2

    init_tree = ast.parse(init.read_text(encoding="utf-8"))
    exported: list[str] = []
    for node in init_tree.body:
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name) and tgt.id == "__all__":
                    exported = list(ast.literal_eval(node.value))
    if not exported:
        print("could not find __all__", file=sys.stderr)
        return 2

    defs: dict[str, dict] = {}
    for py in sorted(pkg.glob("*.py")):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                doc = ast.get_docstring(node) or ""
                defs.setdefault(node.name, {
                    "kind": "function",
                    "signature": _signature(node),
                    "doc": doc.splitlines()[0] if doc else "",
                    "module": py.stem,
                })
            elif isinstance(node, ast.ClassDef):
                doc = ast.get_docstring(node) or ""
                defs.setdefault(node.name, {
                    "kind": "class",
                    "doc": doc.splitlines()[0] if doc else "",
                    "module": py.stem,
                })
            elif isinstance(node, ast.Assign):
                for tgt in node.targets:
                    if isinstance(tgt, ast.Name):
                        # Redact device-identifying constant values (BLE names,
                        # serials) — the manifest ships publicly; the NAME of
                        # the constant is the API, its value is not.
                        redact = tgt.id.endswith(("_BLE_NAME", "_SERIAL", "_MAC"))
                        defs.setdefault(tgt.id, {
                            "kind": "constant",
                            "value": "<device-specific>" if redact else _literal(node.value),
                            "module": py.stem,
                        })

    # Provenance stamp: the DATE of the platform checkout, never its commit sha
    # or branch. This file ships in a public repo; internal VCS identifiers do
    # not belong in it. A date is all the staleness signal a reader needs, and
    # maintainers can map it back to a commit from their own checkout.
    try:
        stamp = subprocess.run(
            ["git", "-C", str(repo), "log", "-1", "--format=%cs"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
    except Exception:
        stamp = "unknown"

    functions = {}
    missing = []
    excluded = _excluded_prefixes()
    for name in exported:
        if excluded and name.startswith(excluded):
            continue
        if name in defs:
            functions[name] = _strip_module(defs[name])
        else:
            # Re-exported from outside the package (e.g. SkillObject from
            # protocol_schema) — record presence without a local definition.
            functions[name] = {"kind": "reexport"}
            missing.append(name)

    manifest = {
        "source": f"execution.execution_functions, platform source dated {stamp}",
        "note": "Curated skill-facing API (__all__). Regenerate with scripts/dev/gen_function_manifest.py.",
        "functions": functions,
    }
    out = json.dumps(manifest, indent=2, sort_keys=False) + "\n"
    if "--write" in argv:
        OUT_REL.write_text(out, encoding="utf-8")
        print(f"wrote {OUT_REL} ({len(functions)} names, {len(missing)} re-exports)")
    else:
        sys.stdout.write(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
