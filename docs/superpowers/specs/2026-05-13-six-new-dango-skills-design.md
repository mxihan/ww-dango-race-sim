# Six New Dango Skills Design

## Goal

Add six built-in dango skills to the Python race simulator while preserving the existing hook-based architecture:

- Augusta
- Iuno
- Phrolova
- Changli
- Jinhsi
- Calcharo

The implementation should keep each skill independently testable and avoid a broad rewrite of the race engine.

## Recommended Approach

Use a minimal extension of the current skill hook system.

The engine already supports dice, movement modification, pre-move behavior, post-move behavior, and reactions to any movement. These new skills only need one small addition:

- An action-order adjustment path for skills that force a dango to act last in the next round.

Movement-related skills should continue to use `before_move`, `after_move`, and `after_any_move` where possible.

## Scope

In scope:

- Add skill classes in `src/dango_sim/skills.py`.
- Add minimal engine support for round-start effects and forced-last action order.
- Add focused tests for each new skill and the engine order hooks.
- Wire the sample config in `main.py` to include the six new dangos.
- Export new skill classes if the package already exposes skill names in a public location.

Out of scope:

- Replacing the hook system with a full event bus.
- Changing existing race, tile, Bu King, or ranking rules except where needed by these skills.
- Adding scenario-file support for the new dangos.

## Rules

### Augusta

After Augusta moves, if Augusta is at the top of its current stack:

- Augusta is marked to act last in the next round.

The forced-last marker applies only to the next round after the check. If Augusta's movement ends the race, no later round occurs and the marker has no effect.

### Iuno

Once per race, when Iuno's movement path passes the midpoint of the track:

- The skill triggers whether Iuno moved as the acting dango or was carried by another dango.
- The midpoint is `board.finish // 2` unless the skill is constructed with an explicit midpoint.
- Current ranking for this skill is calculated with a special ranking method that includes Bu King in the sequence.
- The direct ranked entry immediately before Iuno and the direct ranked entry immediately after Iuno are considered.
- If either direct neighbor is Bu King, that neighbor is not selected and the search does not skip past Bu King to another dango on that side.
- Bu King can therefore block selection on one side, but Bu King itself is never selected or teleported.
- Selected dangos are removed from their current positions and placed on Iuno's current position.
- The selected dangos' order on Iuno's tile follows their pre-teleport ranking order, from better rank to worse rank.
- The selected group is placed on top of the existing stack at Iuno's position.
- The skill is consumed after this teleport, even if only one adjacent ranked dango exists.

If Iuno is not present in rankings when the midpoint condition is met, the skill does not trigger and remains available. This can only happen for unusual edge cases such as an invalid direct state mutation in a test.

### Phrolova

At the start of movement, if Phrolova is already entered and is at the bottom of its current stack:

- Add 3 to Phrolova's movement for that turn.

If Phrolova is unentered, the skill does not trigger before entering the board.

### Changli

After Changli moves, if Changli has one or more dangos below it in the same stack:

- Roll a probability check.
- With 65% chance, mark Changli to act last in the next round.

The forced-last marker applies only to the next round after the check. If Changli's movement ends the race, no later round occurs and the marker has no effect.

### Jinhsi

At the start of movement, if Jinhsi is already entered and has one or more dangos above it in the same stack:

- Roll a probability check.
- With 40% chance, move Jinhsi to the top of its current stack before movement is applied.

After moving to the top, normal stack movement rules apply. If Jinhsi then acts, it carries only itself because no dango remains above it.

### Calcharo

At the start of movement, if Calcharo is currently last among normal dangos:

- Add 3 to Calcharo's movement for that turn.

"Last" uses the engine's current `rankings()` result, which excludes Bu King. If Calcharo is unentered and the ranking model places unentered dangos after entered dangos, Calcharo can be considered last and receive the bonus.

## Engine Changes

The engine should add small, explicit state for order effects:

- `force_last_next_round`: normal dango ids that should be moved to the end of the next round's order.
- `force_last_this_round`: internal round-local copy consumed when building the round order.

At each round:

1. Move pending `force_last_next_round` ids into the current round's order adjustment state.
2. Build the order from normal dice rules.
3. Move any forced-last ids that are present in the order to the end, preserving their relative order.
4. Resolve turns normally.
5. Let post-move hooks mark ids for the next round.

No round-start hook is needed for these rules after the Augusta and Changli checks move to post-movement timing.

The engine should also provide a ranking helper for Iuno that includes Bu King while preserving the same ordering semantics as normal rankings:

- Finished normal dangos first, if any finish state exists.
- Remaining occupied positions by forward distance to start.
- Stack order from top to bottom within each position.
- Unentered normal dangos after entered dangos.
- Bu King included at its occupied position when present, but excluded from final race results.

## Testing Plan

Add tests for:

- Augusta is forced last in the following round when it ends movement on top.
- Augusta does not trigger when it does not end movement on top.
- Iuno teleports adjacent ranked normal dangos to its own tile after passing midpoint.
- Iuno preserves pre-teleport ranking order for teleported dangos.
- Iuno includes Bu King when finding adjacent ranked entries but never selects Bu King.
- Iuno triggers when carried through the midpoint.
- Phrolova gains 3 movement when at stack bottom.
- Phrolova does not gain movement when unentered or not at bottom.
- Changli can mark itself last next round when dango exist below it.
- Changli does not mark itself when no dango is below it.
- Jinhsi can move to top before movement when dango exist above it.
- Jinhsi does not move to top when the probability check fails.
- Calcharo gains 3 movement when current ranking places it last among normal dangos.
- Calcharo ignores Bu King when determining last place.

Run the complete test suite with:

```powershell
uv run pytest
```

## Spec Self-Review

- No placeholder sections remain.
- The ambiguous Iuno phrase has been resolved as "teleport selected ranked neighbors to Iuno's own tile."
- Iuno's neighbor calculation now includes Bu King in ranking context while excluding Bu King from selected teleport targets.
- Calcharo uses ranking position, not track position.
- Augusta and Changli both check after their own movement and can mark themselves last for the next round.
- The design keeps the current hook architecture and avoids a full event bus.
