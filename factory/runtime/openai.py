"""OpenAI adapter for the LLM runtime.

Uses Chat Completions with strict JSON-schema structured outputs so the model
must return a document matching the requested Pydantic model. Transport errors
and rate limits are retried with bounded exponential backoff; a response that
still fails schema validation raises `LLMError` so the caller can fall back to
deterministic behaviour rather than propagate an unvalidated result.
"""

import asyncio
import json
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from factory.runtime.llm import LLMError, LLMUsage

T = TypeVar("T", bound=BaseModel)

DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-4o-mini"
RETRY_STATUS = frozenset({408, 409, 429, 500, 502, 503, 504})

# USD per 1M tokens (prompt, completion). Unknown models yield cost_usd=None.
PRICING: dict[str, tuple[float, float]] = {
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "gpt-4.1": (2.00, 8.00),
    "gpt-4.1-mini": (0.40, 1.60),
}


def estimate_cost_usd(model: str, prompt_tokens: int, completion_tokens: int) -> float | None:
    price = PRICING.get(model)
    if price is None:
        return None
    prompt_price, completion_price = price
    cost = (prompt_tokens * prompt_price + completion_tokens * completion_price) / 1_000_000
    return round(cost, 6)


def _strict_schema(schema: type[BaseModel]) -> dict:
    """Pydantic JSON schema adjusted for OpenAI strict structured outputs."""
    document = schema.model_json_schema()
    for definition in [document, *document.get("$defs", {}).values()]:
        if definition.get("type") == "object":
            definition["additionalProperties"] = False
            definition["required"] = sorted(definition.get("properties", {}))
    return document


class OpenAIRuntime:
    """Structured-output runtime backed by the OpenAI Chat Completions API."""

    name = "openai"

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_MODEL,
        base_url: str = DEFAULT_BASE_URL,
        timeout_seconds: float = 60.0,
        max_attempts: int = 3,
        temperature: float = 0.0,
        backoff_base_seconds: float = 1.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not api_key:
            raise LLMError("OpenAI API key is required")
        self.model = model
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._max_attempts = max_attempts
        self._temperature = temperature
        self._backoff_base = backoff_base_seconds
        self._transport = transport

    async def complete_structured(
        self,
        system: str,
        user: str,
        schema: type[T],
        max_output_tokens: int = 2048,
    ) -> tuple[T, LLMUsage]:
        body = {
            "model": self.model,
            "temperature": self._temperature,
            "max_tokens": max_output_tokens,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": schema.__name__,
                    "strict": True,
                    "schema": _strict_schema(schema),
                },
            },
        }
        payload, attempts = await self._post(body)

        choice = payload.get("choices", [{}])[0]
        if choice.get("finish_reason") == "length":
            raise LLMError("OpenAI response truncated before completing the schema")
        content = choice.get("message", {}).get("content") or ""
        try:
            parsed = schema.model_validate_json(content)
        except ValidationError as exc:
            raise LLMError(f"OpenAI response did not match {schema.__name__}: {exc}") from exc

        raw_usage = payload.get("usage", {})
        prompt_tokens = int(raw_usage.get("prompt_tokens", 0))
        completion_tokens = int(raw_usage.get("completion_tokens", 0))
        usage = LLMUsage(
            model=payload.get("model", self.model),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=int(raw_usage.get("total_tokens", prompt_tokens + completion_tokens)),
            attempts=attempts,
            cost_usd=estimate_cost_usd(self.model, prompt_tokens, completion_tokens),
        )
        return parsed, usage

    async def _post(self, body: dict) -> tuple[dict, int]:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        last_error = ""
        async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
            for attempt in range(1, self._max_attempts + 1):
                try:
                    response = await client.post(
                        f"{self._base_url}/chat/completions", headers=headers, json=body
                    )
                except httpx.HTTPError as exc:
                    last_error = f"transport error: {exc}"
                else:
                    if response.status_code == 200:
                        return json.loads(response.text), attempt
                    last_error = f"HTTP {response.status_code}: {response.text[:200]}"
                    if response.status_code not in RETRY_STATUS:
                        break
                if attempt < self._max_attempts:
                    await asyncio.sleep(self._backoff_base * 2 ** (attempt - 1))
        raise LLMError(f"OpenAI request failed after {self._max_attempts} attempts: {last_error}")
