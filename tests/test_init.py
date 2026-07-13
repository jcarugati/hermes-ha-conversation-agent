"""Tests for config-entry setup, reload, and unload."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import (  # type: ignore[import-untyped]
    MockConfigEntry,
)

from custom_components.hermes_conversation.client import (
    HermesAuthenticationError,
    HermesCapabilities,
    HermesClient,
    HermesClientError,
    HermesProtocolError,
)
from custom_components.hermes_conversation.const import (
    CONF_ALLOW_INSECURE_HTTP,
    CONF_TOKEN,
    CONF_URL,
    DOMAIN,
)

HOME_CAPABILITIES = HermesCapabilities(
    model="validated-model",
    tool_policy="none",
    mcp_policy="none",
    server_enforced=True,
)


async def test_setup_revalidates_and_stores_runtime_client(hass: HomeAssistant) -> None:
    """Every config-entry setup validates before becoming loaded."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_URL: "https://hermes.example.test",
            CONF_TOKEN: "secret",
            CONF_ALLOW_INSECURE_HTTP: False,
        },
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.hermes_conversation.async_validate_connection",
        new=AsyncMock(return_value=HOME_CAPABILITIES),
    ) as validate:
        assert await hass.config_entries.async_setup(entry.entry_id)

    assert entry.state is ConfigEntryState.LOADED
    assert validate.await_args is not None
    assert entry.runtime_data.client is validate.await_args.args[1]
    assert entry.runtime_data.model == "validated-model"
    validate.assert_awaited_once()


async def test_unavailable_setup_raises_not_ready(hass: HomeAssistant) -> None:
    """Unavailable Hermes keeps the entry retryable and unconfigured at runtime."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_URL: "https://hermes.example.test", CONF_TOKEN: "secret"},
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.hermes_conversation.async_validate_connection",
        new=AsyncMock(side_effect=HermesClientError),
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_generic_responses_api_without_home_security_policy_cannot_setup(
    hass: HomeAssistant,
) -> None:
    """Stored generic Hermes entries remain fail-closed during lifecycle setup."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_URL: "https://generic-hermes.example.test", CONF_TOKEN: "secret"},
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.hermes_conversation.async_validate_connection",
        new=AsyncMock(
            side_effect=HermesProtocolError(
                "/v1/capabilities does not advertise the exact no-tools security policy"
            )
        ),
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)

    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert not hasattr(entry, "runtime_data")


@pytest.mark.parametrize("status", [401, 403])
async def test_health_rejection_is_retryable_without_reauth(
    hass: HomeAssistant, status: int
) -> None:
    """Unauthenticated health failures keep setup retryable without reauth."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="https://hermes.example.test",
        data={CONF_URL: "https://hermes.example.test", CONF_TOKEN: "secret"},
    )
    entry.add_to_hass(hass)
    client = MagicMock(spec=HermesClient)
    client.async_health = AsyncMock(
        side_effect=HermesProtocolError(f"GET /health returned HTTP {status}")
    )
    client.async_capabilities = AsyncMock()

    with patch("custom_components.hermes_conversation.create_client", return_value=client):
        assert not await hass.config_entries.async_setup(entry.entry_id)

    assert entry.state is ConfigEntryState.SETUP_RETRY
    client.async_capabilities.assert_not_awaited()
    assert hass.config_entries.flow.async_progress_by_handler(DOMAIN) == []


@pytest.mark.parametrize("status", [401, 403])
async def test_capabilities_rejection_starts_reauth(hass: HomeAssistant, status: int) -> None:
    """Authenticated capabilities failures enter Home Assistant's reauth lifecycle."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="https://hermes.example.test",
        data={CONF_URL: "https://hermes.example.test", CONF_TOKEN: "expired"},
    )
    entry.add_to_hass(hass)
    client = MagicMock(spec=HermesClient)
    client.async_health = AsyncMock()
    client.async_capabilities = AsyncMock(
        side_effect=HermesAuthenticationError(f"GET /v1/capabilities returned HTTP {status}")
    )

    with patch("custom_components.hermes_conversation.create_client", return_value=client):
        assert not await hass.config_entries.async_setup(entry.entry_id)

    assert entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == "reauth"


async def test_unload_clears_runtime_and_reload_revalidates(hass: HomeAssistant) -> None:
    """Unload releases runtime state; reload creates and validates a fresh client."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_URL: "https://hermes.example.test", CONF_TOKEN: "secret"},
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.hermes_conversation.async_validate_connection",
        new=AsyncMock(return_value=HOME_CAPABILITIES),
    ) as validate:
        assert await hass.config_entries.async_setup(entry.entry_id)
        first_client = entry.runtime_data
        assert await hass.config_entries.async_unload(entry.entry_id)
        assert not hasattr(entry, "runtime_data")
        await hass.config_entries.async_reload(entry.entry_id)

    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data is not first_client
    assert validate.await_count == 2
