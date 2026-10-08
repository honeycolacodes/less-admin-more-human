"""The model interface the evals talk to.

The runner depends only on the ModelClient protocol, so tests swap in a fake
and never touch the network.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from anthropic.types import MessageParam


class ModelClient(Protocol):
    def complete(self, prompt: str, *, model: str, max_tokens: int, system: str | None = None) -> str:
        """Send one user message and return the text of the reply."""
        ...


class AnthropicClient:  # pragma: no cover - needs network and an API key
    """ModelClient backed by the Claude API. Reads ANTHROPIC_API_KEY from the environment."""

    def __init__(self, api_key: str | None = None, max_retries: int = 4) -> None:
        import anthropic

        self._client = anthropic.Anthropic(api_key=api_key, max_retries=max_retries)

    def complete(self, prompt: str, *, model: str, max_tokens: int, system: str | None = None) -> str:
        messages: list[MessageParam] = [{"role": "user", "content": prompt}]
        if system:
            reply = self._client.messages.create(
                model=model, max_tokens=max_tokens, system=system, messages=messages
            )
        else:
            reply = self._client.messages.create(model=model, max_tokens=max_tokens, messages=messages)
        # Replies can include thinking blocks; only the text blocks are the answer.
        return "".join(block.text for block in reply.content if block.type == "text").strip()
