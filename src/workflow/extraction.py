"""Structured document extraction."""

import os

from langfuse.openai import AzureOpenAI
from pydantic import BaseModel

from prompts.receipt_extraction import DEFAULT_EXTRACTION_PROMPT
from src.client.langfuse_client import compile_prompt, get_prompt
from src.shared.schemas import ExtractedReceipt

LANGFUSE_PROMPT_NAME = "receipt-key-info-extraction"
LANGFUSE_PROMPT_LABEL = "staging"


def _azure_openai_extract(
    messages: list[dict[str, str]],
    output_schema: type[BaseModel],
) -> BaseModel:
    """Invoke Azure OpenAI with strict structured output."""
    client = AzureOpenAI(
        api_key=os.environ["AZURE_OPENAI_API_KEY"],
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2025-04-01-preview"),
    )
    response = client.beta.chat.completions.parse(
        model=os.environ["AZURE_OPENAI_DEPLOYMENT"],
        messages=messages,
        response_format=output_schema,
    )
    parsed = response.choices[0].message.parsed
    if parsed is None:
        msg = "Azure OpenAI returned an empty extraction response."
        raise ValueError(msg)
    return output_schema.model_validate(parsed)


def extract_structured_document(
    raw_ocr_text: str,
    output_schema: type[BaseModel],
    *,
    messages: list[dict[str, str]] | None = None,
) -> BaseModel:
    """Extract a Pydantic model from OCR text with the configured LLM."""
    provider = os.getenv("LLM_PROVIDER", "mock")
    if provider != "azure_openai":
        msg = f"Unsupported LLM_PROVIDER for structured extraction: {provider}"
        raise ValueError(msg)

    prompt_messages = messages or [
        {
            **message,
            "content": message["content"].replace("{OCR_TEXT}", raw_ocr_text),
        }
        for message in DEFAULT_EXTRACTION_PROMPT
    ]
    return _azure_openai_extract(prompt_messages, output_schema)


def extract_receipt_fields(
    raw_ocr_text: str,
    *,
    prompt_name: str = LANGFUSE_PROMPT_NAME,
    prompt_label: str = LANGFUSE_PROMPT_LABEL,
    prompt_version: int | None = None,
    messages: list[dict[str, str]] | None = None,
) -> ExtractedReceipt:
    """Extract receipt fields from OCR text or return the mock fixture."""
    # return mock values if LLM provider is not configured
    if os.getenv("LLM_PROVIDER", "mock") == "mock":
        return ExtractedReceipt(
            merchant_name="Restoran ABC",
            receipt_date="2026-06-16",
            total_amount=45.90,
            currency="MYR",
            confidence=0.91,
        )

    if messages is None and os.getenv("LANGFUSE_ENABLED", "false").lower() == "true":
        prompt = get_prompt(
            prompt_name,
            label=prompt_label,
            version=prompt_version,
        )
        messages = compile_prompt(prompt, OCR_TEXT=raw_ocr_text)

    result = extract_structured_document(
        raw_ocr_text,
        ExtractedReceipt,
        messages=messages,
    )
    return ExtractedReceipt.model_validate(result)
