"""Validation agent.

Owns FUNCTIONAL_TESTED (run the packaged test suite against the deployed
artifact — not the workspace), AC_VALIDATED (map every acceptance criterion
to its test outcome and enforce the mandatory pass percentage from the
deployment policy) and STORY_COMPLETED (close stories and requirements in
the tracker with full traceability).
"""

import re
import sys
from pathlib import Path

import yaml

from factory.agents.base import AgentResult
from factory.implementation.testgen import ac_slug
from factory.models.enums import FactoryState, TestStatus
from factory.models.evidence import Evidence
from factory.models.feature import FeatureState
from factory.models.story import Story
from factory.orchestrator.events import new_id
from factory.tools.filesystem import FilesystemTool
from factory.tools.notify import Notifier, NotifyError
from factory.tools.shell import ShellTool
from factory.tools.tracker import Tracker, TrackerError, TrackerIssue

FUNCTIONAL_REPORT = "validation/functional-report.txt"
VALIDATION_REPORT = "validation/validation-report.yaml"
RESULT_LINE = re.compile(r"::(test_\w+)\s+(PASSED|FAILED|ERROR)")


class ValidationAgent:
    name = "validation-agent"

    def __init__(
        self,
        project_dir: Path,
        policies_dir: Path,
        *,
        environment: str = "local",
        tracker: Tracker | None = None,
        notifier: Notifier | None = None,
    ) -> None:
        self.project_dir = project_dir
        self.policies_dir = policies_dir
        self.fs = FilesystemTool(project_dir)
        self.environment = environment
        self.tracker = tracker
        self.notifier = notifier

    def _stories(self) -> list[Story]:
        if not self.fs.exists("backlog/stories.yaml"):
            return []
        raw = yaml.safe_load(self.fs.read_text("backlog/stories.yaml")) or []
        return [Story.model_validate(s) for s in raw]

    def _mandatory_pass_percentage(self) -> float:
        policy_path = self.policies_dir / "deployment.yaml"
        if not policy_path.exists():
            return 100.0
        policy = yaml.safe_load(policy_path.read_text(encoding="utf-8")) or {}
        return float(
            policy.get("deployment_policy", {}).get("mandatory_ac_pass_percentage", 100)
        )

    async def execute(self, feature: FeatureState, stage: FactoryState) -> AgentResult:
        if stage == FactoryState.FUNCTIONAL_TESTED:
            return self._functional_test(stage)
        if stage == FactoryState.AC_VALIDATED:
            return self._validate_acs(feature, stage)
        if stage == FactoryState.STORY_COMPLETED:
            return self._complete_stories(feature, stage)
        return AgentResult(status="FAILURE", summary=f"Unsupported stage {stage.value}")

    def _functional_test(self, stage: FactoryState) -> AgentResult:
        target = self.project_dir / "deployments" / self.environment
        if not (target / "tests").exists():
            return AgentResult(
                status="FAILURE", summary=f"No deployed tests under {target}"
            )
        shell = ShellTool(target)
        result = shell.run(
            [sys.executable, "-m", "pytest", "tests", "-v", "--rootdir", "."]
        )
        report_path = self.fs.write_text(
            FUNCTIONAL_REPORT,
            f"$ pytest tests -v  (deployment: {self.environment})\n"
            f"exit={result.exit_code}\n\n{result.stdout}{result.stderr}",
        )
        status = TestStatus.PASSED if result.ok else TestStatus.FAILED
        return AgentResult(
            status="SUCCESS" if result.ok else "FAILURE",
            summary=f"Functional tests against deployed artifact "
                    f"{'passed' if result.ok else 'failed'}",
            evidence=[
                Evidence(
                    evidence_id=new_id("EVD"), stage=stage.value,
                    kind="functional-report", ref=str(report_path),
                    summary=result.stdout.strip().splitlines()[-1]
                    if result.stdout.strip() else "no output",
                )
            ],
            state_updates={"functional_test_status": status},
            skill="testing/functional",
        )

    def _validate_acs(self, feature: FeatureState, stage: FactoryState) -> AgentResult:
        if not self.fs.exists(FUNCTIONAL_REPORT):
            return AgentResult(status="FAILURE", summary="No functional report found")
        outcomes = {
            match.group(1): match.group(2)
            for match in RESULT_LINE.finditer(self.fs.read_text(FUNCTIONAL_REPORT))
        }
        results = []
        for story in self._stories():
            for ac in story.acceptance_criteria:
                outcome = outcomes.get(f"test_{ac_slug(ac.ac_id)}", "MISSING")
                results.append(
                    {
                        "ac_id": ac.ac_id,
                        "story_id": story.story_id,
                        "mandatory": ac.mandatory,
                        "test_outcome": outcome,
                        "passed": outcome == "PASSED",
                    }
                )
        if not results:
            return AgentResult(status="FAILURE", summary="No acceptance criteria found")
        mandatory = [r for r in results if r["mandatory"]]
        passed = [r for r in mandatory if r["passed"]]
        pass_pct = round(100.0 * len(passed) / len(mandatory), 2) if mandatory else 0.0
        threshold = self._mandatory_pass_percentage()
        decision = "PASS" if pass_pct >= threshold else "FAIL"
        report = {
            "feature_id": feature.feature_id,
            "environment": self.environment,
            "mandatory_ac_pass_percentage": pass_pct,
            "threshold": threshold,
            "decision": decision,
            "results": results,
        }
        report_path = self.fs.write_text(
            VALIDATION_REPORT, yaml.safe_dump(report, sort_keys=False)
        )
        return AgentResult(
            status="SUCCESS" if decision == "PASS" else "FAILURE",
            summary=f"AC validation {decision}: {len(passed)}/{len(mandatory)} "
                    f"mandatory ACs passed ({pass_pct}%)",
            evidence=[
                Evidence(
                    evidence_id=new_id("EVD"), stage=stage.value,
                    kind="validation-report", ref=str(report_path),
                    summary=f"{pass_pct}% mandatory AC pass (threshold {threshold}%)",
                    metadata={"decision": decision},
                )
            ],
            skill="validation/acceptance-criteria",
        )

    def _complete_stories(self, feature: FeatureState, stage: FactoryState) -> AgentResult:
        validation = yaml.safe_load(self.fs.read_text(VALIDATION_REPORT)) or {}
        if validation.get("decision") != "PASS":
            return AgentResult(
                status="FAILURE", summary="Cannot close stories without AC validation PASS"
            )
        stories = self._stories()
        completion = {
            "feature_id": feature.feature_id,
            "stories": [
                {"story_id": s.story_id, "status": "DONE",
                 "acceptance_criteria": [ac.ac_id for ac in s.acceptance_criteria]}
                for s in stories
            ],
            "requirements_closed": sorted(feature.requirements),
            "evidence": {
                "validation_report": VALIDATION_REPORT,
                "functional_report": FUNCTIONAL_REPORT,
            },
        }
        issues, tracker_error = self._close_in_tracker(feature, stories)
        if issues:
            for entry, issue in zip(completion["stories"], issues, strict=False):
                entry["issue_key"] = issue.key
                entry["issue_url"] = issue.url
        if tracker_error:
            completion["tracker_error"] = tracker_error
        path = self.fs.write_text(
            "tracker/completion.yaml", yaml.safe_dump(completion, sort_keys=False)
        )
        evidence = [
            Evidence(
                evidence_id=new_id("EVD"), stage=stage.value,
                kind="tracker-completion", ref=str(path),
                summary=f"{len(stories)} stories DONE",
            )
        ]
        notified = self._notify(
            stage,
            f"Story completion — {feature.feature_id}",
            f"{len(stories)} story(ies) and {len(feature.requirements)} "
            "requirement(s) closed after AC validation PASS.",
            {"Feature": feature.feature_id,
             "Issues": ", ".join(i.key for i in issues) or "none",
             "Evidence": str(path)},
        )
        if notified is not None:
            evidence.append(notified)
        return AgentResult(
            summary=f"Closed {len(stories)} story(ies) and "
                    f"{len(feature.requirements)} requirement(s) in tracker",
            evidence=evidence,
            skill="tracking/closure",
        )

    def _close_in_tracker(
        self, feature: FeatureState, stories: list[Story]
    ) -> tuple[list[TrackerIssue], str]:
        """Open and immediately close one issue per validated story."""
        if self.tracker is None:
            return [], ""
        issues: list[TrackerIssue] = []
        try:
            for story in stories:
                acs = ", ".join(ac.ac_id for ac in story.acceptance_criteria)
                issue = self.tracker.open_issue(
                    f"{story.story_id}: {story.title}",
                    f"Delivered by the SDLC factory for {feature.feature_id}.\n"
                    f"Acceptance criteria: {acs}",
                )
                issues.append(
                    self.tracker.complete_issue(
                        issue,
                        f"Acceptance criteria validated ({acs}). "
                        f"Evidence: {VALIDATION_REPORT}",
                    )
                )
        except TrackerError as exc:
            return issues, str(exc)
        return issues, ""

    def _notify(
        self, stage: FactoryState, title: str, text: str, facts: dict[str, str]
    ) -> Evidence | None:
        if self.notifier is None:
            return None
        try:
            ref = self.notifier.send(title, text, facts)
        except NotifyError as exc:
            ref = f"delivery failed: {exc}"
        return Evidence(
            evidence_id=new_id("EVD"), stage=stage.value, kind="notification",
            ref=ref, summary=f"{title} notified via {self.notifier.name}",
        )
