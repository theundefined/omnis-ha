from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, CONF_URL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.httpx_client import get_async_client

from omnis.client import OmnisClient
from .const import DOMAIN, CONF_INSTITUTION, CONF_VIEW, DEFAULT_BASE_URL

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR, Platform.CALENDAR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    httpx_client = get_async_client(hass)
    client = OmnisClient(
        entry.data.get(CONF_URL, DEFAULT_BASE_URL), client=httpx_client
    )

    async def async_update_data():
        try:
            if not client.token:
                await client.login(
                    entry.data[CONF_USERNAME],
                    entry.data[CONF_PASSWORD],
                    entry.data.get(CONF_INSTITUTION),
                    entry.data.get(CONF_VIEW),
                )

            user_info = await client.get_user_info()
            loans = await client.get_loans()
            return {"user_info": user_info, "loans": loans}
        except Exception as err:
            client.token = None  # Force re-login on next fail
            raise UpdateFailed(f"Error communicating with API: {err}")

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=DOMAIN,
        update_method=async_update_data,
        update_interval=timedelta(hours=1),  # Library data doesn't change often
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "coordinator": coordinator,
        "client": client,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def handle_renew_loan(call):
        entry_id = call.data["config_entry_id"]
        loan_id = call.data["loan_id"]

        if entry_id not in hass.data[DOMAIN]:
            raise ValueError("Invalid config entry ID")

        client = hass.data[DOMAIN][entry_id]["client"]
        await client.renew_loan(loan_id)
        # Refresh data after renewal
        await hass.data[DOMAIN][entry_id]["coordinator"].async_refresh()

    hass.services.async_register(DOMAIN, "renew_loan", handle_renew_loan)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        data = hass.data[DOMAIN].pop(entry.entry_id)
        # We do NOT close the client here because it's shared (get_async_client)
        # await data["client"].close()
        # But our OmnisClient.close() now handles checking _close_client flag, so it's safe to call it.
        await data["client"].close()

    return unload_ok
