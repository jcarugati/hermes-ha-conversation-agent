"""Tests for config-entry setup, reload, and unload."""

from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import (  # type: ignore[import-untyped]
    MockConfigEntry,
)

from custom_components.hermes_conversation.client import HermesClientError
from custom_components.hermes_conversation.const import (
    CONF_ALLOW_INSECURE_HTTP,
    CONF_TOKEN,
    CONF_URL,
    DOMAIN,
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
        new=AsyncMock(),
    ) as validate:
        assert await hass.config_entries.async_setup(entry.entry_id)

    assert entry.state is ConfigEntryState.LOADED
    assert validate.await_args is not None
    assert entry.runtime_data is validate.await_args.args[1]
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


async def test_unload_clears_runtime_and_reload_revalidates(hass: HomeAssistant) -> None:
    """Unload releases runtime state; reload creates and validates a fresh client."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_URL: "https://hermes.example.test", CONF_TOKEN: "secret"},
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.hermes_conversation.async_validate_connection",
        new=AsyncMock(),
    ) as validate:
        assert await hass.config_entries.async_setup(entry.entry_id)
        first_client = entry.runtime_data
        assert await hass.config_entries.async_unload(entry.entry_id)
        assert not hasattr(entry, "runtime_data")
        await hass.config_entries.async_reload(entry.entry_id)

    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data is not first_client
    assert validate.await_count == 2
