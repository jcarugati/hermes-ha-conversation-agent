"""Tests for the narrow asynchronous Hermes HTTP client."""

from __future__ import annotations

import asyncio
import datetime
import ipaddress
import json
import math
import ssl
from pathlib import Path
from typing import Any, cast

import aiohttp
import pytest
from aiohttp import web
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from yarl import URL

from custom_components.hermes_conversation.client import (
    HermesAuthenticationError,
    HermesCapabilities,
    HermesClient,
    HermesClientError,
    HermesIndeterminateError,
    HermesProtocolError,
    normalize_base_url,
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
        "features": {"responses_api": True, "chat_completions": True},
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
    ("url", "canonical"),
    [
        ("https://HERMES.Example.Test.:443/", "https://hermes.example.test"),
        (
            "https://b\N{LATIN SMALL LETTER U WITH DIAERESIS}cher.example/",
            "https://xn--bcher-kva.example",
        ),
        ("https://XN--BCHER-KVA.EXAMPLE./", "https://xn--bcher-kva.example"),
        ("https://[2001:0DB8:0:0:0:0:0:1]:443/", "https://[2001:db8::1]"),
        ("http://[FD00:0:0:0:0:0:0:1]:80/", "http://[fd00::1]"),
    ],
)
def test_canonical_endpoint_identity(url: str, canonical: str) -> None:
    assert normalize_base_url(url, url.startswith("http://")) == canonical


@pytest.mark.parametrize(
    "url",
    [
        "https://hermes.example.test/.",
        "https://hermes.example.test/%2e",
        "https://hermes.example.test/%2F",
        "https://hermes.example.test/%252f",
        "https://hermes.example.test//",
    ],
)
def test_canonical_endpoint_identity_rejects_unsafe_path_variants(url: str) -> None:
    with pytest.raises(ValueError, match="path"):
        normalize_base_url(url)


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
    assert capabilities_result == HermesCapabilities(
        model="fixture-model",
        tool_policy="full_agent",
        mcp_policy="server_managed",
        server_enforced=False,
    )
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


@pytest.mark.parametrize("status", [401, 403])
async def test_health_rejection_is_not_an_authentication_error(status: int) -> None:
    session = FakeSession([FakeResponse({}, status=status)])
    client = HermesClient(session, "https://hermes.invalid", "secret")  # type: ignore[arg-type]
    with pytest.raises(HermesProtocolError, match=f"HTTP {status}") as error:
        await client.async_health()
    assert not isinstance(error.value, HermesAuthenticationError)


@pytest.mark.parametrize("status", [401, 403])
async def test_capabilities_rejection_has_distinct_authentication_error(status: int) -> None:
    session = FakeSession([FakeResponse({}, status=status)])
    client = HermesClient(session, "https://hermes.invalid", "secret")  # type: ignore[arg-type]
    with pytest.raises(HermesAuthenticationError, match=f"HTTP {status}"):
        await client.async_capabilities()


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


async def test_accepts_a_direct_hermes_api_server() -> None:
    payload = capabilities()
    client = HermesClient(
        FakeSession([FakeResponse(payload)]),  # type: ignore[arg-type]
        "https://hermes.invalid",
        "secret",
    )

    assert await client.async_capabilities() == HermesCapabilities(
        model="fixture-model",
        tool_policy="full_agent",
        mcp_policy="server_managed",
        server_enforced=False,
    )


@pytest.mark.parametrize("chat_completions", [False, "true", 1, {}, []])
async def test_rejects_a_server_with_an_invalid_chat_completions_feature(
    chat_completions: object,
) -> None:
    payload = capabilities()
    payload["features"] = {"responses_api": True, "chat_completions": chat_completions}
    client = HermesClient(
        FakeSession([FakeResponse(payload)]),  # type: ignore[arg-type]
        "https://hermes.invalid",
        "secret",
    )

    with pytest.raises(HermesProtocolError, match="does not advertise chat_completions"):
        await client.async_capabilities()


async def test_rejects_a_direct_server_with_a_custom_security_policy() -> None:
    payload = capabilities()
    payload["security"] = {
        "tool_policy": "none",
        "mcp_policy": "none",
        "server_enforced": True,
    }
    client = HermesClient(
        FakeSession([FakeResponse(payload)]),  # type: ignore[arg-type]
        "https://hermes.invalid",
        "secret",
    )

    with pytest.raises(HermesProtocolError, match="custom security policy"):
        await client.async_capabilities()


