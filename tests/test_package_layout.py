"""Package-layout checks for the minimal HA/HACS install artifact."""

import json
from pathlib import Path
from struct import unpack
from typing import Any

ROOT = Path(__file__).parents[1]
INTEGRATION = ROOT / "custom_components" / "hermes_conversation"


def _json_object(path: Path) -> dict[str, Any]:
    """Load a JSON file and require an object at its root."""
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_home_assistant_package_has_installable_manifest() -> None:
    """The copied integration directory contains HA's required package files."""
    assert (INTEGRATION / "__init__.py").is_file()
    manifest = _json_object(INTEGRATION / "manifest.json")

    assert manifest == {
        "domain": "hermes_conversation",
        "name": "Hermes Conversation Agent",
        "codeowners": ["@jcarugati"],
        "config_flow": True,
        "dependencies": ["conversation"],
        "documentation": "https://github.com/jcarugati/hermes-ha-conversation-agent",
        "integration_type": "service",
        "issue_tracker": "https://github.com/jcarugati/hermes-ha-conversation-agent/issues",
        "version": "0.0.1",
    }


def test_hacs_repository_metadata_points_to_integration_package() -> None:
    """HACS can identify this repository as a custom integration repository."""
    assert _json_object(ROOT / "hacs.json") == {
        "name": "Hermes Conversation Agent",
    }


def test_bridge_scope_excludes_out_of_scope_runtime_features() -> None:
    """Install metadata enables conversation while excluding later runtime tasks."""
    manifest = _json_object(INTEGRATION / "manifest.json")
    assert manifest["config_flow"] is True
    assert "requirements" not in manifest

    excluded_modules = {
        "diagnostics.py",
        "conversation_cache.py",
        "webhook.py",
    }
    assert excluded_modules.isdisjoint(path.name for path in INTEGRATION.iterdir())
    assert (INTEGRATION / "conversation.py").is_file()


def test_repository_logo_is_packaged_and_documented_without_brands_claim() -> None:
    """The local project logo ships with the integration and is described accurately."""
    logo = INTEGRATION / "assets" / "logo.png"
    content = logo.read_bytes()
    assert content.startswith(b"\x89PNG\r\n\x1a\n")
    assert unpack(">II", content[16:24]) == (1024, 1024)

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "custom_components/hermes_conversation/assets/logo.png" in readme
    assert "not published through Home Assistant Brands" in readme
