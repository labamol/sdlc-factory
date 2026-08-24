"""Bounded self-healing loop.

Drives DIAGNOSE -> RETEST -> UNIT_TESTED cycles after a test failure, bounded
by the policy budget. The loop only sequences transitions (WHEN); diagnosis
and repair live in the self-heal agent, retesting in the test agent. The
episode outcome is recorded from the measured test result, and exhaustion
leaves the feature escalated to a human.
"""

from pathlib import Path

from factory.healing.memory import EpisodicMemory
from factory.models.enums import FactoryState, TestStatus
from factory.models.feature import FeatureState
from factory.orchestrator.engine import OrchestratorEngine


async def run_self_heal(
    engine: OrchestratorEngine,
    feature: FeatureState,
    project_dir: Path,
    *,
    max_cycles: int = 3,
) -> FeatureState:
    memory = EpisodicMemory(project_dir)
    cycles = 0
    while feature.current_state == FactoryState.DIAGNOSE and cycles < max_cycles:
        cycles += 1
        feature = await engine.advance(feature, FactoryState.RETEST)
        if feature.current_state != FactoryState.RETEST:
            break
        feature = await engine.advance(feature, FactoryState.UNIT_TESTED)

    repaired = (
        feature.current_state == FactoryState.UNIT_TESTED
        and feature.unit_test_status == TestStatus.PASSED
    )
    episodes = memory.all()
    if episodes and episodes[-1].outcome == "PENDING":
        last = episodes[-1]
        last.outcome = "REPAIRED" if repaired else "ESCALATED"
        memory.update(last)
    return feature
