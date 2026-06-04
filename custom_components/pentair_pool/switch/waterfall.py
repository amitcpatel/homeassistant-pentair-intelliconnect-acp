"""Waterfall pump on/off switch (Relay 2).

Clone of the Relay-1 pump switch (`switch/pump.py`) pointed at the `rb*`
field family. On the acp0118 IntelliConnect install, Relay 1 drives the pool
LIGHTS and Relay 2 drives the WATERFALL pump. The relay state machine (ra0
values) is shared firmware-wide, so the same RA0_* constants apply to rb0.

`is_on` follows physical truth (`rb4` watts > 0) with an optimistic pending
override on toggle, identical to the Relay-1 switch.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from custom_components.pentair_pool.const import (
    FIELD_RB0,
    FIELD_RB4,
    RA0_OFF_NO_SCHEDULE,
    RA0_OFF_SCHEDULED,
    RA0_ON_NO_SCHEDULE,
    RA0_ON_SCHEDULED,
    RA0_TIMER_DONE_SCHEDULED,
)
from custom_components.pentair_pool.entity import PentairPoolEntity
from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import callback

if TYPE_CHECKING:
    from custom_components.pentair_pool.coordinator import PentairPoolDataUpdateCoordinator

SCHEDULE_ON = {RA0_OFF_SCHEDULED, RA0_ON_SCHEDULED, RA0_TIMER_DONE_SCHEDULED}

DESCRIPTION = SwitchEntityDescription(
    key="waterfall_pump",
    name="Waterfall pump",
    icon="mdi:fountain",
    has_entity_name=True,
)


class PentairPoolWaterfallSwitch(SwitchEntity, PentairPoolEntity):
    """Relay 2 (waterfall pump) switch. `is_on` follows rb4 watts."""

    def __init__(
        self,
        coordinator: PentairPoolDataUpdateCoordinator,
        device_id: str,
    ) -> None:
        """Bind to one device."""
        super().__init__(coordinator, DESCRIPTION, device_id)
        self._attr_name = "Waterfall pump"
        self._pending: bool | None = None

    # ----------------------------------------------------------- state read

    def _running_from_truth(self) -> bool | None:
        v = self.field_value(FIELD_RB4)
        if v is None:
            return None
        try:
            return int(v) > 0
        except (TypeError, ValueError):
            return None

    @property
    def is_on(self) -> bool | None:
        """Real running state, with the user's pending override on top."""
        running = self._running_from_truth()
        if self._pending is not None and running != self._pending:
            return self._pending
        return running

    @property
    def extra_state_attributes(self) -> dict[str, str | bool | None]:
        """Expose rb0/rb4 plus any optimistic override currently held."""
        return {
            "rb0": self.field_value(FIELD_RB0),
            "rb4_watts": self.field_value(FIELD_RB4),
            "pending_override": self._pending,
        }

    # ------------------------------------------------- pending reconciliation

    @callback
    def _handle_coordinator_update(self) -> None:
        """Clear the pending override once rb4 matches the requested state."""
        if self._pending is not None:
            running = self._running_from_truth()
            if running is not None and running == self._pending:
                self._pending = None
        super()._handle_coordinator_update()

    # --------------------------------------------------------------- writes

    async def async_turn_on(self, **_: Any) -> None:
        """Manual override: waterfall on. Preserves the schedule bit."""
        sched = (self.field_value(FIELD_RB0) or "") in SCHEDULE_ON
        target = RA0_ON_SCHEDULED if sched else RA0_ON_NO_SCHEDULE
        await self.coordinator.async_set_fields(self._device_id, {FIELD_RB0: target})
        self._pending = True
        self.async_write_ha_state()

    async def async_turn_off(self, **_: Any) -> None:
        """Manual override: waterfall off. Preserves the schedule bit."""
        sched = (self.field_value(FIELD_RB0) or "") in SCHEDULE_ON
        target = RA0_OFF_SCHEDULED if sched else RA0_OFF_NO_SCHEDULE
        await self.coordinator.async_set_fields(self._device_id, {FIELD_RB0: target})
        self._pending = False
        self.async_write_ha_state()
