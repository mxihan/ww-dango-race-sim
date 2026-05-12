from dango_sim.engine import RaceEngine, TurnContext
from dango_sim.models import BU_KING_ID, Board, Dango, RaceConfig, RaceState
from dango_sim.skills import (
    AemeathSkill,
    AugustaSkill,
    CarlottaSkill,
    LynaeSkill,
    MornyeSkill,
    ChisaSkill,
    ShorekeeperSkill,
)


class FixedRng:
    def __init__(self, choices=None, randoms=None):
        self.choices = list(choices or [])
        self.randoms = list(randoms or [])

    def shuffle(self, values):
        return None

    def choice(self, values):
        return self.choices.pop(0)

    def random(self):
        return self.randoms.pop(0)


class AlwaysSkipRoundStartSkill:
    def on_round_start(self, dango, state, engine, rng) -> None:
        engine.skip_turn_this_round(dango.id)


class StatefulSkipRoundStartSkill:
    def __init__(self):
        self.index = 0

    def on_round_start(self, dango, state, engine, rng) -> None:
        engine.skip_turn_this_round(dango.id)

    def roll(self, dango, state, rng) -> int:
        self.index += 1
        return 1


class SkipOnTurnStartSkill:
    def on_turn_start(self, dango, state, context, rng, engine) -> None:
        engine.skip_turn_this_round(dango.id)


def test_carlotta_doubles_roll_when_probability_triggers():
    skill = CarlottaSkill()
    context = TurnContext(round_rolls={"c": 2}, base_roll=2, movement=2)

    movement = skill.modify_roll(
        Dango(id="c", name="Carlotta"),
        2,
        RaceState.initial(["c"]),
        context,
        FixedRng(randoms=[0.27]),
    )

    assert movement == 4


def test_chisa_adds_two_when_roll_is_round_minimum():
    skill = ChisaSkill()
    context = TurnContext(round_rolls={"q": 1, "a": 1, "b": 3}, base_roll=1, movement=1)

    movement = skill.modify_roll(
        Dango(id="q", name="Chisa"),
        1,
        RaceState.initial(["q"]),
        context,
        FixedRng(),
    )

    assert movement == 3


def test_lynae_blocked_state_wins_over_double_move():
    skill = LynaeSkill()
    context = TurnContext(round_rolls={"l": 2}, base_roll=2, movement=2)
    rng = FixedRng(randoms=[0.10])

    skill.before_move(
        Dango(id="l", name="Lynae"),
        RaceState.initial(["l"]),
        context,
        rng,
    )

    assert context.blocked is True
    assert context.movement == 2
    assert rng.randoms == []


def test_lynae_can_double_when_not_blocked():
    skill = LynaeSkill()
    context = TurnContext(round_rolls={"l": 2}, base_roll=2, movement=2)

    skill.before_move(
        Dango(id="l", name="Lynae"),
        RaceState.initial(["l"]),
        context,
        FixedRng(randoms=[0.50]),
    )

    assert context.blocked is False
    assert context.movement == 4


def test_lynae_moves_normally_when_neither_triggered():
    skill = LynaeSkill()
    context = TurnContext(round_rolls={"l": 2}, base_roll=2, movement=2)

    skill.before_move(
        Dango(id="l", name="Lynae"),
        RaceState.initial(["l"]),
        context,
        FixedRng(randoms=[0.90]),
    )

    assert context.blocked is False
    assert context.movement == 2


def test_mornye_cycles_rolls_three_two_one():
    skill = MornyeSkill()
    dango = Dango(id="m", name="Mornye")
    state = RaceState.initial(["m"])

    assert [skill.roll(dango, state, FixedRng()) for _ in range(4)] == [3, 2, 1, 3]


def test_mornye_skill_state_is_local_to_each_engine():
    config = RaceConfig(
        board=Board(finish=10),
        participants=[Dango(id="m", name="Mornye", skill=MornyeSkill())],
        include_bu_king=False,
    )

    first_engine = RaceEngine(config, rng=FixedRng())
    second_engine = RaceEngine(config, rng=FixedRng())

    assert first_engine.roll_for("m") == 3
    assert second_engine.roll_for("m") == 3
    assert config.participants[0].skill.index == 0


