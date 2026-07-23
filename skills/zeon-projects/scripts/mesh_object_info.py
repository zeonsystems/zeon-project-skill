#!/usr/bin/env python3
"""Read an object's real anchors/articulations from the shared mesh database.

Usage:
    python3 mesh_object_info.py <object_name> [<project_root>]
    python3 mesh_object_info.py --list [<project_root>]

Fetches ONLY the item's manifest and its <name>.object_model.yaml blob (never
mesh binaries) and prints JSON: anchors (name, parent_link, xyz, wxyz,
description), articulation joints, parts, and whether the item is
materializable (has both the URDF and the object-model YAML — geometry-only
catalog items exist and `zeon new object` hard-fails on them).

Use this BEFORE writing skill code against an object that is not yet
materialized into the project — anchor names are the contract between skill
code and objects, and a wrong name fails only at run time.

Auth/URL: token like the CLI (env, ./.env, ~/.zeon/.env); sync URL from
ZEON_SYNC_URL or .zeon/config remote_url, defaulting to
https://zeonsystems.app/sync. Requires PyYAML for anchor parsing.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

DEFAULT_SYNC_URL = "https://zeonsystems.app/sync"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cloud_delta import build_opener, read_config, resolve_token  # noqa: E402


def _get(url: str, token: str) -> bytes:
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with build_opener().open(req, timeout=30) as resp:
        return resp.read()


def _sync_url(root: Path) -> str:
    if os.environ.get("ZEON_SYNC_URL"):
        return os.environ["ZEON_SYNC_URL"].rstrip("/")
    cfg = read_config(root / ".zeon")
    if cfg.get("remote_url"):
        return str(cfg["remote_url"]).rstrip("/")
    return DEFAULT_SYNC_URL


def main(argv: list[str]) -> int:
    args = [a for a in argv[1:] if not a.startswith("--")]
    list_mode = "--list" in argv[1:]
    if not list_mode and not args:
        print(__doc__, file=sys.stderr)
        return 2
    name = None if list_mode else args[0]
    root = Path.cwd()
    root_args = args if list_mode else args[1:]
    if root_args:
        candidate = Path(root_args[-1])
        if not candidate.is_dir():
            print(f"project root not found: {candidate}", file=sys.stderr)
            return 2
        root = candidate.resolve()

    token = resolve_token(root)
    if token is None:
        print("no ZEON_API_TOKEN found (env, ./.env, ~/.zeon/.env); "
              "ask the user to run `zeon auth login`", file=sys.stderr)
        return 1
    base = _sync_url(root)

    try:
        if list_mode:
            data = json.loads(_get(f"{base}/mesh-database", token))
            items = (data.get("items") if isinstance(data, dict) else data) or []
            out = []
            for it in items:
                if isinstance(it, dict):
                    files = it.get("manifest") or it.get("files") or []
                    nm = it.get("name", "?")
                    out.append({
                        "name": nm,
                        "tags": it.get("tags", []),
                        "materializable": any(str(f).endswith(".object_model.yaml") for f in files)
                        and any(str(f).endswith(".urdf") for f in files),
                    })
            json.dump({"items": out}, sys.stdout, indent=2)
            sys.stdout.write("\n")
            return 0

        quoted = urllib.parse.quote(name, safe="")
        item = json.loads(_get(f"{base}/mesh-database/{quoted}", token))
        files = item.get("manifest") or item.get("files") or []
        file_names = [str(f) for f in files]
        has_yaml = any(f.endswith(".object_model.yaml") for f in file_names)
        has_urdf = any(f.endswith(".urdf") for f in file_names)

        result: dict = {
            "name": name,
            "tags": item.get("tags", []),
            "visibility": item.get("visibility"),
            "files": file_names,
            "materializable": has_yaml and has_urdf,
        }
        if not (has_yaml and has_urdf):
            result["note"] = ("geometry-only catalog item — `zeon new object` will fail "
                              "with 'missing required file(s)'")
        if has_yaml:
            blob = _get(f"{base}/mesh-database/{quoted}/blobs/{quoted}.object_model.yaml", token)
            try:
                import yaml  # type: ignore
                try:
                    model = yaml.safe_load(blob.decode("utf-8", errors="replace"))
                except yaml.YAMLError:
                    model = None
                if not isinstance(model, dict):
                    result["anchors_raw_yaml"] = blob.decode("utf-8", errors="replace")
                    model = {}
                anchors = model.get("anchors") or {}
                result["anchors"] = {
                    a: {
                        "parent_link": v.get("parent_link"),
                        "description": v.get("description", ""),
                        "xyz": (v.get("link_T_anchor") or {}).get("xyz"),
                        "wxyz": (v.get("link_T_anchor") or {}).get("wxyz"),
                        **({"grasp": v["grasp"]} if isinstance(v.get("grasp"), dict) else {}),
                    }
                    for a, v in anchors.items() if isinstance(v, dict)
                }
                arts = model.get("articulations") or {}
                joints = set()
                for art in arts.values():
                    if isinstance(art, dict):
                        joints |= set((art.get("joints") or {}).keys())
                result["joints"] = sorted(joints)
                result["parts"] = sorted((model.get("parts") or {}).keys())
            except ImportError:
                result["anchors_raw_yaml"] = blob.decode("utf-8")
        json.dump(result, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            print(f"not found in the mesh database: {name!r}", file=sys.stderr)
        else:
            print(f"HTTP {exc.code} from {base}", file=sys.stderr)
        return 1
    except (urllib.error.URLError, TimeoutError) as exc:
        print(f"cannot reach {base}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
