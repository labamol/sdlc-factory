"""Human-in-the-loop gate agent.

When blocking ambiguity remains, the orchestrator transitions the feature to
HUMAN_INPUT and this agent renders a clarification request for the human
gate. Answers arrive as Decision records (meeting transcripts or direct
input), which route the feature back through CLARIFICATION.
"""

from pathlib import Path

import yaml

from factory.agents.base import AgentResult
from factory.models.enums import FactoryState
from factory.models.evidence import Evidence
from factory.models.feature import FeatureState
from factory.orchestrator.events import new_id
from factory.tools.filesystem import FilesystemTool
from factory.tools.notify import Notifier, NotifyError


class HitlGateAgent:
    name = "orchestrator"

    def __init__(self, project_dir: Path, notifier: Notifier | None = None) -> None:
        self.fs = FilesystemTool(project_dir)
        self.notifier = notifier

    async def execute(self, feature: FeatureState, stage: FactoryState) -> AgentResult:
        if stage != FactoryState.HUMAN_INPUT:
            return AgentResult(status="FAILURE", summary=f"Unsupported stage {stage.value}")

        clarifications = []
        if self.fs.exists("requirements/clarifications.yaml"):
            clarifications = (
                yaml.safe_load(self.fs.read_text("requirements/clarifications.yaml")) or []
            )
        open_blocking = [
            c for c in clarifications
            if c["ambiguity_class"] == "BLOCKING" and c["status"] == "OPEN"
        ]
        lines = [
            f"# Clarification Request — {feature.feature_id}",
            "",
            "The factory is paused. Please answer the blocking questions below",
            "(as a meeting decision or direct decision record) and resume.",
            "",
        ]
        for c in open_blocking:
            lines.append(f"- **{c['clr_id']}** [{c['req_id']}]: {c['question']}")
        lines.append("")
        path = self.fs.write_text("hitl/clarification-request.md", "\n".join(lines))
        evidence = [
            Evidence(
                evidence_id=new_id("EVD"),
                stage=stage.value,
                kind="hitl-request",
                ref=str(path),
                summary=f"{len(open_blocking)} blocking questions for human input",
            )
        ]
        notified = self._notify(feature, stage, open_blocking, path)
        if notified is not None:
            evidence.append(notified)
        return AgentResult(
            summary=f"HITL request raised for {len(open_blocking)} blocking clarification(s)",
            evidence=evidence,
        )

    def _notify(
        self,
        feature: FeatureState,
        stage: FactoryState,
        open_blocking: list[dict],
        path: Path,
    ) -> Evidence | None:
        """A paused factory is only useful if a human is told it paused."""
        if self.notifier is None:
            return None
        questions = "\n".join(
            f"- **{c['clr_id']}** [{c['req_id']}]: {c['question']}" for c in open_blocking
        )
        try:
            ref = self.notifier.send(
                f"Human input needed — {feature.feature_id}",
                f"The factory is paused awaiting {len(open_blocking)} "
                f"blocking clarification(s).\n\n{questions}",
                {
                    "Feature": feature.feature_id,
                    "State": stage.value,
                    "Request": str(path),
                },
            )
        except NotifyError as exc:
            ref = f"delivery failed: {exc}"
        return Evidence(
            evidence_id=new_id("EVD"),
            stage=stage.value,
            kind="notification",
            ref=ref,
            summary=f"HITL request notified via {self.notifier.name}",
        )
