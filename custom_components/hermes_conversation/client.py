"""Narrow, defensive asynchronous client for the verified Hermes API contract."""

from __future__ import annotations

import asyncio
import ipaddress
import json
import math
from dataclasses import dataclass
from numbers import Real
from typing import Any, Final
from urllib.parse import unquote, urlsplit, urlunsplit

import aiohttp

DEFAULT_CONNECT_TIMEOUT: Final = 5.0
DEFAULT_TOTAL_TIMEOUT: Final = 30.0
DEFAULT_MAX_REQUEST_BYTES: Final = 32_768
DEFAULT_MAX_RESPONSE_BYTES: Final = 1_048_576
DEFAULT_MAX_UTTERANCE_CHARS: Final = 8_192
DEFAULT_MAX_OUTPUT_CHARS: Final = 8_192
MAX_MODEL_CHARS: Final = 512
MAX_CONVERSATION_CHARS: Final = 512
_HTTP_HOST_SUFFIXES: Final = (".local", ".home.arpa", ".ts.net")
_HTTP_NETWORKS: Final = tuple(
    ipaddress.ip_network(network)
    for network in (
        "127.0.0.0/8",
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "169.254.0.0/16",
        "100.64.0.0/10",
        "::1/128",
        "fc00::/7",
        "fe80::/10",
    )
)


class HermesClientError(RuntimeError):
    """A sanitized Hermes request failure."""


class HermesAuthenticationError(HermesClientError):
    """Hermes rejected bearer authentication."""


class HermesProtocolError(HermesClientError):
    """Hermes returned data outside the verified contract."""


class HermesIndeterminateError(HermesClientError):
    """A dispatched request timed out and its outcome may be unknown."""


class _HermesPreDispatchError(HermesClientError):
    """A sanitized failure known to have happened before request dispatch."""


@dataclass(frozen=True, slots=True)
class HermesHealth:
    """Validated health response."""

    version: str


@dataclass(frozen=True, slots=True)
class HermesCapabilities:
    """Validated capabilities required by this client."""

    model: str


@dataclass(frozen=True, slots=True)
class HermesResponse:
    """Validated completed response with bounded assistant text."""

    response_id: str
    text: str


def normalize_base_url(base_url: str, allow_insecure_http: bool = False) -> str:
    """Validate and normalize a Hermes API base URL."""
    try:
        parsed = urlsplit(base_url)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError:
        raise ValueError("base URL is malformed") from None
    if parsed.scheme not in {"http", "https"} or hostname is None:
        raise ValueError("base URL must use HTTPS and include a host")
    if parsed.scheme == "http" and not allow_insecure_http:
        raise ValueError("base URL must use HTTPS unless insecure HTTP is explicitly allowed")
    if parsed.scheme == "http" and not _is_allowed_http_host(hostname):
        raise ValueError("plaintext HTTP is limited to allowlisted local/private hosts")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("base URL must not contain credentials")
    if parsed.query or parsed.fragment:
        raise ValueError("base URL must not contain query values or fragments")
    if parsed.path not in {"", "/"} or unquote(parsed.path) not in {"", "/"}:
        raise ValueError("base URL must not contain a path")
    if any(character.isspace() for character in base_url):
        raise ValueError("base URL is malformed")
    canonical_hostname = _canonicalize_hostname(hostname)
    host = f"[{canonical_hostname}]" if ":" in canonical_hostname else canonical_hostname
    default_port = 443 if parsed.scheme == "https" else 80
    netloc = f"{host}:{port}" if port is not None and port != default_port else host
    return urlunsplit((parsed.scheme, netloc, "", "", ""))


def _canonicalize_hostname(hostname: str) -> str:
    """Return one stable ASCII identity for DNS names and IP literals."""
    candidate = hostname.rstrip(".")
    if not candidate or "%" in candidate:
        raise ValueError("base URL host is malformed")
    try:
        return ipaddress.ip_address(candidate).compressed.lower()
    except ValueError:
        try:
            return candidate.encode("idna").decode("ascii").lower()
        except UnicodeError:
            raise ValueError("base URL host is malformed") from None


def _is_allowed_http_host(hostname: str) -> bool:
    """Allow plaintext only for explicit local/private address classes and DNS suffixes."""
    normalized = hostname.rstrip(".").lower()
    try:
        address = ipaddress.ip_address(normalized)
    except ValueError:
        return normalized == "localhost" or normalized.endswith(_HTTP_HOST_SUFFIXES)
    return any(address in network for network in _HTTP_NETWORKS)


