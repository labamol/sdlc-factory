from datetime import date

from pydantic import BaseModel, Field

from factory.models.enums import AmbiguityClass


class Requirement(BaseModel):
    req_id: str  # BR-xx
    statement: str
    source: str  # document/section provenance
    section: str = ""
    actors: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)


class Clarification(BaseModel):
    clr_id: str  # CLR-xx
    req_id: str
    question: str
    ambiguity_class: AmbiguityClass
    trigger: str = ""  # the phrase that triggered the ambiguity
    status: str = "OPEN"  # OPEN | ANSWERED | ASSUMED | OUT_OF_SCOPE
    answer: str = ""


class Assumption(BaseModel):
    asm_id: str  # ASM-xx
    req_id: str
    statement: str
    rationale: str = ""
    risk: str = "low"
    scope: str = "feature"
    status: str = "ACTIVE"  # ACTIVE | SUPERSEDED | INVALIDATED


class Decision(BaseModel):
    """Normalized decision/clarification with provenance and supersession."""

    decision_id: str  # DEC-xx
    source: str  # e.g. teams-meeting-2026-08-24 or hitl
    feature: str | None = None
    requirement: str | None = None
    type: str = "clarification"  # clarification | decision | assumption-approval
    question: str = ""
    decision: str
    decided_by: str = ""
    confidence: str = "confirmed"  # confirmed | tentative
    status: str = "APPROVED"  # APPROVED | PROPOSED | SUPERSEDED
    effective_from: date | None = None
    supersedes: str | None = None
    source_version: str = ""


class Feature(BaseModel):
    feature_id: str  # FEAT-xx
    title: str
    description: str = ""
    requirements: list[str] = Field(default_factory=list)  # BR-xx ids
    priority: str = "medium"
