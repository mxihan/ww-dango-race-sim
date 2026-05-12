from dango_sim.engine import RaceEngine, TurnContext
from dango_sim.models import BU_KING_ID, Board, Dango, RaceConfig, RaceState
from dango_sim.skills import (
    AemeathSkill,
    AugustaSkill,
    CalcharoSkill,
    CarlottaSkill,
    ChangliSkill,
    IunoSkill,
    JinhsiSkill,
    LynaeSkill,
    MornyeSkill,
    PhrolovaSkill,
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


def test_iuno_teleports_direct_ranked_normal_neighbors_in_ranking_order():
    config = RaceConfig(
        board=Board(finish=12),
        participants=[
            Dango(id="leader", name="Leader"),
            Dango(id="iuno", name="Iuno", skill=IunoSkill()),
            Dango(id="trailer", name="Trailer"),
            Dango(id="far", name="Far"),
        ],
        include_bu_king=False,
    )
    engine = RaceEngine(config, rng=FixedRng())
    engine.state = RaceState(
        positions={8: ["leader"], 5: ["iuno"], 4: ["trailer"], 1: ["far"]}
    )

    engine.take_turn(
        "iuno",
        base_roll=1,
        round_rolls={"leader": 1, "iuno": 1, "trailer": 1, "far": 1},
    )

    assert engine.dangos["iuno"].skill.used is True
    assert engine.state.stack_at(6) == ["iuno", "trailer", "leader"]
    assert engine.state.stack_at(8) == []
    assert engine.state.stack_at(4) == []


def test_iuno_direct_bu_king_neighbor_blocks_that_side_without_skipping():
    config = RaceConfig(
        board=Board(finish=12),
        participants=[
            Dango(id="leader", name="Leader"),
            Dango(id="iuno", name="Iuno", skill=IunoSkill()),
            Dango(id="after_bu", name="After Bu"),
            Dango(id="trailer", name="Trailer"),
        ],
    )
    engine = RaceEngine(config, rng=FixedRng())
    engine.state = RaceState(
        positions={
            8: ["leader"],
            6: [BU_KING_ID],
            5: ["iuno"],
            4: ["after_bu"],
            2: ["trailer"],
        }
    )

    engine.take_turn(
        "iuno",
        base_roll=1,
        round_rolls={"leader": 1, "iuno": 1, "after_bu": 1, "trailer": 1},
    )

    assert engine.dangos["iuno"].skill.used is True
    assert engine.state.stack_at(6) == [BU_KING_ID, "iuno", "leader"]
    assert engine.state.stack_at(8) == []
    assert engine.state.stack_at(4) == ["after_bu"]


def test_iuno_triggers_when_carried_through_midpoint():
    config = RaceConfig(
        board=Board(finish=12),
        participants=[
            Dango(id="leader", name="Leader"),
            Dango(id="carrier", name="Carrier"),
            Dango(id="iuno", name="Iuno", skill=IunoSkill()),
            Dango(id="trailer", name="Trailer"),
        ],
        include_bu_king=False,
    )
    engine = RaceEngine(config, rng=FixedRng())
    engine.state = RaceState(
        positions={8: ["leader"], 5: ["carrier", "iuno"], 4: ["trailer"]}
    )

    engine.take_turn(
        "carrier",
        base_roll=1,
        round_rolls={"leader": 1, "carrier": 1, "iuno": 1, "trailer": 1},
    )

    assert engine.dangos["iuno"].skill.used is True
    assert engine.state.stack_at(6) == ["iuno", "carrier", "leader"]
    assert engine.state.stack_at(4) == ["trailer"]


def test_iuno_triggers_only_once_per_race():
    config = RaceConfig(
        board=Board(finish=12),
        participants=[
            Dango(id="leader", name="Leader"),
            Dango(id="iuno", name="Iuno", skill=IunoSkill()),
            Dango(id="trailer", name="Trailer"),
            Dango(id="second_trailer", name="Second Trailer"),
        ],
        include_bu_king=False,
    )
    engine = RaceEngine(config, rng=FixedRng())
    engine.state = RaceState(
        positions={
            8: ["leader"],
            5: ["iuno"],
            4: ["trailer"],
            2: ["second_trailer"],
        }
    )

    engine.take_turn(
        "iuno",
        base_roll=1,
        round_rolls={
            "leader": 1,
            "iuno": 1,
            "trailer": 1,
            "second_trailer": 1,
        },
    )
    engine.state.remove_ids(["leader", "trailer"])
    engine.state.place_group(["leader"], 8)
    engine.state.place_group(["trailer"], 4)

    engine.take_turn(
        "iuno",
        base_roll=12,
        round_rolls={
            "leader": 1,
            "iuno": 12,
            "trailer": 1,
            "second_trailer": 1,
        },
    )

    assert engine.dangos["iuno"].skill.used is True
    assert engine.state.stack_at(6) == []
    assert engine.state.stack_at(8) == ["leader"]
    assert engine.state.stack_at(4) == ["trailer"]
    assert engine.state.stack_at(0) == ["iuno"]


def test_iuno_consumes_when_only_direct_neighbors_are_bu_king():
    config = RaceConfig(
        board=Board(finish=12),
        participants=[Dango(id="iuno", name="Iuno", skill=IunoSkill())],
    )
    engine = RaceEngine(config, rng=FixedRng())
    engine.state = RaceState(positions={5: ["iuno"], 7: [BU_KING_ID]})

    engine.take_turn("iuno", base_roll=1, round_rolls={"iuno": 1})

    assert engine.dangos["iuno"].skill.used is True
    assert engine.state.stack_at(6) == ["iuno"]
    assert engine.state.stack_at(7) == [BU_KING_ID]


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


def test_phrolova_gains_three_when_bottom_with_rider_above():
    skill = PhrolovaSkill()
    context = TurnContext(round_rolls={"phrolova": 2}, base_roll=2, movement=2)
    state = RaceState(positions={4: ["phrolova", "rider"]})

    skill.before_move(
        Dango(id="phrolova", name="Phrolova"),
        state,
        context,
        FixedRng(),
    )

    assert context.movement == 5


def test_phrolova_does_not_gain_bonus_when_alone_in_stack():
    skill = PhrolovaSkill()
    context = TurnContext(round_rolls={"phrolova": 2}, base_roll=2, movement=2)
    state = RaceState(positions={4: ["phrolova"]})

    skill.before_move(
        Dango(id="phrolova", name="Phrolova"),
        state,
        context,
        FixedRng(),
    )

    assert context.movement == 2


def test_phrolova_does_not_gain_bonus_when_not_bottom():
    skill = PhrolovaSkill()
    context = TurnContext(round_rolls={"phrolova": 2}, base_roll=2, movement=2)
    state = RaceState(positions={4: ["base", "phrolova"]})

    skill.before_move(
        Dango(id="phrolova", name="Phrolova"),
        state,
        context,
        FixedRng(),
    )

    assert context.movement == 2


def test_phrolova_does_not_gain_bonus_when_unentered():
    skill = PhrolovaSkill()
    context = TurnContext(round_rolls={"phrolova": 2}, base_roll=2, movement=2)
    state = RaceState.empty(["phrolova"])

    skill.before_move(
        Dango(id="phrolova", name="Phrolova"),
        state,
        context,
        FixedRng(),
    )

    assert context.movement == 2


def test_jinhsi_moves_to_top_before_movement_and_moves_alone_when_probability_triggers():
    config = RaceConfig(
        board=Board(finish=20),
        participants=[
            Dango(id="base", name="Base"),
            Dango(id="jinhsi", name="Jinhsi", skill=JinhsiSkill()),
            Dango(id="rider", name="Rider"),
        ],
        include_bu_king=False,
    )
    engine = RaceEngine(config, rng=FixedRng(randoms=[0.39]))
    engine.state = RaceState(positions={2: ["base", "jinhsi", "rider"]})

    engine.take_turn(
        "jinhsi",
        base_roll=1,
        round_rolls={"base": 1, "jinhsi": 1, "rider": 1},
    )

    assert engine.state.stack_at(2) == ["base", "rider"]
    assert engine.state.stack_at(3) == ["jinhsi"]


def test_jinhsi_keeps_stack_position_and_carries_rider_when_probability_misses():
    config = RaceConfig(
        board=Board(finish=20),
        participants=[
            Dango(id="base", name="Base"),
            Dango(id="jinhsi", name="Jinhsi", skill=JinhsiSkill()),
            Dango(id="rider", name="Rider"),
        ],
        include_bu_king=False,
    )
    engine = RaceEngine(config, rng=FixedRng(randoms=[0.40]))
    engine.state = RaceState(positions={2: ["base", "jinhsi", "rider"]})

    engine.take_turn(
        "jinhsi",
        base_roll=1,
        round_rolls={"base": 1, "jinhsi": 1, "rider": 1},
    )

    assert engine.state.stack_at(2) == ["base"]
    assert engine.state.stack_at(3) == ["jinhsi", "rider"]


def test_jinhsi_without_dango_above_does_not_consume_rng_or_reorder_before_normal_move():
    config = RaceConfig(
        board=Board(finish=20),
        participants=[
            Dango(id="base", name="Base"),
            Dango(id="jinhsi", name="Jinhsi", skill=JinhsiSkill()),
        ],
        include_bu_king=False,
    )
    engine = RaceEngine(config, rng=FixedRng(randoms=[]))
    engine.state = RaceState(positions={2: ["base", "jinhsi"]})

    engine.take_turn(
        "jinhsi",
        base_roll=1,
        round_rolls={"base": 1, "jinhsi": 1},
    )

    assert engine.state.stack_at(2) == ["base"]
    assert engine.state.stack_at(3) == ["jinhsi"]


def test_changli_marks_next_round_last_after_ending_with_dango_below():
    config = RaceConfig(
        board=Board(finish=20),
        participants=[
            Dango(id="changli", name="Changli", skill=ChangliSkill()),
            Dango(id="destination_base", name="Destination Base"),
        ],
        include_bu_king=False,
    )
    engine = RaceEngine(config, rng=FixedRng(randoms=[0.0]))
    engine.state = RaceState(positions={2: ["changli"], 3: ["destination_base"]})

    engine.take_turn(
        "changli",
        base_roll=1,
        round_rolls={"changli": 1, "destination_base": 1},
    )

    assert engine.state.stack_at(3) == ["destination_base", "changli"]
    assert engine.force_last_next_round_ids == {"changli"}


def test_changli_marks_next_round_last_at_sixty_four_percent_boundary():
    config = RaceConfig(
        board=Board(finish=20),
        participants=[
            Dango(id="changli", name="Changli", skill=ChangliSkill()),
            Dango(id="destination_base", name="Destination Base"),
        ],
        include_bu_king=False,
    )
    engine = RaceEngine(config, rng=FixedRng(randoms=[0.64]))
    engine.state = RaceState(positions={2: ["changli"], 3: ["destination_base"]})

    engine.take_turn(
        "changli",
        base_roll=1,
        round_rolls={"changli": 1, "destination_base": 1},
    )

    assert engine.force_last_next_round_ids == {"changli"}


def test_changli_does_not_mark_next_round_last_at_sixty_five_percent_boundary():
    config = RaceConfig(
        board=Board(finish=20),
        participants=[
            Dango(id="changli", name="Changli", skill=ChangliSkill()),
            Dango(id="destination_base", name="Destination Base"),
        ],
        include_bu_king=False,
    )
    engine = RaceEngine(config, rng=FixedRng(randoms=[0.65]))
    engine.state = RaceState(positions={2: ["changli"], 3: ["destination_base"]})

    engine.take_turn(
        "changli",
        base_roll=1,
        round_rolls={"changli": 1, "destination_base": 1},
    )

    assert engine.force_last_next_round_ids == set()


def test_changli_does_not_mark_next_round_last_without_dango_below_after_move():
    config = RaceConfig(
        board=Board(finish=20),
        participants=[
            Dango(id="changli", name="Changli", skill=ChangliSkill()),
            Dango(id="other", name="Other"),
        ],
        include_bu_king=False,
    )
    engine = RaceEngine(config, rng=FixedRng())
    engine.state = RaceState(positions={2: ["changli"], 10: ["other"]})

    engine.take_turn(
        "changli",
        base_roll=1,
        round_rolls={"changli": 1, "other": 1},
    )

    assert engine.state.stack_at(3) == ["changli"]
    assert engine.force_last_next_round_ids == set()


def test_calcharo_gains_three_when_ranked_last_among_normal_dangos():
    config = RaceConfig(
        board=Board(finish=20),
        participants=[
            Dango(id="leader", name="Leader"),
            Dango(id="calcharo", name="Calcharo", skill=CalcharoSkill()),
        ],
    )
    engine = RaceEngine(config)
    engine.state = RaceState(positions={0: [BU_KING_ID], 8: ["leader"], 2: ["calcharo"]})
    context = TurnContext(round_rolls={"calcharo": 2}, base_roll=2, movement=2)
    context.engine = engine

    engine.dangos["calcharo"].skill.before_move(
        engine.dangos["calcharo"],
        engine.state,
        context,
        engine.rng,
    )

    assert engine.rankings() == ["leader", "calcharo"]
    assert context.movement == 5


def test_calcharo_uses_engine_context_during_turn_movement():
    config = RaceConfig(
        board=Board(finish=20),
        participants=[
            Dango(id="leader", name="Leader"),
            Dango(id="calcharo", name="Calcharo", skill=CalcharoSkill()),
        ],
    )
    engine = RaceEngine(config)
    engine.state = RaceState(positions={0: [BU_KING_ID], 8: ["leader"], 2: ["calcharo"]})

    engine.take_turn(
        "calcharo",
        base_roll=2,
        round_rolls={"leader": 1, "calcharo": 2},
    )

    assert engine.state.stack_at(7) == ["calcharo"]
