from pydantic import BaseModel, Field


class AcceptanceCriterion(BaseModel):
    ac_id: str
    description: str
    mandatory: bool = True


class Story(BaseModel):
    story_id: str
    feature_id: str
    title: str
    description: str = ""
    acceptance_criteria: list[AcceptanceCriterion] = Field(default_factory=list)
