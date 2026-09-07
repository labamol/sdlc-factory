"""LLM-assisted requirements reasoning.

The deterministic keyword parsers stay the baseline and the source of stable
`BR-xx` / `CLR-xxx` / `ASM-xxx` identifiers. A configured runtime replaces the
*judgement* — which sentences are genuinely requirements, and how ambiguous
each one is — while identifier assignment, provenance and record shape remain
factory-owned. Every model response is schema-validated; anything invalid
raises `LLMError` and the caller falls back to the deterministic path.
"""

from pydantic import BaseModel, Field

from factory.models.enums import AmbiguityClass
from factory.models.requirement import Assumption, Clarification, Requirement
from factory.runtime.llm import LLMRuntime, LLMUsage

EXTRACTION_SYSTEM = (
    "You are the Requirements Analyst of a spec-driven engineering factory. "
    "Extract atomic, testable business requirements from a BRD. One requirement "
    "per obligation; preserve the author's wording and never invent scope. "
    "Ignore background, goals and non-normative narrative."
)

CLASSIFICATION_SYSTEM = (
    "You are the Requirements Analyst of a spec-driven engineering factory. "
    "Classify ambiguity in each requirement:\n"
    "BLOCKING - scope or intent is undecided; work must pause for a human.\n"
    "MATERIAL_ASSUMABLE - imprecise but a safe, explicit default can proceed.\n"
    "IMPLEMENTATION_DETAIL - engineering standards resolve it without asking.\n"
    "Return only requirements that are genuinely ambiguous."
)


class RequirementDraft(BaseModel):
    statement: str
    section: str = ""
    actors: list[str] = Field(default_factory=list)


class ExtractionResult(BaseModel):
    title: str = ""
    requirements: list[RequirementDraft] = Field(default_factory=list)


class AmbiguityJudgement(BaseModel):
    req_id: str
    ambiguity_class: AmbiguityClass
    trigger: str = ""
    question: str = ""
    suggested_assumption: str = ""
    rationale: str = ""
    risk: str = "medium"


class ClassificationResult(BaseModel):
    judgements: list[AmbiguityJudgement] = Field(default_factory=list)


async def extract_requirements(
    runtime: LLMRuntime, brd_text: str, source: str
) -> tuple[str, list[Requirement], LLMUsage]:
    """Extract requirements from a BRD, assigning stable ids in document order."""
    result, usage = await runtime.complete_structured(
        system=EXTRACTION_SYSTEM,
        user=f"BRD document:\n\n{brd_text}",
        schema=ExtractionResult,
        max_output_tokens=4096,
    )
    drafts = [draft for draft in result.requirements if draft.statement.strip()]
    requirements = [
        Requirement(
            req_id=f"BR-{index:02d}",
            statement=draft.statement.strip(),
            source=source,
            section=draft.section.strip(),
            actors=draft.actors,
        )
        for index, draft in enumerate(drafts, start=1)
    ]
    return result.title.strip(), requirements, usage


async def classify_requirements(
    runtime: LLMRuntime, requirements: list[Requirement]
) -> tuple[list[Clarification], list[Assumption], LLMUsage]:
    """Classify ambiguity per requirement into clarifications and assumptions."""
    listing = "\n".join(f"{req.req_id}: {req.statement}" for req in requirements)
    result, usage = await runtime.complete_structured(
        system=CLASSIFICATION_SYSTEM,
        user=f"Requirements:\n\n{listing}",
        schema=ClassificationResult,
        max_output_tokens=4096,
    )

    known = {req.req_id for req in requirements}
    clarifications: list[Clarification] = []
    assumptions: list[Assumption] = []
    order = {req.req_id: index for index, req in enumerate(requirements)}
    judgements = [j for j in result.judgements if j.req_id in known]
    judgements.sort(key=lambda j: order[j.req_id])

    for index, judgement in enumerate(judgements, start=1):
        clarification = Clarification(
            clr_id=f"CLR-{index:03d}",
            req_id=judgement.req_id,
            question=judgement.question
            or f"{judgement.req_id} is ambiguous: please define measurable criteria",
            ambiguity_class=judgement.ambiguity_class,
            trigger=judgement.trigger,
        )
        if judgement.ambiguity_class == AmbiguityClass.MATERIAL_ASSUMABLE:
            clarification.status = "ASSUMED"
            assumptions.append(
                Assumption(
                    asm_id=f"ASM-{len(assumptions) + 1:03d}",
                    req_id=judgement.req_id,
                    statement=judgement.suggested_assumption
                    or f"Apply the factory default engineering standard for {judgement.req_id}.",
                    rationale=judgement.rationale
                    or "Material but assumable ambiguity; safe default applied.",
                    risk=judgement.risk or "medium",
                )
            )
        elif judgement.ambiguity_class == AmbiguityClass.IMPLEMENTATION_DETAIL:
            clarification.status = "ASSUMED"
        clarifications.append(clarification)
    return clarifications, assumptions, usage
