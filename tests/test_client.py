"""Tests for the narrow asynchronous Hermes HTTP client."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import aiohttp
import pytest

from custom_components.hermes_conversation.client import (
    HermesClient,
    HermesClientError,
    HermesIndeterminateError,
    HermesProtocolError,
)


class FakeContent:
    def __init__(self, body: bytes, *, block: asyncio.Event | None = None) -> None:
        self._body = body
        self._sent = False
        self._block = block

    async def iter_chunked(self, size: int) -> Any:
        del size
        if self._block is not None:
            await self._block.wait()
        if not self._sent:
            self._sent = True
            yield self._body


class FakeResponse:
    def __init__(
        self,
        payload: object = None,
        *,
        status: int = 200,
        content_type: str = "application/json",
        raw: bytes | None = None,
        block: asyncio.Event | None = None,
    ) -> None:
        self.status = status
        self.headers = {"Content-Type": content_type}
        body = json.dumps(payload).encode() if raw is None else raw
        self.content = FakeContent(body, block=block)

    async def __aenter__(self) -> FakeResponse:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None


class FakeSession:
    def __init__(self, responses: list[FakeResponse | BaseException]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, str, dict[str, Any]]] = []

    def request(self, method: str, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append((method, url, kwargs))
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response


def health() -> dict[str, object]:
    return {"status": "ok", "platform": "hermes-agent", "version": "0.18.2"}


def capabilities() -> dict[str, object]:
    return {
        "object": "hermes.api_server.capabilities",
        "model": "fixture-model",
        "auth": {"type": "bearer", "required": True},
        "features": {"responses_api": True},
        "endpoints": {"responses": {"method": "POST", "path": "/v1/responses"}},
    }


def completed_response(text: str = "safe status") -> dict[str, object]:
    return {
        "id": "resp_1",
        "object": "response",
        "created_at": 1,
        "status": "completed",
        "model": "fixture-model",
        "output": [
            {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": text}],
            }
        ],
        "usage": {"input_tokens": 1, "output_tokens": 2, "total_tokens": 3},
    }


@pytest.mark.parametrize(
    "url",
    [
        "http://hermes.invalid",
        "ftp://hermes.invalid",
        "https://user:secret@hermes.invalid",
        "https://hermes.invalid?token=secret",
        "https://hermes.invalid#fragment",
        "https://hermes.invalid/api",
        "https://hermes.invalid//",
        "https://hermes.invalid/../api",
        "https://hermes.invalid/%2fapi",
    ],
)
def test_rejects_unsafe_base_urls(url: str) -> None:
    with pytest.raises(ValueError, match="base URL"):
        HermesClient(FakeSession([]), url, "secret")  # type: ignore[arg-type]


def test_http_requires_explicit_opt_in() -> None:
    client = HermesClient(
        FakeSession([]),  # type: ignore[arg-type]
        "http://127.0.0.1:8080/",
        "secret",
        allow_insecure_http=True,
    )
    assert client.base_url == "http://127.0.0.1:8080"


def test_rejects_empty_or_header_injecting_token() -> None:
    for token in ("", "token\r\nX-Evil: yes"):
        with pytest.raises(ValueError, match="token"):
            HermesClient(FakeSession([]), "https://hermes.invalid", token)  # type: ignore[arg-type]


async def test_fixed_endpoints_auth_headers_and_allowlisted_body() -> None:
    session = FakeSession(
        [FakeResponse(health()), FakeResponse(capabilities()), FakeResponse(completed_response())]
    )
    client = HermesClient(session, "https://hermes.invalid", "fixture-secret")  # type: ignore[arg-type]

    health_result = await client.async_health()
    capabilities_result = await client.async_capabilities()
    response = await client.async_respond(
        model=capabilities_result.model,
        utterance="Is the kitchen light on?",
        conversation="opaque-conversation",
    )

    assert health_result.version == "0.18.2"
    assert response.text == "safe status"
    assert [call[:2] for call in session.calls] == [
        ("GET", "https://hermes.invalid/health"),
        ("GET", "https://hermes.invalid/v1/capabilities"),
        ("POST", "https://hermes.invalid/v1/responses"),
    ]
    assert "Authorization" not in session.calls[0][2]["headers"]
    assert session.calls[1][2]["headers"]["Authorization"] == "Bearer fixture-secret"
    request = session.calls[2][2]
    assert request["allow_redirects"] is False
    assert json.loads(request["data"]) == {
        "model": "fixture-model",
        "input": "Is the kitchen light on?",
        "conversation": "opaque-conversation",
        "stream": False,
    }
    assert set(json.loads(request["data"])) == {"model", "input", "conversation", "stream"}
    assert request["headers"]["Content-Type"] == "application/json"
    assert isinstance(request["timeout"], aiohttp.ClientTimeout)
    assert request["timeout"].connect is not None
    assert request["timeout"].total is not None


@pytest.mark.parametrize("status", [301, 302, 307, 308])
async def test_rejects_redirects_without_following(status: int) -> None:
    session = FakeSession([FakeResponse({}, status=status)])
    client = HermesClient(session, "https://hermes.invalid", "secret")  # type: ignore[arg-type]
    with pytest.raises(HermesProtocolError, match=f"HTTP {status}"):
        await client.async_capabilities()
    assert len(session.calls) == 1
    assert session.calls[0][2]["allow_redirects"] is False


@pytest.mark.parametrize(
    ("response", "message"),
    [
        (FakeResponse({}, content_type="text/plain"), "content type"),
        (FakeResponse(raw=b"not json"), "malformed JSON"),
        (FakeResponse([]), "JSON root"),
        (FakeResponse({"object": "wrong"}), "capabilities"),
        (FakeResponse(capabilities() | {"features": {}}), "responses_api"),
    ],
)
async def test_rejects_invalid_content_and_capability_schema(
    response: FakeResponse, message: str
) -> None:
    client = HermesClient(FakeSession([response]), "https://hermes.invalid", "secret")  # type: ignore[arg-type]
    with pytest.raises(HermesProtocolError, match=message):
        await client.async_capabilities()


async def test_rejects_oversized_response_without_parsing_it() -> None:
    client = HermesClient(
        FakeSession([FakeResponse(raw=b"x" * 33)]),  # type: ignore[arg-type]
        "https://hermes.invalid",
        "secret",
        max_response_bytes=32,
    )
    with pytest.raises(HermesProtocolError, match="exceeds 32 bytes"):
        await client.async_health()


async def test_rejects_invalid_response_schema_and_excessive_output() -> None:
    invalid = completed_response() | {"output": [{"type": "tool_call"}]}
    long = completed_response("x" * 9)
    for payload, message in ((invalid, "assistant messages"), (long, "output exceeds")):
        client = HermesClient(
            FakeSession([FakeResponse(payload)]),  # type: ignore[arg-type]
            "https://hermes.invalid",
            "secret",
            max_output_chars=8,
        )
        with pytest.raises(HermesProtocolError, match=message):
            await client.async_respond(model="fixture-model", utterance="status", conversation="c")


async def test_bounds_request_fields_before_dispatch() -> None:
    session = FakeSession([])
    client = HermesClient(session, "https://hermes.invalid", "secret", max_utterance_chars=4)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="utterance"):
        await client.async_respond(model="model", utterance="12345", conversation="c")
    assert session.calls == []


async def test_response_api_exposes_no_tools_or_actions() -> None:
    client = HermesClient(FakeSession([]), "https://hermes.invalid", "secret")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        await client.async_respond(  # type: ignore[call-arg]
            model="model", utterance="status", conversation="c", tools=[]
        )


async def test_timeout_is_indeterminate_and_never_retried() -> None:
    session = FakeSession([TimeoutError()])
    client = HermesClient(session, "https://hermes.invalid", "secret")  # type: ignore[arg-type]
    with pytest.raises(HermesIndeterminateError, match="outcome may be unknown"):
        await client.async_respond(model="model", utterance="status", conversation="c")
    assert len(session.calls) == 1


async def test_post_disconnect_is_indeterminate_and_never_retried() -> None:
    session = FakeSession([aiohttp.ServerDisconnectedError()])
    client = HermesClient(session, "https://hermes.invalid", "secret")  # type: ignore[arg-type]
    with pytest.raises(HermesIndeterminateError, match="outcome may be unknown"):
        await client.async_respond(model="model", utterance="status", conversation="c")
    assert len(session.calls) == 1


async def test_transport_errors_and_exception_text_do_not_leak_token_or_url() -> None:
    token = "-".join(("super", "secret", "token"))
    session = FakeSession([aiohttp.ClientError(f"failed with {token} at private host")])
    client = HermesClient(session, "https://private.invalid", token)  # type: ignore[arg-type]
    with pytest.raises(HermesClientError) as raised:
        await client.async_capabilities()
    text = str(raised.value)
    assert token not in text
    assert "private.invalid" not in text


async def test_cancellation_propagates() -> None:
    block = asyncio.Event()
    session = FakeSession([FakeResponse(health(), block=block)])
    client = HermesClient(session, "https://hermes.invalid", "secret")  # type: ignore[arg-type]
    task = asyncio.create_task(client.async_health())
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert len(session.calls) == 1
