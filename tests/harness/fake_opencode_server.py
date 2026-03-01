"""In-process ASGI fake OpenCode server for contract/integration tests."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

import httpx

from jarvis.opencode_client import OpenCodeClient


@dataclass(frozen=True)
class RouteFailure:
    """Configured route failure response."""

    status_code: int
    body: str


class FakeOpenCodeServer:
    """Minimal OpenCode API stub with JSON + SSE endpoints."""

    def __init__(self) -> None:
        self.created_sessions: list[str] = []
        self.message_payloads: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.prompt_payloads: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.command_payloads: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.question_replies: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.permission_replies: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.message_history: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.message_response: dict[str, Any] = {
            "parts": [{"type": "text", "text": "ok"}],
            "info": {"modelID": "gpt-4o", "providerID": "openai", "agent": "default"},
        }
        self.prompt_async_status_code = 204
        self.route_failures: dict[tuple[str, str], RouteFailure] = {}
        self._session_index = 0
        self._sse_chunks: list[bytes] = []

    @property
    def app(self) -> Any:
        """Expose ASGI callable."""
        return self._asgi_app

    def set_failure(self, method: str, path: str, status_code: int, body: str) -> None:
        """Configure route-level failure response."""
        self.route_failures[(method.upper(), path)] = RouteFailure(
            status_code=status_code, body=body
        )

    def queue_sse_events(self, blocks: list[str]) -> None:
        """Set raw SSE blocks to emit from /event endpoint."""
        payload = "\n\n".join(block.rstrip("\n") for block in blocks)
        payload = f"{payload}\n\n" if payload else ""
        self._sse_chunks = [payload.encode("utf-8")]

    def queue_sse_chunks(self, chunks: list[str]) -> None:
        """Set SSE response chunks to simulate chunked transfer."""
        self._sse_chunks = [chunk.encode("utf-8") for chunk in chunks]

    async def _asgi_app(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            return

        method = str(scope.get("method", "")).upper()
        path = str(scope.get("path", ""))

        failure = self.route_failures.get((method, path))
        if failure is not None:
            await self._send_text(send, failure.status_code, failure.body)
            return

        if method == "GET" and path == "/global/health":
            await self._send_json(send, 200, {"healthy": True, "version": "test"})
            return

        if method == "POST" and path == "/session":
            self._session_index += 1
            session_id = f"sess-{self._session_index}"
            self.created_sessions.append(session_id)
            await self._send_json(send, 200, {"id": session_id})
            return

        message_match = re.fullmatch(r"/session/([^/]+)/message", path)
        if method == "POST" and message_match:
            session_id = message_match.group(1)
            payload = await self._read_json_body(receive)
            self.message_payloads[session_id].append(payload)
            await self._send_json(send, 200, self.message_response)
            return

        command_match = re.fullmatch(r"/session/([^/]+)/command", path)
        if method == "POST" and command_match:
            session_id = command_match.group(1)
            payload = await self._read_json_body(receive)
            self.command_payloads[session_id].append(payload)
            await self._send_json(send, 200, self.message_response)
            return

        prompt_match = re.fullmatch(r"/session/([^/]+)/prompt_async", path)
        if method == "POST" and prompt_match:
            session_id = prompt_match.group(1)
            payload = await self._read_json_body(receive)
            self.prompt_payloads[session_id].append(payload)
            if self.prompt_async_status_code == 204:
                await self._send_empty(send, 204)
            else:
                await self._send_text(send, self.prompt_async_status_code, "prompt_async_failed")
            return

        messages_match = re.fullmatch(r"/session/([^/]+)/message", path)
        if method == "GET" and messages_match:
            session_id = messages_match.group(1)
            await self._send_json(send, 200, self.message_history.get(session_id, []))
            return

        question_reply_match = re.fullmatch(r"/question/([^/]+)/reply", path)
        if method == "POST" and question_reply_match:
            request_id = question_reply_match.group(1)
            self.question_replies[request_id].append(await self._read_json_body(receive))
            await self._send_json(send, 200, True)
            return

        question_reject_match = re.fullmatch(r"/question/([^/]+)/reject", path)
        if method == "POST" and question_reject_match:
            await self._send_json(send, 200, True)
            return

        permission_reply_match = re.fullmatch(r"/permission/([^/]+)/reply", path)
        if method == "POST" and permission_reply_match:
            request_id = permission_reply_match.group(1)
            self.permission_replies[request_id].append(await self._read_json_body(receive))
            await self._send_json(send, 200, True)
            return

        if method == "GET" and path == "/event":
            await self._send_sse(send)
            return

        await self._send_text(send, 404, "not found")

    async def _send_sse(self, send: Any) -> None:
        headers = [(b"content-type", b"text/event-stream")]
        await send({"type": "http.response.start", "status": 200, "headers": headers})
        chunks = self._sse_chunks or [b""]
        for index, chunk in enumerate(chunks):
            await send(
                {
                    "type": "http.response.body",
                    "body": chunk,
                    "more_body": index < len(chunks) - 1,
                }
            )

    @staticmethod
    async def _read_json_body(receive: Any) -> dict[str, Any]:
        body = b""
        while True:
            message = await receive()
            body += message.get("body", b"")
            if not message.get("more_body", False):
                break
        if not body:
            return {}
        parsed = json.loads(body.decode("utf-8"))
        return parsed if isinstance(parsed, dict) else {}

    @staticmethod
    async def _send_empty(send: Any, status_code: int) -> None:
        await send({"type": "http.response.start", "status": status_code, "headers": []})
        await send({"type": "http.response.body", "body": b"", "more_body": False})

    @staticmethod
    async def _send_text(send: Any, status_code: int, text: str) -> None:
        headers = [(b"content-type", b"text/plain; charset=utf-8")]
        await send({"type": "http.response.start", "status": status_code, "headers": headers})
        await send(
            {
                "type": "http.response.body",
                "body": text.encode("utf-8"),
                "more_body": False,
            }
        )

    @staticmethod
    async def _send_json(send: Any, status_code: int, payload: Any) -> None:
        headers = [(b"content-type", b"application/json")]
        body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        await send({"type": "http.response.start", "status": status_code, "headers": headers})
        await send({"type": "http.response.body", "body": body, "more_body": False})


async def build_opencode_client(server: FakeOpenCodeServer) -> OpenCodeClient:
    """Create OpenCodeClient bound to in-process fake server."""
    client = OpenCodeClient("http://opencode.test", "test_password")
    await client.client.aclose()
    client.client = httpx.AsyncClient(
        auth=client.auth,
        base_url="http://opencode.test",
        transport=httpx.ASGITransport(app=server.app),
        timeout=60.0,
    )
    return client
