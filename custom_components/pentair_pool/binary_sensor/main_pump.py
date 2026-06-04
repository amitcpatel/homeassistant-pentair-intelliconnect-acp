"""IntelliFlo VSF main-pump running indicator.

Reports whether the variable-speed main/filter pump is circulating water,
based on the `ifs1` Running_Stopped status field (value 10 = running) with a
power-draw fallback (`ifs3` watts > 0). This pump runs on its own schedule and
is independent of the IntelliConnect relays, so it has no `ra*`/`rb*` entry.

Read-only: there is no write path here by design.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from custom_components.pentair_pool.const import FIELD_IFS1, FIELD_IFS3
from custom_components.pentair_pool.entity import PentairPoolEntity
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)

if TYPE_CHECKING:
    from custom_components.pentair_pool.coordinator import PentairPoolDataUpdateCoordinator

DESCRIPTION = BinarySensorEntityDescription(
    key="main_pump_running",
    name="Main pump running",
    device_class=BinarySensorDeviceClass.RUNNING,
    icon="mdi:pump",
    has_entity_name=True,
)

# ifs1 Running_Stopped: 10 = running (observed); treat anything else as the
# pump being stopped, but fall back to power draw if the status is missing.
_RUNNING_STATUS = "10"


class PentairPoolMainPumpRunningBinarySensor(BinarySensorEntity, PentairPoolEntity):
    """IntelliFlo VSF running indicator (ifs1 == 10, or ifs3 watts > 0)."""

    def __init__(
        self,
        coordinator: PentairPoolDataUpdateCoordinator,
        device_id: str,
    ) -> None:
        """Bind to one device."""
        super().__init__(coordinator, DESCRIPTION, device_id)
        self._attr_name = "Main pump running"

    @property
    def is_on(self) -> bool | None:
        """True when the VSF pump is running."""
        status = self.field_value(FIELD_IFS1)
        if status is not None:
            if status == _RUNNING_STATUS:
                return True
            # Known stopped status; corroborate with power before saying off.
            watts = self.field_value(FIELD_IFS3)
            if watts is not None:
                try:
                    return int(watts) > 0
                except (TypeError, ValueError):
                    pass
            return False
        # No status field: fall back to power draw alone.
        watts = self.field_value(FIELD_IFS3)
        if watts is None:
            return None
        try:
            return int(watts) > 0
        except (TypeError, ValueError):
            return None
