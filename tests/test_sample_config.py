from dango_sim.sample_config import build_sample_config
from dango_sim.skills import (
    AugustaSkill,
    CalcharoSkill,
    ChangliSkill,
    IunoSkill,
    JinhsiSkill,
    PhrolovaSkill,
)


def test_sample_config_includes_new_dango_skills():
    config = build_sample_config()

    skills_by_id = {dango.id: dango.skill for dango in config.participants}

    assert isinstance(skills_by_id["augusta"], AugustaSkill)
    assert isinstance(skills_by_id["iuno"], IunoSkill)
    assert isinstance(skills_by_id["phrolova"], PhrolovaSkill)
    assert isinstance(skills_by_id["changli"], ChangliSkill)
    assert isinstance(skills_by_id["jinhsi"], JinhsiSkill)
    assert isinstance(skills_by_id["calcharo"], CalcharoSkill)
