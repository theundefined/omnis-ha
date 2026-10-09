import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, CONF_URL
from homeassistant.core import callback
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

# The demo tenant is a mock server for app store reviews, not a real library.
LIBRARIES = [t for t in KNOWN_TENANTS if not t.get("is_demo")]
LIBRARY_NAMES = [t["name"] for t in LIBRARIES] + [CUSTOM_LIBRARY_NAME]


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
                (t for t in LIBRARIES if t["name"] == selected_lib_name), None
            )
            if tenant:
                self._data[CONF_URL] = tenant["base_url"]
                self._data[CONF_INSTITUTION] = tenant["institution"]
                self._data[CONF_VIEW] = tenant["view"]
                return await self.async_verify_and_create()

            errors["base"] = "invalid_library"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Required(CONF_LIBRARY, default=LIBRARY_NAMES[0]): vol.In(
                        LIBRARY_NAMES
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
            # A dedicated client keeps the login session out of HA's shared client;
            # created in the executor, as building the SSL context does blocking I/O.
            client = await self.hass.async_add_executor_job(
                OmnisClient, self._data[CONF_URL]
            )
            try:
                await client.login(
                    self._data[CONF_USERNAME],
                    self._data[CONF_PASSWORD],
                    self._data[CONF_INSTITUTION],
                    self._data[CONF_VIEW],
                )
                user_info = await client.get_user_info()
            finally:
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
                    vol.Required(
                        CONF_LIBRARY, default=self._data.get(CONF_LIBRARY)
                    ): vol.In(LIBRARY_NAMES),
                }
            ),
            errors=errors,
        )
