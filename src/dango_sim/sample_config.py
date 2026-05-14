from __future__ import annotations

from dango_sim.models import Board, Dango, RaceConfig
from dango_sim.skills import (
    AemeathSkill,
    AugustaSkill,
    CalcharoSkill,
    CarlottaSkill,
    ChangliSkill,
    ChisaSkill,
    IunoSkill,
    JinhsiSkill,
    LuukHerssenSkill,
    LynaeSkill,
    MornyeSkill,
    PhoebeSkill,
    PhrolovaSkill,
    ShorekeeperSkill,
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
            # Dango(id="carlotta", name="珂莱塔团子", skill=CarlottaSkill()),
            # Dango(id="chisa", name="千咲团子", skill=ChisaSkill()),
            Dango(id="lynae", name="琳奈团子", skill=LynaeSkill()),
            Dango(id="mornye", name="莫宁团子", skill=MornyeSkill()),
            # Dango(id="aemeath", name="爱弥斯团子", skill=AemeathSkill()),
            # Dango(id="shorekeeper", name="守岸人团子", skill=ShorekeeperSkill()),
            # Dango(id="augusta", name="奥古斯塔团子", skill=AugustaSkill()),
            # Dango(id="iuno", name="尤诺团子", skill=IunoSkill()),
            Dango(id="phrolova", name="弗洛洛团子", skill=PhrolovaSkill()),
            Dango(id="changli", name="长离团子", skill=ChangliSkill()),
            # Dango(id="jinhsi", name="今汐团子", skill=JinhsiSkill()),
            # Dango(id="calcharo", name="卡卡罗团子", skill=CalcharoSkill()),
            Dango(id="phoebe", name="菲比团子", skill=PhoebeSkill()),
            Dango(id="luuk_herssen", name="陆·赫斯团子", skill=LuukHerssenSkill()),
        ],
        starting_state=starting_state,
    )