@pytest.mark.parametrize("security", [{}, {"tool_policy": "none"}, {"server_enforced": False}])
async def test_rejects_any_custom_security_object(
    security: dict[str, object],
) -> None:
    payload = capabilities()
    payload["features"] = {"responses_api": True, "chat_completions": True}
    payload["security"] = security
    client = HermesClient(
        FakeSession([FakeResponse(payload)]),  # type: ignore[arg-type]
        "https://hermes.invalid",
        "secret",
    )

    with pytest.raises(HermesProtocolError, match="custom security policy"):
        await client.async_capabilities()


async def test_rejects_responses_server_without_chat_completions() -> None:
    payload = capabilities()
    payload["features"] = {"responses_api": True}
    client = HermesClient(
        FakeSession([FakeResponse(payload)]),  # type: ignore[arg-type]
        "https://hermes.invalid",
        "secret",
    )

    with pytest.raises(HermesProtocolError, match="does not advertise chat_completions"):
        await client.async_capabilities()


async def test_non_direct_capability_contract_prevents_response_dispatch() -> None:
    payload = capabilities()
    payload["features"] = {"responses_api": True}
    session = FakeSession([FakeResponse(payload)])
    client = HermesClient(session, "https://hermes.invalid", "secret")  # type: ignore[arg-type]

    with pytest.raises(HermesProtocolError, match="does not advertise chat_completions"):
        await client.async_respond(
            model="fixture-model", utterance="status", conversation="conversation"
        )

    assert [call[0] for call in session.calls] == ["GET"]


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


@pytest.mark.parametrize("tool_type", ["function_call", "function_call_output"])
def test_rejects_completed_response_with_only_tool_records(tool_type: str) -> None:
    payload = completed_response() | {"output": [{"type": tool_type}]}
    client = HermesClient(FakeSession([]), "https://hermes.invalid", "secret")  # type: ignore[arg-type]

    with pytest.raises(HermesProtocolError, match="assistant output"):
        client._parse_response(payload, "fixture-model")


async def test_accepts_tool_records_followed_by_final_assistant_output() -> None:
    payload = completed_response() | {
        "output": [
            {"type": "function_call"},
            {"type": "function_call_output"},
            completed_response()["output"][0],  # type: ignore[index]
        ]
    }
    client = HermesClient(
        FakeSession([FakeResponse(capabilities()), FakeResponse(payload)]),  # type: ignore[arg-type]
        "https://hermes.invalid",
        "secret",
    )

    response = await client.async_respond(
        model="fixture-model", utterance="status", conversation="c"
    )

    assert response.text == "safe status"


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


async def test_model_alias_changes_only_the_wire_model() -> None:
    """An alias overrides the wire model while retaining the strict DTO."""
    caps = capabilities()
    session = FakeSession(
        [
            FakeResponse(caps),
            FakeResponse(completed_response() | {"model": "alias-model"}),
        ]
    )
    client = HermesClient(session, "https://hermes.invalid", "secret")  # type: ignore[arg-type]

    response = await client.async_respond(
        model="fixture-model",
        utterance="status",
        conversation="c",
        model_alias="alias-model",
    )
    assert response.text == "safe status"
    request = json.loads(session.calls[1][2]["data"])
    assert request == {
        "model": "alias-model",
        "input": "status",
        "conversation": "c",
        "stream": False,
    }
    assert set(request) == {"model", "input", "conversation", "stream"}


async def test_model_alias_response_mismatch_is_rejected() -> None:
    """When model_alias is set, the response must echo the alias model."""
    caps = capabilities()
    session = FakeSession(
        [
            FakeResponse(caps),
            FakeResponse(completed_response() | {"model": "different-model"}),
        ]
    )
    client = HermesClient(session, "https://hermes.invalid", "secret")  # type: ignore[arg-type]

    with pytest.raises(HermesIndeterminateError, match="outcome may be unknown"):
        await client.async_respond(
            model="fixture-model",
            utterance="status",
            conversation="c",
            model_alias="alias-model",
        )


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
            assert captured[0]["Authorization"] == "Bearer fixture-secret"
            assert "Cookie" not in captured[0] or captured[0]["Cookie"] == ""
    finally:
        await runner.cleanup()


