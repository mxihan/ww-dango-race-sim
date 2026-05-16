from __future__ import annotations

from dango_sim.models import Board, Dango, RaceConfig
from dango_sim.skills import (
    AugustaSkill,
    CalcharoSkill,
    CartethyiaSkill,
    DeniaSkill,
    HiyukiSkill,
    IunoSkill,
    JinhsiSkill,
    SigrikaSkill,
)
from dango_sim.tiles import Booster, Inhibitor, SpaceTimeRift


def build_sample_config(starting_state=None) -> RaceConfig:
    # Board layout (32 tiles, start/finish share position 0):
    #   0 = start = finish
    #   1..31 = track tiles (1 = first tile ahead of start)
    #   finish = 32 means dangos travel 32 tiles to complete a lap
    return RaceConfig(
        board=Board(
            finish=32,
            tiles={
                3: Booster(),
                6: SpaceTimeRift(),
                10: Inhibitor(),
                11: Booster(),
                16: Booster(),
                20: SpaceTimeRift(),
                23: Booster(),
                28: Inhibitor(),
            },
        ),
        participants=[
            Dango(id="augusta", name="奥古斯塔团子", skill=AugustaSkill()),
            Dango(id="jinhsi", name="今汐团子", skill=JinhsiSkill()),
            Dango(id="hiyuki", name="绯雪团子", skill=HiyukiSkill()),
            Dango(id="iuno", name="尤诺团子", skill=IunoSkill()),
            Dango(id="calcharo", name="卡卡罗团子", skill=CalcharoSkill()),
            Dango(id="cartethyia", name="卡提希娅团子", skill=CartethyiaSkill()),
            Dango(id="denia", name="达妮娅团子", skill=DeniaSkill()),
            Dango(id="sigrika", name="西格莉卡团子", skill=SigrikaSkill()),
        ],
        starting_state=starting_state,
    )
