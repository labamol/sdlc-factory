"""Template-driven source generation.

One module per feature; one entry function per story. Every function
validates its input (the negative/boundary acceptance criterion) and returns
a stored record with a stable identifier (the positive criterion). Generated
code is stdlib-only so build and unit tests run anywhere.
"""

from factory.models.requirement import Feature
from factory.models.story import Story


def feature_module_name(feature_id: str) -> str:
    return feature_id.lower().replace("-", "_")


def story_function_name(story_id: str) -> str:
    return story_id.lower().replace("-", "_").replace(".", "_")


def generate_feature_module(feature: Feature, stories: list[Story]) -> str:
    lines = [
        f'"""Generated service module for {feature.feature_id}: {feature.title}.',
        "",
        f"Implements stories: {', '.join(s.story_id for s in stories)}.",
        '"""',
        "",
        "",
        "class ServiceError(ValueError):",
        '    """Raised when a request violates a story contract."""',
        "",
        "",
        "_RECORDS: list[dict] = []",
        "",
        "",
        "def reset() -> None:",
        "    _RECORDS.clear()",
        "",
    ]
    for story in stories:
        func = story_function_name(story.story_id)
        lines += [
            "",
            f"def {func}(record: dict) -> dict:",
            f'    """{story.story_id}: {story.title}',
            "",
            f"    Traceability: {', '.join(ac.ac_id for ac in story.acceptance_criteria)}",
            '    """',
            "    if not isinstance(record, dict) or not record:",
            f'        raise ServiceError("{story.story_id}: record must be a non-empty dict")',
            "    stored = dict(record)",
            f'    stored["story_id"] = "{story.story_id}"',
            '    stored["record_id"] = len(_RECORDS) + 1',
            "    _RECORDS.append(stored)",
            "    return stored",
            "",
        ]
    return "\n".join(lines)
