"""Spec Kit adapter: runs the spec lifecycle for a feature and versions
the resulting artifacts in Git.

Phases (see :mod:`factory.speckit.lifecycle`):
- specify: render spec.md from requirements, stories and acceptance criteria
- clarify: fold approved decisions and assumptions into the spec
- plan:    render plan.md (architecture/technology plan placeholder sections)
- tasks:   render tasks.md with per-story implementation/test tasks
- analyze: cross-check spec/plan/tasks coverage and write analysis.md
"""

from pathlib import Path

import yaml

from factory.models.requirement import Assumption, Decision, Feature, Requirement
from factory.models.story import Story
from factory.speckit.lifecycle import SPEC_LIFECYCLE
from factory.tools.filesystem import FilesystemTool
from factory.tools.git import GitError, GitTool


class SpecAnalysisError(Exception):
    """Raised when analyze finds spec/plan/tasks inconsistencies."""


class SpecKitAdapter:
    def __init__(self, project_dir: Path) -> None:
        self.fs = FilesystemTool(project_dir)
        self.git = GitTool(project_dir)

    # ------------------------------------------------------------------ IO

    def _spec_dir(self, feature_id: str) -> str:
        return f"specs/{feature_id}"

    def _load_yaml(self, relative: str) -> list[dict]:
        if not self.fs.exists(relative):
            return []
        return yaml.safe_load(self.fs.read_text(relative)) or []

    # -------------------------------------------------------------- phases

    def specify(
        self,
        feature: Feature,
        requirements: list[Requirement],
        stories: list[Story],
    ) -> Path:
        req_by_id = {r.req_id: r for r in requirements}
        lines = [
            f"# Specification: {feature.feature_id} — {feature.title}",
            "",
            f"> {feature.description}",
            "",
            "## Requirements",
            "",
        ]
        for req_id in feature.requirements:
            req = req_by_id[req_id]
            lines.append(f"- **{req.req_id}** ({req.source}): {req.statement}")
        lines += ["", "## Stories and Acceptance Criteria", ""]
        for story in stories:
            lines.append(f"### {story.story_id}: {story.title}")
            lines.append("")
            for ac in story.acceptance_criteria:
                marker = "mandatory" if ac.mandatory else "optional"
                lines.append(f"- **{ac.ac_id}** ({marker}): {ac.description}")
            lines.append("")
        lines += ["## Open Points", "", "_Resolved during the clarify phase._", ""]
        return self.fs.write_text(f"{self._spec_dir(feature.feature_id)}/spec.md", "\n".join(lines))

    def clarify(
        self,
        feature: Feature,
        decisions: list[Decision],
        assumptions: list[Assumption],
    ) -> Path:
        relevant_decisions = [
            d for d in decisions
            if d.status == "APPROVED"
            and (d.feature in (None, feature.feature_id) or d.requirement in feature.requirements)
        ]
        relevant_assumptions = [
            a for a in assumptions if a.status == "ACTIVE" and a.req_id in feature.requirements
        ]
        lines = [
            f"# Clarifications: {feature.feature_id}",
            "",
            "## Approved Decisions",
            "",
        ]
        if relevant_decisions:
            for d in relevant_decisions:
                scope = d.requirement or d.feature or "general"
                lines.append(
                    f"- **{d.decision_id}** [{scope}] ({d.source}): {d.decision}"
                )
        else:
            lines.append("_None._")
        lines += ["", "## Active Assumptions", ""]
        if relevant_assumptions:
            for a in relevant_assumptions:
                lines.append(f"- **{a.asm_id}** [{a.req_id}] risk={a.risk}: {a.statement}")
        else:
            lines.append("_None._")
        lines.append("")
        return self.fs.write_text(
            f"{self._spec_dir(feature.feature_id)}/clarifications.md", "\n".join(lines)
        )

    def plan(self, feature: Feature) -> Path:
        lines = [
            f"# Implementation Plan: {feature.feature_id} — {feature.title}",
            "",
            "## Architecture",
            "",
            "- Components affected and their responsibilities are derived from the",
            "  requirements in spec.md; each requirement maps to at least one component.",
            "",
            "## Technology",
            "",
            "- Use the project's established stack and approved templates; deviations",
            "  require an approved Decision record.",
            "",
            "## Data and Interfaces",
            "",
            "- Data contracts and interface changes are enumerated per story in tasks.md.",
            "",
            "## Risks",
            "",
            "- Risks inherit from active assumptions listed in clarifications.md.",
            "",
        ]
        return self.fs.write_text(f"{self._spec_dir(feature.feature_id)}/plan.md", "\n".join(lines))

    def tasks(self, feature: Feature, stories: list[Story]) -> Path:
        lines = [f"# Tasks: {feature.feature_id} — {feature.title}", ""]
        task_number = 0
        for story in stories:
            lines.append(f"## {story.story_id}: {story.title}")
            lines.append("")
            task_number += 1
            lines.append(
                f"- [ ] TASK-{task_number:03d} Implement {story.story_id}: {story.description}"
            )
            for ac in story.acceptance_criteria:
                task_number += 1
                lines.append(
                    f"- [ ] TASK-{task_number:03d} Test {ac.ac_id}: {ac.description}"
                )
            lines.append("")
        return self.fs.write_text(
            f"{self._spec_dir(feature.feature_id)}/tasks.md", "\n".join(lines)
        )

    def analyze(self, feature: Feature, stories: list[Story]) -> Path:
        spec_dir = self._spec_dir(feature.feature_id)
        problems: list[str] = []
        for artifact in ("spec.md", "clarifications.md", "plan.md", "tasks.md"):
            if not self.fs.exists(f"{spec_dir}/{artifact}"):
                problems.append(f"missing artifact: {artifact}")
        if not problems:
            spec_text = self.fs.read_text(f"{spec_dir}/spec.md")
            tasks_text = self.fs.read_text(f"{spec_dir}/tasks.md")
            for req_id in feature.requirements:
                if req_id not in spec_text:
                    problems.append(f"{req_id} not covered in spec.md")
            for story in stories:
                if story.story_id not in tasks_text:
                    problems.append(f"{story.story_id} has no tasks")
                for ac in story.acceptance_criteria:
                    if ac.ac_id not in tasks_text:
                        problems.append(f"{ac.ac_id} has no test task")
        status = "PASS" if not problems else "FAIL"
        lines = [
            f"# Spec Analysis: {feature.feature_id}",
            "",
            f"Result: **{status}**",
            "",
        ]
        lines += [f"- {p}" for p in problems] or ["- All requirements, stories and ACs covered."]
        lines.append("")
        path = self.fs.write_text(f"{spec_dir}/analysis.md", "\n".join(lines))
        if problems:
            raise SpecAnalysisError("; ".join(problems))
        return path

    # ------------------------------------------------------------ lifecycle

    def run_lifecycle(
        self,
        feature: Feature,
        requirements: list[Requirement],
        stories: list[Story],
        decisions: list[Decision],
        assumptions: list[Assumption],
    ) -> dict[str, Path]:
        """Run all Spec Kit phases for one feature; returns artifact paths."""
        artifacts: dict[str, Path] = {}
        for phase in SPEC_LIFECYCLE:
            if phase == "specify":
                artifacts[phase] = self.specify(feature, requirements, stories)
            elif phase == "clarify":
                artifacts[phase] = self.clarify(feature, decisions, assumptions)
            elif phase == "plan":
                artifacts[phase] = self.plan(feature)
            elif phase == "tasks":
                artifacts[phase] = self.tasks(feature, stories)
            elif phase == "analyze":
                artifacts[phase] = self.analyze(feature, stories)
        return artifacts

    def commit_spec(self, feature: Feature, version: str) -> str | None:
        """Version the spec directory in Git; returns the commit hash."""
        spec_dir = self._spec_dir(feature.feature_id)
        try:
            self.git.add(spec_dir)
            if not self.git.status_porcelain():
                return None
            return self.git.commit(f"spec({feature.feature_id}): {version}")
        except GitError:
            return None
