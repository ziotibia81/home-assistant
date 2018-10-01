"""
Support for Actions on Google Assistant Smart Home Control.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/google_assistant/
"""
import asyncio
import logging
from typing import Dict, Any

import aiohttp
import async_timeout

import voluptuous as vol

# Typing imports
from homeassistant.core import HomeAssistant, ServiceCall

from homeassistant.const import CONF_NAME
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    DOMAIN, CONF_PROJECT_ID, CONF_EXPOSE_BY_DEFAULT, DEFAULT_EXPOSE_BY_DEFAULT,
    CONF_EXPOSED_DOMAINS, DEFAULT_EXPOSED_DOMAINS, CONF_API_KEY,
    SERVICE_REQUEST_SYNC, REQUEST_SYNC_BASE_URL, CONF_ENTITY_CONFIG,
    CONF_EXPOSE, CONF_ALIASES, CONF_ROOM_HINT
)
from .http import async_register_http

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['http']

DEFAULT_AGENT_USER_ID = 'home-assistant'

ENTITY_SCHEMA = vol.Schema({
    vol.Optional(CONF_NAME): cv.string,
    vol.Optional(CONF_EXPOSE): cv.boolean,
    vol.Optional(CONF_ALIASES): vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(CONF_ROOM_HINT): cv.string
})

GOOGLE_ASSISTANT_SCHEMA = vol.Schema({
    vol.Required(CONF_PROJECT_ID): cv.string,
    vol.Optional(CONF_EXPOSE_BY_DEFAULT,
                 default=DEFAULT_EXPOSE_BY_DEFAULT): cv.boolean,
    vol.Optional(CONF_EXPOSED_DOMAINS,
                 default=DEFAULT_EXPOSED_DOMAINS): cv.ensure_list,
    vol.Optional(CONF_API_KEY): cv.string,
    vol.Optional(CONF_ENTITY_CONFIG): {cv.entity_id: ENTITY_SCHEMA}
}, extra=vol.PREVENT_EXTRA)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: GOOGLE_ASSISTANT_SCHEMA
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass: HomeAssistant, yaml_config: Dict[str, Any]):
    """Activate Google Actions component."""
    config = yaml_config.get(DOMAIN, {})
    api_key = config.get(CONF_API_KEY)
    async_register_http(hass, config)

    async def request_sync_service_handler(call: ServiceCall):
        """Handle request sync service calls."""
        websession = async_get_clientsession(hass)
        try:
            with async_timeout.timeout(5, loop=hass.loop):
                res = await websession.post(
                    REQUEST_SYNC_BASE_URL,
                    params={'key': api_key},
                    json={'agent_user_id': call.context.user_id})
                _LOGGER.info("Submitted request_sync request to Google")
                res.raise_for_status()
        except aiohttp.ClientResponseError:
            body = await res.read()
            _LOGGER.error(
                'request_sync request failed: %d %s', res.status, body)
        except (asyncio.TimeoutError, aiohttp.ClientError):
            _LOGGER.error("Could not contact Google for request_sync")

    # Register service only if api key is provided
    if api_key is not None:
        hass.services.async_register(
            DOMAIN, SERVICE_REQUEST_SYNC, request_sync_service_handler)

    return True
