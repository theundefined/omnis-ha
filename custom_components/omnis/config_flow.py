import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, CONF_URL
from homeassistant.core import callback
from homeassistant.helpers.httpx_client import get_async_client
import homeassistant.helpers.config_validation as cv

from omnis.client import OmnisClient
from omnis.tenants import KNOWN_TENANTS
from .const import (
    DOMAIN,
    CONF_INSTITUTION,
    CONF_VIEW,
    CONF_LIBRARY,
    DEFAULT_INSTITUTION,
    DEFAULT_VIEW,
    DEFAULT_BASE_URL,
)

CUSTOM_LIBRARY_NAME = "Custom / Własna..."


class OmnisConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self):
        self._data = {}

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            self._data.update(user_input)
            selected_lib_name = user_input[CONF_LIBRARY]

            if selected_lib_name == CUSTOM_LIBRARY_NAME:
                return await self.async_step_custom()

            # Find tenant details
            tenant = next(
                (t for t in KNOWN_TENANTS if t["name"] == selected_lib_name), None
            )
            if tenant:
                self._data[CONF_URL] = tenant["base_url"]
                self._data[CONF_INSTITUTION] = tenant["institution"]
                self._data[CONF_VIEW] = tenant["view"]
                return await self.async_verify_and_create()

            errors["base"] = "invalid_library"

        library_names = [t["name"] for t in KNOWN_TENANTS]

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Required(CONF_LIBRARY, default=library_names[0]): vol.In(
                        library_names
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_custom(self, user_input=None):
        errors = {}
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_verify_and_create()

        return self.async_show_form(
            step_id="custom",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_URL, default=DEFAULT_BASE_URL): str,
                    vol.Required(CONF_INSTITUTION, default=DEFAULT_INSTITUTION): str,
                    vol.Required(CONF_VIEW, default=DEFAULT_VIEW): str,
                }
            ),
            errors=errors,
        )

    async def async_verify_and_create(self):
        errors = {}
        try:
            # Use HA's shared httpx client to avoid blocking I/O on SSL load
            httpx_client = get_async_client(self.hass)
            client = OmnisClient(self._data[CONF_URL], client=httpx_client)

            await client.login(
                self._data[CONF_USERNAME],
                self._data[CONF_PASSWORD],
                self._data[CONF_INSTITUTION],
                self._data[CONF_VIEW],
            )
            user_info = await client.get_user_info()
            # We don't close the shared client
            await client.close()

            return self.async_create_entry(
                title=f"{user_info.display_name} ({self._data[CONF_USERNAME]})",
                data=self._data,
            )
        except Exception:
            errors["base"] = "auth"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_USERNAME, default=self._data.get(CONF_USERNAME)
                    ): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Required(CONF_LIBRARY): vol.In(
                        [t["name"] for t in KNOWN_TENANTS]
                    ),
                }
            ),
            errors=errors,
        )
