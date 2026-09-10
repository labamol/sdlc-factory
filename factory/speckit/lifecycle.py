"""Spec Kit lifecycle phases, executed in order for each feature.

Spec Kit is a specification service inside the factory, not the entire
factory: the factory owns everything before (requirements, decisions) and
after (implementation orchestration, evidence, governance) the spec.
"""

SPEC_LIFECYCLE: list[str] = ["specify", "clarify", "plan", "tasks", "analyze"]
