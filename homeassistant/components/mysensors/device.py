"""Handle MySensors devices."""
import logging

from homeassistant.const import (
    ATTR_BATTERY_LEVEL, STATE_OFF, STATE_ON)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import SIGNAL_CALLBACK

_LOGGER = logging.getLogger(__name__)

ATTR_CHILD_ID = 'child_id'
ATTR_DESCRIPTION = 'description'
ATTR_DEVICE = 'device'
ATTR_NODE_ID = 'node_id'
MYSENSORS_PLATFORM_DEVICES = 'mysensors_devices_{}'


def get_mysensors_devices(hass, domain):
    """Return MySensors devices for a platform."""
    if MYSENSORS_PLATFORM_DEVICES.format(domain) not in hass.data:
        hass.data[MYSENSORS_PLATFORM_DEVICES.format(domain)] = {}
    return hass.data[MYSENSORS_PLATFORM_DEVICES.format(domain)]


class MySensorsDevice:
    """Representation of a MySensors device."""

    def __init__(self, gateway, node_id, child_id, name, value_type):
        """Set up the MySensors device."""
        self.gateway = gateway
        self.node_id = node_id
        self.child_id = child_id
        self._name = name
        self.value_type = value_type
        child = gateway.sensors[node_id].children[child_id]
        self.child_type = child.type
        self._values = {}

    @property
    def name(self):
        """Return the name of this entity."""
        return self._name

    @property
    def device_state_attributes(self):
        """Return device specific state attributes."""
        node = self.gateway.sensors[self.node_id]
        child = node.children[self.child_id]
        attr = {
            ATTR_BATTERY_LEVEL: node.battery_level,
            ATTR_CHILD_ID: self.child_id,
            ATTR_DESCRIPTION: child.description,
            ATTR_DEVICE: self.gateway.device,
            ATTR_NODE_ID: self.node_id,
        }

        set_req = self.gateway.const.SetReq

        for value_type, value in self._values.items():
            attr[set_req(value_type).name] = value

        return attr

    async def async_update(self):
        """Update the controller with the latest value from a sensor."""
        node = self.gateway.sensors[self.node_id]
        child = node.children[self.child_id]
        set_req = self.gateway.const.SetReq
        for value_type, value in child.values.items():
            _LOGGER.debug(
                "Entity update: %s: value_type %s, value = %s",
                self._name, value_type, value)
            if value_type in (set_req.V_ARMED, set_req.V_LIGHT,
                              set_req.V_LOCK_STATUS, set_req.V_TRIPPED):
                self._values[value_type] = (
                    STATE_ON if int(value) == 1 else STATE_OFF)
            elif value_type == set_req.V_DIMMER:
                self._values[value_type] = int(value)
            else:
                self._values[value_type] = value


class MySensorsEntity(MySensorsDevice, Entity):
    """Representation of a MySensors entity."""

    @property
    def should_poll(self):
        """Return the polling state. The gateway pushes its states."""
        return False

    @property
    def available(self):
        """Return true if entity is available."""
        return self.value_type in self._values

    @callback
    def async_update_callback(self):
        """Update the entity."""
        self.async_schedule_update_ha_state(True)

    async def async_added_to_hass(self):
        """Register update callback."""
        dev_id = id(self.gateway), self.node_id, self.child_id, self.value_type
        async_dispatcher_connect(
            self.hass, SIGNAL_CALLBACK.format(*dev_id),
            self.async_update_callback)
