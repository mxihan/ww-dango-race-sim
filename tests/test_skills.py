from dango_sim.engine import RaceEngine, TurnContext
from dango_sim.models import BU_KING_ID, Board, Dango, RaceConfig, RaceState
from dango_sim.skills import (
    AimisSkill,
    CorletaSkill,
    LinnaeSkill,
    MorningSkill,
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


def test_corleta_doubles_roll_when_probability_triggers():
    skill = CorletaSkill()
    context = TurnContext(round_rolls={"c": 2}, base_roll=2, movement=2)

    movement = skill.modify_roll(
        Dango(id="c", name="Corleta"),
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


def test_linnae_blocked_state_wins_over_double_move():
    skill = LinnaeSkill()
    context = TurnContext(round_rolls={"l": 2}, base_roll=2, movement=2)
    rng = FixedRng(randoms=[0.10])

    skill.before_move(
        Dango(id="l", name="Linnae"),
        RaceState.initial(["l"]),
        context,
        rng,
    )

    assert context.blocked is True
    assert context.movement == 2
    assert rng.randoms == []


def test_linnae_can_double_when_not_blocked():
    skill = LinnaeSkill()
    context = TurnContext(round_rolls={"l": 2}, base_roll=2, movement=2)

    skill.before_move(
        Dango(id="l", name="Linnae"),
        RaceState.initial(["l"]),
        context,
        FixedRng(randoms=[0.50]),
    )

    assert context.blocked is False
    assert context.movement == 4


def test_linnae_moves_normally_when_neither_triggered():
    skill = LinnaeSkill()
    context = TurnContext(round_rolls={"l": 2}, base_roll=2, movement=2)

    skill.before_move(
        Dango(id="l", name="Linnae"),
        RaceState.initial(["l"]),
        context,
        FixedRng(randoms=[0.90]),
    )

    assert context.blocked is False
    assert context.movement == 2


def test_morning_cycles_rolls_three_two_one():
    skill = MorningSkill()
    dango = Dango(id="m", name="Morning")
    state = RaceState.initial(["m"])

    assert [skill.roll(dango, state, FixedRng()) for _ in range(4)] == [3, 2, 1, 3]


def test_morning_skill_state_is_local_to_each_engine():
    config = RaceConfig(
        board=Board(finish=10),
        participants=[Dango(id="m", name="Morning", skill=MorningSkill())],
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


def test_aimis_teleports_once_to_nearest_dango_ahead():
    config = RaceConfig(
        board=Board(finish=10),
        participants=[
            Dango(id="aimis", name="Aimis", skill=AimisSkill()),
            Dango(id="near", name="Near"),
            Dango(id="far", name="Far"),
        ],
        include_bu_king=False,
    )
    engine = RaceEngine(config, rng=FixedRng())
    engine.state = RaceState(positions={5: ["aimis"], 7: ["near"], 9: ["far"]})
    context = TurnContext(round_rolls={"aimis": 3}, base_roll=3, movement=3)

    config.participants[0].skill.after_move(
        config.participants[0],
        engine.state,
        context,
        FixedRng(),
        engine,
    )

    assert engine.state.stack_at(7) == ["near", "aimis"]


def test_aimis_teleports_only_itself_not_dango_above_it():
    config = RaceConfig(
        board=Board(finish=10),
        participants=[
            Dango(id="lower", name="Lower"),
            Dango(id="aimis", name="Aimis", skill=AimisSkill()),
            Dango(id="rider", name="Rider"),
            Dango(id="target", name="Target"),
        ],
        include_bu_king=False,
    )
    engine = RaceEngine(config, rng=FixedRng())
    engine.state = RaceState(positions={5: ["lower", "aimis", "rider"], 7: ["target"]})
    context = TurnContext(round_rolls={"aimis": 3}, base_roll=3, movement=3)

    engine.dangos["aimis"].skill.after_move(
        engine.dangos["aimis"],
        engine.state,
        context,
        FixedRng(),
        engine,
    )

    assert engine.state.stack_at(5) == ["lower", "rider"]
    assert engine.state.stack_at(7) == ["target", "aimis"]


def test_aimis_ignores_bu_king_only_stack_when_teleporting():
    config = RaceConfig(
        board=Board(finish=10),
        participants=[
            Dango(id="aimis", name="Aimis", skill=AimisSkill()),
            Dango(id="target", name="Target"),
        ],
        include_bu_king=False,
    )
    engine = RaceEngine(config, rng=FixedRng())
    engine.state = RaceState(
        positions={5: ["aimis"], 6: [BU_KING_ID], 8: ["target"]}
    )
    context = TurnContext(round_rolls={"aimis": 3}, base_roll=3, movement=3)

    config.participants[0].skill.after_move(
        config.participants[0],
        engine.state,
        context,
        FixedRng(),
        engine,
    )

    assert engine.state.stack_at(6) == [BU_KING_ID]
    assert engine.state.stack_at(8) == ["target", "aimis"]


def test_aimis_skill_state_is_local_to_each_engine():
    config = RaceConfig(
        board=Board(finish=10),
        participants=[
            Dango(id="aimis", name="Aimis", skill=AimisSkill()),
            Dango(id="target", name="Target"),
        ],
        include_bu_king=False,
    )

    first_engine = RaceEngine(config, rng=FixedRng())
    first_engine.state = RaceState(positions={5: ["aimis"], 7: ["target"]})
    first_context = TurnContext(round_rolls={"aimis": 3}, base_roll=3, movement=3)
    first_engine.dangos["aimis"].skill.after_move(
        first_engine.dangos["aimis"],
        first_engine.state,
        first_context,
        FixedRng(),
        first_engine,
    )

    second_engine = RaceEngine(config, rng=FixedRng())
    second_engine.state = RaceState(positions={5: ["aimis"], 7: ["target"]})
    second_context = TurnContext(round_rolls={"aimis": 3}, base_roll=3, movement=3)
    second_engine.dangos["aimis"].skill.after_move(
        second_engine.dangos["aimis"],
        second_engine.state,
        second_context,
        FixedRng(),
        second_engine,
    )

    assert first_engine.state.stack_at(7) == ["target", "aimis"]
    assert second_engine.state.stack_at(7) == ["target", "aimis"]
    assert config.participants[0].skill.used is False


def test_aimis_preserves_skill_when_no_target_ahead():
    """By default, Aimis keeps its skill if no valid target is found."""
    skill = AimisSkill()
    config = RaceConfig(
        board=Board(finish=10),
        participants=[Dango(id="aimis", name="Aimis", skill=skill)],
        include_bu_king=False,
    )
    engine = RaceEngine(config, rng=FixedRng())
    engine.state = RaceState(positions={6: ["aimis"]})
    context = TurnContext(round_rolls={"aimis": 1}, base_roll=1, movement=1)

    skill.after_move(
        engine.dangos["aimis"],
        engine.state,
        context,
        FixedRng(),
        engine,
    )

    assert skill.used is False


def test_aimis_consumes_skill_on_fail_when_configured():
    """With consume_on_fail=True, the skill is consumed even without a target."""
    skill = AimisSkill(consume_on_fail=True)
    config = RaceConfig(
        board=Board(finish=10),
        participants=[Dango(id="aimis", name="Aimis", skill=skill)],
        include_bu_king=False,
    )
    engine = RaceEngine(config, rng=FixedRng())
    engine.state = RaceState(positions={6: ["aimis"]})
    context = TurnContext(round_rolls={"aimis": 1}, base_roll=1, movement=1)

    skill.after_move(
        engine.dangos["aimis"],
        engine.state,
        context,
        FixedRng(),
        engine,
    )

    assert skill.used is True
