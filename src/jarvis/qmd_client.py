"""QMD (Query Markup Documents) MCP HTTP client.

Provides hybrid search (BM25 + vector + LLM reranking) via QMD's MCP HTTP server.
https://github.com/tobi/qmd
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from jarvis.logging_config import get_logger

logger = get_logger(__name__)

MCP_PROTOCOL_VERSION = "2025-03-26"


@dataclass(frozen=True)
class QMDResult:
    """A single search result from QMD."""

    docid: str
    title: str
    score: float
    display_path: str
    context: str | None
    snippet: str


@dataclass(frozen=True)
class QMDDocument:
    """A full document retrieved from QMD."""

    docid: str
    title: str
    display_path: str
    context: str | None
    body: str


@dataclass(frozen=True)
class QMDStatus:
    """QMD server status."""

    healthy: bool
    collections: int
    documents: int
    uptime_seconds: float | None = None


class QMDError(Exception):
    """QMD client error."""

    def __init__(self, message: str, code: int | None = None) -> None:
        super().__init__(message)
        self.code = code


class QMDClient:
    """HTTP client for QMD MCP server.

    Communicates with QMD's MCP HTTP endpoint using JSON-RPC 2.0.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8181",
        timeout: float = 30.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._mcp_endpoint = f"{self._base_url}/mcp"
        self._health_endpoint = f"{self._base_url}/health"
        self._timeout = timeout
        self._client = httpx.AsyncClient(
            timeout=timeout,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
                "MCP-Protocol-Version": MCP_PROTOCOL_VERSION,
            },
        )
        self._request_id = 0

    def _next_request_id(self) -> int:
        self._request_id += 1
        return self._request_id

    async def _call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        """Call an MCP tool and return the result."""
        request_id = self._next_request_id()
        payload = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {
                "name": name,
                "arguments": arguments,
            },
        }

        try:
            response = await self._client.post(self._mcp_endpoint, json=payload)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as e:
            raise QMDError(f"HTTP error: {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise QMDError(f"Request error: {e}") from e
        except ValueError as e:
            raise QMDError(f"Invalid JSON response: {e}") from e

        if "error" in data:
            error = data["error"]
            raise QMDError(
                error.get("message", "Unknown error"),
                code=error.get("code"),
            )

        result = data.get("result", {})
        content = result.get("content", [])

        if not content:
            return None

        text_content = content[0].get("text", "")
        if not text_content:
            return None

        try:
            return __import__("json").loads(text_content)
        except (ValueError, TypeError):
            return text_content

    async def search(
        self,
        query: str,
        *,
        limit: int = 5,
        min_score: float = 0.0,
        collection: str | None = None,
    ) -> list[QMDResult]:
        """Search vault content using QMD hybrid search.

        Args:
            query: Search query string
            limit: Maximum number of results
            min_score: Minimum score threshold (0.0-1.0)
            collection: Optional collection name to restrict search

        Returns:
            List of QMDResult objects
        """
        arguments: dict[str, Any] = {
            "query": query,
            "limit": limit,
        }
        if min_score > 0:
            arguments["minScore"] = min_score
        if collection:
            arguments["collection"] = collection

        try:
            results = await self._call_tool("query", arguments)
        except QMDError as e:
            logger.warning("qmd_search_failed", error=str(e), query=query[:50])
            return []

        if not results or not isinstance(results, list):
            return []

        parsed: list[QMDResult] = []
        for item in results:
            if not isinstance(item, dict):
                continue
            parsed.append(
                QMDResult(
                    docid=item.get("docid", ""),
                    title=item.get("title", ""),
                    score=float(item.get("score", 0.0)),
                    display_path=item.get("displayPath", item.get("display_path", "")),
                    context=item.get("context"),
                    snippet=item.get("snippet", ""),
                )
            )

        logger.info(
            "qmd_search_complete",
            query=query[:50],
            results=len(parsed),
            top_score=parsed[0].score if parsed else 0,
        )
        return parsed

    async def get(self, docid: str) -> QMDDocument | None:
        """Retrieve a document by docid or path.

        Args:
            docid: Document ID or path

        Returns:
            QMDDocument if found, None otherwise
        """
        try:
            result = await self._call_tool("get", {"path": docid})
        except QMDError as e:
            logger.warning("qmd_get_failed", error=str(e), docid=docid)
            return None

        if not result or not isinstance(result, dict):
            return None

        if "error" in result:
            return None

        return QMDDocument(
            docid=result.get("docid", ""),
            title=result.get("title", ""),
            display_path=result.get("displayPath", result.get("display_path", "")),
            context=result.get("context"),
            body=result.get("body", ""),
        )

    async def status(self) -> QMDStatus:
        """Check QMD server health and index status.

        Returns:
            QMDStatus with health info
        """
        try:
            response = await self._client.get(self._health_endpoint)
            if response.status_code == httpx.codes.OK:
                data = response.json()
                return QMDStatus(
                    healthy=True,
                    collections=data.get("collections", 0),
                    documents=data.get("documents", 0),
                    uptime_seconds=data.get("uptime"),
                )
        except Exception as e:
            logger.warning("qmd_health_check_failed", error=str(e))

        return QMDStatus(
            healthy=False,
            collections=0,
            documents=0,
        )

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

    async def __aenter__(self) -> QMDClient:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()
