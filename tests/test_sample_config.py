from dango_sim.sample_config import build_sample_config
from dango_sim.skills import (
    ChangliSkill,
    LuukHerssenSkill,
    LynaeSkill,
    MornyeSkill,
    PhoebeSkill,
    PhrolovaSkill,
)


def test_sample_config_includes_active_dango_skills():
    config = build_sample_config()

    skills_by_id = {dango.id: dango.skill for dango in config.participants}

    assert isinstance(skills_by_id["lynae"], LynaeSkill)
    assert isinstance(skills_by_id["mornye"], MornyeSkill)
    assert isinstance(skills_by_id["phrolova"], PhrolovaSkill)
    assert isinstance(skills_by_id["changli"], ChangliSkill)
    assert isinstance(skills_by_id["phoebe"], PhoebeSkill)
    assert isinstance(skills_by_id["luuk_herssen"], LuukHerssenSkill)
