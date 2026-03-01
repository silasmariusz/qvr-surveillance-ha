"""QVR Surveillance - standalone integration. No pyqvrpro dependency."""

from __future__ import annotations

import asyncio
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
    SERVICE_CHANNEL_INDEX,
    SERVICE_ENTITY_ID,
    SERVICE_PTZ,
    SERVICE_PTZ_ACTION,
    SERVICE_PTZ_DIRECTION,
    SERVICE_RECONNECT,
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

def _resolve_guid(
    hass: HomeAssistant,
    *,
    guid: str | None = None,
    entity_id: str | None = None,
    channel_index: int | None = None,
) -> str:
    """Resolve channel GUID from guid, entity_id, or channel_index."""
    if guid:
        return guid
    if entity_id:
        state = hass.states.get(entity_id)
        if state and state.attributes.get("qvr_guid"):
            return state.attributes["qvr_guid"]
        raise ValueError(f"Entity {entity_id} has no qvr_guid attribute")
    if channel_index is not None:
        data = hass.data.get(DOMAIN)
        if not data:
            raise ValueError("QVR Surveillance not configured")
        channels = data.get(DATA_CHANNELS, [])
        # channel_index is 1-based; API uses 0-based channel_index
        for ch in channels:
            if ch.get("channel_index", -1) + 1 == channel_index:
                return ch.get("guid", "")
        raise ValueError(f"No channel with index {channel_index}")
    raise ValueError("Must provide guid, entity_id, or channel_index")


def _require_guid_source(value):
    if not any((value.get(SERVICE_CHANNEL_GUID), value.get(SERVICE_ENTITY_ID), value.get(SERVICE_CHANNEL_INDEX))):
        raise vol.Invalid("Must provide guid, entity_id, or channel_index")
    return value


SERVICE_CHANNEL_RECORD_SCHEMA = vol.Schema(
    vol.All(
        {
            vol.Optional(SERVICE_CHANNEL_GUID): cv.string,
            vol.Optional(SERVICE_ENTITY_ID): cv.entity_id,
            vol.Optional(SERVICE_CHANNEL_INDEX): vol.All(vol.Coerce(int), vol.Range(min=1)),
        },
        _require_guid_source,
    )
)

SERVICE_PTZ_SCHEMA = vol.Schema(
    vol.All(
        {
            vol.Optional(SERVICE_CHANNEL_GUID): cv.string,
            vol.Optional(SERVICE_ENTITY_ID): cv.entity_id,
            vol.Optional(SERVICE_CHANNEL_INDEX): vol.All(vol.Coerce(int), vol.Range(min=1)),
            vol.Required(SERVICE_PTZ_ACTION): cv.string,
            vol.Optional(SERVICE_PTZ_DIRECTION): cv.string,
        },
        _require_guid_source,
    )
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
    raw_channels = channel_resp.get("channels") or channel_resp.get("channel") or []
    for i, ch in enumerate(raw_channels):
        idx = ch.get("channel_index", ch.get("channelIndex", i))
        if isinstance(idx, (int, float)) and int(idx) + 1 in excluded_channels:
            continue
        guid = ch.get("guid") or ch.get("channelGUID") or ch.get("channel_guid") or ""
        name = ch.get("channel_name") or ch.get("channelName") or ch.get("name") or f"Channel {i + 1}"
        channels.append({
            "guid": guid,
            "channel_index": int(idx) if isinstance(idx, (int, float)) else i,
            "channel_name": name,
            "name": name,
            "model": ch.get("model", ""),
            "brand": ch.get("brand", ""),
        })

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

        future = asyncio.run_coroutine_threadsafe(
            async_get_media_source(hass), hass.loop
        )
        source = future.result(timeout=10)
        hass.data.setdefault(MEDIA_SOURCE_DATA, {})[DOMAIN] = source
    except Exception as ex:
        _LOGGER.warning("Could not register media source: %s", ex)

    def handle_start_record(call: ServiceCall) -> None:
        guid = _resolve_guid(
            hass,
            guid=call.data.get(SERVICE_CHANNEL_GUID),
            entity_id=call.data.get(SERVICE_ENTITY_ID),
            channel_index=call.data.get(SERVICE_CHANNEL_INDEX),
        )
        client.start_recording(guid)

    def handle_stop_record(call: ServiceCall) -> None:
        guid = _resolve_guid(
            hass,
            guid=call.data.get(SERVICE_CHANNEL_GUID),
            entity_id=call.data.get(SERVICE_ENTITY_ID),
            channel_index=call.data.get(SERVICE_CHANNEL_INDEX),
        )
        client.stop_recording(guid)

    def handle_ptz(call: ServiceCall) -> None:
        guid = _resolve_guid(
            hass,
            guid=call.data.get(SERVICE_CHANNEL_GUID),
            entity_id=call.data.get(SERVICE_ENTITY_ID),
            channel_index=call.data.get(SERVICE_CHANNEL_INDEX),
        )
        client.ptz_control(
            guid,
            call.data[SERVICE_PTZ_ACTION],
            direction=call.data.get(SERVICE_PTZ_DIRECTION),
        )

    def handle_reconnect(call: ServiceCall) -> None:
        client.force_reconnect()
        try:
            client.get_channel_list()
            _LOGGER.info("QVR Surveillance reconnected successfully")
        except Exception as ex:
            _LOGGER.warning("Reconnect probe failed: %s", ex)

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
    hass.services.register(DOMAIN, SERVICE_RECONNECT, handle_reconnect)

    return True
