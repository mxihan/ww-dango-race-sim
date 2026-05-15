from dango_sim.sample_config import build_sample_config
from dango_sim.skills import (
    AugustaSkill,
    CalcharoSkill,
    CartethyiaSkill,
    HiyukiSkill,
    IunoSkill,
    JinhsiSkill,
)


def test_sample_config_includes_active_dango_skills():
    config = build_sample_config()

    skills_by_id = {dango.id: dango.skill for dango in config.participants}

    assert isinstance(skills_by_id["augusta"], AugustaSkill)
    assert isinstance(skills_by_id["jinhsi"], JinhsiSkill)
    assert isinstance(skills_by_id["hiyuki"], HiyukiSkill)
    assert isinstance(skills_by_id["iuno"], IunoSkill)
    assert isinstance(skills_by_id["calcharo"], CalcharoSkill)
    assert isinstance(skills_by_id["cartethyia"], CartethyiaSkill)
