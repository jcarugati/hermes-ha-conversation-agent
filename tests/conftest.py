"""Home Assistant test fixtures for the compatibility spike."""

from collections.abc import AsyncGenerator, Generator
from pathlib import Path

import pytest
import pytest_socket
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def loopback_socket_guard() -> None:
    """Permit only loopback TCP plus the Unix sockets asyncio requires."""
    pytest_socket.enable_socket()
    pytest_socket.socket_allow_hosts(["127.0.0.1"], allow_unix_socket=True)


@pytest.fixture(autouse=True)
def custom_components_path(enable_custom_integrations: None) -> Generator[None]:
    """Expose this checkout's custom components to HA's integration loader."""
    import custom_components

    path = str(Path(__file__).parents[1] / "custom_components")
    original_path = custom_components.__path__
    custom_components.__path__ = [*original_path, path]
    yield
    custom_components.__path__ = original_path


@pytest.fixture(autouse=True)
async def setup_homeassistant_component(hass: HomeAssistant) -> AsyncGenerator[None]:
    """Initialize core registries required by the real conversation component."""
    assert await async_setup_component(hass, "homeassistant", {})
    yield
