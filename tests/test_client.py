"""Tests for the narrow asynchronous Hermes HTTP client."""

from __future__ import annotations

import asyncio
import json
import math
from typing import Any, cast

import aiohttp
import pytest
from aiohttp import web
from yarl import URL

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


@pytest.mark.parametrize(
    "url",
    [
        "http://192.168.1.10",
        "http://10.23.45.67:8080",
        "http://172.16.0.1",
        "http://169.254.10.20",
        "http://100.64.0.1",
        "http://hermes.local",
        "http://hermes.home.arpa",
        "http://node.tailnet-name.ts.net",
    ],
)
def test_http_opt_in_allows_only_explicit_local_private_hosts(url: str) -> None:
    assert HermesClient(FakeSession([]), url, "secret", allow_insecure_http=True).base_url == url  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com",
        "http://8.8.8.8",
        "http://100.128.0.1",
        "http://hermes.invalid",
        "http://notlocal",
    ],
)
def test_http_opt_in_rejects_public_or_unclassified_hosts(url: str) -> None:
    with pytest.raises(ValueError, match="local/private"):
        HermesClient(FakeSession([]), url, "secret", allow_insecure_http=True)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("connect_timeout", True),
        ("connect_timeout", math.inf),
        ("connect_timeout", math.nan),
        ("connect_timeout", 0),
        ("total_timeout", "30"),
        ("max_request_bytes", 1.5),
        ("max_response_bytes", False),
        ("max_utterance_chars", -1),
        ("max_output_chars", None),
    ],
)
def test_rejects_invalid_numeric_limits_and_timeouts(name: str, value: object) -> None:
    with pytest.raises(ValueError, match=name):
        HermesClient(FakeSession([]), "https://hermes.invalid", "secret", **{name: value})  # type: ignore[arg-type]


def test_rejects_empty_or_header_injecting_token() -> None:
    for token in ("", "token\r\nX-Evil: yes"):
        with pytest.raises(ValueError, match="token"):
            HermesClient(FakeSession([]), "https://hermes.invalid", token)  # type: ignore[arg-type]


async def test_fixed_endpoints_auth_headers_and_allowlisted_body() -> None:
    session = FakeSession(
        [
            FakeResponse(health()),
            FakeResponse(capabilities()),
            FakeResponse(capabilities()),
            FakeResponse(completed_response()),
        ]
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
        ("GET", "https://hermes.invalid/v1/capabilities"),
        ("POST", "https://hermes.invalid/v1/responses"),
    ]
    assert "Authorization" not in session.calls[0][2]["headers"]
    assert session.calls[1][2]["headers"]["Authorization"] == "Bearer fixture-secret"
    request = session.calls[3][2]
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
    for payload in (invalid, long):
        client = HermesClient(
            FakeSession([FakeResponse(capabilities()), FakeResponse(payload)]),  # type: ignore[arg-type]
            "https://hermes.invalid",
            "secret",
            max_output_chars=8,
        )
        with pytest.raises(HermesIndeterminateError, match="outcome may be unknown"):
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
    session = FakeSession([FakeResponse(capabilities()), TimeoutError()])
    client = HermesClient(session, "https://hermes.invalid", "secret")  # type: ignore[arg-type]
    with pytest.raises(HermesIndeterminateError, match="outcome may be unknown"):
        await client.async_respond(model="fixture-model", utterance="status", conversation="c")
    assert [call[0] for call in session.calls] == ["GET", "POST"]


async def test_post_disconnect_is_indeterminate_and_never_retried() -> None:
    session = FakeSession([FakeResponse(capabilities()), aiohttp.ServerDisconnectedError()])
    client = HermesClient(session, "https://hermes.invalid", "secret")  # type: ignore[arg-type]
    with pytest.raises(HermesIndeterminateError, match="outcome may be unknown"):
        await client.async_respond(model="fixture-model", utterance="status", conversation="c")
    assert [call[0] for call in session.calls] == ["GET", "POST"]


