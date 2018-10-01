"""Config flow to configure the OpenUV component."""

from collections import OrderedDict

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.const import (
    CONF_API_KEY, CONF_ELEVATION, CONF_LATITUDE, CONF_LONGITUDE)
from homeassistant.helpers import aiohttp_client, config_validation as cv

from .const import DOMAIN


@callback
def configured_instances(hass):
    """Return a set of configured OpenUV instances."""
    return set(
        '{0}, {1}'.format(
            entry.data[CONF_LATITUDE], entry.data[CONF_LONGITUDE])
        for entry in hass.config_entries.async_entries(DOMAIN))


@config_entries.HANDLERS.register(DOMAIN)
class OpenUvFlowHandler(config_entries.ConfigFlow):
    """Handle an OpenUV config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize the config flow."""
        pass

    async def async_step_import(self, import_config):
        """Import a config entry from configuration.yaml."""
        return await self.async_step_user(import_config)

    async def async_step_user(self, user_input=None):
        """Handle the start of the config flow."""
        from pyopenuv.util import validate_api_key

        errors = {}

        if user_input is not None:
            identifier = '{0}, {1}'.format(
                user_input.get(CONF_LATITUDE, self.hass.config.latitude),
                user_input.get(CONF_LONGITUDE, self.hass.config.longitude))

            if identifier in configured_instances(self.hass):
                errors['base'] = 'identifier_exists'
            else:
                websession = aiohttp_client.async_get_clientsession(self.hass)
                api_key_validation = await validate_api_key(
                    user_input[CONF_API_KEY], websession)
                if api_key_validation:
                    return self.async_create_entry(
                        title=identifier,
                        data=user_input,
                    )
                errors['base'] = 'invalid_api_key'

        data_schema = OrderedDict()
        data_schema[vol.Required(CONF_API_KEY)] = str
        data_schema[vol.Optional(CONF_LATITUDE)] = cv.latitude
        data_schema[vol.Optional(CONF_LONGITUDE)] = cv.longitude
        data_schema[vol.Optional(CONF_ELEVATION)] = vol.Coerce(float)

        return self.async_show_form(
            step_id='user',
            data_schema=vol.Schema(data_schema),
            errors=errors,
        )