def _positive_timeout(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite positive number")
    converted = float(value)
    if not math.isfinite(converted) or converted <= 0:
        raise ValueError(f"{name} must be a finite positive number")
    return converted


def _positive_limit(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _required_string(payload: dict[str, Any], key: str, endpoint: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise HermesProtocolError(f"{endpoint} requires non-empty string field '{key}'")
    return value


def _required_nonnegative_int(payload: dict[str, Any], key: str, endpoint: str) -> int:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise HermesProtocolError(f"{endpoint} requires non-negative integer field '{key}'")
    return value


class HermesClient:
    """Call only the three fixed endpoints in the verified Hermes contract."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        base_url: str,
        token: str,
        *,
        allow_insecure_http: bool = False,
        connect_timeout: float = DEFAULT_CONNECT_TIMEOUT,
        total_timeout: float = DEFAULT_TOTAL_TIMEOUT,
        max_request_bytes: int = DEFAULT_MAX_REQUEST_BYTES,
        max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
        max_utterance_chars: int = DEFAULT_MAX_UTTERANCE_CHARS,
        max_output_chars: int = DEFAULT_MAX_OUTPUT_CHARS,
    ) -> None:
        self.base_url = normalize_base_url(base_url, allow_insecure_http)
        if not token or "\r" in token or "\n" in token:
            raise ValueError("bearer token must be non-empty and header-safe")
        connect_timeout = _positive_timeout("connect_timeout", connect_timeout)
        total_timeout = _positive_timeout("total_timeout", total_timeout)
        max_request_bytes = _positive_limit("max_request_bytes", max_request_bytes)
        max_response_bytes = _positive_limit("max_response_bytes", max_response_bytes)
        max_utterance_chars = _positive_limit("max_utterance_chars", max_utterance_chars)
        max_output_chars = _positive_limit("max_output_chars", max_output_chars)
        self._session = session
        self._token = token
        self._timeout = aiohttp.ClientTimeout(total=total_timeout, connect=connect_timeout)
        self._max_request_bytes = max_request_bytes
        self._max_response_bytes = max_response_bytes
        self._max_utterance_chars = max_utterance_chars
        self._max_output_chars = max_output_chars

    async def async_health(self) -> HermesHealth:
        """Validate the unauthenticated Hermes health endpoint."""
        payload = await self._request_json("GET", "/health", authenticated=False)
        if payload.get("status") != "ok" or payload.get("platform") != "hermes-agent":
            raise HermesProtocolError("/health does not identify a healthy hermes-agent")
        return HermesHealth(version=_required_string(payload, "version", "/health"))

    async def async_capabilities(self) -> HermesCapabilities:
        """Validate support for the exact authenticated Responses API contract."""
        payload = await self._request_json("GET", "/v1/capabilities", authenticated=True)
        if payload.get("object") != "hermes.api_server.capabilities":
            raise HermesProtocolError(
                "/v1/capabilities returned an unsupported capabilities object"
            )
        features = payload.get("features")
        if not isinstance(features, dict) or features.get("responses_api") is not True:
            raise HermesProtocolError("/v1/capabilities does not advertise responses_api")
        auth = payload.get("auth")
        if not isinstance(auth, dict) or auth != {"type": "bearer", "required": True}:
            raise HermesProtocolError("/v1/capabilities does not require bearer authentication")
        endpoints = payload.get("endpoints")
        expected = {"method": "POST", "path": "/v1/responses"}
        if not isinstance(endpoints, dict) or endpoints.get("responses") != expected:
            raise HermesProtocolError("/v1/capabilities does not advertise the responses endpoint")
        return HermesCapabilities(model=_required_string(payload, "model", "/v1/capabilities"))

    async def async_respond(
        self, *, model: str, utterance: str, conversation: str
    ) -> HermesResponse:
        """Submit one bounded, non-streaming, data-only named-conversation turn."""
        self._validate_request_string("model", model, MAX_MODEL_CHARS)
        self._validate_request_string("utterance", utterance, self._max_utterance_chars)
        self._validate_request_string("conversation", conversation, MAX_CONVERSATION_CHARS)
        body: dict[str, object] = {
            "model": model,
            "input": utterance,
            "conversation": conversation,
            "stream": False,
        }
        encoded = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode()
        if len(encoded) > self._max_request_bytes:
            raise ValueError(f"request exceeds {self._max_request_bytes} bytes")
        capabilities = await self.async_capabilities()
        if capabilities.model != model:
            raise HermesProtocolError("/v1/capabilities model does not match the request")
        try:
            payload = await self._request_json(
                "POST", "/v1/responses", authenticated=True, body=encoded, indeterminate=True
            )
            return self._parse_response(payload, model)
        except asyncio.CancelledError:
            raise
        except HermesIndeterminateError:
            raise
        except _HermesPreDispatchError:
            raise
        except HermesClientError:
            raise HermesIndeterminateError(
                "POST /v1/responses failed after dispatch; outcome may be unknown"
            ) from None

    @staticmethod
    def _validate_request_string(name: str, value: str, maximum: int) -> None:
        if not isinstance(value, str) or not value or len(value) > maximum:
            raise ValueError(f"{name} must be a non-empty string of at most {maximum} characters")

    async def _request_json(
        self,
        method: str,
        path: str,
        *,
        authenticated: bool,
        body: bytes | None = None,
        indeterminate: bool = False,
    ) -> dict[str, Any]:
        headers = {"Accept": "application/json"}
        if authenticated:
            headers["Authorization"] = f"Bearer {self._token}"
        if body is not None:
            headers["Content-Type"] = "application/json"
        headers["Cookie"] = ""
        cookie_jar = getattr(self._session, "cookie_jar", None)
        if cookie_jar is not None and any(True for _cookie in cookie_jar):
            raise _HermesPreDispatchError(
                f"{method} {path} refused a shared session containing cookies"
            )
        try:
            request = self._session.request(
                method,
                f"{self.base_url}{path}",
                headers=headers,
                data=body,
                allow_redirects=False,
                timeout=self._timeout,
            )
        except asyncio.CancelledError:
            raise
        except aiohttp.ConnectionTimeoutError:
            raise _HermesPreDispatchError(f"{method} {path} connect timed out") from None
        except aiohttp.ClientConnectorError:
            raise _HermesPreDispatchError(
                f"{method} {path} connection failed before dispatch"
            ) from None
        except HermesClientError:
            raise HermesClientError(f"{method} {path} request setup failed") from None
        except (TimeoutError, aiohttp.ClientError):
            raise HermesClientError(f"{method} {path} request setup failed") from None
        try:
            async with request as response:
                if response.status in {401, 403}:
                    raise HermesAuthenticationError(
                        f"{method} {path} returned HTTP {response.status}"
                    )
                if response.status != 200:
                    raise HermesProtocolError(f"{method} {path} returned HTTP {response.status}")
                media_type = (
                    response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
                )
                if media_type != "application/json":
                    raise HermesProtocolError(f"{method} {path} returned unexpected content type")
                raw = bytearray()
                async for chunk in response.content.iter_chunked(64 * 1024):
                    raw.extend(chunk)
                    if len(raw) > self._max_response_bytes:
                        raise HermesProtocolError(
                            f"{method} {path} response exceeds {self._max_response_bytes} bytes"
                        )
        except asyncio.CancelledError:
            raise
        except aiohttp.ConnectionTimeoutError:
            raise _HermesPreDispatchError(f"{method} {path} connect timed out") from None
        except aiohttp.ClientConnectorError:
            raise _HermesPreDispatchError(
                f"{method} {path} connection failed before dispatch"
            ) from None
        except TimeoutError:
            if indeterminate:
                raise HermesIndeterminateError(
                    f"{method} {path} timed out after dispatch; outcome may be unknown"
                ) from None
            raise HermesClientError(f"{method} {path} timed out") from None
        except HermesClientError:
            raise
        except aiohttp.ClientError:
            if indeterminate:
                raise HermesIndeterminateError(
                    f"{method} {path} connection failed after dispatch; outcome may be unknown"
                ) from None
            raise HermesClientError(f"{method} {path} transport failure") from None
        try:
            payload = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise HermesProtocolError(f"{method} {path} returned malformed JSON") from None
        if not isinstance(payload, dict):
            raise HermesProtocolError(f"{method} {path} JSON root must be an object")
        return payload

    def _parse_response(self, payload: dict[str, Any], model: str) -> HermesResponse:
        response_id = _required_string(payload, "id", "/v1/responses")
        if payload.get("object") != "response" or payload.get("status") != "completed":
            raise HermesProtocolError("/v1/responses did not return a completed response object")
        if payload.get("model") != model:
            raise HermesProtocolError("/v1/responses model does not match the request")
        _required_nonnegative_int(payload, "created_at", "/v1/responses")
        usage = payload.get("usage")
        if not isinstance(usage, dict):
            raise HermesProtocolError("/v1/responses requires object field 'usage'")
        for key in ("input_tokens", "output_tokens", "total_tokens"):
            _required_nonnegative_int(usage, key, "/v1/responses usage")
        output = payload.get("output")
        if not isinstance(output, list) or not output:
            raise HermesProtocolError("/v1/responses requires non-empty array field 'output'")
        parts: list[str] = []
        for item in output:
            if (
                not isinstance(item, dict)
                or item.get("type") != "message"
                or item.get("role") != "assistant"
            ):
                raise HermesProtocolError("/v1/responses output items must be assistant messages")
            content = item.get("content")
            if not isinstance(content, list) or not content:
                raise HermesProtocolError("/v1/responses message requires non-empty content")
            for part in content:
                if (
                    not isinstance(part, dict)
                    or part.get("type") != "output_text"
                    or not isinstance(part.get("text"), str)
                    or not part["text"]
                ):
                    raise HermesProtocolError(
                        "/v1/responses content items must be non-empty output_text"
                    )
                parts.append(part["text"])
        text = "\n".join(parts)
        if len(text) > self._max_output_chars:
            raise HermesProtocolError(
                f"/v1/responses output exceeds {self._max_output_chars} characters"
            )
        return HermesResponse(response_id=response_id, text=text)
