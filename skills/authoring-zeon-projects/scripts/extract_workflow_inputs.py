#!/usr/bin/env python3
"""Print the inputs declared by a workflow.

Usage:
    python3 extract_workflow_inputs.py <workflow_path>

Output: JSON on stdout. Shape:

    {
      "workflow_id": "<id>",
      "name": "<display name>",
      "inputs": [ {<input>}, ... ]
    }

The output is what the canvas generator needs to map types → form widgets.

Exit codes:
    0 success
    2 usage error
    3 invalid JSON / not a workflow file
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: extract_workflow_inputs.py <workflow_path>", file=sys.stderr)
        return 2
    path = Path(argv[1])
    if not path.is_file():
        print(f"not a file: {path}", file=sys.stderr)
        return 2
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"invalid JSON in {path}: {exc}", file=sys.stderr)
        return 3

    if not isinstance(data, dict) or "workflow_id" not in data:
        print(f"{path}: does not look like a workflow file (missing workflow_id)", file=sys.stderr)
        return 3

    out = {
        "workflow_id": data.get("workflow_id"),
        "name": data.get("name"),
        "inputs": data.get("inputs") or [],
    }
    json.dump(out, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
