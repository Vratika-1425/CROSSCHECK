"""Single-entry API Lambda handler for all CROSSCHECK REST endpoints."""

import os
import json
import uuid
import urllib.parse
import boto3
from decimal import Decimal

REGION = os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "us-east-1"))

s3 = boto3.client("s3", region_name=REGION)
dynamodb = boto3.resource("dynamodb", region_name=REGION)

PROJECTS_TABLE_NAME = os.environ.get("PROJECTS_TABLE", "ProjectsTable")
CONFLICTS_TABLE_NAME = os.environ.get("CONFLICTS_TABLE", "ConflictsTable")
BUCKET_NAME = os.environ.get("UPLOAD_BUCKET", "crosscheck-uploads")

projects_table = dynamodb.Table(PROJECTS_TABLE_NAME)
conflicts_table = dynamodb.Table(CONFLICTS_TABLE_NAME)


def decimal_to_python(obj):
    """Recursively convert Decimal to float/int for JSON serialization."""
    if isinstance(obj, list):
        return [decimal_to_python(i) for i in obj]
    elif isinstance(obj, dict):
        return {k: decimal_to_python(v) for k, v in obj.items()}
    elif isinstance(obj, Decimal):
        return float(obj)
    return obj


def _json_response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
            "Access-Control-Allow-Methods": "OPTIONS,POST,GET"
        },
        "body": json.dumps(body)
    }


def _get_path(event):
    """Extract the path from API Gateway v2 or v1 event."""
    raw_path = event.get("path") or "/"
    decoded = urllib.parse.unquote(raw_path)
    return decoded


def _presigned_upload():
    doc_id = str(uuid.uuid4())
    key = f"uploads/{doc_id}.pdf"

    url = s3.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": BUCKET_NAME,
            "Key": key,
            "ContentType": "application/pdf"
        },
        ExpiresIn=300
    )

    return _json_response(200, {
        "uploadUrl": url,
        "documentId": doc_id,
        "key": key
    })


def _get_projects():
    result = projects_table.scan()
    items = result.get("Items", [])

    items = sorted(items, key=lambda x: str(x.get("start_date") or "9999-99-99"), reverse=True)

    return _json_response(200, {
        "projects": decimal_to_python(items)
    })


def _get_conflicts():
    result = conflicts_table.scan()
    items = result.get("Items", [])

    risk_order = {"HIGH": 0, "POTENTIAL": 1}
    items = sorted(
        items,
        key=lambda x: (risk_order.get(x.get("risk_level", ""), 99), x.get("window_start", "")),
        reverse=False
    )

    high_risk = [c for c in items if c.get("risk_level") == "HIGH"]

    return _json_response(200, {
        "conflicts": decimal_to_python(items),
        "total_expenditure_at_risk_inr": decimal_to_python(high_risk)
    })


def _get_conflict(conflict_id):
    result = conflicts_table.get_item(Key={"conflictId": conflict_id})
    if "Item" not in result:
        return _json_response(404, {"error": "Conflict not found"})

    return _json_response(200, decimal_to_python(result["Item"]))


def _get_document_url(document_id):
    key = f"uploads/{document_id}.pdf"

    url = s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": BUCKET_NAME, "Key": key},
        ExpiresIn=300
    )

    return _json_response(200, {
        "url": url,
        "documentId": document_id
    })


def handler(event, context):
    """Main entry point for API Gateway events."""

    method = event.get("httpMethod", "GET")
    path = _get_path(event)

    print(f"API Request: {method} {path}")

    if method == "OPTIONS":
        return _json_response(200, {"message": "CORS preflight OK"})

    if method == "POST" and path == "/uploads":
        return _presigned_upload()

    if method == "GET" and path == "/projects":
        return _get_projects()

    if method == "GET" and path == "/conflicts":
        return _get_conflicts()

    if method == "GET" and path.startswith("/conflicts/"):
        conflict_id = path.split("/")[-1]
        return _get_conflict(conflict_id)

    if method == "GET" and path.startswith("/documents/") and path.endswith("/url"):
        parts = path.rstrip("/").split("/")
        document_id = parts[-2]
        return _get_document_url(document_id)

    return _json_response(404, {"error": "Route not found"})
