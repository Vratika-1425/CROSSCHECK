"""S3 Event-triggered Lambda Handler for Tender Extraction and Conflict Detection."""

import os
import json
import urllib.parse
from decimal import Decimal
import boto3

from .pdf_reader import read_pdf_from_s3
from .bedrock_client import extract_project_data
from ..core.gazetteer import Gazetteer
from ..core.collision import compute_all_conflicts

s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")
bedrock = boto3.client("bedrock-runtime")

PROJECTS_TABLE_NAME = os.environ.get("PROJECTS_TABLE", "ProjectsTable")
CONFLICTS_TABLE_NAME = os.environ.get("CONFLICTS_TABLE", "ConflictsTable")

gazetteer = Gazetteer()


def convert_floats_to_decimal(obj):
    """Recursively converts all float values in a dict/list to Decimal for DynamoDB compatibility."""
    if isinstance(obj, list):
        return [convert_floats_to_decimal(i) for i in obj]
    elif isinstance(obj, dict):
        return {k: convert_floats_to_decimal(v) for k, v in obj.items()}
    elif isinstance(obj, float):
        return Decimal(str(obj))
    return obj


def handler(event, context):
    """Entry point for S3 ObjectCreated events."""
    print("Received event:", json.dumps(event))

    projects_table = dynamodb.Table(PROJECTS_TABLE_NAME)
    conflicts_table = dynamodb.Table(CONFLICTS_TABLE_NAME)

    for record in event.get("Records", []):
        bucket = record["s3"]["bucket"]["name"]
        raw_key = record["s3"]["object"]["key"]
        key = urllib.parse.unquote_plus(raw_key)

        print(f"Processing PDF from s3://{bucket}/{key}")
        doc_id = key.split("/")[-1].replace(".pdf", "")

        try:
            # 1. Read PDF Pages
            pages = read_pdf_from_s3(s3, bucket, key)
            if not pages:
                raise ValueError("PDF contains no readable pages.")

            # 2. Extract structured fields via Bedrock
            extraction = extract_project_data(bedrock, pages)
            if extraction.get("status") == "FAILED":
                raise ValueError(f"Bedrock extraction failed: {extraction.get('error')}")

            # 3. Resolve road name against Gazetteer
            raw_road = extraction.get("road_name", {}).get("value")
            matched_road_id = gazetteer.match_road(raw_road) if raw_road else None

            # Determine overall project status
            status = "EXTRACTED"
            if not matched_road_id or not extraction.get("start_date", {}).get("value"):
                status = "NEEDS_REVIEW"

            # Flatten project item for DynamoDB
            project_item = {
                "projectId": doc_id,
                "documentId": doc_id,
                "s3_key": key,
                "s3_bucket": bucket,
                "title": extraction.get("title", {}).get("value") or f"Tender {doc_id[:8]}",
                "agency": extraction.get("agency", {}).get("value") or "Unknown Agency",
                "work_order_id": extraction.get("work_order_id", {}).get("value"),
                "work_type": extraction.get("work_type", {}).get("value") or "other",
                "excavation_required": bool(extraction.get("excavation_required", {}).get("value", False)),
                "road_name": raw_road,
                "road_id": matched_road_id,
                "start_date": extraction.get("start_date", {}).get("value"),
                "end_date": extraction.get("end_date", {}).get("value"),
                "duration_days": extraction.get("duration_days", {}).get("value"),
                "cost_inr": extraction.get("cost_inr", {}).get("value") or 0.0,
                "status": status,
                "evidence": extraction,  # Contains page citations & verbatim quotes
            }

            # 4. Save/Update project in DynamoDB
            projects_table.put_item(Item=convert_floats_to_decimal(project_item))
            print(f"Saved project {doc_id} with status: {status}")

            # 5. Recompute all conflicts across all extracted projects
            all_projects = projects_table.scan().get("Items", [])
            
            # Convert Decimals back to floats for math
            def decimal_to_python(item):
                if isinstance(item, list):
                    return [decimal_to_python(i) for i in item]
                elif isinstance(item, dict):
                    return {k: decimal_to_python(v) for k, v in item.items()}
                elif isinstance(item, Decimal):
                    return float(item)
                return item

            clean_projects = [decimal_to_python(p) for p in all_projects]
            conflicts, total_at_risk = compute_all_conflicts(clean_projects, gazetteer)

            # 6. Save updated conflicts to DynamoDB
            for conf in conflicts:
                conflicts_table.put_item(Item=convert_floats_to_decimal(conf))

            print(f"Recomputed {len(conflicts)} conflicts. Total expenditure exposed: ₹{total_at_risk:,.2f}")

        except Exception as e:
            print(f"Error processing {key}: {str(e)}")
            projects_table.put_item(
                Item={
                    "projectId": doc_id,
                    "documentId": doc_id,
                    "s3_key": key,
                    "status": "FAILED",
                    "error_message": str(e)
                }
            )

    return {"statusCode": 200, "body": "Extraction pipeline completed successfully."}
