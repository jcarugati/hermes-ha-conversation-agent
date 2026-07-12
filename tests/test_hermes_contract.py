"""Deterministic tests for the opt-in Hermes contract verifier."""

from __future__ import annotations

import json
import os
import re
import threading
import unittest
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, TypedDict
from unittest.mock import patch

import pytest

from tools.hermes_contract import (
    ContractError,
    _completed_response,
    _endpoint,
    _new_probe_identifiers,
    live_config_from_env,
    verify_contract,
)


class _RecordedRequest(TypedDict):
    method: str
    path: str
    authorization: str | None
    accept: str | None
    content_type: str | None
    body: bytes


class _HermesFixture(BaseHTTPRequestHandler):
    requests: list[_RecordedRequest] = []
    response_override: tuple[int, str, bytes] | None = None
    post_count = 0
    markers: dict[str, str] = {}
    reuse_response_id = False

    def log_message(self, format: str, *args: object) -> None:
        """Keep deterministic tests silent."""

    def _record(self, body: bytes = b"") -> None:
        self.requests.append(
            {
                "method": self.command,
                "path": self.path,
                "authorization": self.headers.get("Authorization"),
                "accept": self.headers.get("Accept"),
                "content_type": self.headers.get("Content-Type"),
                "body": body,
            }
        )

    def _json(self, status: int, payload: object) -> None:
        encoded = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self) -> None:  # noqa: N802
        self._record()
        if self.response_override:
            status, content_type, body = self.response_override
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/health":
            self._json(
                200, {"status": "ok", "platform": "hermes-agent", "version": "0.18.2"}
            )
        elif self.path == "/v1/capabilities":
            self._json(
                200,
                {
                    "object": "hermes.api_server.capabilities",
                    "platform": "hermes-agent",
                    "model": "fixture-model",
                    "auth": {"type": "bearer", "required": True},
                    "features": {"responses_api": True},
                    "endpoints": {
                        "responses": {"method": "POST", "path": "/v1/responses"}
                    },
                },
            )
        else:
            self._json(404, {"error": {"message": "not found"}})

    def do_POST(self) -> None:  # noqa: N802
        body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        self._record(body)
        type(self).post_count += 1
        request = json.loads(body)
        conversation = request["conversation"]
        marker_match = re.search(
            r"continuity marker: ([A-Za-z0-9_-]+)", request["input"]
        )
        if marker_match:
            self.markers[conversation] = marker_match.group(1)
            text = "acknowledged"
        else:
            text = self.markers.get(conversation, "unknown")
        self._json(
            200,
            {
                "id": "resp_fixture"
                if self.reuse_response_id
                else f"resp_fixture_{self.post_count}",
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
                "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
            },
        )


