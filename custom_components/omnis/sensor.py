from datetime import datetime, date
import logging

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
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

    entities = []
    # Main account sensor (Loans count)
    entities.append(OmnisAccountSensor(coordinator, entry))
    
    # Fines sensor
    entities.append(OmnisFinesSensor(coordinator, entry))

    # Next Due Date sensor
    entities.append(OmnisNextDueSensor(coordinator, entry))
    
    # Branch sensors logic
    branches = set()
    for loan in coordinator.data["loans"]:
        branches.add(loan.location_name)
    
    for branch in branches:
        entities.append(OmnisBranchSensor(coordinator, entry, branch))

    async_add_entities(entities)

class OmnisBaseSensor(CoordinatorEntity, SensorEntity):
    """Base class for Omnis sensors."""

    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self._entry = entry
        self._user_info = coordinator.data["user_info"]

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this entity."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name=f"OMNIS {self._user_info.display_name}",
            manufacturer="Ex Libris",
            model="Primo API",
            configuration_url=self._entry.data.get("url"),
            entry_type=None,
        )

class OmnisAccountSensor(OmnisBaseSensor):
    """Sensor for total loans count."""
    
    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_name = "Wypożyczone książki"
        self._attr_unique_id = f"{entry.entry_id}_total_loans"
        self._attr_icon = "mdi:library"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = "szt."

    @property
    def native_value(self):
        return self.coordinator.data["user_info"].loans_count

    @property
    def extra_state_attributes(self):
        user_info = self.coordinator.data["user_info"]
        return {
            "display_name": user_info.display_name,
            "user_name": user_info.user_name,
            "requests_count": user_info.requests_count,
            "loans": [
                {
                    "title": l.title,
                    "author": l.author,
                    "due_date": l.due_date,
                    "location": l.location_name,
                    "status": l.status,
                    "renewable": l.renewable,
                    "loan_id": l.id
                }
                for l in self.coordinator.data["loans"]
            ]
        }

class OmnisFinesSensor(OmnisBaseSensor):
    """Sensor for fines (kary)."""

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_name = "Naliczone kary"
        self._attr_unique_id = f"{entry.entry_id}_fines"
        self._attr_icon = "mdi:cash-multiple"
        self._attr_device_class = SensorDeviceClass.MONETARY
        self._attr_state_class = SensorStateClass.TOTAL

    @property
    def native_value(self):
        return self.coordinator.data["user_info"].fines_amount

    @property
    def native_unit_of_measurement(self):
        return self.coordinator.data["user_info"].fines_currency

class OmnisNextDueSensor(OmnisBaseSensor):
    """Sensor for the nearest return date."""

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_name = "Najbliższy zwrot"
        self._attr_unique_id = f"{entry.entry_id}_next_due"
        self._attr_icon = "mdi:calendar-clock"
        self._attr_device_class = SensorDeviceClass.TIMESTAMP

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
    def native_value(self):
        loans = self.coordinator.data["loans"]
        if not loans:
            return None
        
        # Filter valid dates and sort
        valid_loans = []
        for loan in loans:
            d = self._parse_date(loan.due_date)
            if d:
                valid_loans.append((d, loan))
        
        if not valid_loans:
            return None
            
        valid_loans.sort(key=lambda x: x[0])
        nearest_date, _ = valid_loans[0]
        
        # Return as aware datetime at end of day
        return dt_util.start_of_local_day(datetime.combine(nearest_date, datetime.min.time()))

    @property
    def extra_state_attributes(self):
        loans = self.coordinator.data["loans"]
        if not loans:
            return {}

        valid_loans = []
        for loan in loans:
            d = self._parse_date(loan.due_date)
            if d:
                valid_loans.append((d, loan))
        
        if not valid_loans:
            return {}

        valid_loans.sort(key=lambda x: x[0])
        nearest_date, nearest_loan = valid_loans[0]
        
        days_until = (nearest_date - date.today()).days

        return {
            "days_until": days_until,
            "book_title": nearest_loan.title,
            "book_author": nearest_loan.author,
            "library_branch": nearest_loan.location_name,
            "due_date_str": nearest_loan.due_date
        }

class OmnisBranchSensor(OmnisBaseSensor):
    """Sensor for loans per branch."""

    def __init__(self, coordinator, entry, branch):
        super().__init__(coordinator, entry)
        self._branch = branch
        self._attr_name = f"Wypożyczenia - {branch}"
        self._attr_unique_id = f"{entry.entry_id}_{branch}"
        self._attr_icon = "mdi:bookshelf"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = "szt."

    @property
    def native_value(self):
        count = 0
        for loan in self.coordinator.data["loans"]:
            if loan.location_name == self._branch:
                count += 1
        return count

    @property
    def extra_state_attributes(self):
        branch_loans = [
            l for l in self.coordinator.data["loans"] if l.location_name == self._branch
        ]
        return {
            "loans": [
                {
                    "title": l.title,
                    "author": l.author,
                    "due_date": l.due_date,
                    "sub_location": l.sub_location_name,
                    "status": l.status,
                    "renewable": l.renewable,
                }
                for l in branch_loans
            ]
        }
