"""Langfuse client and prompt helpers."""

import os
from contextlib import AbstractContextManager, nullcontext
from functools import lru_cache

from langfuse import Langfuse
from langfuse.model import BasePromptClient


def is_langfuse_enabled() -> bool:
    """Return whether Langfuse integration is enabled."""
    return os.getenv("LANGFUSE_ENABLED", "false").lower() == "true"


@lru_cache(maxsize=1)
def get_langfuse_client() -> Langfuse:
    """Create the configured Langfuse client."""
    return Langfuse(
        public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
        secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
        host=os.getenv("LANGFUSE_HOST"),
    )


def get_prompt(
    name: str,
    *,
    label: str | None = None,
    version: int | None = None,
) -> BasePromptClient:
    """Fetch a Langfuse prompt by immutable version or mutable label."""
    if version is not None:
        return get_langfuse_client().get_prompt(name, version=version)
    return get_langfuse_client().get_prompt(name, label=label or "production")


def compile_prompt(
    prompt: BasePromptClient,
    **variables: str,
) -> list[dict[str, str]]:
    """Compile a Langfuse text or chat prompt into chat messages."""
    compiled = prompt.compile(**variables)
    if isinstance(compiled, str):
        return [{"role": "user", "content": compiled}]
    return compiled


def observation(
    *,
    name: str,
    as_type: str = "span",
    input_data: object = None,
    metadata: dict[str, object] | None = None,
    trace_id: str | None = None,
) -> AbstractContextManager[object | None]:
    """Start a Langfuse observation when tracing is enabled."""
    if not is_langfuse_enabled():
        return nullcontext()
    return get_langfuse_client().start_as_current_observation(
        trace_context={"trace_id": trace_id} if trace_id else None,
        name=name,
        as_type=as_type,
        input=input_data,
        metadata=metadata,
    )


def get_trace_url(trace_id: str) -> str | None:
    """Return the Langfuse URL for a stored trace ID."""
    if not is_langfuse_enabled():
        return None
    return get_langfuse_client().get_trace_url(trace_id=trace_id)
