"""Verify the narrow Hermes Responses API contract without external dependencies."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

DEFAULT_MAX_RESPONSE_BYTES = 1_048_576
CONTRACT_MARKER = "marker-7319"
CONTRACT_INPUT = f"Remember the synthetic marker {CONTRACT_MARKER}. Reply only: stored"
CONTRACT_FOLLOW_UP = "Reply only with the synthetic marker I asked you to remember."


class ContractError(RuntimeError):
    """A remote endpoint does not satisfy the required contract."""


@dataclass(frozen=True)
class ContractEvidence:
    """Non-sensitive facts observed during one successful verification."""

    hermes_version: str
    model: str
    health_status: str
    responses_api: bool
    response_status: str
    response_object: str
    conversation_continuity: bool
    content_types: tuple[str, str, str]


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req: Request, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> None:
        return None


def _endpoint(base_url: str, path: str) -> str:
    parsed = urlsplit(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ContractError("base URL must use http or https and include a host")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ContractError("base URL must not contain credentials, query values, or fragments")
    base_path = parsed.path.rstrip("/")
    return urlunsplit((parsed.scheme, parsed.netloc, f"{base_path}{path}", "", ""))


def _json_request(
    opener: Any,
    base_url: str,
    path: str,
    *,
    token: str | None,
    timeout: float,
    max_response_bytes: int,
    body: dict[str, object] | None = None,
) -> tuple[dict[str, Any], str]:
    headers = {"Accept": "application/json"}
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    data = None
    method = "GET"
    if body is not None:
        data = json.dumps(body, separators=(",", ":")).encode("utf-8")
        headers["Content-Type"] = "application/json"
        method = "POST"
    request = Request(_endpoint(base_url, path), data=data, headers=headers, method=method)
    try:
        with opener.open(request, timeout=timeout) as response:
            status = response.status
            content_type = response.headers.get_content_type()
            raw = response.read(max_response_bytes + 1)
    except HTTPError as exc:
        exc.close()
        raise ContractError(f"{method} {path} returned HTTP {exc.code}") from None
    except (URLError, TimeoutError, OSError) as exc:
        raise ContractError(f"{method} {path} failed: {type(exc).__name__}") from None
    if status != 200:
        raise ContractError(f"{method} {path} returned HTTP {status}")
    if content_type != "application/json":
        raise ContractError(f"{method} {path} returned unexpected content type")
    if len(raw) > max_response_bytes:
        raise ContractError(f"{method} {path} response exceeds {max_response_bytes} bytes")
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ContractError(f"{method} {path} returned malformed JSON") from None
    if not isinstance(payload, dict):
        raise ContractError(f"{method} {path} JSON root must be an object")
    return payload, content_type


def _required_string(payload: dict[str, Any], key: str, endpoint: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ContractError(f"{endpoint} requires non-empty string field '{key}'")
    return value


def _output_text(payload: dict[str, Any]) -> str:
    output = payload.get("output")
    if not isinstance(output, list):
        raise ContractError("/v1/responses requires array field 'output'")
    parts: list[str] = []
    for item in output:
        if not isinstance(item, dict) or not isinstance(item.get("content"), list):
            continue
        for content in item["content"]:
            if isinstance(content, dict) and isinstance(content.get("text"), str):
                parts.append(content["text"])
    return "\n".join(parts)


def verify_contract(
    base_url: str,
    token: str,
    *,
    conversation: str = "ha-contract-test",
    timeout: float = 30.0,
    max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
) -> ContractEvidence:
    """Verify health, capabilities, and harmless named-conversation continuity."""
    if not token:
        raise ContractError("bearer token is required")
    opener = build_opener(_NoRedirect())
    health, health_type = _json_request(
        opener, base_url, "/health", token=None, timeout=timeout, max_response_bytes=max_response_bytes
    )
    health_status = _required_string(health, "status", "/health")
    if health_status != "ok" or health.get("platform") != "hermes-agent":
        raise ContractError("/health does not identify a healthy hermes-agent")
    version = _required_string(health, "version", "/health")

    capabilities, capabilities_type = _json_request(
        opener,
        base_url,
        "/v1/capabilities",
        token=token,
        timeout=timeout,
        max_response_bytes=max_response_bytes,
    )
    if capabilities.get("object") != "hermes.api_server.capabilities":
        raise ContractError("/v1/capabilities returned an unsupported object")
    features = capabilities.get("features")
    if not isinstance(features, dict) or features.get("responses_api") is not True:
        raise ContractError("/v1/capabilities does not advertise responses_api")
    auth = capabilities.get("auth")
    if not isinstance(auth, dict) or auth.get("type") != "bearer" or auth.get("required") is not True:
        raise ContractError("/v1/capabilities does not advertise required bearer authentication")
    endpoints = capabilities.get("endpoints")
    expected_response_endpoint = {"method": "POST", "path": "/v1/responses"}
    if not isinstance(endpoints, dict) or endpoints.get("responses") != expected_response_endpoint:
        raise ContractError("/v1/capabilities does not advertise the required responses endpoint")
    model = _required_string(capabilities, "model", "/v1/capabilities")

    response, _response_type = _json_request(
        opener,
        base_url,
        "/v1/responses",
        token=token,
        timeout=timeout,
        max_response_bytes=max_response_bytes,
        body={"model": model, "input": CONTRACT_INPUT, "conversation": conversation, "stream": False},
    )
    response_object = _required_string(response, "object", "/v1/responses")
    response_status = _required_string(response, "status", "/v1/responses")
    _required_string(response, "id", "/v1/responses")
    if response_object != "response" or response_status != "completed":
        raise ContractError("/v1/responses did not return a completed response object")
    if response.get("model") != model:
        raise ContractError("/v1/responses model does not match advertised model")
    _output_text(response)

    follow_up, follow_up_type = _json_request(
        opener,
        base_url,
        "/v1/responses",
        token=token,
        timeout=timeout,
        max_response_bytes=max_response_bytes,
        body={"model": model, "input": CONTRACT_FOLLOW_UP, "conversation": conversation, "stream": False},
    )
    follow_up_status = _required_string(follow_up, "status", "/v1/responses")
    if follow_up.get("object") != "response" or follow_up_status != "completed":
        raise ContractError("/v1/responses follow-up did not complete")
    if CONTRACT_MARKER not in _output_text(follow_up):
        raise ContractError("named conversation did not preserve the synthetic marker")

    return ContractEvidence(
        hermes_version=version,
        model=model,
        health_status=health_status,
        responses_api=True,
        response_status=follow_up_status,
        response_object=response_object,
        conversation_continuity=True,
        content_types=(health_type, capabilities_type, follow_up_type),
    )


def live_config_from_env() -> tuple[str, str] | None:
    """Return live settings only after an explicit opt-in and complete configuration."""
    if os.getenv("HERMES_CONTRACT_LIVE") != "1":
        return None
    base_url = os.getenv("HERMES_CONTRACT_BASE_URL")
    token = os.getenv("HERMES_CONTRACT_TOKEN")
    if not base_url or not token:
        return None
    return base_url, token


def main() -> int:
    config = live_config_from_env()
    if config is None:
        print(
            "Live verification is disabled. Set HERMES_CONTRACT_LIVE=1, "
            "HERMES_CONTRACT_BASE_URL, and HERMES_CONTRACT_TOKEN.",
            file=sys.stderr,
        )
        return 2
    try:
        evidence = verify_contract(*config, conversation="ha-contract-live")
    except ContractError as exc:
        print(f"Hermes contract verification failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(asdict(evidence), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
