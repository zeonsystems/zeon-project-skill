#!/usr/bin/env python3
"""Read-only check of how a local Zeon working tree relates to the cloud.

Usage:
    python3 cloud_delta.py [<project_root>]

Prints JSON:
    {
      "project_id": "...",
      "local_head": "<sha>|null",
      "last_synced_remote": "<sha>|null",   # .zeon/remote_refs/heads/main
      "cloud_head": "<sha>|null",           # live ref from the sync service
      "merge_in_progress": bool,
      "cloud_moved": bool,       # cloud_head != last_synced_remote
      "local_ahead": bool        # local_head != last_synced_remote
    }

Unlike `zeon sync`, this NEVER mutates anything — no auto-commit, no merge,
no conflict markers. Use it before editing to learn whether the cloud moved
(e.g. the user edited in the web IDE) and whether local work is unpushed.

Auth: resolves ZEON_API_TOKEN exactly like the CLI (shell env, then ./.env,
then ~/.zeon/.env). The token stays in memory and is never printed.
Pure stdlib. Exit 0 on success, 1 when the cloud is unreachable/unauthorized
(local fields are still printed), 2 on usage errors (not a linked project).
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

try:
    import tomllib
except ImportError:  # Python < 3.11
    tomllib = None  # type: ignore


def _read_env_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def resolve_token(root: Path) -> str | None:
    if os.environ.get("ZEON_API_TOKEN"):
        return os.environ["ZEON_API_TOKEN"]
    for env_path in (root / ".env", Path.home() / ".zeon" / ".env"):
        tok = _read_env_file(env_path).get("ZEON_API_TOKEN")
        if tok:
            return tok
    return None


def read_config(zeon_dir: Path) -> dict:
    cfg_path = zeon_dir / "config"
    if not cfg_path.is_file():
        return {}
    text = cfg_path.read_text(encoding="utf-8")
    if tomllib is not None:
        try:
            return tomllib.loads(text)
        except tomllib.TOMLDecodeError:
            pass
    # Minimal fallback: key = "value" lines.
    cfg = {}
    for m in re.finditer(r'^(\w+)\s*=\s*"([^"]*)"', text, re.M):
        cfg[m.group(1)] = m.group(2)
    return cfg


def _read_ref(path: Path) -> str | None:
    try:
        content = path.read_text(encoding="utf-8").strip()
        return content or None
    except OSError:
        return None


class _NoCrossHostRedirect(urllib.request.HTTPRedirectHandler):
    """Refuse redirects to a different host so the Authorization header can
    never leak to a third party."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: N802
        old_host = urllib.parse.urlsplit(req.full_url).netloc
        new_host = urllib.parse.urlsplit(newurl).netloc
        if new_host != old_host:
            raise urllib.error.HTTPError(
                req.full_url, code,
                f"refusing cross-host redirect to {new_host}", headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def build_opener() -> urllib.request.OpenerDirector:
    return urllib.request.build_opener(_NoCrossHostRedirect())


def fetch_cloud_head(remote_url: str, project_id: str, token: str) -> tuple[str | None, str | None]:
    """Return (sha, error). GET the live main ref; never mutates."""
    url = f"{remote_url.rstrip('/')}/projects/{project_id}/refs/heads/main"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with build_opener().open(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("commit_sha"), None
    except urllib.error.HTTPError as exc:
        return None, f"HTTP {exc.code}"
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return None, str(exc)


def main(argv: list[str]) -> int:
    if len(argv) > 2:
        print("usage: cloud_delta.py [<project_root>]", file=sys.stderr)
        return 2
    root = (Path(argv[1]) if len(argv) == 2 else Path.cwd()).resolve()
    zeon_dir = root / ".zeon"
    if not zeon_dir.is_dir():
        print(f"not a linked Zeon working tree (no .zeon/ in {root})", file=sys.stderr)
        return 2

    cfg = read_config(zeon_dir)
    project_id = cfg.get("project_id")
    remote_url = cfg.get("remote_url")

    local_head = _read_ref(zeon_dir / "refs" / "heads" / "main")
    if local_head is None:
        head = _read_ref(zeon_dir / "HEAD")
        if head and not head.startswith("ref:"):
            local_head = head
    last_synced = _read_ref(zeon_dir / "remote_refs" / "heads" / "main")
    merge_in_progress = (zeon_dir / "MERGE_HEAD").is_file()

    cloud_head = None
    error = None
    if project_id and remote_url:
        token = resolve_token(root)
        if token is None:
            error = "no ZEON_API_TOKEN found (env, ./.env, ~/.zeon/.env)"
        else:
            cloud_head, error = fetch_cloud_head(remote_url, project_id, token)
    else:
        error = ".zeon/config missing project_id/remote_url"

    result = {
        "project_id": project_id,
        "local_head": local_head,
        "last_synced_remote": last_synced,
        "cloud_head": cloud_head,
        "merge_in_progress": merge_in_progress,
        "cloud_moved": (cloud_head is not None and cloud_head != last_synced),
        "local_ahead": (local_head is not None and local_head != last_synced),
    }
    if error:
        result["error"] = error
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 1 if error else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
