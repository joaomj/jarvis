"""Tests for QMD client."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from jarvis.qmd_client import QMDClient


@pytest.fixture
def mock_httpx_client():
    client = AsyncMock()
    return client


@pytest.fixture
def qmd_client(mock_httpx_client):
    with patch("httpx.AsyncClient", return_value=mock_httpx_client):
        client = QMDClient(base_url="http://localhost:8181", timeout=30.0)
        client._client = mock_httpx_client
        return client


class TestQMDClient:
    """Test QMD client functionality."""

    @pytest.mark.asyncio
    async def test_search_success(self, qmd_client, mock_httpx_client):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": '[{"docid": "abc123", "title": "Test Doc", "score": 0.85, "displayPath": "test.md", "snippet": "Test snippet"}]',
                    }
                ],
            },
        }
        mock_httpx_client.post.return_value = mock_response

        results = await qmd_client.search("test query", limit=5)

        assert len(results) == 1
        assert results[0].docid == "abc123"
        assert results[0].title == "Test Doc"
        assert results[0].score == 0.85

    @pytest.mark.asyncio
    async def test_search_empty_results(self, qmd_client, mock_httpx_client):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {"content": [{"type": "text", "text": "[]"}]},
        }
        mock_httpx_client.post.return_value = mock_response

        results = await qmd_client.search("test query", limit=5)

        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_search_with_error(self, qmd_client, mock_httpx_client):
        mock_httpx_client.post.side_effect = httpx.HTTPStatusError(
            "500",
            request=MagicMock(),
            response=MagicMock(),
        )

        results = await qmd_client.search("test query", limit=5)

        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_get_document_success(self, qmd_client, mock_httpx_client):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": '{"docid": "abc123", "title": "Test", "displayPath": "test.md", "body": "Full content"}',
                    }
                ],
            },
        }
        mock_httpx_client.post.return_value = mock_response

        doc = await qmd_client.get("abc123")

        assert doc is not None
        assert doc.docid == "abc123"
        assert doc.title == "Test"
        assert doc.body == "Full content"

    @pytest.mark.asyncio
    async def test_get_document_not_found(self, qmd_client, mock_httpx_client):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {"content": [{"type": "text", "text": '{"error": "not found"}'}]},
        }
        mock_httpx_client.post.return_value = mock_response

        doc = await qmd_client.get("nonexistent")

        assert doc is None

    @pytest.mark.asyncio
    async def test_status_healthy(self, qmd_client, mock_httpx_client):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "collections": 1,
            "documents": 42,
            "uptime": 3600.5,
        }
        mock_httpx_client.get.return_value = mock_response

        status = await qmd_client.status()

        assert status.healthy
        assert status.collections == 1
        assert status.documents == 42
        assert status.uptime_seconds == 3600.5

    @pytest.mark.asyncio
    async def test_status_unhealthy(self, qmd_client, mock_httpx_client):
        mock_httpx_client.get.side_effect = httpx.RequestError("Connection error")

        status = await qmd_client.status()

        assert not status.healthy
        assert status.collections == 0
        assert status.documents == 0

    @pytest.mark.asyncio
    async def test_close_client(self, qmd_client, mock_httpx_client):
        await qmd_client.close()
        mock_httpx_client.aclose.assert_called_once()