@pytest.mark.parametrize(
    "capability_response",
    [
        FakeResponse(capabilities() | {"features": {}}),
        FakeResponse({}, status=401),
        FakeResponse(raw=b"not json"),
    ],
)
async def test_capability_failure_prevents_post(capability_response: FakeResponse) -> None:
    session = FakeSession([capability_response])
    client = HermesClient(session, "https://hermes.invalid", "secret")  # type: ignore[arg-type]
    with pytest.raises(HermesClientError):
        await client.async_respond(model="fixture-model", utterance="status", conversation="c")
    assert [call[0] for call in session.calls] == ["GET"]


async def test_capability_model_mismatch_prevents_post() -> None:
    session = FakeSession([FakeResponse(capabilities())])
    client = HermesClient(session, "https://hermes.invalid", "secret")  # type: ignore[arg-type]
    with pytest.raises(HermesProtocolError, match="model"):
        await client.async_respond(model="different-model", utterance="status", conversation="c")
    assert [call[0] for call in session.calls] == ["GET"]


@pytest.mark.parametrize(
    "post_response",
    [
        FakeResponse({}, status=500),
        FakeResponse(raw=b"not json"),
        FakeResponse(raw=b"x" * 1_025),
        FakeResponse(completed_response() | {"output": [{"type": "tool_call"}]}),
    ],
)
async def test_post_failures_are_indeterminate_after_exactly_one_dispatch(
    post_response: FakeResponse,
) -> None:
    session = FakeSession([FakeResponse(capabilities()), post_response])
    client = HermesClient(
        session,  # type: ignore[arg-type]
        "https://hermes.invalid",
        "secret",
        max_response_bytes=1_024,
    )
    with pytest.raises(HermesIndeterminateError, match="outcome may be unknown"):
        await client.async_respond(model="fixture-model", utterance="status", conversation="c")
    assert [call[0] for call in session.calls] == ["GET", "POST"]


async def test_connect_timeout_before_post_dispatch_is_not_indeterminate() -> None:
    session = FakeSession([FakeResponse(capabilities()), aiohttp.ConnectionTimeoutError()])
    client = HermesClient(session, "https://hermes.invalid", "secret")  # type: ignore[arg-type]
    with pytest.raises(HermesClientError, match="connect") as raised:
        await client.async_respond(model="fixture-model", utterance="status", conversation="c")
    assert not isinstance(raised.value, HermesIndeterminateError)
    assert [call[0] for call in session.calls] == ["GET", "POST"]


async def test_post_cancellation_propagates_after_one_dispatch() -> None:
    block = asyncio.Event()
    session = FakeSession(
        [FakeResponse(capabilities()), FakeResponse(completed_response(), block=block)]
    )
    client = HermesClient(session, "https://hermes.invalid", "secret")  # type: ignore[arg-type]
    task = asyncio.create_task(
        client.async_respond(model="fixture-model", utterance="status", conversation="c")
    )
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert [call[0] for call in session.calls] == ["GET", "POST"]


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


async def test_real_aiohttp_redirect_does_not_forward_bearer_or_cookie(
    unused_tcp_port: int,
) -> None:
    captured: list[dict[str, str]] = []

    async def capabilities_redirect(request: web.Request) -> web.Response:
        captured.append(dict(request.headers))
        return web.Response(
            status=307,
            headers={"Location": "/capture", "Set-Cookie": "session=attacker"},
        )

    async def capture(request: web.Request) -> web.Response:
        captured.append(dict(request.headers))
        return web.json_response(capabilities())

    app = web.Application()
    app.router.add_get("/v1/capabilities", capabilities_redirect)
    app.router.add_get("/capture", capture)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", unused_tcp_port)
    await site.start()
    try:
        async with aiohttp.ClientSession() as session:
            client = HermesClient(
                session,
                f"http://127.0.0.1:{unused_tcp_port}",
                "fixture-secret",
                allow_insecure_http=True,
            )
            with pytest.raises(HermesProtocolError, match="HTTP 307"):
                await client.async_capabilities()
            assert len(captured) == 1
            assert "Cookie" not in captured[0] or captured[0]["Cookie"] == ""
    finally:
        await runner.cleanup()


