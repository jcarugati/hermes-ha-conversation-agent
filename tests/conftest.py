"""Home Assistant test fixtures for the compatibility spike."""

from collections.abc import Generator
from pathlib import Path

import pytest

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def custom_components_path(enable_custom_integrations: None) -> Generator[None]:
    """Expose this checkout's custom components to HA's integration loader."""
    import custom_components

    path = str(Path(__file__).parents[1] / "custom_components")
    custom_components.__path__.append(path)
    yield
    custom_components.__path__.remove(path)
