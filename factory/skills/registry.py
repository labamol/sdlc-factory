"""Portable skill catalogue registry.

A skill is a versioned directory containing SKILL.md plus optional
templates/, examples/, scripts/ and validation/. Deterministic work belongs
in scripts/tools; the skill supplies reusable engineering practice.
"""

from pathlib import Path

from pydantic import BaseModel, Field


class Skill(BaseModel):
    skill_id: str  # e.g. "requirements/brd-analysis"
    path: Path
    instructions: str
    templates: list[str] = Field(default_factory=list)
    scripts: list[str] = Field(default_factory=list)

    model_config = {"arbitrary_types_allowed": True}


class SkillRegistry:
    def __init__(self, skills_dir: Path) -> None:
        self.skills_dir = skills_dir

    def list_skills(self) -> list[str]:
        if not self.skills_dir.exists():
            return []
        return sorted(
            str(p.parent.relative_to(self.skills_dir))
            for p in self.skills_dir.rglob("SKILL.md")
        )

    def load(self, skill_id: str) -> Skill:
        skill_dir = self.skills_dir / skill_id
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            raise FileNotFoundError(f"Skill not found: {skill_id}")
        return Skill(
            skill_id=skill_id,
            path=skill_dir,
            instructions=skill_md.read_text(encoding="utf-8"),
            templates=sorted(
                str(p.relative_to(skill_dir)) for p in (skill_dir / "templates").glob("*")
            )
            if (skill_dir / "templates").exists()
            else [],
            scripts=sorted(
                str(p.relative_to(skill_dir)) for p in (skill_dir / "scripts").glob("*")
            )
            if (skill_dir / "scripts").exists()
            else [],
        )
