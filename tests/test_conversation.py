"""Scope guard for the config-lifecycle tracker task."""

from pathlib import Path


def test_config_lifecycle_does_not_add_conversation_runtime() -> None:
    """This task must not register an entity or add bridge behavior."""
    integration = Path(__file__).parents[1] / "custom_components" / "hermes_conversation"
    assert not (integration / "conversation.py").exists()
