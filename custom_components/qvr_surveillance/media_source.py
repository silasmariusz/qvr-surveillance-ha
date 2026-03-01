"""Media source for QVR Surveillance recordings."""

from __future__ import annotations

import re
from datetime import datetime, timezone

from homeassistant.components.media_source import MediaSourceItem, PlayMedia
from homeassistant.components.media_source.error import Unresolvable
from homeassistant.components.media_source.models import MediaSource
from homeassistant.core import HomeAssistant

from .const import DOMAIN

RECORDINGS_PATTERN = re.compile(r"^recordings/([^/]+)/([^/]+)/(\d{4}-\d{2}-\d{2})/(\d{2})$")


async def async_get_media_source(hass: HomeAssistant) -> MediaSource:
    return QVRSurveillanceMediaSource(hass)


class QVRSurveillanceMediaSource(MediaSource):
    name = "QVR Surveillance"

    def __init__(self, hass: HomeAssistant) -> None:
        super().__init__(DOMAIN)
        self.hass = hass

    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        data = self.hass.data.get(DOMAIN)
        if not data:
            raise Unresolvable("QVR Surveillance not configured")

        match = RECORDINGS_PATTERN.match(item.identifier)
        if not match:
            raise Unresolvable(f"Invalid identifier: {item.identifier}")

        client_id, camera_guid, date_str, hour_str = match.groups()
        year, month, day = map(int, date_str.split("-"))
        hour = int(hour_str)

        dt = datetime(year, month, day, hour, 0, 0, tzinfo=timezone.utc)
        start_ts = int(dt.timestamp())
        end_ts = start_ts + 3600

        path = f"/api/qvr_surveillance/{client_id}/recording/{camera_guid}/start/{start_ts}/end/{end_ts}"
        return PlayMedia(path, "video/mp4")

    async def async_browse_media(self, item: MediaSourceItem):
        from homeassistant.components.media_source.models import BrowseMediaSource
        from homeassistant.components.media_player import MediaClass, MediaType

        return BrowseMediaSource(
            domain=DOMAIN,
            identifier="",
            media_class=MediaClass.DIRECTORY,
            media_content_type=MediaType.VIDEO,
            title="QVR Surveillance Recordings",
            can_play=False,
            can_expand=False,
            children=[],
        )
