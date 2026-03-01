"""QVR Surveillance - standalone integration. No pyqvrpro dependency."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.discovery import load_platform
from homeassistant.helpers.typing import ConfigType

from .client import QVRClient, QVRAuthError, QVRConnectionError, QVRPermissionError
from .const import (
    CONF_CLIENT_ID,
    CONF_EXCLUDE_CHANNELS,
    CONF_USE_SSL,
    CONF_VERIFY_SSL,
    DATA_CHANNELS,
    DATA_CLIENT,
    DEFAULT_CLIENT_ID,
    DEFAULT_PORT_HTTP,
    DEFAULT_PORT_HTTPS,
    DEFAULT_USE_SSL,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
    RECONNECT_INTERVAL,
    SERVICE_CHANNEL_GUID,
    SERVICE_PTZ,
    SERVICE_PTZ_ACTION,
    SERVICE_PTZ_DIRECTION,
    SERVICE_START_RECORD,
    SERVICE_STOP_RECORD,
)

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_HOST): cv.string,
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Optional(CONF_PORT): cv.port,
                vol.Optional(CONF_USE_SSL, default=DEFAULT_USE_SSL): cv.boolean,
                vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
                vol.Optional(CONF_EXCLUDE_CHANNELS, default=[]): vol.All(
                    cv.ensure_list_csv, [cv.positive_int]
                ),
                vol.Optional(CONF_CLIENT_ID, default=DEFAULT_CLIENT_ID): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

SERVICE_CHANNEL_RECORD_SCHEMA = vol.Schema({vol.Required(SERVICE_CHANNEL_GUID): cv.string})

SERVICE_PTZ_SCHEMA = vol.Schema(
    {
        vol.Required(SERVICE_CHANNEL_GUID): cv.string,
        vol.Required(SERVICE_PTZ_ACTION): cv.string,
        vol.Optional(SERVICE_PTZ_DIRECTION): cv.string,
    }
)


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up QVR Surveillance."""
    conf = config[DOMAIN]
    user = conf[CONF_USERNAME]
    password = conf[CONF_PASSWORD]
    host = conf[CONF_HOST]
    use_ssl = conf[CONF_USE_SSL]
    verify_ssl = conf[CONF_VERIFY_SSL]
    excluded_channels = conf[CONF_EXCLUDE_CHANNELS]
    client_id = conf[CONF_CLIENT_ID]

    port = conf.get(CONF_PORT)
    if port is None:
        port = DEFAULT_PORT_HTTPS if use_ssl else DEFAULT_PORT_HTTP
    else:
        port = int(port)

    protocol = "https" if use_ssl else "http"

    try:
        client = QVRClient(
            user,
            password,
            host,
            protocol=protocol,
            port=port,
            verify_ssl=verify_ssl,
        )
        channel_resp = client.get_channel_list()
    except QVRConnectionError as ex:
        _LOGGER.warning(
            "Cannot connect to QVR at %s://%s:%s. Will retry in %s s: %s",
            protocol, host, port, RECONNECT_INTERVAL, ex,
        )
        hass.loop.call_later(RECONNECT_INTERVAL, lambda: setup(hass, config))
        return False
    except QVRPermissionError:
        _LOGGER.error("User must have Surveillance Management permission")
        return False
    except QVRAuthError:
        _LOGGER.error("Authentication failed - check credentials")
        return False
    except Exception as ex:
        _LOGGER.exception("Failed to connect to QVR at %s://%s:%s: %s", protocol, host, port, ex)
        return False

    channels = []
    for channel in channel_resp.get("channels", []):
        if channel.get("channel_index", -1) + 1 in excluded_channels:
            continue
        channels.append(channel)

    hass.data[DOMAIN] = {
        DATA_CLIENT: client,
        DATA_CHANNELS: channels,
        "client_id": client_id,
        "config": conf,
    }

    load_platform(hass, "camera", DOMAIN, {}, config)

    from . import views, ws_api

    ws_api.async_setup(hass)
    views.async_setup(hass)

    try:
        from homeassistant.components.media_source.const import MEDIA_SOURCE_DATA
        from .media_source import async_get_media_source

        source = hass.async_run_coroutine_threadsafe(
            async_get_media_source(hass), hass.loop
        ).result()
        hass.data.setdefault(MEDIA_SOURCE_DATA, {})[DOMAIN] = source
    except Exception as ex:
        _LOGGER.warning("Could not register media source: %s", ex)

    def handle_start_record(call: ServiceCall) -> None:
        client.start_recording(call.data[SERVICE_CHANNEL_GUID])

    def handle_stop_record(call: ServiceCall) -> None:
        client.stop_recording(call.data[SERVICE_CHANNEL_GUID])

    def handle_ptz(call: ServiceCall) -> None:
        client.ptz_control(
            call.data[SERVICE_CHANNEL_GUID],
            call.data[SERVICE_PTZ_ACTION],
            direction=call.data.get(SERVICE_PTZ_DIRECTION),
        )

    hass.services.register(
        DOMAIN,
        SERVICE_START_RECORD,
        handle_start_record,
        schema=SERVICE_CHANNEL_RECORD_SCHEMA,
    )
    hass.services.register(
        DOMAIN,
        SERVICE_STOP_RECORD,
        handle_stop_record,
        schema=SERVICE_CHANNEL_RECORD_SCHEMA,
    )
    hass.services.register(
        DOMAIN,
        SERVICE_PTZ,
        handle_ptz,
        schema=SERVICE_PTZ_SCHEMA,
    )

    return True