def test_shorekeeper_faces_are_two_and_three():
    assert ShorekeeperSkill().roll_faces(
        Dango(id="s", name="Shorekeeper"),
        RaceState.initial(["s"]),
    ) == [2, 3]


def test_aemeath_triggers_when_movement_path_passes_midpoint():
    config = RaceConfig(
        board=Board(finish=10),
        participants=[
            Dango(id="aemeath", name="Aemeath", skill=AemeathSkill()),
            Dango(id="target", name="Target"),
        ],
        include_bu_king=False,
    )
    engine = RaceEngine(config, rng=FixedRng())
    engine.state = RaceState(positions={4: ["aemeath"], 8: ["target"]})

    engine.take_turn("aemeath", base_roll=2, round_rolls={"aemeath": 2, "target": 1})

    assert engine.dangos["aemeath"].skill.used is True
    assert engine.state.stack_at(8) == ["target", "aemeath"]


def test_aemeath_teleports_only_itself_not_dango_above_it():
    config = RaceConfig(
        board=Board(finish=10),
        participants=[
            Dango(id="lower", name="Lower"),
            Dango(id="aemeath", name="Aemeath", skill=AemeathSkill()),
            Dango(id="rider", name="Rider"),
            Dango(id="target", name="Target"),
        ],
        include_bu_king=False,
    )
    engine = RaceEngine(config, rng=FixedRng())
    engine.state = RaceState(positions={4: ["lower", "aemeath", "rider"], 8: ["target"]})

    engine.take_turn("aemeath", base_roll=1, round_rolls={"aemeath": 1, "target": 1})

    assert engine.state.stack_at(4) == ["lower"]
    assert engine.state.stack_at(5) == ["rider"]
    assert engine.state.stack_at(8) == ["target", "aemeath"]


def test_aemeath_ignores_bu_king_only_stack_when_teleporting():
    config = RaceConfig(
        board=Board(finish=10),
        participants=[
            Dango(id="aemeath", name="Aemeath", skill=AemeathSkill()),
            Dango(id="target", name="Target"),
        ],
    )
    engine = RaceEngine(config, rng=FixedRng())
    engine.state = RaceState(
        positions={4: ["aemeath"], 6: [BU_KING_ID], 8: ["target"]}
    )

    engine.take_turn("aemeath", base_roll=2, round_rolls={"aemeath": 2, "target": 1})

    assert engine.state.stack_at(6) == [BU_KING_ID]
    assert engine.state.stack_at(8) == ["target", "aemeath"]


def test_aemeath_skill_state_is_local_to_each_engine():
    config = RaceConfig(
        board=Board(finish=10),
        participants=[
            Dango(id="aemeath", name="Aemeath", skill=AemeathSkill()),
            Dango(id="target", name="Target"),
        ],
        include_bu_king=False,
    )

    first_engine = RaceEngine(config, rng=FixedRng())
    first_engine.state = RaceState(positions={4: ["aemeath"], 7: ["target"]})
    first_engine.take_turn(
        "aemeath",
        base_roll=1,
        round_rolls={"aemeath": 1, "target": 1},
    )

    second_engine = RaceEngine(config, rng=FixedRng())
    second_engine.state = RaceState(positions={4: ["aemeath"], 7: ["target"]})
    second_engine.take_turn(
        "aemeath",
        base_roll=1,
        round_rolls={"aemeath": 1, "target": 1},
    )

    assert first_engine.state.stack_at(7) == ["target", "aemeath"]
    assert second_engine.state.stack_at(7) == ["target", "aemeath"]
    assert config.participants[0].skill.used is False


def test_aemeath_waits_when_no_target_after_midpoint():
    skill = AemeathSkill()
    config = RaceConfig(
        board=Board(finish=10),
        participants=[Dango(id="aemeath", name="Aemeath", skill=skill)],
        include_bu_king=False,
    )
    engine = RaceEngine(config, rng=FixedRng())
    engine.state = RaceState(positions={4: ["aemeath"]})

    engine.take_turn(
        "aemeath",
        base_roll=2,
        round_rolls={"aemeath": 2},
    )

    engine_skill = engine.dangos["aemeath"].skill
    assert engine_skill.used is False
    assert engine_skill.waiting is True