async def test_real_aiohttp_refuses_shared_session_cookies_without_dispatch(
    unused_tcp_port: int,
) -> None:
    requests = 0

    async def capabilities_handler(request: web.Request) -> web.Response:
        nonlocal requests
        requests += 1
        return web.json_response(capabilities())

    app = web.Application()
    app.router.add_get("/v1/capabilities", capabilities_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", unused_tcp_port)
    await site.start()
    try:
        async with aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar(unsafe=True)) as session:
            session.cookie_jar.update_cookies(
                {"ha_session": "private-cookie"},
                response_url=URL(f"http://127.0.0.1:{unused_tcp_port}"),
            )
            client = HermesClient(
                session,
                f"http://127.0.0.1:{unused_tcp_port}",
                "fixture-secret",
                allow_insecure_http=True,
            )
            with pytest.raises(HermesClientError, match="containing cookies"):
                await client.async_capabilities()
            assert requests == 0
    finally:
        await runner.cleanup()


async def test_real_aiohttp_body_read_total_timeout_is_indeterminate(
    unused_tcp_port: int,
) -> None:
    posts = 0

    async def capabilities_handler(request: web.Request) -> web.Response:
        return web.json_response(capabilities())

    async def response_handler(request: web.Request) -> web.StreamResponse:
        nonlocal posts
        posts += 1
        response = web.StreamResponse(headers={"Content-Type": "application/json"})
        await response.prepare(request)
        await asyncio.sleep(0.2)
        return response

    app = web.Application()
    app.router.add_get("/v1/capabilities", capabilities_handler)
    app.router.add_post("/v1/responses", response_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", unused_tcp_port)
    await site.start()
    try:
        async with aiohttp.ClientSession() as session:
            client = HermesClient(
                session,
                f"http://127.0.0.1:{unused_tcp_port}",
                "fixture-secret",
                allow_insecure_http=True,
                connect_timeout=0.1,
                total_timeout=0.05,
            )
            with pytest.raises(HermesIndeterminateError, match="outcome may be unknown"):
                await client.async_respond(
                    model="fixture-model", utterance="status", conversation="c"
                )
            assert posts == 1
    finally:
        await runner.cleanup()


async def test_real_aiohttp_https_never_downgrades_to_plaintext(unused_tcp_port: int) -> None:
    async def capabilities_handler(request: web.Request) -> web.Response:
        return web.json_response(capabilities())

    app = web.Application()
    app.router.add_get("/v1/capabilities", capabilities_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", unused_tcp_port)
    await site.start()
    try:
        async with aiohttp.ClientSession() as session:
            client = HermesClient(session, f"https://127.0.0.1:{unused_tcp_port}", "fixture-secret")
            with pytest.raises(HermesClientError, match="transport failure|before dispatch"):
                await client.async_capabilities()
    finally:
        await runner.cleanup()


def test_client_uses_only_injected_session() -> None:
    session = FakeSession([])
    client = HermesClient(session, "https://hermes.invalid", "secret")  # type: ignore[arg-type]
    assert client._session is cast(Any, session)


@pytest.mark.parametrize(
    "failure",
    [
        aiohttp.ClientError("token-secret https://private.invalid/path?token=secret"),
        TimeoutError("token-secret https://private.invalid/path?token=secret"),
        HermesProtocolError("token-secret https://private.invalid/path?token=secret"),
    ],
)
async def test_all_client_error_categories_have_redacted_representations(
    failure: BaseException,
) -> None:
    session = FakeSession([failure])
    client = HermesClient(session, "https://private.invalid", "token-secret")  # type: ignore[arg-type]
    with pytest.raises(HermesClientError) as raised:
        await client.async_capabilities()
    for representation in (str(raised.value), repr(raised.value)):
        assert "token-secret" not in representation
        assert "private.invalid" not in representation
