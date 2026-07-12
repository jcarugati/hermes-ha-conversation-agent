"""Tests for the HA-local read-only/status policy contract."""

import inspect
from collections.abc import Callable

import pytest

from custom_components.hermes_conversation import safety

HIGH_IMPACT_OR_UNCLASSIFIED_OPERATIONS = (
    "lock",
    "alarm",
    "door_or_garage",
    "pet_feeding",
    "destructive",
    "home_assistant_configuration",
    "other_action",
    "unclassified",
)


def test_public_policy_exposes_only_read_status() -> None:
    """Make action-bearing and generic dispatch routes unavailable by construction."""
    public_routes = {
        name: value
        for name, value in vars(safety).items()
        if not name.startswith("_") and inspect.isfunction(value)
    }

    assert public_routes == {"read_status": safety.read_status}


@pytest.mark.parametrize("operation", HIGH_IMPACT_OR_UNCLASSIFIED_OPERATIONS)
def test_no_public_policy_route_dispatches_a_supplied_operation(operation: str) -> None:
    """A caller-supplied operation label can never authorize callback execution."""
    calls = 0

    def executable_route() -> str:
        nonlocal calls
        calls += 1
        return "executed"

    with pytest.raises(TypeError):
        safety.read_status(operation, executable_route)  # type: ignore[arg-type, call-arg]

    assert calls == 0


def test_read_status_invokes_its_capability_specific_route() -> None:
    """Keep one explicit contract for a future innocuous status integration."""
    calls = 0

    def read_status_route() -> str:
        nonlocal calls
        calls += 1
        return "all clear"

    assert safety.read_status(read_status_route) == "all clear"
    assert calls == 1


def test_read_status_has_no_operation_prompt_or_confirmation_input() -> None:
    """Labels, prompt text, and spoken confirmation cannot unlock another route."""
    assert inspect.signature(safety.read_status).parameters.keys() == {"route"}
    assert safety.read_status.__annotations__ == {
        "route": Callable[[], object],
        "return": object,
    }