def test_aemeath_waiting_rechecks_after_any_move():
    skill = AemeathSkill()
    config = RaceConfig(
        board=Board(finish=12),
        participants=[
            Dango(id="aemeath", name="Aemeath", skill=skill),
            Dango(id="target", name="Target"),
            Dango(id="other", name="Other"),
        ],
        include_bu_king=False,
    )
    engine = RaceEngine(config, rng=FixedRng())
    engine.state = RaceState(positions={5: ["aemeath"], 2: ["target"], 1: ["other"]})

    engine.take_turn(
        "aemeath",
        base_roll=1,
        round_rolls={"aemeath": 1, "target": 1, "other": 1},
    )
    engine_skill = engine.dangos["aemeath"].skill
    assert engine_skill.waiting is True

    engine.take_turn(
        "target",
        base_roll=5,
        round_rolls={"aemeath": 1, "target": 5, "other": 1},
    )

    assert engine_skill.used is True
    assert engine_skill.waiting is False
    assert engine.state.stack_at(7) == ["target", "aemeath"]


def test_aemeath_triggers_when_carried_through_midpoint():
    skill = AemeathSkill()
    config = RaceConfig(
        board=Board(finish=12),
        participants=[
            Dango(id="carrier", name="Carrier"),
            Dango(id="aemeath", name="Aemeath", skill=skill),
            Dango(id="target", name="Target"),
        ],
        include_bu_king=False,
    )
    engine = RaceEngine(config, rng=FixedRng())
    engine.state = RaceState(positions={5: ["carrier", "aemeath"], 8: ["target"]})

    engine.take_turn(
        "carrier",
        base_roll=1,
        round_rolls={"carrier": 1, "aemeath": 1, "target": 1},
    )

    assert engine.dangos["aemeath"].skill.used is True
    assert engine.state.stack_at(6) == ["carrier"]
    assert engine.state.stack_at(8) == ["target", "aemeath"]


def test_aemeath_consumes_skill_on_fail_when_configured():
    """With consume_on_fail=True, the skill is consumed even without a target."""
    skill = AemeathSkill(consume_on_fail=True)
    config = RaceConfig(
        board=Board(finish=10),
        participants=[Dango(id="aemeath", name="Aemeath", skill=skill)],
        include_bu_king=False,
    )
    engine = RaceEngine(config, rng=FixedRng())
    engine.state = RaceState(positions={4: ["aemeath"]})

    engine.take_turn(
        "aemeath",
        base_roll=2,
        round_rolls={"aemeath": 2},
    )

    engine_skill = engine.dangos["aemeath"].skill
    assert engine_skill.used is True
    assert engine_skill.waiting is False


def test_mornye_rolls_once_for_order_and_once_for_movement():
    skill = MornyeSkill()
    config = RaceConfig(
        board=Board(finish=20),
        participants=[Dango(id="m", name="Mornye", skill=skill)],
        include_bu_king=False,
    )
    engine = RaceEngine(config)

    assert engine.roll_for_order("m") == 3
    assert engine.roll_for_movement("m") == 2


def test_chisa_uses_base_movement_roll_pool_before_modifiers():
    skill = ChisaSkill()
    config = RaceConfig(
        board=Board(finish=20),
        participants=[
            Dango(id="chisa", name="Chisa", skill=skill),
            Dango(id="other", name="Other"),
        ],
        include_bu_king=False,
    )
    engine = RaceEngine(config)
    context = TurnContext(
        round_rolls={"chisa": 1, "other": 1},
        base_roll=1,
        movement=1,
    )

    assert skill.modify_roll(
        engine.dangos["chisa"],
        1,
        engine.state,
        context,
        engine.rng,
    ) == 3
    assert context.round_rolls == {"chisa": 1, "other": 1}


def test_aemeath_ignores_unentered_dango_targets():
    skill = AemeathSkill()
    config = RaceConfig(
        board=Board(finish=10),
        participants=[
            Dango(id="aemeath", name="Aemeath", skill=skill),
            Dango(id="target", name="Target"),
        ],
        include_bu_king=False,
    )
    engine = RaceEngine(config)

    engine.take_turn("aemeath", base_roll=6, round_rolls={"aemeath": 6, "target": 1})

    engine_skill = engine.dangos["aemeath"].skill
    assert engine_skill.waiting
    assert engine.state.positions == {6: ["aemeath"]}


