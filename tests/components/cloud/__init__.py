"""Tests for the cloud component."""
from unittest.mock import patch
from homeassistant.setup import async_setup_component
from homeassistant.components import cloud

from jose import jwt

from tests.common import mock_coro


def mock_cloud(hass, config={}):
    """Mock cloud."""
    with patch('homeassistant.components.cloud.Cloud.async_start',
               return_value=mock_coro()):
        assert hass.loop.run_until_complete(async_setup_component(
            hass, cloud.DOMAIN, {
                'cloud': config
            }))

    hass.data[cloud.DOMAIN]._decode_claims = \
        lambda token: jwt.get_unverified_claims(token)


def mock_cloud_prefs(hass, prefs={}):
    """Fixture for cloud component."""
    prefs_to_set = {
        cloud.STORAGE_ENABLE_ALEXA: True,
        cloud.STORAGE_ENABLE_GOOGLE: True,
    }
    prefs_to_set.update(prefs)
    hass.data[cloud.DOMAIN]._prefs = prefs_to_set
    return prefs_to_set
