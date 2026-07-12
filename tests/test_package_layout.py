"""Package-layout checks for the minimal HA/HACS install artifact."""

import json
from pathlib import Path
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