def test_chisa_minimum_check_includes_bu_king_once_bu_king_can_act():
    skill = ChisaSkill()
    config = RaceConfig(
        board=Board(finish=20),
        participants=[Dango(id="chisa", name="Chisa", skill=skill)],
    )
    engine = RaceEngine(config)
    context = TurnContext(
        round_rolls={"chisa": 2, BU_KING_ID: 1},
        base_roll=2,
        movement=2,
    )

    assert skill.modify_roll(
        engine.dangos["chisa"],
        2,
        engine.state,
        context,
        engine.rng,
    ) == 2


def test_augusta_skips_current_round_when_round_starts_on_top():
    config = RaceConfig(
        board=Board(finish=20),
        participants=[
            Dango(id="base", name="Base"),
            Dango(id="augusta", name="Augusta", skill=AugustaSkill()),
        ],
        include_bu_king=False,
    )
    engine = RaceEngine(config, rng=FixedRng(choices=[3, 1, 1, 1]))
    engine.state = RaceState(positions={2: ["base", "augusta"]})
    engine.state.round_number = 1
    engine.start_round(1)

    order = engine.build_round_order(1)
    round_rolls = {"base": 1, "augusta": 3}
    for dango_id in order:
        engine.take_turn(dango_id, base_roll=round_rolls[dango_id], round_rolls=round_rolls)

    assert engine.state.stack_at(2) == []
    assert engine.state.stack_at(3) == ["base", "augusta"]
    assert engine.force_last_next_round_ids == {"augusta"}


def test_augusta_forced_last_marker_moves_it_to_next_round_end():
    config = RaceConfig(
        board=Board(finish=20),
        participants=[
            Dango(id="base", name="Base"),
            Dango(id="augusta", name="Augusta", skill=AugustaSkill()),
            Dango(id="other", name="Other"),
        ],
        include_bu_king=False,
    )
    engine = RaceEngine(config, rng=FixedRng(choices=[3, 1, 2, 1, 3, 2]))
    engine.force_last_next_round_ids.add("augusta")
    engine.start_round(2)

    assert engine.build_round_order(2)[-1] == "augusta"
    assert engine.force_last_next_round_ids == set()


def test_run_loop_skips_dango_marked_to_skip_this_round():
    class RunLoopSkipProbeEngine(RaceEngine):
        def take_turn(self, dango_id, *, base_roll=None, round_rolls=None):
            if dango_id == "skipped":
                raise AssertionError("run loop should skip this dango before take_turn")
            return super().take_turn(
                dango_id,
                base_roll=base_roll,
                round_rolls=round_rolls,
            )

    config = RaceConfig(
        board=Board(finish=1),
        participants=[
            Dango(id="skipped", name="Skipped", skill=AlwaysSkipRoundStartSkill()),
            Dango(id="winner", name="Winner"),
        ],
        include_bu_king=False,
    )
    engine = RunLoopSkipProbeEngine(config, rng=FixedRng(choices=[3, 1, 1, 1]))

    result = engine.run()

    assert result.winner_id == "winner"
    assert "skipped" not in engine.state.finished_group


def test_run_loop_does_not_roll_skipped_stateful_skill():
    skill = StatefulSkipRoundStartSkill()
    config = RaceConfig(
        board=Board(finish=1),
        participants=[
            Dango(id="skipped", name="Skipped", skill=skill),
            Dango(id="winner", name="Winner"),
        ],
        include_bu_king=False,
    )
    engine = RaceEngine(config, rng=FixedRng(choices=[1, 1]))

    result = engine.run()

    assert result.winner_id == "winner"
    assert engine.dangos["skipped"].skill.index == 0


def test_on_turn_start_can_skip_before_movement():
    config = RaceConfig(
        board=Board(finish=20),
        participants=[
            Dango(id="skipped", name="Skipped", skill=SkipOnTurnStartSkill()),
        ],
        include_bu_king=False,
    )
    engine = RaceEngine(config)

    engine.take_turn("skipped", base_roll=3, round_rolls={"skipped": 3})

    assert engine.state.positions == {}
