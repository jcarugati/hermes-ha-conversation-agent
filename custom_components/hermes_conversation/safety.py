"""HA-local prototype contract exposing only read-only/status work."""

from collections.abc import Callable


def read_status(route: Callable[[], object]) -> object:
    """Invoke the explicit read-only/status capability route."""
    return route()
