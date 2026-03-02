"""QVR Surveillance camera platform."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.camera import Camera
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .client import QVRClient, QVRAuthError, QVRConnectionError, QVRResponseError, QVRAPIError
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
    add_substream = data.get("add_substream", True)
    client_id = data.get("client_id", "qvr_surveillance")

    entities = []
    for channel in channels:
        channel_index = channel.get("channel_index", 0)
        base_name = channel.get("name", "Camera")
        guid = channel.get("guid", "")

        # Main stream (index 0)
        stream_source_main = _get_stream_source(guid, client, 0)
        entities.append(
            QVRSurveillanceCamera(
                name=base_name,
                model=channel.get("model", ""),
                brand=channel.get("brand", ""),
                channel_index=channel_index,
                guid=guid,
                stream_source=stream_source_main,
                client=client,
                unique_id=f"qvr_surveillance_{client_id}_{channel_index}",
                stream_index=0,
                client_id=client_id,
                is_substream=False,
            )
        )

        # Sub stream (index 1) – enables substream switch in Advanced Camera Card
        if add_substream:
            stream_source_sub = _get_stream_source(guid, client, 1)
            entities.append(
                QVRSurveillanceCamera(
                    name=f"{base_name} Sub",
                    model=channel.get("model", ""),
                    brand=channel.get("brand", ""),
                    channel_index=channel_index,
                    guid=guid,
                    stream_source=stream_source_sub,
                    client=client,
                    unique_id=f"qvr_surveillance_{client_id}_{channel_index}_sub",
                    stream_index=1,
                    client_id=client_id,
                    is_substream=True,
                )
            )

    add_entities(entities)


def _get_stream_source(guid: str, client: QVRClient, stream: int = 0) -> str | None:
    """Get RTSP stream URL. stream: 0=Main, 1=Substream, 2=Mobile."""
    try:
        resp = client.get_channel_live_stream(guid, stream=stream, protocol="rtsp")
    except (QVRResponseError, QVRConnectionError, QVRAPIError) as ex:
        _LOGGER.error("Failed to get stream for %s | type=%s code=%s: %s", guid, getattr(ex, "error_type", "?"), getattr(ex, "code", ""), ex)
        return None

    raw = resp.get("resourceUris") or resp.get("resourceUri") if isinstance(resp, dict) else None
    full_url = raw[0] if isinstance(raw, list) and raw else (raw if isinstance(raw, str) else None)
    if not full_url:
        return None

    protocol = full_url[:7] if len(full_url) >= 7 else "rtsp://"
    auth = f"{client.get_auth_string_for_url()}@"
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
        stream_index: int = 0,
        client_id: str = "qvr_surveillance",
        is_substream: bool = False,
    ) -> None:
        super().__init__()
        self._attr_unique_id = unique_id
        self._name = f"{SHORT_NAME} {name}"
        self._is_substream = is_substream
        self._model = model
        self._brand = brand
        self.index = channel_index
        self.guid = guid
        self._client = client
        self._stream_source = stream_source
        self._stream_index = stream_index
        self._client_id = client_id

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
        attrs = {
            "qvr_guid": self.guid,
            "qvr_client_id": self._client_id,
            "channel_index": self.index,
            "channel_number": self.index + 1,
        }
        if self._is_substream:
            attrs["qvr_is_substream"] = True
        return attrs

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Async snapshot to avoid blocking event loop (QVR can be slow)."""
        return await self.hass.async_add_executor_job(
            self._sync_camera_image, width, height
        )

    def camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Sync fallback for older HA versions."""
        return self._sync_camera_image(width, height)

    def _sync_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        try:
            img = self._client.get_snapshot(self.guid)
            if img:
                return img
            return None
        except (QVRResponseError, QVRConnectionError, QVRAPIError, QVRAuthError) as ex:
            _LOGGER.warning(
                "Snapshot failed for %s | type=%s code=%s: %s",
                self.guid, getattr(ex, "error_type", "?"), getattr(ex, "code", ""), ex,
            )
            try:
                self._client._authenticated = False
                self._client._ensure_connection()
                img = self._client.get_snapshot(self.guid)
                if img:
                    new_src = _get_stream_source(self.guid, self._client, self._stream_index)
                    if new_src:
                        self._stream_source = new_src
                    return img
            except Exception:
                pass
            return None

    async def stream_source(self) -> str | None:
        """Always fetch fresh URL on each request - QVR sessions expire, enables recovery after stream crash."""
        try:
            new_src = await self.hass.async_add_executor_job(
                _get_stream_source, self.guid, self._client, self._stream_index
            )
            if new_src:
                self._stream_source = new_src
        except Exception as ex:
            _LOGGER.debug("Stream URL refresh failed for %s, using cached: %s", self.guid, ex)
        return self._stream_source
