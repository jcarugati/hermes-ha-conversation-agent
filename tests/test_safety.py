"""Tests for the HA-local read-only/status capability declaration."""

import inspect

import pytest

from custom_components.hermes_conversation import safety


def test_public_policy_exposes_no_executable_route() -> None:
    """The local policy contract has no function that can dispatch work."""
    public_functions = {
        name: value
        for name, value in vars(safety).items()
        if not name.startswith("_") and inspect.isfunction(value)
    }

    assert public_functions == {}


def test_high_impact_callable_cannot_be_passed_or_executed() -> None:
    """The public request constructor cannot receive an executable capability."""
    calls = 0

    def high_impact_action() -> None:
        nonlocal calls
        calls += 1

    with pytest.raises(TypeError):
        safety.ReadOnlyStatusRequest(high_impact_action)  # type: ignore[call-arg]

    assert calls == 0


def test_read_only_status_request_is_data_only_and_capability_bound() -> None:
    """The only request declaration is immutable and fixed to status reads."""
    request = safety.ReadOnlyStatusRequest()

    assert request.capability == safety.READ_ONLY_STATUS
    assert inspect.signature(safety.ReadOnlyStatusRequest).parameters == {}
    with pytest.raises((AttributeError, TypeError)):
        request.capability = "lock"  # type: ignore[misc]


def test_allowlist_contains_only_read_only_status_request() -> None:
    """The local allowlist declares status reads without executing anything."""
    assert safety.ALLOWED_REQUEST_TYPES == frozenset({safety.ReadOnlyStatusRequest})
