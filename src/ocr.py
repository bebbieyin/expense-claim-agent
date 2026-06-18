"""Receipt OCR placeholder."""


def extract_text_from_receipt(image_path: str) -> str:
    """Return mock OCR text until a real OCR provider is integrated."""
    del image_path
    # TODO(phase-2): Add EasyOCR or Tesseract.  # noqa: FIX002, TD003
    return "Restoran ABC\nDate: 2026-06-16\nTotal: MYR 45.90"
