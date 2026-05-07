from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from openai import OpenAI

from src.config import build_schema_format


class LLMClientError(Exception):
    """Friendly wrapper for API errors."""

    def __init__(self, message: str, attempts_used: int = 0) -> None:
        super().__init__(message)
        self.attempts_used = attempts_used


@dataclass
class LLMCallResult:
    raw_text: str
    attempts_used: int
    response_id: str
    repair_used: bool = False


class ComplaintLLMClient:
    def __init__(self, api_key: str, model: str) -> None:
        self.model = model
        self.client = OpenAI(api_key=api_key)

    def test_connection(self) -> str:
        try:
            response = self.client.responses.create(
                model=self.model,
                input="Reply with exactly OK.",
            )
            return response.output_text.strip()
        except Exception as exc:
            raise LLMClientError(self._friendly_error_message(exc)) from exc

    def classify_batch(
        self,
        instructions: str,
        user_input: str,
        max_retries: int,
    ) -> LLMCallResult:
        last_error: Exception | None = None
        attempts_used = 0
        for attempt in range(1, max_retries + 2):
            try:
                attempts_used = attempt
                response = self.client.responses.create(
                    model=self.model,
                    instructions=instructions,
                    input=user_input,
                    text={"format": build_schema_format()},
                )
                return LLMCallResult(
                    raw_text=response.output_text,
                    attempts_used=attempt,
                    response_id=getattr(response, "id", ""),
                )
            except Exception as exc:
                last_error = exc
        raise LLMClientError(
            self._friendly_error_message(last_error),
            attempts_used=attempts_used,
        ) from last_error

    def repair_json(
        self,
        malformed_response: str,
        max_retries: int,
    ) -> LLMCallResult:
        instructions = (
            "You repair malformed JSON. Return only valid JSON that matches the provided schema."
        )
        user_input = f"""Repair this malformed model output into valid JSON matching the schema.

Malformed output:
{malformed_response}
"""
        last_error: Exception | None = None
        attempts_used = 0
        for attempt in range(1, max_retries + 2):
            try:
                attempts_used = attempt
                response = self.client.responses.create(
                    model=self.model,
                    instructions=instructions,
                    input=user_input,
                    text={"format": build_schema_format()},
                )
                return LLMCallResult(
                    raw_text=response.output_text,
                    attempts_used=attempt,
                    response_id=getattr(response, "id", ""),
                    repair_used=True,
                )
            except Exception as exc:
                last_error = exc
        raise LLMClientError(
            self._friendly_error_message(last_error),
            attempts_used=attempts_used,
        ) from last_error

    @staticmethod
    def _friendly_error_message(error: Exception | None) -> str:
        if error is None:
            return "The OpenAI request failed for an unknown reason."

        message = str(error)
        lowered = message.lower()
        if "api key" in lowered or "authentication" in lowered or "401" in lowered:
            return "The OpenAI API key was rejected. Please check that the key is valid and active."
        if "rate limit" in lowered or "429" in lowered:
            return "The OpenAI request hit a rate limit. Please wait a moment and try again."
        if "connection" in lowered or "timeout" in lowered:
            return "The app could not reach the OpenAI API. Please check your internet connection and try again."
        if "model" in lowered and "not found" in lowered:
            return "The selected OpenAI model is not available for this API key."
        return "The OpenAI request failed. Please try again or switch models."