class ContractTest(unittest.TestCase):
    def setUp(self) -> None:
        _HermesFixture.requests = []
        _HermesFixture.response_override = None
        _HermesFixture.post_count = 0
        _HermesFixture.markers = {}
        _HermesFixture.reuse_response_id = False
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), _HermesFixture)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    @pytest.mark.allow_hosts(["127.0.0.1"])
    def test_verifies_narrow_contract_and_allowlisted_request(self) -> None:
        with patch(
            "tools.hermes_contract.token_urlsafe",
            side_effect=("conversation-token", "marker-token"),
        ):
            evidence = verify_contract(self.base_url, "fixture-secret")

        self.assertEqual(evidence.hermes_version, "0.18.2")
        self.assertEqual(evidence.model, "fixture-model")
        self.assertEqual(evidence.response_status, "completed")
        self.assertTrue(evidence.conversation_continuity)
        self.assertEqual(
            [request["path"] for request in _HermesFixture.requests],
            ["/health", "/v1/capabilities", "/v1/responses", "/v1/responses"],
        )
        post = _HermesFixture.requests[-2]
        self.assertEqual(post["authorization"], "Bearer fixture-secret")
        self.assertEqual(post["accept"], "application/json")
        self.assertEqual(post["content_type"], "application/json")
        self.assertEqual(
            json.loads(post["body"]),
            {
                "model": "fixture-model",
                "input": "Inert continuity marker: marker-token. Reply only: acknowledged.",
                "conversation": "conversation-token",
                "stream": False,
            },
        )
        follow_up = json.loads(_HermesFixture.requests[-1]["body"])
        self.assertEqual(
            follow_up,
            {
                "model": "fixture-model",
                "input": "Reply only with the inert continuity marker from the preceding message.",
                "conversation": "conversation-token",
                "stream": False,
            },
        )
        self.assertIsNone(_HermesFixture.requests[0]["authorization"])

    @pytest.mark.allow_hosts(["127.0.0.1"])
    def test_endpoint_rejects_unsafe_url_components(self) -> None:
        unsafe_urls = (
            "file:///private/data",
            "ftp://hermes.invalid",
            "https://user:secret@hermes.invalid",
            "https://hermes.invalid?token=secret",
            "https://hermes.invalid#private",
        )
        for url in unsafe_urls:
            with self.subTest(url=url), self.assertRaises(ContractError):
                _endpoint(url, "/health")

    @pytest.mark.allow_hosts(["127.0.0.1"])
    def test_rejects_missing_responses_capability_before_post(self) -> None:
        original = _HermesFixture.do_GET

        def without_capability(handler: _HermesFixture) -> None:
            if handler.path == "/v1/capabilities":
                handler._record()
                handler._json(
                    200,
                    {
                        "object": "hermes.api_server.capabilities",
                        "model": "m",
                        "features": {},
                    },
                )
            else:
                original(handler)

        with patch.object(_HermesFixture, "do_GET", without_capability):
            with self.assertRaisesRegex(ContractError, "responses_api"):
                verify_contract(self.base_url, "fixture-secret")
        self.assertEqual(len(_HermesFixture.requests), 2)

    @pytest.mark.allow_hosts(["127.0.0.1"])
    def test_rejects_capabilities_without_required_bearer(self) -> None:
        original = _HermesFixture.do_GET

        def unsupported_contract(handler: _HermesFixture) -> None:
            if handler.path == "/v1/capabilities":
                handler._record()
                handler._json(
                    200,
                    {
                        "object": "hermes.api_server.capabilities",
                        "model": "m",
                        "auth": {"type": "bearer", "required": False},
                        "features": {"responses_api": True},
                        "endpoints": {
                            "responses": {"method": "POST", "path": "/v1/responses"}
                        },
                    },
                )
            else:
                original(handler)

        with patch.object(_HermesFixture, "do_GET", unsupported_contract):
            with self.assertRaisesRegex(ContractError, "required bearer"):
                verify_contract(self.base_url, "fixture-secret")
        self.assertEqual(len(_HermesFixture.requests), 2)

    @pytest.mark.allow_hosts(["127.0.0.1"])
    def test_rejects_capabilities_without_required_response_route(self) -> None:
        original = _HermesFixture.do_GET

        def unsupported_endpoint(handler: _HermesFixture) -> None:
            if handler.path == "/v1/capabilities":
                handler._record()
                handler._json(
                    200,
                    {
                        "object": "hermes.api_server.capabilities",
                        "model": "m",
                        "auth": {"type": "bearer", "required": True},
                        "features": {"responses_api": True},
                        "endpoints": {},
                    },
                )
            else:
                original(handler)

        with patch.object(_HermesFixture, "do_GET", unsupported_endpoint):
            with self.assertRaisesRegex(ContractError, "responses endpoint"):
                verify_contract(self.base_url, "fixture-secret")
        self.assertEqual(len(_HermesFixture.requests), 2)

    @pytest.mark.allow_hosts(["127.0.0.1"])
    def test_rejects_text_without_explicit_output_text_structure(self) -> None:
        original = _HermesFixture.do_POST

        def invalid_content(handler: _HermesFixture) -> None:
            if _HermesFixture.post_count == 0:
                body = handler.rfile.read(
                    int(handler.headers.get("Content-Length", "0"))
                )
                handler._record(body)
                type(handler).post_count += 1
                handler._json(
                    200,
                    {
                        "id": "resp_invalid",
                        "object": "response",
                        "created_at": 1,
                        "status": "completed",
                        "model": "fixture-model",
                        "output": [
                            {
                                "type": "message",
                                "role": "assistant",
                                "content": [{"text": "acknowledged"}],
                            }
                        ],
                        "usage": {
                            "input_tokens": 1,
                            "output_tokens": 1,
                            "total_tokens": 2,
                        },
                    },
                )
            else:
                original(handler)

        with patch.object(_HermesFixture, "do_POST", invalid_content):
            with self.assertRaisesRegex(ContractError, "output_text"):
                verify_contract(self.base_url, "fixture-secret")

    @pytest.mark.allow_hosts(["127.0.0.1"])
    def test_rejects_missing_claimed_response_fields(self) -> None:
        original = _HermesFixture.do_POST

        def missing_usage(handler: _HermesFixture) -> None:
            if _HermesFixture.post_count == 0:
                body = handler.rfile.read(
                    int(handler.headers.get("Content-Length", "0"))
                )
                handler._record(body)
                type(handler).post_count += 1
                handler._json(
                    200,
                    {
                        "id": "resp_missing",
                        "object": "response",
                        "status": "completed",
                        "model": "fixture-model",
                        "output": [
                            {
                                "type": "message",
                                "role": "assistant",
                                "content": [
                                    {"type": "output_text", "text": "acknowledged"}
                                ],
                            }
                        ],
                    },
                )
            else:
                original(handler)

        with patch.object(_HermesFixture, "do_POST", missing_usage):
            with self.assertRaisesRegex(ContractError, "created_at"):
                verify_contract(self.base_url, "fixture-secret")

    @pytest.mark.allow_hosts(["127.0.0.1"])
    def test_response_schema_requires_every_documented_nested_field(self) -> None:
        valid = {
            "id": "resp_schema",
            "object": "response",
            "created_at": 1,
            "status": "completed",
            "model": "fixture-model",
            "output": [
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "acknowledged"}],
                }
            ],
            "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
        }
        mutations: tuple[
            tuple[str, Callable[[dict[str, Any]], object]], ...
        ] = (
            ("message type", lambda payload: payload["output"][0].pop("type")),
            ("message role", lambda payload: payload["output"][0].pop("role")),
            (
                "content type",
                lambda payload: payload["output"][0]["content"][0].pop("type"),
            ),
            (
                "content text",
                lambda payload: payload["output"][0]["content"][0].pop("text"),
            ),
            ("input tokens", lambda payload: payload["usage"].pop("input_tokens")),
            ("output tokens", lambda payload: payload["usage"].pop("output_tokens")),
            ("total tokens", lambda payload: payload["usage"].pop("total_tokens")),
        )
        for label, mutate in mutations:
            with self.subTest(label=label):
                payload = json.loads(json.dumps(valid))
                mutate(payload)
                with self.assertRaises(ContractError):
                    _completed_response(payload, "fixture-model")

    @pytest.mark.allow_hosts(["127.0.0.1"])
    def test_rejects_reused_response_id(self) -> None:
        _HermesFixture.reuse_response_id = True
        with self.assertRaisesRegex(ContractError, "reused an id"):
            verify_contract(self.base_url, "fixture-secret")

    @pytest.mark.allow_hosts(["127.0.0.1"])
    def test_each_probe_uses_fresh_conversation_and_marker(self) -> None:
        verify_contract(self.base_url, "fixture-secret")
        first_posts = [
            json.loads(request["body"])
            for request in _HermesFixture.requests
            if request["method"] == "POST"
        ]
        _HermesFixture.requests = []
        _HermesFixture.post_count = 0
        verify_contract(self.base_url, "fixture-secret")
        second_posts = [
            json.loads(request["body"])
            for request in _HermesFixture.requests
            if request["method"] == "POST"
        ]

        self.assertNotEqual(
            first_posts[0]["conversation"], second_posts[0]["conversation"]
        )
        self.assertNotEqual(first_posts[0]["input"], second_posts[0]["input"])

    @pytest.mark.allow_hosts(["127.0.0.1"])
    def test_conversation_and_marker_cannot_collide_within_a_probe(self) -> None:
        with patch(
            "tools.hermes_contract.token_urlsafe",
            side_effect=("same", "same", "different"),
        ):
            self.assertEqual(_new_probe_identifiers(), ("same", "different"))

    @pytest.mark.allow_hosts(["127.0.0.1"])
    def test_stale_marker_replay_does_not_prove_continuity(self) -> None:
        def replay_old_marker(handler: _HermesFixture) -> None:
            body = handler.rfile.read(int(handler.headers.get("Content-Length", "0")))
            handler._record(body)
            type(handler).post_count += 1
            text = "acknowledged" if _HermesFixture.post_count == 1 else "old-marker"
            handler._json(
                200,
                {
                    "id": f"resp_replay_{_HermesFixture.post_count}",
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
                    "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
                },
            )

        with (
            patch.object(_HermesFixture, "do_POST", replay_old_marker),
            patch(
                "tools.hermes_contract.token_urlsafe",
                side_effect=("conversation-token", "new-marker"),
            ),
        ):
            with self.assertRaisesRegex(ContractError, "continuity"):
                verify_contract(self.base_url, "fixture-secret")

    @pytest.mark.allow_hosts(["127.0.0.1"])
    def test_rejects_non_json_response(self) -> None:
        _HermesFixture.response_override = (200, "text/plain", b"not json")
        with self.assertRaisesRegex(ContractError, "content type"):
            verify_contract(self.base_url, "fixture-secret")

    @pytest.mark.allow_hosts(["127.0.0.1"])
    def test_rejects_http_error_without_echoing_response_or_token(self) -> None:
        _HermesFixture.response_override = (
            401,
            "application/json",
            b'{"error":{"message":"private"}}',
        )
        with self.assertRaises(ContractError) as raised:
            verify_contract(self.base_url, "fixture-secret")
        message = str(raised.exception)
        self.assertIn("401", message)
        self.assertNotIn("private", message)
        self.assertNotIn("fixture-secret", message)

    @pytest.mark.allow_hosts(["127.0.0.1"])
    def test_rejects_oversized_response(self) -> None:
        _HermesFixture.response_override = (200, "application/json", b" " * 4097)
        with self.assertRaisesRegex(ContractError, "exceeds 4096 bytes"):
            verify_contract(self.base_url, "fixture-secret", max_response_bytes=4096)

    @pytest.mark.allow_hosts(["127.0.0.1"])
    def test_live_config_requires_explicit_flag_url_and_token(self) -> None:
        names = (
            "HERMES_CONTRACT_LIVE",
            "HERMES_CONTRACT_BASE_URL",
            "HERMES_CONTRACT_TOKEN",
        )
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(live_config_from_env())
        with patch.dict(
            os.environ, {names[0]: "1", names[1]: "https://example.invalid"}, clear=True
        ):
            self.assertIsNone(live_config_from_env())
        with patch.dict(
            os.environ,
            {names[0]: "1", names[1]: "https://example.invalid", names[2]: "secret"},
            clear=True,
        ):
            self.assertEqual(
                live_config_from_env(), ("https://example.invalid", "secret")
            )


class LiveContractTest(unittest.TestCase):
    @unittest.skipUnless(
        os.getenv("HERMES_CONTRACT_LIVE") == "1",
        "live Hermes contract not explicitly enabled",
    )
    def test_explicitly_configured_live_contract(self) -> None:
        config = live_config_from_env()
        if config is None:
            self.fail(
                "live test needs HERMES_CONTRACT_BASE_URL and HERMES_CONTRACT_TOKEN"
            )
        evidence = verify_contract(*config)
        self.assertTrue(evidence.hermes_version)
        self.assertTrue(evidence.model)
        self.assertEqual(evidence.response_status, "completed")


if __name__ == "__main__":
    unittest.main()
