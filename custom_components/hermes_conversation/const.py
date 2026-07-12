"""Constants for the Hermes Conversation integration."""

from typing import Final

from .client import (
    DEFAULT_CONNECT_TIMEOUT,
    DEFAULT_MAX_OUTPUT_CHARS,
    DEFAULT_TOTAL_TIMEOUT,
)

DOMAIN: Final = "hermes_conversation"

CONF_URL: Final = "url"
CONF_TOKEN: Final = "token"  # noqa: S105 - configuration key, not a credential value
CONF_ALLOW_INSECURE_HTTP: Final = "allow_insecure_http"
CONF_ACKNOWLEDGE_INSECURE_HTTP: Final = "acknowledge_insecure_http"
CONF_CONNECT_TIMEOUT: Final = "connect_timeout"
CONF_TOTAL_TIMEOUT: Final = "total_timeout"
CONF_MAX_OUTPUT_CHARS: Final = "max_output_chars"

__all__ = [
    "CONF_ACKNOWLEDGE_INSECURE_HTTP",
    "CONF_ALLOW_INSECURE_HTTP",
    "CONF_CONNECT_TIMEOUT",
    "CONF_MAX_OUTPUT_CHARS",
    "CONF_TOKEN",
    "CONF_TOTAL_TIMEOUT",
    "CONF_URL",
    "DEFAULT_CONNECT_TIMEOUT",
    "DEFAULT_MAX_OUTPUT_CHARS",
    "DEFAULT_TOTAL_TIMEOUT",
    "DOMAIN",
]