async def test_real_aiohttp_shared_session_cookies_are_not_forwarded(
    unused_tcp_port: int,
) -> None:
    captured: list[dict[str, str]] = []

    async def capabilities_handler(request: web.Request) -> web.Response:
        captured.append(dict(request.headers))
        return web.json_response(capabilities())

    async def response_handler(request: web.Request) -> web.Response:
        captured.append(dict(request.headers))
        return web.json_response(completed_response())

    app = web.Application()
    app.router.add_get("/v1/capabilities", capabilities_handler)
    app.router.add_post("/v1/responses", response_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", unused_tcp_port)
    await site.start()
    try:
        connector = aiohttp.TCPConnector()
        async with aiohttp.ClientSession(
            connector=connector,
            cookie_jar=aiohttp.CookieJar(unsafe=True),
        ) as session:
            session.cookie_jar.update_cookies(
                {"ha_capabilities": "private-cookie"},
                response_url=URL(f"http://127.0.0.1:{unused_tcp_port}/v1/capabilities"),
            )
            session.cookie_jar.update_cookies(
                {"ha_response": "private-cookie"},
                response_url=URL(f"http://127.0.0.1:{unused_tcp_port}/v1/responses"),
            )
            client = HermesClient(
                session,
                f"http://127.0.0.1:{unused_tcp_port}",
                "fixture-secret",
                allow_insecure_http=True,
            )
            response = await client.async_respond(
                model="fixture-model",
                utterance="status",
                conversation="opaque-conversation",
            )
            assert response.text == "safe status"
            assert len(captured) == 2
            assert all("Cookie" not in headers for headers in captured)
            assert session.connector is connector
            assert not session.closed
            assert not connector.closed
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


async def test_real_aiohttp_https_rejects_ephemeral_untrusted_certificate(
    tmp_path: Path, unused_tcp_port: int
) -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "127.0.0.1")])
    now = datetime.datetime.now(datetime.UTC)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=1))
        .not_valid_after(now + datetime.timedelta(minutes=5))
        .add_extension(
            x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]),
            critical=False,
        )
        .sign(private_key, hashes.SHA256())
    )
    cert_path = tmp_path / "untrusted-cert.pem"
    key_path = tmp_path / "untrusted-key.pem"
    cert_path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    server_ssl = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server_ssl.load_cert_chain(cert_path, key_path)
    requests = 0

    async def capabilities_handler(request: web.Request) -> web.Response:
        nonlocal requests
        requests += 1
        return web.json_response(capabilities())

    app = web.Application()
    app.router.add_get("/v1/capabilities", capabilities_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", unused_tcp_port, ssl_context=server_ssl)
    loop = asyncio.get_running_loop()
    previous_exception_handler = loop.get_exception_handler()

    def ignore_expected_rejected_tls_handshake(
        current_loop: asyncio.AbstractEventLoop, context: dict[str, Any]
    ) -> None:
        if isinstance(context.get("exception"), ConnectionResetError):
            return
        if previous_exception_handler is not None:
            previous_exception_handler(current_loop, context)
        else:
            current_loop.default_exception_handler(context)

    loop.set_exception_handler(ignore_expected_rejected_tls_handshake)
    await site.start()
    try:
        async with aiohttp.ClientSession() as session:
            client = HermesClient(session, f"https://127.0.0.1:{unused_tcp_port}", "fixture-secret")
            with pytest.raises(HermesClientError, match="before dispatch") as raised:
                await client.async_capabilities()
            assert isinstance(raised.value.__context__, aiohttp.ClientConnectorCertificateError)
            assert requests == 0
    finally:
        await runner.cleanup()
        await asyncio.sleep(0)
        loop.set_exception_handler(previous_exception_handler)


async def test_real_aiohttp_async_connector_connect_timeout_is_predispatch() -> None:
    class StalledConnector(aiohttp.TCPConnector):
        attempts = 0

        async def _create_connection(
            self,
            req: Any,
            traces: Any,
            timeout: Any,  # noqa: ASYNC109
        ) -> Any:
            del req, traces, timeout
            self.attempts += 1
            await asyncio.get_running_loop().create_future()

    connector = StalledConnector()
    async with aiohttp.ClientSession(connector=connector) as session:
        client = HermesClient(
            session,
            "https://127.0.0.1:1",
            "fixture-secret",
            connect_timeout=0.01,
            total_timeout=1,
        )
        with pytest.raises(HermesClientError, match="connect timed out") as raised:
            await client.async_capabilities()
        assert not isinstance(raised.value, HermesIndeterminateError)
        assert connector.attempts == 1


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
