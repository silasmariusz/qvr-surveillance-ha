"""QVR Surveillance camera platform."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.camera import Camera
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .client import QVRClient, QVRConnectionError, QVRResponseError, QVRAPIError
from .const import DATA_CHANNELS, DATA_CLIENT, DOMAIN, SHORT_NAME

_LOGGER = logging.getLogger(__name__)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up QVR Surveillance cameras."""
    if discovery_info is None:
        return

    data = hass.data.get(DOMAIN)
    if not data:
        return

    client: QVRClient = data[DATA_CLIENT]
    channels = data.get(DATA_CHANNELS, [])

    client_id = data.get("client_id", "qvr_surveillance")
    entities = []
    for channel in channels:
        channel_index = channel.get("channel_index", 0)
        stream_source = _get_stream_source(channel.get("guid"), client)
        entities.append(
            QVRSurveillanceCamera(
                name=channel.get("name", "Camera"),
                model=channel.get("model", ""),
                brand=channel.get("brand", ""),
                channel_index=channel_index,
                guid=channel.get("guid", ""),
                stream_source=stream_source,
                client=client,
                unique_id=f"qvr_surveillance_{client_id}_{channel_index}",
            )
        )

    add_entities(entities)


def _get_stream_source(guid: str, client: QVRClient) -> str | None:
    """Get RTSP stream URL."""
    try:
        resp = client.get_channel_live_stream(guid, protocol="rtsp")
    except (QVRResponseError, QVRConnectionError, QVRAPIError) as ex:
        _LOGGER.error("Failed to get stream for %s | type=%s code=%s: %s", guid, getattr(ex, "error_type", "?"), getattr(ex, "code", ""), ex)
        return None

    full_url = resp.get("resourceUris") if isinstance(resp, dict) else None
    if not full_url:
        return None

    protocol = full_url[:7] if len(full_url) >= 7 else "rtsp://"
    auth = f"{client.get_auth_string()}@"
    url = full_url[7:] if full_url.startswith("rtsp://") else full_url
    return f"{protocol}{auth}{url}"


class QVRSurveillanceCamera(Camera):
    """Representation of a QVR Surveillance camera."""

    def __init__(
        self,
        name: str,
        model: str,
        brand: str,
        channel_index: int,
        guid: str,
        stream_source: str | None,
        client: QVRClient,
        unique_id: str,
    ) -> None:
        super().__init__()
        self._attr_unique_id = unique_id
        self._name = f"{SHORT_NAME} {name}"
        self._model = model
        self._brand = brand
        self.index = channel_index
        self.guid = guid
        self._client = client
        self._stream_source = stream_source

    @property
    def name(self) -> str:
        return self._name

    @property
    def model(self) -> str:
        return self._model

    @property
    def brand(self) -> str:
        return self._brand

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"qvr_guid": self.guid, "channel_index": self.index, "channel_number": self.index + 1}

    def camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        try:
            return self._client.get_snapshot(self.guid)
        except (QVRResponseError, QVRConnectionError, QVRAPIError) as ex:
            _LOGGER.warning(
                "Snapshot failed for %s | type=%s code=%s: %s",
                self.guid, getattr(ex, "error_type", "?"), getattr(ex, "code", ""), ex,
            )
            try:
                self._client._authenticated = False
                self._client._ensure_connection()
                img = self._client.get_snapshot(self.guid)
                if img is not None:
                    new_src = _get_stream_source(self.guid, self._client)
                    if new_src:
                        self._stream_source = new_src
                return img
            except Exception:
                return None

    async def stream_source(self) -> str | None:
        """Always fetch fresh URL on each request - QVR sessions expire, enables recovery after stream crash."""
        try:
            new_src = await self.hass.async_add_executor_job(
                _get_stream_source, self.guid, self._client
            )
            if new_src:
                self._stream_source = new_src
        except Exception as ex:
            _LOGGER.debug("Stream URL refresh failed for %s, using cached: %s", self.guid, ex)
        return self._stream_source
