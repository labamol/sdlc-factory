"""LLM runtime contract.

Agents reason; a runtime is how that reasoning is executed. Every runtime
returns *schema-validated* structures, never free text, so agent results stay
typed and downstream policy gates keep their deterministic contract.

Usage is accounted per call so cost-per-feature is derivable from the same
immutable records the rest of the factory writes.
"""

from typing import Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMError(Exception):
    """Raised when a runtime cannot produce a schema-valid result."""


class LLMUsage(BaseModel):
    model: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    attempts: int = 1
    cost_usd: float | None = None


class LLMRuntime(Protocol):
    name: str
    model: str

    async def complete_structured(
        self,
        system: str,
        user: str,
        schema: type[T],
        max_output_tokens: int = 2048,
    ) -> tuple[T, LLMUsage]:
        """Return an instance of `schema` parsed from the model response."""
        ...
