"""Deterministic ambiguity detection and classification.

Blocking -> pause scope and request human clarification.
Material but assumable -> proceed with an explicit recorded assumption.
Implementation detail -> apply engineering standards without interruption.
"""

import re

from factory.models.enums import AmbiguityClass
from factory.models.requirement import Assumption, Clarification, Requirement

BLOCKING_MARKERS = re.compile(
    r"\b(TBD|to be (?:decided|determined|confirmed)|unknown|conflict(?:s|ing)?|"
    r"pending decision|out of scope\?)\b",
    re.IGNORECASE,
)
VAGUE_MARKERS = re.compile(
    r"\b(fast|quick(?:ly)?|user-friendly|intuitive|scalable|robust|efficient(?:ly)?|"
    r"appropriate|reasonable|as needed|etc\.?|some|various|flexible|easily|"
    r"performant|seamless(?:ly)?|modern)\b",
    re.IGNORECASE,
)
DETAIL_MARKERS = re.compile(
    r"\b(logging|log format|naming|code style|folder structure|indentation|"
    r"library choice|framework version)\b",
    re.IGNORECASE,
)


def classify(statement: str) -> tuple[AmbiguityClass | None, str]:
    """Return the ambiguity class and the triggering phrase, or (None, "")."""
    blocking = BLOCKING_MARKERS.search(statement)
    if blocking:
        return AmbiguityClass.BLOCKING, blocking.group(0)
    detail = DETAIL_MARKERS.search(statement)
    if detail:
        return AmbiguityClass.IMPLEMENTATION_DETAIL, detail.group(0)
    vague = VAGUE_MARKERS.search(statement)
    if vague:
        return AmbiguityClass.MATERIAL_ASSUMABLE, vague.group(0)
    return None, ""


def analyze_requirements(
    requirements: list[Requirement],
) -> tuple[list[Clarification], list[Assumption]]:
    clarifications: list[Clarification] = []
    assumptions: list[Assumption] = []
    clr_counter = 0
    asm_counter = 0

    for req in requirements:
        ambiguity_class, trigger = classify(req.statement)
        if ambiguity_class is None:
            continue
        clr_counter += 1
        clarification = Clarification(
            clr_id=f"CLR-{clr_counter:03d}",
            req_id=req.req_id,
            question=f"'{trigger}' in {req.req_id} is ambiguous: "
            f"please define measurable criteria for \"{req.statement}\"",
            ambiguity_class=ambiguity_class,
            trigger=trigger,
        )
        if ambiguity_class == AmbiguityClass.MATERIAL_ASSUMABLE:
            asm_counter += 1
            clarification.status = "ASSUMED"
            assumptions.append(
                Assumption(
                    asm_id=f"ASM-{asm_counter:03d}",
                    req_id=req.req_id,
                    statement=f"Interpret '{trigger}' using the factory's default "
                    f"engineering standard for {req.req_id}; revisit if product disagrees.",
                    rationale="Material but assumable ambiguity; safe default applied.",
                    risk="medium",
                )
            )
        elif ambiguity_class == AmbiguityClass.IMPLEMENTATION_DETAIL:
            clarification.status = "ASSUMED"
        clarifications.append(clarification)
    return clarifications, assumptions


def has_blocking(clarifications: list[Clarification]) -> bool:
    return any(
        c.ambiguity_class == AmbiguityClass.BLOCKING and c.status == "OPEN"
        for c in clarifications
    )
