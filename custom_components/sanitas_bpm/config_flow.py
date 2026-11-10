"""Config flow: monitor address, systolic threshold and the two household names."""
import re

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_ADDRESS

from .const import CONF_HIGH_NAME, CONF_LOW_NAME, CONF_THRESHOLD, DOMAIN

SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ADDRESS): str,
        vol.Required(CONF_THRESHOLD, default=110): vol.All(int, vol.Range(min=60, max=200)),
        vol.Required(CONF_HIGH_NAME): str,
        vol.Required(CONF_LOW_NAME): str,
    }
)


class SanitasBpmConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            address = user_input[CONF_ADDRESS].strip().upper()
            if re.fullmatch(r"([0-9A-F]{2}:){5}[0-9A-F]{2}", address):
                await self.async_set_unique_id(address)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="Sanitas SBM 67", data={**user_input, CONF_ADDRESS: address}
                )
            errors[CONF_ADDRESS] = "invalid_address"
        return self.async_show_form(step_id="user", data_schema=SCHEMA, errors=errors)
