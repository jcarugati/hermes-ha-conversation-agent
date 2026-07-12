"""Deterministic tests for the opt-in Hermes contract verifier."""

from __future__ import annotations

import json
import os
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

from tools.hermes_contract import (
    ContractError,
    live_config_from_env,
    verify_contract,
)


class _HermesFixture(BaseHTTPRequestHandler):
    requests: list[dict[str, object]] = []
    response_override: tuple[int, str, bytes] | None = None
    post_count = 0

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
            self._json(200, {"status": "ok", "platform": "hermes-agent", "version": "0.18.2"})
        elif self.path == "/v1/capabilities":
            self._json(
                200,
                {
                    "object": "hermes.api_server.capabilities",
                    "platform": "hermes-agent",
                    "model": "fixture-model",
                    "auth": {"type": "bearer", "required": True},
                    "features": {"responses_api": True},
                    "endpoints": {"responses": {"method": "POST", "path": "/v1/responses"}},
                },
            )
        else:
            self._json(404, {"error": {"message": "not found"}})

    def do_POST(self) -> None:  # noqa: N802
        body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        self._record(body)
        type(self).post_count += 1
        text = "marker-7319" if self.post_count == 2 else "stored"
        self._json(
            200,
            {
                "id": "resp_fixture",
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
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), _HermesFixture)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def test_verifies_narrow_contract_and_allowlisted_request(self) -> None:
        evidence = verify_contract(self.base_url, "fixture-secret", conversation="ha-contract-fixture")

        self.assertEqual(evidence.hermes_version, "0.18.2")
        self.assertEqual(evidence.model, "fixture-model")
        self.assertEqual(evidence.response_status, "completed")
        self.assertTrue(evidence.conversation_continuity)
        self.assertEqual([request["path"] for request in _HermesFixture.requests], [
            "/health", "/v1/capabilities", "/v1/responses", "/v1/responses"
        ])
        post = _HermesFixture.requests[-2]
        self.assertEqual(post["authorization"], "Bearer fixture-secret")
        self.assertEqual(post["accept"], "application/json")
        self.assertEqual(post["content_type"], "application/json")
        self.assertEqual(
            json.loads(post["body"]),
            {
                "model": "fixture-model",
                "input": "Remember the synthetic marker marker-7319. Reply only: stored",
                "conversation": "ha-contract-fixture",
                "stream": False,
            },
        )
        follow_up = json.loads(_HermesFixture.requests[-1]["body"])
        self.assertEqual(
            follow_up,
            {
                "model": "fixture-model",
                "input": "Reply only with the synthetic marker I asked you to remember.",
                "conversation": "ha-contract-fixture",
                "stream": False,
            },
        )
        self.assertIsNone(_HermesFixture.requests[0]["authorization"])

    def test_rejects_missing_responses_capability_before_post(self) -> None:
        original = _HermesFixture.do_GET

        def without_capability(handler: _HermesFixture) -> None:
            if handler.path == "/v1/capabilities":
                handler._record()
                handler._json(200, {"object": "hermes.api_server.capabilities", "model": "m", "features": {}})
            else:
                original(handler)

        with patch.object(_HermesFixture, "do_GET", without_capability):
            with self.assertRaisesRegex(ContractError, "responses_api"):
                verify_contract(self.base_url, "fixture-secret")
        self.assertEqual(len(_HermesFixture.requests), 2)

    def test_rejects_capabilities_without_required_bearer_and_response_route(self) -> None:
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
                        "endpoints": {},
                    },
                )
            else:
                original(handler)

        with patch.object(_HermesFixture, "do_GET", unsupported_contract):
            with self.assertRaisesRegex(ContractError, "required bearer"):
                verify_contract(self.base_url, "fixture-secret")
        self.assertEqual(len(_HermesFixture.requests), 2)

    def test_rejects_non_json_response(self) -> None:
        _HermesFixture.response_override = (200, "text/plain", b"not json")
        with self.assertRaisesRegex(ContractError, "content type"):
            verify_contract(self.base_url, "fixture-secret")

    def test_rejects_http_error_without_echoing_response_or_token(self) -> None:
        _HermesFixture.response_override = (401, "application/json", b'{"error":{"message":"private"}}')
        with self.assertRaises(ContractError) as raised:
            verify_contract(self.base_url, "fixture-secret")
        message = str(raised.exception)
        self.assertIn("401", message)
        self.assertNotIn("private", message)
        self.assertNotIn("fixture-secret", message)

    def test_rejects_oversized_response(self) -> None:
        _HermesFixture.response_override = (200, "application/json", b" " * 4097)
        with self.assertRaisesRegex(ContractError, "exceeds 4096 bytes"):
            verify_contract(self.base_url, "fixture-secret", max_response_bytes=4096)

    def test_live_config_requires_explicit_flag_url_and_token(self) -> None:
        names = ("HERMES_CONTRACT_LIVE", "HERMES_CONTRACT_BASE_URL", "HERMES_CONTRACT_TOKEN")
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(live_config_from_env())
        with patch.dict(os.environ, {names[0]: "1", names[1]: "https://example.invalid"}, clear=True):
            self.assertIsNone(live_config_from_env())
        with patch.dict(
            os.environ,
            {names[0]: "1", names[1]: "https://example.invalid", names[2]: "secret"},
            clear=True,
        ):
            self.assertEqual(live_config_from_env(), ("https://example.invalid", "secret"))


class LiveContractTest(unittest.TestCase):
    @unittest.skipUnless(os.getenv("HERMES_CONTRACT_LIVE") == "1", "live Hermes contract not explicitly enabled")
    def test_explicitly_configured_live_contract(self) -> None:
        config = live_config_from_env()
        self.assertIsNotNone(config, "live test needs HERMES_CONTRACT_BASE_URL and HERMES_CONTRACT_TOKEN")
        evidence = verify_contract(*config, conversation="ha-contract-live")
        self.assertTrue(evidence.hermes_version)
        self.assertTrue(evidence.model)
        self.assertEqual(evidence.response_status, "completed")


if __name__ == "__main__":
    unittest.main()
