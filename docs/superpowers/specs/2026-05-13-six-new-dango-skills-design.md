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

The engine already supports dice, movement modification, pre-move behavior, post-move behavior, and reactions to any movement. These new skills only need two small additions:

- A round-start hook for skills that inspect current stack position before the round's action order is resolved.
- An action-order adjustment path for skills that force a dango to act last in the next round or skip its current action.

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

At the start of each round, if Augusta is already entered and is at the top of its current stack:

- Augusta does not act during that round.
- Augusta is marked to act last in the next round.

The skip applies only to the current round. The forced-last marker applies only to the next round after the skipped round. If Augusta is unentered at round start, the skill does not trigger.

### Iuno

Once per race, when Iuno's movement path passes the midpoint of the track:

- The skill triggers whether Iuno moved as the acting dango or was carried by another dango.
- The midpoint is `board.finish // 2` unless the skill is constructed with an explicit midpoint.
- Current ranking is calculated with the engine's existing `rankings()` method.
- The normal dango immediately before Iuno in ranking and the normal dango immediately after Iuno in ranking are selected.
- Bu King is ignored because `rankings()` excludes special actors.
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

At the start of each round, if Changli is already entered and has one or more dangos below it in the same stack:

- Roll a probability check.
- With 65% chance, mark Changli to act last in the next round.

Changli still acts normally in the current round. The forced-last marker applies only to the next round.

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

- `skip_turns_this_round`: normal dango ids that should not act in the current round.
- `force_last_next_round`: normal dango ids that should be moved to the end of the next round's order.
- `force_last_this_round`: internal round-local copy consumed when building the round order.

At each round:

1. Move pending `force_last_next_round` ids into the current round's order adjustment state.
2. Clear current skip state.
3. Call round-start hooks on entered and unentered participants. Each skill decides whether the dango's state qualifies.
4. Build the order from normal dice rules.
5. Move any forced-last ids that are present in the order to the end, preserving their relative order.
6. Skip any actor in `skip_turns_this_round` when its turn is reached.

The hook can be named `on_round_start(dango, state, engine, rng)` so skills can use existing state helpers and engine ranking logic.

## Testing Plan

Add tests for:

- Augusta skips this round when on top.
- Augusta is forced last in the following round after skipping.
- Augusta does not trigger when unentered or not on top.
- Iuno teleports adjacent ranked normal dangos to its own tile after passing midpoint.
- Iuno preserves pre-teleport ranking order for teleported dangos.
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
- Calcharo uses ranking position, not track position.
- Augusta and Changli both use next-round forced-last behavior, but only Augusta skips the current round.
- The design keeps the current hook architecture and avoids a full event bus.
