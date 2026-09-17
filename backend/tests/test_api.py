import json
from unittest.mock import patch, MagicMock
import backend.src.api.handler as api_handler


def test_presigned_upload():
    mock_url = "https://s3.amazonaws.com/mock-upload-url?signature=xyz"
    
    with patch.object(api_handler.s3, "generate_presigned_url", return_value=mock_url):
        response = api_handler.handler(
            {"httpMethod": "POST", "path": "/uploads"},
            MagicMock()
        )
    
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert "uploadUrl" in body
    assert "documentId" in body


def test_get_projects_empty():
    with patch.object(api_handler.projects_table, "scan", return_value={"Items": []}):
        response = api_handler.handler(
            {"httpMethod": "GET", "path": "/projects"},
            MagicMock()
        )
    
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["projects"] == []


def test_get_conflict_not_found():
    with patch.object(api_handler.conflicts_table, "get_item", return_value={}):
        response = api_handler.handler(
            {"httpMethod": "GET", "path": "/conflicts/CONF_123"},
            MagicMock()
        )
    
    assert response["statusCode"] == 404


def test_get_document_url():
    mock_url = "https://s3.amazonaws.com/mock-download-url?signature=abc"
    
    with patch.object(api_handler.s3, "generate_presigned_url", return_value=mock_url):
        response = api_handler.handler(
            {"httpMethod": "GET", "path": "/documents/doc123/url"},
            MagicMock()
        )
    
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert "url" in body
