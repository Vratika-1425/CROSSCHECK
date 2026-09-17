"""Verifies that quotes extracted by the LLM exist verbatim on the cited page."""

import re


def normalize_text(text: str) -> str:
    """Lowercase and collapse multiple spaces/newlines into a single space."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip().lower()


def verify_quote(page_text: str, quote: str) -> bool:
    """
    Checks if a quote exists inside the given page's text.
    Handles minor whitespace/newline differences between PDF layouts.
    """
    if not quote or not page_text:
        return False

    clean_page = normalize_text(page_text)
    clean_quote = normalize_text(quote)

    return clean_quote in clean_page


def verify_extraction_field(field_data: dict, pages_by_number: dict[int, str]) -> dict:
    """
    Takes a single field dict: {"value": ..., "page": 1, "quote": "..."}
    and adds a "verified" boolean flag.
    """
    if not isinstance(field_data, dict):
        return {"value": field_data, "page": None, "quote": None, "verified": False}

    value = field_data.get("value")
    page = field_data.get("page")
    quote = field_data.get("quote")

    if value is None:
        return {"value": None, "page": None, "quote": None, "verified": True}

    if page is None or quote is None or page not in pages_by_number:
        return {"value": value, "page": page, "quote": quote, "verified": False}

    target_page_text = pages_by_number[page]
    is_valid = verify_quote(target_page_text, quote)

    return {
        "value": value,
        "page": page,
        "quote": quote,
        "verified": is_valid
    }
