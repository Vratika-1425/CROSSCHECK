"""Amazon Bedrock Converse tool-use client for structured project extraction."""

import json
from .evidence import verify_extraction_field

EXTRACTION_TOOL = {
    "toolSpec": {
        "name": "extract_infrastructure_tender",
        "description": "Extract structured municipal tender details along with page numbers and exact evidence quotes.",
        "inputSchema": {
            "json": {
                "type": "object",
                "properties": {
                    "agency": {
                        "type": "object",
                        "properties": {
                            "value": {"type": ["string", "null"]},
                            "page": {"type": ["integer", "null"]},
                            "quote": {"type": ["string", "null"]}
                        },
                        "required": ["value", "page", "quote"]
                    },
                    "work_order_id": {
                        "type": "object",
                        "properties": {
                            "value": {"type": ["string", "null"]},
                            "page": {"type": ["integer", "null"]},
                            "quote": {"type": ["string", "null"]}
                        },
                        "required": ["value", "page", "quote"]
                    },
                    "title": {
                        "type": "object",
                        "properties": {
                            "value": {"type": ["string", "null"]},
                            "page": {"type": ["integer", "null"]},
                            "quote": {"type": ["string", "null"]}
                        },
                        "required": ["value", "page", "quote"]
                    },
                    "work_type": {
                        "type": "object",
                        "properties": {
                            "value": {
                                "type": ["string", "null"],
                                "enum": [
                                    "road_resurfacing",
                                    "road_construction",
                                    "drainage",
                                    "water_supply",
                                    "sewerage",
                                    "electrical_cable",
                                    "telecom_fiber",
                                    "other",
                                    None
                                ]
                            },
                            "page": {"type": ["integer", "null"]},
                            "quote": {"type": ["string", "null"]}
                        },
                        "required": ["value", "page", "quote"]
                    },
                    "excavation_required": {
                        "type": "object",
                        "properties": {
                            "value": {"type": ["boolean", "null"]},
                            "page": {"type": ["integer", "null"]},
                            "quote": {"type": ["string", "null"]}
                        },
                        "required": ["value", "page", "quote"]
                    },
                    "road_name": {
                        "type": "object",
                        "properties": {
                            "value": {"type": ["string", "null"]},
                            "page": {"type": ["integer", "null"]},
                            "quote": {"type": ["string", "null"]}
                        },
                        "required": ["value", "page", "quote"]
                    },
                    "start_date": {
                        "type": "object",
                        "properties": {
                            "value": {"type": ["string", "null"]},
                            "page": {"type": ["integer", "null"]},
                            "quote": {"type": ["string", "null"]}
                        },
                        "required": ["value", "page", "quote"]
                    },
                    "end_date": {
                        "type": "object",
                        "properties": {
                            "value": {"type": ["string", "null"]},
                            "page": {"type": ["integer", "null"]},
                            "quote": {"type": ["string", "null"]}
                        },
                        "required": ["value", "page", "quote"]
                    },
                    "duration_days": {
                        "type": "object",
                        "properties": {
                            "value": {"type": ["integer", "null"]},
                            "page": {"type": ["integer", "null"]},
                            "quote": {"type": ["string", "null"]}
                        },
                        "required": ["value", "page", "quote"]
                    },
                    "cost_inr": {
                        "type": "object",
                        "properties": {
                            "value": {"type": ["number", "null"]},
                            "page": {"type": ["integer", "null"]},
                            "quote": {"type": ["string", "null"]}
                        },
                        "required": ["value", "page", "quote"]
                    }
                },
                "required": ["agency", "work_type", "road_name", "excavation_required"]
            }
        }
    }
}


def build_prompt(pages: list[dict]) -> str:
    """Combines page text with explicit page markers."""
    doc_content = []
    for p in pages:
        doc_content.append(f"--- PAGE {p['page']} ---\n{p['text']}")

    joined_doc = "\n\n".join(doc_content)

    return f"""You are a municipal procurement auditor. Extract project information from this tender document.

CRITICAL INSTRUCTIONS:
1. For every field, provide "value", the 1-based "page" number where it was found, and the exact short "quote" from that page.
2. If a field cannot be found, set value: null, page: null, quote: null. NEVER guess.
3. Date format must be YYYY-MM-DD.
4. If work includes trenching, laying underground pipes, cables, or drains, set excavation_required.value = true.
5. If only duration (e.g., '6 months') is mentioned without a specific end date, extract duration_days (convert to days, e.g. 180) and set end_date.value = null.

DOCUMENT:
{joined_doc}"""


def extract_project_data(bedrock_client, pages: list[dict], model_id: str = "anthropic.claude-3-haiku-20240307-v1:0") -> dict:
    """
    Sends document text to Bedrock, parses tool response, and runs evidence verification.
    """
    prompt = build_prompt(pages)
    pages_by_number = {p["page"]: p["text"] for p in pages}

    response = bedrock_client.converse(
        modelId=model_id,
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={"temperature": 0.0},
        toolConfig={"tools": [EXTRACTION_TOOL]}
    )

    # Extract the tool output from response
    raw_extraction = None
    output_message = response.get("output", {}).get("message", {})
    for content_block in output_message.get("content", []):
        if "toolUse" in content_block and content_block["toolUse"]["name"] == "extract_infrastructure_tender":
            raw_extraction = content_block["toolUse"]["input"]
            break

    if not raw_extraction:
        return {
            "status": "FAILED",
            "error": "Model did not return structured tool output."
        }

    # Verify all evidence deterministically
    verified_data = {}
    for field_name, field_dict in raw_extraction.items():
        verified_data[field_name] = verify_extraction_field(field_dict, pages_by_number)

    verified_data["status"] = "EXTRACTED"
    return verified_data
