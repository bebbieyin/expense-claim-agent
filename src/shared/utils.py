"""Shared filesystem utilities."""

import hashlib
import re
from pathlib import Path
from typing import BinaryIO


def next_claim_id(last_id: int | None) -> str:
    """Create the next readable claim identifier."""
    return f"CLM-{(last_id or 0) + 1:04d}"


def save_uploaded_receipt(
    uploaded_file: BinaryIO,
    original_name: str,
    upload_dir: Path = Path("uploads"),
) -> str:
    """Save an uploaded receipt under a safe unique filename."""
    upload_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(original_name).suffix.lower()
    safe_stem = re.sub(r"[^a-zA-Z0-9_-]+", "-", Path(original_name).stem).strip("-")
    digest = hashlib.sha256(uploaded_file.read()).hexdigest()[:12]
    uploaded_file.seek(0)
    filename = f"{safe_stem or 'receipt'}-{digest}{suffix}"
    destination = upload_dir / filename
    destination.write_bytes(uploaded_file.read())
    return str(destination)
