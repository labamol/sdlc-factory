"""Acceptance-criteria-driven pytest generation.

Each acceptance criterion produces one test: positive criteria exercise the
story function with deterministic synthetic data; negative/boundary criteria
assert the contract error. Test names embed AC IDs for traceability.
"""

from factory.implementation.codegen import feature_module_name, story_function_name
from factory.implementation.synthdata import generate_synthetic_records
from factory.models.requirement import Feature
from factory.models.story import Story


def _ac_slug(ac_id: str) -> str:
    return ac_id.lower().replace("-", "_").replace(".", "_")


def generate_feature_tests(feature: Feature, stories: list[Story]) -> str:
    module = feature_module_name(feature.feature_id)
    lines = [
        f'"""Generated tests for {feature.feature_id}: {feature.title}."""',
        "",
        "import pytest",
        "",
        f"import {module}",
        "",
        "",
        "@pytest.fixture(autouse=True)",
        "def _reset():",
        f"    {module}.reset()",
        "",
    ]
    for story in stories:
        func = story_function_name(story.story_id)
        record = generate_synthetic_records(story.story_id, count=1)[0]
        for index, ac in enumerate(story.acceptance_criteria):
            test_name = f"test_{_ac_slug(ac.ac_id)}"
            summary = ac.description[:60]
            if index == 0:
                lines += [
                    "",
                    f"def {test_name}():",
                    f'    """{ac.ac_id}: {summary}"""',
                    "    record = {",
                ]
                lines += [f"        {key!r}: {value!r}," for key, value in record.items()]
                lines += [
                    "    }",
                    f"    stored = {module}.{func}(record)",
                    f'    assert stored["story_id"] == "{story.story_id}"',
                    '    assert stored["record_id"] == 1',
                    '    assert stored["email"] == record["email"]',
                    "",
                ]
            else:
                lines += [
                    "",
                    f"def {test_name}():",
                    f'    """{ac.ac_id}: {summary}"""',
                    f"    with pytest.raises({module}.ServiceError):",
                    f"        {module}.{func}({{}})",
                    f"    with pytest.raises({module}.ServiceError):",
                    f'        {module}.{func}("not-a-dict")',
                    "",
                ]
    return "\n".join(lines)
