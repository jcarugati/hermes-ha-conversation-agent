"""Tests for the v0.1 executable-route safety boundary."""

from collections.abc import Callable

import pytest

from custom_components.hermes_conversation.safety import (
    OperationClass,
    SensitiveOperationBlocked,
    dispatch_read_only,
)


@pytest.mark.parametrize(
    "operation",
    [
        OperationClass.LOCK,
        OperationClass.ALARM,
        OperationClass.DOOR_OR_GARAGE,
        OperationClass.PET_FEEDING,
        OperationClass.DESTRUCTIVE,
        OperationClass.HOME_ASSISTANT_CONFIGURATION,
        OperationClass.OTHER_ACTION,
        OperationClass.UNCLASSIFIED,
    ],
)
def test_action_bearing_and_unclassified_operations_never_reach_route(
    operation: OperationClass,
) -> None:
    """Block every operation except the explicitly read-only class."""
    calls = 0

    def executable_route() -> str:
        nonlocal calls
        calls += 1
        return "executed"

    with pytest.raises(SensitiveOperationBlocked):
        dispatch_read_only(operation, executable_route)

    assert calls == 0


def test_read_only_status_operation_reaches_distinct_route() -> None:
    """Keep an explicit route for future innocuous status integration."""
    calls = 0

    def read_only_route() -> str:
        nonlocal calls
        calls += 1
        return "all clear"

    assert dispatch_read_only(OperationClass.READ_ONLY_STATUS, read_only_route) == "all clear"
    assert calls == 1


def test_route_has_no_prompt_or_confirmation_override() -> None:
    """An executable route cannot be unlocked by prompt text or voice confirmation."""
    annotations = dispatch_read_only.__annotations__

    assert set(annotations) == {"operation", "route", "return"}
    assert annotations["route"] == Callable[[], object]
