"""Reads a PDF from S3 (or local disk) and returns text per page."""

import io
from pypdf import PdfReader


def read_pdf_bytes(pdf_bytes: bytes) -> list[dict]:
    """
    Takes raw PDF bytes, returns a list of dicts:
    [{"page": 1, "text": "..."}, {"page": 2, "text": "..."}]
    """
    reader = PdfReader(io.BytesIO(pdf_bytes))
    pages = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        pages.append({"page": i + 1, "text": text})
    return pages


def read_pdf_from_s3(s3_client, bucket: str, key: str) -> list[dict]:
    """
    Downloads a PDF from S3 and returns page-marked text.
    s3_client is a boto3 S3 client (injected so we can mock it in tests).
    """
    response = s3_client.get_object(Bucket=bucket, Key=key)
    pdf_bytes = response["Body"].read()
    return read_pdf_bytes(pdf_bytes)
