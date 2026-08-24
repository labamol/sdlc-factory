"""Product Decomposition agent.

Converts baselined requirements into features, stories and acceptance
criteria with stable traceability IDs (BR -> FEAT -> STORY -> AC) and writes
the machine-readable traceability map. Jira (or another tracker) mutation is
performed by a tool; this agent determines the backlog structure.
"""

from collections import defaultdict
from pathlib import Path

import yaml

from factory.agents.base import AgentResult
from factory.models.enums import FactoryState
from factory.models.evidence import Evidence
from factory.models.feature import FeatureState
from factory.models.requirement import Feature, Requirement
from factory.models.story import AcceptanceCriterion, Story
from factory.orchestrator.events import new_id
from factory.tools.filesystem import FilesystemTool


def decompose(requirements: list[Requirement]) -> tuple[list[Feature], list[Story]]:
    """Group requirements by BRD section into features; one story per requirement."""
    by_section: dict[str, list[Requirement]] = defaultdict(list)
    for req in requirements:
        by_section[req.section or "General"].append(req)

    features: list[Feature] = []
    stories: list[Story] = []
    for feat_index, (section, reqs) in enumerate(by_section.items(), start=1):
        feature = Feature(
            feature_id=f"FEAT-{feat_index:02d}",
            title=section,
            description=f"Feature derived from BRD section '{section}'",
            requirements=[r.req_id for r in reqs],
        )
        features.append(feature)
        for story_index, req in enumerate(reqs, start=1):
            story_id = f"STORY-{feat_index:02d}.{story_index:02d}"
            stories.append(
                Story(
                    story_id=story_id,
                    feature_id=feature.feature_id,
                    title=req.statement[:80],
                    description=req.statement,
                    acceptance_criteria=[
                        AcceptanceCriterion(
                            ac_id=f"AC-{feat_index:02d}.{story_index:02d}.01",
                            description=f"Given the system, when exercised, "
                            f"then: {req.statement}",
                        ),
                        AcceptanceCriterion(
                            ac_id=f"AC-{feat_index:02d}.{story_index:02d}.02",
                            description=f"Negative/boundary behavior for {req.req_id} "
                            "is handled without data loss and with a clear error.",
                        ),
                    ],
                )
            )
    return features, stories


def build_traceability(
    features: list[Feature], stories: list[Story]
) -> dict:
    trace: dict = {"features": []}
    for feature in features:
        feature_stories = [s for s in stories if s.feature_id == feature.feature_id]
        trace["features"].append(
            {
                "feature": feature.feature_id,
                "requirements": feature.requirements,
                "stories": [
                    {
                        "story": s.story_id,
                        "acceptance_criteria": [ac.ac_id for ac in s.acceptance_criteria],
                    }
                    for s in feature_stories
                ],
            }
        )
    return trace


class ProductAgent:
    name = "product-agent"

    def __init__(self, project_dir: Path) -> None:
        self.fs = FilesystemTool(project_dir)

    async def execute(self, feature: FeatureState, stage: FactoryState) -> AgentResult:
        if stage != FactoryState.DECOMPOSED:
            return AgentResult(status="FAILURE", summary=f"Unsupported stage {stage.value}")

        raw = yaml.safe_load(self.fs.read_text("requirements/requirements.yaml")) or []
        requirements = [Requirement.model_validate(r) for r in raw]
        features, stories = decompose(requirements)
        traceability = build_traceability(features, stories)

        features_path = self.fs.write_text(
            "backlog/features.yaml",
            yaml.safe_dump([f.model_dump(mode="json") for f in features], sort_keys=False),
        )
        stories_path = self.fs.write_text(
            "backlog/stories.yaml",
            yaml.safe_dump([s.model_dump(mode="json") for s in stories], sort_keys=False),
        )
        trace_path = self.fs.write_text(
            "traceability/traceability.yaml", yaml.safe_dump(traceability, sort_keys=False)
        )

        def evidence(kind: str, ref: Path, summary: str) -> Evidence:
            return Evidence(
                evidence_id=new_id("EVD"), stage=stage.value, kind=kind, ref=str(ref),
                summary=summary,
            )

        all_acs = [ac.ac_id for s in stories for ac in s.acceptance_criteria]
        return AgentResult(
            summary=f"{len(features)} features, {len(stories)} stories, {len(all_acs)} ACs",
            evidence=[
                evidence("features", features_path, f"{len(features)} features"),
                evidence("stories", stories_path, f"{len(stories)} stories"),
                evidence("traceability", trace_path, "BR->FEAT->STORY->AC map"),
            ],
            state_updates={
                "stories": [s.story_id for s in stories],
                "acceptance_criteria": all_acs,
            },
            skill="product/feature-decomposition",
        )
