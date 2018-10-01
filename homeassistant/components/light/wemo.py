"""
Support for Belkin WeMo lights.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/light.wemo/
"""
import logging
from datetime import timedelta
import requests

from homeassistant import util
from homeassistant.components.light import (
    Light, ATTR_BRIGHTNESS, ATTR_COLOR_TEMP, ATTR_HS_COLOR, ATTR_TRANSITION,
    SUPPORT_BRIGHTNESS, SUPPORT_COLOR_TEMP, SUPPORT_COLOR, SUPPORT_TRANSITION)
from homeassistant.exceptions import PlatformNotReady
import homeassistant.util.color as color_util

DEPENDENCIES = ['wemo']

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)
MIN_TIME_BETWEEN_FORCED_SCANS = timedelta(milliseconds=100)

_LOGGER = logging.getLogger(__name__)

SUPPORT_WEMO = (SUPPORT_BRIGHTNESS | SUPPORT_COLOR_TEMP | SUPPORT_COLOR |
                SUPPORT_TRANSITION)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up discovered WeMo switches."""
    from pywemo import discovery

    if discovery_info is not None:
        location = discovery_info['ssdp_description']
        mac = discovery_info['mac_address']

        try:
            device = discovery.device_from_description(location, mac)
        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout) as err:
            _LOGGER.error('Unable to access %s (%s)', location, err)
            raise PlatformNotReady

        if device.model_name == 'Dimmer':
            add_entities([WemoDimmer(device)])
        else:
            setup_bridge(device, add_entities)


def setup_bridge(bridge, add_entities):
    """Set up a WeMo link."""
    lights = {}

    @util.Throttle(MIN_TIME_BETWEEN_SCANS, MIN_TIME_BETWEEN_FORCED_SCANS)
    def update_lights():
        """Update the WeMo led objects with latest info from the bridge."""
        bridge.bridge_update()

        new_lights = []

        for light_id, device in bridge.Lights.items():
            if light_id not in lights:
                lights[light_id] = WemoLight(device, update_lights)
                new_lights.append(lights[light_id])

        if new_lights:
            add_entities(new_lights)

    update_lights()


class WemoLight(Light):
    """Representation of a WeMo light."""

    def __init__(self, device, update_lights):
        """Initialize the WeMo light."""
        self.light_id = device.name
        self.wemo = device
        self.update_lights = update_lights

    @property
    def unique_id(self):
        """Return the ID of this light."""
        return self.wemo.uniqueID

    @property
    def name(self):
        """Return the name of the light."""
        return self.wemo.name

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self.wemo.state.get('level', 255)

    @property
    def hs_color(self):
        """Return the hs color values of this light."""
        xy_color = self.wemo.state.get('color_xy')
        return color_util.color_xy_to_hs(*xy_color) if xy_color else None

    @property
    def color_temp(self):
        """Return the color temperature of this light in mireds."""
        return self.wemo.state.get('temperature_mireds')

    @property
    def is_on(self):
        """Return true if device is on."""
        return self.wemo.state['onoff'] != 0

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_WEMO

    @property
    def available(self):
        """Return if light is available."""
        return self.wemo.state['available']

    def turn_on(self, **kwargs):
        """Turn the light on."""
        transitiontime = int(kwargs.get(ATTR_TRANSITION, 0))

        hs_color = kwargs.get(ATTR_HS_COLOR)

        if hs_color is not None:
            xy_color = color_util.color_hs_to_xy(*hs_color)
            self.wemo.set_color(xy_color, transition=transitiontime)

        if ATTR_COLOR_TEMP in kwargs:
            colortemp = kwargs[ATTR_COLOR_TEMP]
            self.wemo.set_temperature(mireds=colortemp,
                                      transition=transitiontime)

        if ATTR_BRIGHTNESS in kwargs:
            brightness = kwargs.get(ATTR_BRIGHTNESS, self.brightness or 255)
            self.wemo.turn_on(level=brightness, transition=transitiontime)
        else:
            self.wemo.turn_on(transition=transitiontime)

    def turn_off(self, **kwargs):
        """Turn the light off."""
        transitiontime = int(kwargs.get(ATTR_TRANSITION, 0))
        self.wemo.turn_off(transition=transitiontime)

    def update(self):
        """Synchronize state with bridge."""
        self.update_lights(no_throttle=True)


class WemoDimmer(Light):
    """Representation of a WeMo dimmer."""

    def __init__(self, device):
        """Initialize the WeMo dimmer."""
        self.wemo = device
        self._brightness = None
        self._state = None

    async def async_added_to_hass(self):
        """Register update callback."""
        wemo = self.hass.components.wemo
        # The register method uses a threading condition, so call via executor.
        # and await to wait until the task is done.
        await self.hass.async_add_job(
            wemo.SUBSCRIPTION_REGISTRY.register, self.wemo)
        # The on method just appends to a defaultdict list.
        wemo.SUBSCRIPTION_REGISTRY.on(self.wemo, None, self._update_callback)

    def _update_callback(self, _device, _type, _params):
        """Update the state by the Wemo device."""
        _LOGGER.debug("Subscription update for  %s", _device)
        updated = self.wemo.subscription_update(_type, _params)
        self._update(force_update=(not updated))
        self.schedule_update_ha_state()

    @property
    def unique_id(self):
        """Return the ID of this WeMo dimmer."""
        return self.wemo.serialnumber

    @property
    def name(self):
        """Return the name of the dimmer if any."""
        return self.wemo.name

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_BRIGHTNESS

    @property
    def should_poll(self):
        """No polling needed with subscriptions."""
        return False

    @property
    def brightness(self):
        """Return the brightness of this light between 1 and 100."""
        return self._brightness

    @property
    def is_on(self):
        """Return true if dimmer is on. Standby is on."""
        return self._state

    def _update(self, force_update=True):
        """Update the device state."""
        try:
            self._state = self.wemo.get_state(force_update)
            wemobrightness = int(self.wemo.get_brightness(force_update))
            self._brightness = int((wemobrightness * 255) / 100)
        except AttributeError as err:
            _LOGGER.warning("Could not update status for %s (%s)",
                            self.name, err)

    def turn_on(self, **kwargs):
        """Turn the dimmer on."""
        self.wemo.on()

        # Wemo dimmer switches use a range of [0, 100] to control
        # brightness. Level 255 might mean to set it to previous value
        if ATTR_BRIGHTNESS in kwargs:
            brightness = kwargs[ATTR_BRIGHTNESS]
            brightness = int((brightness / 255) * 100)
        else:
            brightness = 255
        self.wemo.set_brightness(brightness)

    def turn_off(self, **kwargs):
        """Turn the dimmer off."""
        self.wemo.off()
