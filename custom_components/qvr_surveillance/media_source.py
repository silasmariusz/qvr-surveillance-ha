"""Media source for QVR Surveillance recordings."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from homeassistant.components.media_source import MediaSourceItem, PlayMedia
from homeassistant.components.media_source.error import Unresolvable
from homeassistant.components.media_source.models import MediaSource
from homeassistant.core import HomeAssistant

from .const import DATA_CHANNELS, DOMAIN

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

        data = self.hass.data.get(DOMAIN)
        if not data:
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

        client_id = data.get("client_id", "qvr_surveillance")
        channels = data.get(DATA_CHANNELS, [])

        ident = (item.identifier or "").strip()
        children: list = []

        if not ident or ident == "recordings":
            # Root: list cameras
            for ch in channels:
                guid = ch.get("guid")
                if not guid:
                    continue
                name = ch.get("channel_name") or ch.get("name") or f"Channel {ch.get('channel_index', -1) + 1}"
                children.append(BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=f"recordings/{client_id}/{guid}",
                    media_class=MediaClass.DIRECTORY,
                    media_content_type=MediaType.VIDEO,
                    title=name,
                    can_play=False,
                    can_expand=True,
                    children=[],
                ))
            return BrowseMediaSource(
                domain=DOMAIN,
                identifier="recordings",
                media_class=MediaClass.DIRECTORY,
                media_content_type=MediaType.VIDEO,
                title="QVR Surveillance Recordings",
                can_play=False,
                can_expand=True,
                children=children,
            )

        parts = ident.split("/")
        if len(parts) == 3 and parts[0] == "recordings":
            # recordings/client_id/camera_guid -> list days (last 7)
            _cid, camera_guid = parts[1], parts[2]
            now = datetime.now(timezone.utc)
            for day_off in range(7):
                d = now - timedelta(days=day_off)
                date_str = d.strftime("%Y-%m-%d")
                children.append(BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=f"recordings/{client_id}/{camera_guid}/{date_str}",
                    media_class=MediaClass.DIRECTORY,
                    media_content_type=MediaType.VIDEO,
                    title=date_str,
                    can_play=False,
                    can_expand=True,
                    children=[],
                ))
            cam_name = next(
                (ch.get("channel_name") or ch.get("name") or f"Channel {ch.get('channel_index', -1) + 1}"
                 for ch in channels if ch.get("guid") == camera_guid),
                camera_guid[:8],
            )
            return BrowseMediaSource(
                domain=DOMAIN,
                identifier=ident,
                media_class=MediaClass.DIRECTORY,
                media_content_type=MediaType.VIDEO,
                title=cam_name,
                can_play=False,
                can_expand=True,
                children=children,
            )

        if len(parts) == 4 and parts[0] == "recordings":
            # recordings/client_id/camera_guid/YYYY-MM-DD -> list hours
            _cid, camera_guid, date_str = parts[1], parts[2], parts[3]
            for hour in range(24):
                hh = f"{hour:02d}"
                children.append(BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=f"recordings/{client_id}/{camera_guid}/{date_str}/{hh}",
                    media_class=MediaClass.VIDEO,
                    media_content_type=MediaType.VIDEO,
                    title=f"{date_str} {hh}:00",
                    can_play=True,
                    can_expand=False,
                    children=[],
                ))
            return BrowseMediaSource(
                domain=DOMAIN,
                identifier=ident,
                media_class=MediaClass.DIRECTORY,
                media_content_type=MediaType.VIDEO,
                title=date_str,
                can_play=False,
                can_expand=True,
                children=children,
            )

        return BrowseMediaSource(
            domain=DOMAIN,
            identifier="recordings",
            media_class=MediaClass.DIRECTORY,
            media_content_type=MediaType.VIDEO,
            title="QVR Surveillance Recordings",
            can_play=False,
            can_expand=True,
            children=[],
        )
