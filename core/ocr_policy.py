"""Global policy switch for local OCR/Tesseract execution."""

from __future__ import annotations

import os


_FALSE_VALUES = {"0", "false", "no", "off", "disabled"}


def ocr_enabled() -> bool:
    """Return whether any project feature may execute local OCR."""
    return os.environ.get("OCR_ENABLED", "true").strip().lower() not in _FALSE_VALUES
