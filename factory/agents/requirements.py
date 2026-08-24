"""Requirements Analyst agent.

Owns INTAKE and CLARIFICATION: parses the BRD into stable requirements,
classifies ambiguity, records assumptions when safe to proceed and normalizes
meeting transcripts into decision records with provenance.
"""

from pathlib import Path

import yaml

from factory.agents.ambiguity import analyze_requirements, has_blocking
from factory.agents.base import AgentResult
from factory.knowledge.ingestion.brd import parse_brd, render_requirements_md
from factory.knowledge.ingestion.meetings import extract_decisions
from factory.models.enums import FactoryState
from factory.models.evidence import Evidence
from factory.models.feature import FeatureState
from factory.orchestrator.events import new_id
from factory.tools.filesystem import FilesystemTool


class RequirementsAgent:
    name = "requirements-agent"

    def __init__(self, project_dir: Path) -> None:
        self.fs = FilesystemTool(project_dir)

    def _evidence(self, stage: FactoryState, kind: str, path: Path, summary: str) -> Evidence:
        return Evidence(
            evidence_id=new_id("EVD"), stage=stage.value, kind=kind, ref=str(path),
            summary=summary,
        )

    async def execute(self, feature: FeatureState, stage: FactoryState) -> AgentResult:
        if stage == FactoryState.INTAKE:
            return self._intake(feature, stage)
        if stage == FactoryState.CLARIFICATION:
            return self._clarify(feature, stage)
        if stage == FactoryState.REQUIREMENTS_READY:
            return self._requirements_ready(feature, stage)
        return AgentResult(status="FAILURE", summary=f"Unsupported stage {stage.value}")

    def _intake(self, feature: FeatureState, stage: FactoryState) -> AgentResult:
        if not self.fs.exists("intake/brd.md"):
            return AgentResult(
                status="FAILURE", summary="No BRD found at intake/brd.md", skill=None
            )
        parsed = parse_brd(self.fs.read_text("intake/brd.md"), source="intake/brd.md")
        if not parsed.requirements:
            return AgentResult(
                status="FAILURE",
                summary="BRD contains no identifiable requirements; human clarification needed",
            )
        path = self.fs.write_text("requirements/requirements.md", render_requirements_md(parsed))
        yaml_path = self.fs.write_text(
            "requirements/requirements.yaml",
            yaml.safe_dump(
                [r.model_dump(mode="json") for r in parsed.requirements], sort_keys=False
            ),
        )
        return AgentResult(
            summary=f"Extracted {len(parsed.requirements)} requirements from BRD",
            evidence=[
                self._evidence(stage, "requirements", path, "Extracted requirements"),
                self._evidence(stage, "requirements-yaml", yaml_path, "Structured requirements"),
            ],
            state_updates={"requirements": [r.req_id for r in parsed.requirements]},
            skill="requirements/brd-analysis",
        )

    def _clarify(self, feature: FeatureState, stage: FactoryState) -> AgentResult:
        parsed = parse_brd(self.fs.read_text("intake/brd.md"), source="intake/brd.md")
        clarifications, assumptions = analyze_requirements(parsed.requirements)

        clr_path = self.fs.write_text(
            "requirements/clarifications.yaml",
            yaml.safe_dump([c.model_dump(mode="json") for c in clarifications], sort_keys=False),
        )
        asm_path = self.fs.write_text(
            "requirements/assumptions.yaml",
            yaml.safe_dump([a.model_dump(mode="json") for a in assumptions], sort_keys=False),
        )

        evidence = [
            self._evidence(stage, "clarifications", clr_path,
                           f"{len(clarifications)} clarifications"),
            self._evidence(stage, "assumptions", asm_path, f"{len(assumptions)} assumptions"),
        ]

        decisions = []
        if self.fs.exists("intake/meetings"):
            for name in self.fs.list_dir("intake/meetings"):
                transcript = self.fs.read_text(f"intake/meetings/{name}")
                decisions += extract_decisions(
                    transcript, source=f"intake/meetings/{name}", start_index=len(decisions) + 1
                )
        if decisions:
            dec_path = self.fs.write_text(
                "decisions/decisions.yaml",
                yaml.safe_dump(
                    [d.model_dump(mode="json") for d in decisions], sort_keys=False
                ),
            )
            evidence.append(
                self._evidence(stage, "decisions", dec_path, f"{len(decisions)} decisions")
            )
            # A confirmed decision resolves matching open clarifications.
            for clarification in clarifications:
                if clarification.status == "OPEN" and any(
                    d.requirement == clarification.req_id for d in decisions
                ):
                    clarification.status = "ANSWERED"
            self.fs.write_text(
                "requirements/clarifications.yaml",
                yaml.safe_dump(
                    [c.model_dump(mode="json") for c in clarifications], sort_keys=False
                ),
            )

        blocking = has_blocking(clarifications)
        return AgentResult(
            summary=(
                "Blocking clarifications remain; human input required"
                if blocking
                else f"{len(clarifications)} clarifications ({len(assumptions)} assumed)"
            ),
            evidence=evidence,
            state_updates={},
            skill="requirements/ambiguity-detection",
        )

    def _requirements_ready(self, feature: FeatureState, stage: FactoryState) -> AgentResult:
        clarifications = yaml.safe_load(self.fs.read_text("requirements/clarifications.yaml")) or []
        open_blocking = [
            c for c in clarifications
            if c["ambiguity_class"] == "BLOCKING" and c["status"] == "OPEN"
        ]
        if open_blocking:
            return AgentResult(
                status="FAILURE",
                summary=f"{len(open_blocking)} blocking clarifications still open",
            )
        return AgentResult(
            summary="Requirements baselined; no blocking ambiguity",
            skill="requirements/assumption-management",
        )
