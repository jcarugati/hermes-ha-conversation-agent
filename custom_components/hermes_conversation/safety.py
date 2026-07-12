"""Fail-closed executable-route policy for the v0.1 integration boundary."""

from collections.abc import Callable
from enum import Enum


class OperationClass(Enum):
    """Security classes understood by the HA-side v0.1 boundary."""

    READ_ONLY_STATUS = "read_only_status"
    LOCK = "lock"
    ALARM = "alarm"
    DOOR_OR_GARAGE = "door_or_garage"
    PET_FEEDING = "pet_feeding"
    DESTRUCTIVE = "destructive"
    HOME_ASSISTANT_CONFIGURATION = "home_assistant_configuration"
    OTHER_ACTION = "other_action"
    UNCLASSIFIED = "unclassified"


class SensitiveOperationBlocked(Exception):
    """Raised before an operation can reach an executable route."""


def dispatch_read_only(operation: OperationClass, route: Callable[[], object]) -> object:
    """Invoke the sole v0.1 route only for explicitly read-only status work."""
    if operation is not OperationClass.READ_ONLY_STATUS:
        raise SensitiveOperationBlocked("operation is not allowed by the v0.1 safety policy")
    return route()
