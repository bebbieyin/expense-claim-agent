"""Provider-neutral receipt OCR."""

import os
from pathlib import Path
from typing import Any

import httpx

from src.shared.schemas import OCRLine, OCRResult

MOCK_OCR_TEXT = "Restoran ABC\nDate: 2026-06-16\nTotal: MYR 45.90"
OCR_TIMEOUT_SECONDS = 30
AZURE_OCR_PATH = (
    "computervision/imageanalysis:analyze"
    "?features=read&model-version=latest&api-version=2024-02-01"
)


def _flatten_polygon(polygon: list[Any] | None) -> list[float]:
    """Normalize Azure polygon coordinates to a flat list of floats."""
    coordinates = []
    for point in polygon or []:
        if hasattr(point, "x") and hasattr(point, "y"):
            coordinates.extend((point.x, point.y))
        elif isinstance(point, dict):
            coordinates.extend((float(point["x"]), float(point["y"])))
        else:
            coordinates.extend((float(point),))
    return coordinates


def _azure_ocr_endpoint(endpoint: str) -> str:
    """Return a complete Azure Vision Image Analysis endpoint."""
    if "imageanalysis:analyze" in endpoint:
        return endpoint
    return f"{endpoint.rstrip('/')}/{AZURE_OCR_PATH}"


def _azure_ocr(image_path: str) -> OCRResult:
    """Extract receipt text using the configured Azure Vision OCR endpoint."""
    endpoint = _azure_ocr_endpoint(os.environ["AZURE_OCR_ENDPOINT"])
    api_key = os.environ["AZURE_OCR_API_KEY"]
    with Path(image_path).open("rb") as document:
        response = httpx.post(
            endpoint,
            headers={
                "Content-Type": "application/octet-stream",
                "Ocp-Apim-Subscription-Key": api_key,
            },
            content=document.read(),
            timeout=OCR_TIMEOUT_SECONDS,
        )
    response.raise_for_status()
    raw_response = response.json()

    blocks = raw_response.get("readResult", {}).get("blocks", [])
    lines = []
    for page_number, block in enumerate(blocks, start=1):
        lines.extend(
            OCRLine(
                text=line.get("text", ""),
                page_number=page_number,
                polygon=_flatten_polygon(line.get("boundingPolygon")),
            )
            for line in block.get("lines", [])
        )

    return OCRResult(
        full_text="\n".join(line.text for line in lines),
        pages=len(blocks),
        lines=lines,
        provider="azure_ocr",
        model="read",
        raw_response=raw_response,
    )


def extract_document(image_path: str) -> OCRResult:
    """Extract text using the configured OCR provider."""
    provider = os.getenv("OCR_PROVIDER", "mock")
    if provider == "mock":
        return OCRResult(
            full_text=MOCK_OCR_TEXT,
            pages=1,
            lines=[
                OCRLine(text=text, page_number=1) for text in MOCK_OCR_TEXT.splitlines()
            ],
            provider="mock",
            model="mock",
        )
    if provider == "azure_ocr":
        return _azure_ocr(image_path)
    msg = f"Unsupported OCR_PROVIDER: {provider}"
    raise ValueError(msg)


def extract_text_from_receipt(image_path: str) -> str:
    """Return plain OCR text for the existing receipt workflow."""
    return extract_document(image_path).full_text
