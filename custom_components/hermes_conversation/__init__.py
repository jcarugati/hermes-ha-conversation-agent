"""Config-entry lifecycle for the Hermes Conversation integration."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .client import HermesClient, HermesClientError
from .const import (
    CONF_ALLOW_INSECURE_HTTP,
    CONF_CONNECT_TIMEOUT,
    CONF_MAX_OUTPUT_CHARS,
    CONF_TOKEN,
    CONF_TOTAL_TIMEOUT,
    CONF_URL,
    DEFAULT_CONNECT_TIMEOUT,
    DEFAULT_MAX_OUTPUT_CHARS,
    DEFAULT_TOTAL_TIMEOUT,
)

type HermesConfigEntry = ConfigEntry[HermesClient]


def create_client(hass: HomeAssistant, entry: ConfigEntry[Any]) -> HermesClient:
    """Build a client exclusively from stored entry data and non-secret options."""
    return HermesClient(
        async_get_clientsession(hass),
        entry.data[CONF_URL],
        entry.data[CONF_TOKEN],
        allow_insecure_http=entry.data.get(CONF_ALLOW_INSECURE_HTTP, False),
        connect_timeout=entry.options.get(CONF_CONNECT_TIMEOUT, DEFAULT_CONNECT_TIMEOUT),
        total_timeout=entry.options.get(CONF_TOTAL_TIMEOUT, DEFAULT_TOTAL_TIMEOUT),
        max_output_chars=entry.options.get(CONF_MAX_OUTPUT_CHARS, DEFAULT_MAX_OUTPUT_CHARS),
    )


async def async_validate_connection(hass: HomeAssistant, client: HermesClient) -> None:
    """Validate health, authentication, and the required Responses API capability."""
    del hass
    await client.async_health()
    await client.async_capabilities()


async def async_setup_entry(hass: HomeAssistant, entry: HermesConfigEntry) -> bool:
    """Set up an entry only after revalidating its complete stored configuration."""
    try:
        client = create_client(hass, entry)
        await async_validate_connection(hass, client)
    except (HermesClientError, ValueError) as err:
        raise ConfigEntryNotReady("Hermes endpoint validation failed") from err
    entry.runtime_data = client
    return True


async def async_unload_entry(hass: HomeAssistant, entry: HermesConfigEntry) -> bool:
    """Unload an entry without owning or closing Home Assistant's shared session."""
    del hass, entry
    return True
