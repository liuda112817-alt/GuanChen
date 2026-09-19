from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from guanchen_v2.api.app import create_app
from guanchen_v2.api.contracts import ChatResponse, ChatStatus
from guanchen_v2.api.errors import APIApplicationError
from guanchen_v2.memory.implementations.inmemory import InMemoryMemoryStore


@pytest.fixture
def client():
    mock_service = AsyncMock()
    app = create_app(chat_service=mock_service, session_store=InMemoryMemoryStore())
    return TestClient(app), mock_service


def test_chat_valid_request(client):
    test_client, mock_service = client
    mock_service.chat.return_value = ChatResponse(session_id="123", status=ChatStatus.ANSWERED, content="Hello")

    resp = test_client.post("/api/v1/chat", json={"message": "hi"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "answered"


def test_chat_empty_message(client):
    test_client, _ = client
    resp = test_client.post("/api/v1/chat", json={"message": "   "})
    assert resp.status_code == 422
    assert resp.json()["code"] == "INVALID_REQUEST"


def test_chat_unknown_field(client):
    test_client, _ = client
    resp = test_client.post("/api/v1/chat", json={"message": "hi", "invalid_field": True})
    assert resp.status_code == 422
    assert resp.json()["code"] == "INVALID_REQUEST"


def test_chat_runtime_error(client):
    test_client, mock_service = client
    mock_service.chat.side_effect = APIApplicationError(code="RUNTIME_ERROR", message="Error", trace_id="trace1")

    resp = test_client.post("/api/v1/chat", json={"message": "hi"})
    assert resp.status_code == 500
    data = resp.json()
    assert data["code"] == "RUNTIME_ERROR"
    assert data["trace_id"] == "trace1"
