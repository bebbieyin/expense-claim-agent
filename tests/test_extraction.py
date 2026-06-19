"""Tests for structured receipt extraction."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.shared.schemas import ExtractedReceipt
from src.workflow.extraction import (
    _azure_openai_extract,
    extract_receipt_fields,
    extract_structured_document,
)


def test_azure_openai_returns_validated_structured_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Azure OpenAI parsed output is validated with the requested schema."""
    parsed = {
        "merchant_name": "Example Store",
        "receipt_date": "2026-06-18",
        "total_amount": 12.50,
        "currency": "MYR",
        "confidence": 0.95,
        "source_text": "Example Store\nTotal MYR 12.50",
    }
    parse = MagicMock(
        return_value=SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(parsed=parsed))]
        )
    )
    azure_openai = MagicMock(
        return_value=SimpleNamespace(
            beta=SimpleNamespace(
                chat=SimpleNamespace(
                    completions=SimpleNamespace(parse=parse),
                )
            )
        )
    )
    monkeypatch.setattr("src.workflow.extraction.AzureOpenAI", azure_openai)
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "key")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.test")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "receipt-model")

    result = _azure_openai_extract(
        [{"role": "user", "content": "receipt text"}],
        ExtractedReceipt,
    )

    assert result == ExtractedReceipt.model_validate(parsed)
    parse.assert_called_once_with(
        model="receipt-model",
        messages=[{"role": "user", "content": "receipt text"}],
        response_format=ExtractedReceipt,
    )


def test_extract_structured_document_rejects_unknown_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only configured structured extraction providers are accepted."""
    monkeypatch.setenv("LLM_PROVIDER", "unknown")

    with pytest.raises(ValueError, match="Unsupported LLM_PROVIDER"):
        extract_structured_document("receipt text", ExtractedReceipt)


def test_receipt_extraction_uses_langfuse_prompt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Enabled Langfuse extraction fetches and compiles the configured prompt."""
    expected = ExtractedReceipt(
        merchant_name="Example Store",
        receipt_date="2026-06-18",
        total_amount=12.50,
        currency="MYR",
        confidence=0.95,
        source_text="receipt text",
    )
    prompt = object()
    get_prompt = MagicMock(return_value=prompt)
    compile_prompt = MagicMock(
        return_value=[{"role": "user", "content": "compiled receipt text"}]
    )
    structured_extract = MagicMock(return_value=expected)
    monkeypatch.setenv("LLM_PROVIDER", "azure_openai")
    monkeypatch.setenv("LANGFUSE_ENABLED", "true")
    monkeypatch.setattr("src.workflow.extraction.get_prompt", get_prompt)
    monkeypatch.setattr("src.workflow.extraction.compile_prompt", compile_prompt)
    monkeypatch.setattr(
        "src.workflow.extraction.extract_structured_document",
        structured_extract,
    )

    result = extract_receipt_fields("receipt text")

    assert result == expected
    get_prompt.assert_called_once_with(
        "receipt-key-info-extraction",
        label="staging",
        version=None,
    )
    compile_prompt.assert_called_once_with(prompt, OCR_TEXT="receipt text")
    structured_extract.assert_called_once_with(
        "receipt text",
        ExtractedReceipt,
        messages=[{"role": "user", "content": "compiled receipt text"}],
    )
