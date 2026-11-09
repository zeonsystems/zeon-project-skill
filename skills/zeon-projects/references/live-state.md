# live_state.yaml: mutable per-world runtime state

> Hosted docs: [Building a world](https://readme.zeonsystems.app/docs/building-a-world.md) · [The world state file](https://readme.zeonsystems.app/docs/worlds-world-state-json.md)

`worlds/<world_id>/live_state.yaml` sits beside `world_state.json` and holds what
changes at run time: tip pointers, calibration offsets, per-object facts. Skills read
and write it through `get_world_state(object_id)` / `set_world_state(object_id,
updates)`. Its mistakes do not error: they pipette the wrong well or reuse a tip.

## Shape (version 2: seat-keyed)

Calibration belongs to **where an object sits and what type it is**, so it is stored
on the **holder**, per seat anchor, per occupant type:

```yaml
version: 2
objects:
  wellplate_stand_1:                 # a holder (instance id)
    type: wellplate_stand
    seats:
      top_center:                    # the seat anchor
        wellplate_pcr:               # an occupant type allowed here
          calibration_epipette_10ul: {A1: [0.003, -0.003], H12: [-0.0065, 0.013]}
          depths_epipette_10ul: {aspirate: 0.014, dispense: 0.0145}
        wellplate_96_deep: {}        # allowed, nothing taught yet
  tipbox_holder_1:
    seats:
      top_center:
        tipbox_10ul: {tip_index: 12, active: true, calibration_epipette_10ul: {"1": [0.018, 0.106]}}
  epipette_10ul_1:                   # state that travels with the object stays on it
    tcp_offset: [-0.1566, 0.0024, -0.0212]
```

- **Seat keys** (stored on the seat for a seated object): keys starting
  `calibration`, `depths_`, `attach_depths_`, `trim_`; `pipette_rpy`, `attach_rpy`,
  `mc_xy_trim`, `tip_height`, `tip_count`; and the run-time `tip_index`, `active`.
  Everything else (`tcp_offset`, `in_hand`, contents) stays on the object's own entry.
- A seat exists because it is listed under the holder's `seats`; the types under it
  are the types allowed there.
- `version: 1` files (calibration on the object entry) are still read: a seat key
  missing from the seat falls back to the object's entry. In version 2 the seat is
  the only source.

## The API

- **Key strictly by instance id** (`resolve(obj)` / `SkillObject.id`). A display
  name reads `{}` (calibration silently falls back to zeros) and a write creates a
  bogus entry. validate.py flags display-name literals.
- `get_world_state(id)` for a seated object returns its own entry with the seat
  keys taken from its seat on the holder. You do not address the holder yourself.
- `set_world_state(id, updates)` shallow-merges: seat keys go to the seat, the rest
  to the object. **Nested maps are replaced wholesale**:
  `set_world_state(id, {"calibration_epipette_10ul": {"A1": [...]}})` drops every
  other well. Read the whole map, change a copy, write it back.
- A write that changes `tip_index` or `active` refreshes the canvas tip counts;
  include them in the write that changes them.
- No file locking: concurrent writers are last-writer-wins. Keep writes small and
  sequential.

Read idiom (uncalibrated entries are absent, not zero):

```python
cal = get_world_state(plate_id).get("calibration_epipette_10ul", {})
dx, dy = cal.get(well, [0.0, 0.0])          # plate: "B3"
dx, dy = cal.get(str(tip_index), [0.0, 0.0])  # tip box: str(1-based int)
```

Use the calibration key names the project's existing skills use.

## Indexing conventions

- **Tip boxes are 1-based.** `tip_index` is the next tip, `1..96`; calibration keys
  are `"1".."96"`. Advance with `+ 1` and at 96 hand off to the next box (`active`,
  `tip_index: 1`). Never wrap with `% 96`, never index from 0.
- **Plates are keyed by well label** (`"A1".."H12"`), the same string as the well's
  anchor name: `anchor(plate_id, "A1")` pairs with `cal["A1"]`.
- **Calibration values are `[dx, dy]` in metres**, XY only, added to the anchor or
  tip position.

## Lifecycle

- State persists across runs; nothing resets it at run start. A protocol that uses
  tips keeps advancing until the operator resets the box in the app.
- Sim and real runs that load the same world share the file.
- Swapping the type at a seat keeps every type's calibration; a type that comes back
  finds its table unchanged (its run-time state is reset: it is a new unit).
- `despawn` drops the object's live state from memory only; the world's files on
  disk are not edited by a run.
- Calibration is taught with the platform's tools. Skills read it; write calibration
  only when the user asks, respecting the wholesale-replace rule.
