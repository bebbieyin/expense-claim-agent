"""Langfuse client and prompt helpers."""

import os
from functools import lru_cache

from langfuse import Langfuse
from langfuse.model import BasePromptClient


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
