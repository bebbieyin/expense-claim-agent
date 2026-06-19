"""Tests for provider-neutral OCR behavior."""

from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from src.workflow.ocr import (
    MOCK_OCR_TEXT,
    OCR_TIMEOUT_SECONDS,
    _azure_ocr,
    _azure_ocr_endpoint,
    _flatten_polygon,
    extract_document,
)


def test_mock_ocr_returns_normalized_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The default mock provider returns the generic OCR schema."""
    monkeypatch.delenv("OCR_PROVIDER", raising=False)

    result = extract_document("unused.jpg")

    assert result.full_text == MOCK_OCR_TEXT
    assert result.provider == "mock"
    assert result.pages == 1
    assert [line.text for line in result.lines] == MOCK_OCR_TEXT.splitlines()


def test_flatten_polygon_supports_azure_coordinate_formats() -> None:
    """Azure polygons may contain floats or point objects."""
    assert _flatten_polygon([1.0, 2.0, 3.0, 4.0]) == [1.0, 2.0, 3.0, 4.0]
    assert _flatten_polygon(
        [SimpleNamespace(x=1.0, y=2.0), SimpleNamespace(x=3.0, y=4.0)]
    ) == [1.0, 2.0, 3.0, 4.0]
    assert _flatten_polygon([{"x": 1, "y": 2}, {"x": 3, "y": 4}]) == [
        1.0,
        2.0,
        3.0,
        4.0,
    ]


def test_azure_ocr_endpoint_accepts_base_or_full_url() -> None:
    """Azure OCR accepts the portal base endpoint or a complete API URL."""
    base_endpoint = "https://example.cognitiveservices.azure.com/"
    full_endpoint = (
        "https://example.cognitiveservices.azure.com/"
        "computervision/imageanalysis:analyze"
        "?features=read&model-version=latest&api-version=2024-02-01"
    )

    assert _azure_ocr_endpoint(base_endpoint) == full_endpoint
    assert _azure_ocr_endpoint(full_endpoint) == full_endpoint


def test_azure_ocr_returns_read_lines(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Azure Vision Read responses map to the generic OCR schema."""
    image_path = tmp_path / "receipt.png"
    image_path.write_bytes(b"receipt")
    monkeypatch.setenv("AZURE_OCR_ENDPOINT", "https://example.test")
    monkeypatch.setenv("AZURE_OCR_API_KEY", "secret")

    def fake_post(
        endpoint: str,
        *,
        headers: dict[str, str],
        content: bytes,
        timeout: int,
    ) -> httpx.Response:
        assert headers["Ocp-Apim-Subscription-Key"] == "secret"
        assert content == b"receipt"
        assert timeout == OCR_TIMEOUT_SECONDS
        assert "imageanalysis:analyze" in endpoint
        request = httpx.Request("POST", endpoint)
        return httpx.Response(
            200,
            request=request,
            json={
                "readResult": {
                    "blocks": [
                        {
                            "lines": [
                                {
                                    "text": "Example Store",
                                    "boundingPolygon": [
                                        {"x": 1, "y": 2},
                                        {"x": 3, "y": 4},
                                    ],
                                },
                                {"text": "Total 3.00"},
                            ]
                        }
                    ]
                }
            },
        )

    monkeypatch.setattr(httpx, "post", fake_post)

    result = _azure_ocr(str(image_path))

    assert result.full_text == "Example Store\nTotal 3.00"
    assert result.provider == "azure_ocr"
    assert result.model == "read"
    assert result.pages == 1
    assert result.tables == []
    assert result.lines[0].polygon == [1.0, 2.0, 3.0, 4.0]
