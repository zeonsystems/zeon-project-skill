#!/usr/bin/env bash
# PostToolUse hook: after a Write/Edit inside a Zeon project (any ancestor
# containing project.json), run the deterministic validator and feed errors
# back to the agent (exit 2 = blocking feedback per the hooks contract).
#
# NOTE: as of Claude Code issue #34573, plugin-shipped PostToolUse *command*
# hooks are silently dropped at plugin load — this config is shipped for the
# day that's fixed. Until then, users can install the same hook in their own
# settings.json; see the README's "Automatic validation" section.
set -u

INPUT=$(cat)

FILE_PATH=$(printf '%s' "$INPUT" | python3 -c '
import json, sys
try:
    data = json.load(sys.stdin)
    print((data.get("tool_input") or {}).get("file_path") or "")
except Exception:
    pass
')
[ -z "$FILE_PATH" ] && exit 0

DIR=$(dirname "$FILE_PATH")
PROJECT_ROOT=""
while [ "$DIR" != "/" ] && [ -n "$DIR" ]; do
  if [ -f "$DIR/project.json" ]; then PROJECT_ROOT="$DIR"; break; fi
  DIR=$(dirname "$DIR")
done
[ -z "$PROJECT_ROOT" ] && exit 0

PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
OUTPUT=$(python3 "$PLUGIN_ROOT/skills/zeon-projects/scripts/validate.py" "$PROJECT_ROOT" 2>&1)
STATUS=$?

if [ $STATUS -eq 1 ]; then
  # Validation errors: surface them to the agent as blocking feedback.
  printf 'zeon-projects validator found errors in %s:\n%s\n' "$PROJECT_ROOT" "$OUTPUT" >&2
  exit 2
fi
exit 0
