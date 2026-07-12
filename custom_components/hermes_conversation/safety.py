"""Non-executing HA-local declaration for read-only/status work."""

import dataclasses

READ_ONLY_STATUS = "read_only_status"


@dataclasses.dataclass(frozen=True, slots=True)
class ReadOnlyStatusRequest:
    """Declare the sole HA-local capability without carrying executable input."""

    capability: str = dataclasses.field(init=False, default=READ_ONLY_STATUS)


ALLOWED_REQUEST_TYPES = frozenset({ReadOnlyStatusRequest})
