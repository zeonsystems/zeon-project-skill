# live_state.yaml — mutable per-world runtime state

> Hosted docs: [Building a world](https://readme.zeonsystems.app/docs/building-a-world.md) · [The world state file](https://readme.zeonsystems.app/docs/worlds-world-state-json.md)

`worlds/<world_id>/live_state.yaml` is the mutable sibling of the frozen
`world_state.json`: consumable counters, calibration offsets, and other
per-object runtime facts. Liquid-handling skills read and write it constantly,
and its conventions are easy to get wrong in ways that don't error — they
pipette the wrong well or reuse a spent tip.

## Shape

```yaml
version: 1
objects:
  <instance_id>:        # the world instance id (SkillObject.id) — NOT the display name
    name: tipbox_10ul_1  # display name (informational)
    type: tipbox_grey
    ...per-object state...
```

Three entry shapes you'll meet (arbitrary per-object keys are allowed):

```yaml
# Tip box
tipbox_grey_<uuid>:
  name: tipbox_10ul_1
  type: tipbox_grey
  active: true            # exactly ONE box active at a time
  tip_index: 1            # 1-based — the NEXT tip to use (1..96)
  calibration:
    '1': [0.018, 0.106]   # keys "1".."96" (string ints, 1-BASED); values [dx, dy] metres
    '96': [0.090, 0.028]

# Well plate
wellplate_pcr_<uuid>:
  name: wellplate_pcr_parts_1
  type: wellplate_pcr
  calibration:
    A1: [0.003, -0.003]   # keys are WELL LABELS "A1".."H12" — identical to anchor names
    H12: [-0.0065, 0.013]

# Pipette
epipette_10ul_<uuid>:
  name: epipette_10ul
  type: epipette_10ul
  tcp_offset: [-0.1566, 0.0024, -0.0212]   # fixed TCP→tip offset, 3-vector, metres
```

## Indexing conventions — get these exactly right

- **Tip boxes are 1-based.** `tip_index` starts at 1 and points at the *next*
  tip; calibration keys are `"1"…"96"`. Advance with `tip_index + 1` and
  **stop at 96 → hand off to the next rack** (mark it `active`, `tip_index: 1`).
  **Never** use `% 96` wrap-around or 0-based indexing — some platform
  docstrings show stale 0-based examples; the real files and every real skill
  are 1-based. Tips are addressed by integer index only; never translate a tip
  number into a well letter.
- **Well plates are keyed by well label** (`"A1"…"H12"`, rows A–H, columns
  1–12). The same string is the calibration key *and* the anchor name:
  `load_object_anchor(obj.id, "A1")` pairs with `calibration["A1"]`. No numeric
  conversion, ever.
- **Calibration values are 2-element `[dx, dy]` lists in metres** (XY only —
  Z is never calibrated here), applied as `pos[0] += dx; pos[1] += dy` on top
  of the anchor/tip pose. Not `{x:…, y:…}` dicts, not 3-element.

## The API — get_world_state / set_world_state

- **Key strictly by instance id** (`SkillObject.id` / the world instance key).
  A display name **silently returns `{}`** on read — calibration falls back to
  zeros with no error — and on write it **creates a bogus new entry** instead
  of updating the real one. validate.py flags display-name literals.
- Canonical read idiom (the zero-fallback is load-bearing — uncalibrated
  entries are absent, not zero):

  ```python
  cal = get_world_state(obj.id).get("calibration", {})
  dx, dy = cal.get(str(tip_index), [0.0, 0.0])   # tip box: str(1-based int)
  dx, dy = cal.get(well, [0.0, 0.0])             # plate: "B3"
  ```

- **Writes merge top-level keys only; nested maps are replaced wholesale.**
  `set_world_state(id, {"calibration": {"A1": [.1, .2]}})` deletes every other
  well's calibration. To edit one entry: read the whole map, mutate a copy,
  write the whole map back. Safe partial updates are top-level scalars:
  `set_world_state(tipbox_id, {"tip_index": tip_index + 1})`.
- Writes that change `tip_index`/`active` also refresh the canvas tip-count
  display — include them in the write that changes them.
- There is **no file locking** — concurrent writers are last-writer-wins on
  the whole file. Keep writes small, top-level, and sequential.

## Lifecycle

- **State persists across runs.** There is no run-start reset: a protocol that
  consumes tips keeps advancing `tip_index` run after run until the operator
  resets the box in the app ("tip box replaced" → `tip_index: 1`, `active`
  flipped). Never assume a fresh box.
- **Sim and real can share the same file** when they load the same world — a
  sim run that advances `tip_index` moves the pointer a real run will read.
  Don't treat sim writes as isolated.
- **Calibration data is provisioned externally** (hand-edited / calibration
  tooling). Skills *read* it; write calibration only when the user explicitly
  asks, respecting the wholesale-replace rule.

## Established idioms

- **Tip advancement** (attach skills): read the `active` box → use
  `tip_index` → after seating, `set_world_state(box_id, {"tip_index": n + 1})`;
  at 96, activate the next box in the project's tip-box registry with
  `tip_index: 1`; when the last box is spent, escalate to the operator
  (`references/patterns.md` reliability ladder) and reset.
- **Aspirate/dispense are read-only** — they apply calibration but never write
  state.
- **`tcp_offset`** on a pipette entry is read as the fixed TCP→tip transform
  (guard with `if stored is not None and len(stored) == 3`).
