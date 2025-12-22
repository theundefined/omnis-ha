from datetime import datetime, timedelta, date
import logging

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.device_registry import DeviceInfo
import homeassistant.util.dt as dt_util

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]

    async_add_entities([OmnisCalendar(coordinator, entry)])

class OmnisCalendar(CoordinatorEntity, CalendarEntity):
    """Representation of an OMNIS Calendar."""

    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self._entry = entry
        self._user_info = coordinator.data["user_info"]
        self._attr_name = f"Terminy zwrotów - {self._user_info.display_name}"
        self._attr_unique_id = f"{entry.entry_id}_calendar"
        self._attr_icon = "mdi:calendar-book"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name=f"OMNIS {self._user_info.display_name}",
            manufacturer="Ex Libris",
            model="Primo API",
            configuration_url=self._entry.data.get("url"),
            entry_type=None,
        )

    def _parse_date(self, date_str):
        """Try to parse date string from API."""
        formats = ["%Y%m%d", "%Y-%m-%d", "%d/%m/%Y"]
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue
        return None

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""
        # Not strictly necessary if we implement async_get_events, 
        # but good for state display.
        events = self._get_events_list()
        # Filter for future events
        now = dt_util.now().date()
        future_events = [e for e in events if e.start >= now]
        
        if future_events:
            future_events.sort(key=lambda x: x.start)
            return future_events[0]
        return None

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Return calendar events within a datetime range."""
        events = self._get_events_list()
        
        # Convert range to date for comparison
        start = start_date.date()
        end = end_date.date()

        return [
            event for event in events
            if event.start >= start and event.end <= end
        ]

    def _get_events_list(self) -> list[CalendarEvent]:
        """Convert loans to CalendarEvents."""
        events = []
        loans = self.coordinator.data.get("loans", [])
        
        for loan in loans:
            loan_date = self._parse_date(loan.due_date)
            if not loan_date:
                continue
            
            # Create description
            desc = [
                f"Autor: {loan.author}",
                f"Filia: {loan.location_name}"
            ]
            if loan.sub_location_name:
                desc.append(f"Lokalizacja: {loan.sub_location_name}")
            
            if loan.renewable:
                desc.append("✅ Możliwa prolongata")
            else:
                desc.append("❌ Brak prolongaty")

            events.append(
                CalendarEvent(
                    summary=loan.title,
                    start=loan_date,
                    end=loan_date + timedelta(days=1), # All day event
                    description="\n".join(desc),
                    location=loan.location_name
                )
            )
        return events
