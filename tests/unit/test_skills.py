from pathlib import Path

from factory.skills.registry import SkillRegistry

SKILLS_DIR = Path(__file__).resolve().parents[2] / "skills"


def test_registry_lists_and_loads_skills():
    registry = SkillRegistry(SKILLS_DIR)
    skills = registry.list_skills()
    assert "requirements/brd-analysis" in skills

    skill = registry.load("requirements/brd-analysis")
    assert "## Purpose" in skill.instructions
    assert "## Steps" in skill.instructions
