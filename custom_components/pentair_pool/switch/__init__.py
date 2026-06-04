"""Switch platform for pentair_pool."""

from __future__ import annotations

from typing import TYPE_CHECKING

from custom_components.pentair_pool.const import (
    FIELD_RA0,
    FIELD_RB0,
    PARALLEL_UPDATES as PARALLEL_UPDATES,
)

from .pump import PentairPoolPumpSwitch
from .schedule import PentairPoolDailyScheduleSwitch
from .waterfall import PentairPoolWaterfallSwitch

if TYPE_CHECKING:
    from custom_components.pentair_pool.data import PentairPoolConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    entry: PentairPoolConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the switch platform.

    Relay-1 pump + Daily Schedule switches are gated on `ra0`. The Relay-2
    waterfall switch is gated independently on `rb0`, so installs without a
    second relay won't get an orphan waterfall entity.
    """
    coordinator = entry.runtime_data.coordinator
    entities = []
    for device_id, dev in (coordinator.data or {}).items():
        fields = dev.get("fields") or {}
        if FIELD_RA0 in fields:
            entities.append(PentairPoolPumpSwitch(coordinator, device_id))
            entities.append(PentairPoolDailyScheduleSwitch(coordinator, device_id))
        if FIELD_RB0 in fields:
            entities.append(PentairPoolWaterfallSwitch(coordinator, device_id))
    async_add_entities(entities)
