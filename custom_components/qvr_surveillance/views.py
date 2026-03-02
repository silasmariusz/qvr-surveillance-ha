"""HTTP views for QVR Surveillance - recording proxy."""

from __future__ import annotations

import logging

import aiohttp
from aiohttp import web

from homeassistant.helpers.http import KEY_AUTHENTICATED, KEY_HASS
from homeassistant.core import HomeAssistant

from .const import CONF_VERIFY_SSL, DATA_CLIENT, DOMAIN

_LOGGER = logging.getLogger(__name__)

RECORDING_URL = r"/api/qvr_surveillance/{instance_id:.+}/recording/{camera:.+}/start/{start:[.0-9]+}/end/{end:[.0-9]+}"
SNAPSHOT_URL = r"/api/qvr_surveillance/{instance_id:.+}/snapshot/{camera:.+}"


def async_setup(hass: HomeAssistant) -> None:
    hass.http.app.router.add_route("GET", RECORDING_URL, _handle_recording_request)
    hass.http.app.router.add_route("GET", SNAPSHOT_URL, _handle_snapshot_request)


async def _handle_recording_request(request: web.Request) -> web.StreamResponse:
    try:
        if not request[KEY_AUTHENTICATED]:
            return web.Response(status=401)
    except (KeyError, TypeError):
        return web.Response(status=401)

    hass = request.app[KEY_HASS]
    data = hass.data.get(DOMAIN)
    if not data:
        return web.Response(status=404, text="QVR Surveillance not configured")

    client = data.get(DATA_CLIENT)
    if not client:
        return web.Response(status=503, text="QVR Surveillance client unavailable")

    camera_guid = request.match_info["camera"]
    start_ts = int(float(request.match_info["start"]))
    end_ts = int(float(request.match_info["end"]))

    duration_ms = (end_ts - start_ts) * 1000
    pre_period = duration_ms // 2
    post_period = duration_ms - pre_period

    try:
        import asyncio
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: client.get_recording(
                start_ts,
                camera_guid,
                channel_id=0,
                pre_period=int(pre_period),
                post_period=int(post_period),
            ),
        )
    except Exception as ex:
        err_msg = str(ex)
        _LOGGER.warning("Failed to fetch recording: %s", ex)
        if "404" in err_msg or "Invalid request" in err_msg or "not exist" in err_msg.lower():
            return web.Response(
                status=404,
                text="Recording playback not supported by this QVR device. "
                "The /camera/recordingfile/ API may not be available on QVR Surveillance (standalone NVR).",
            )
        return web.Response(status=502, text=err_msg)

    if response is None:
        return web.Response(
            status=404,
            text="No recording found. QVR Surveillance may not support the recording playback API.",
        )

    body = None
    content_type = "video/mp4"

    try:
        if isinstance(response, bytes):
            body = response
        elif isinstance(response, dict):
            resource_uri = response.get("resourceUris") or response.get("url")
            if isinstance(resource_uri, (list, tuple)) and resource_uri:
                resource_uri = resource_uri[0]
            if resource_uri:
                from urllib.parse import urlparse
                from homeassistant.helpers.aiohttp_client import async_get_clientsession

                session = async_get_clientsession(hass)
                auth_str = client.get_auth_string()
                if isinstance(resource_uri, str) and not resource_uri.startswith("http"):
                    base = f"{client._protocol}://{client._host}:{client._effective_port}"
                    url = f"{base}{resource_uri}" if resource_uri.startswith("/") else f"{base}/{resource_uri}"
                else:
                    url = str(resource_uri)
                parsed = urlparse(url)
                if auth_str and "@" not in parsed.netloc:
                    url = f"{parsed.scheme}://{auth_str}@{parsed.netloc}{parsed.path or '/'}"
                    if parsed.query:
                        url += f"?{parsed.query}"
                sid = client.get_session_id()
                if sid:
                    sep = "&" if "?" in url else "?"
                    url = f"{url}{sep}sid={sid}&ver=1.1.0"
                verify_ssl = data.get("config", {}).get(CONF_VERIFY_SSL, False)
                timeout = aiohttp.ClientTimeout(total=600)  # 10 min – nagrania 1h mogą mieć ~3+ GB
                async with session.get(url, ssl=verify_ssl, timeout=timeout) as resp:
                    if resp.status != 200:
                        return web.Response(
                            status=404,
                            text=f"Recording URL returned {resp.status}. "
                            "QVR may not support playback for this device.",
                        )
                    body = await resp.read()
                    content_type = resp.content_type or "video/mp4"
            else:
                return web.Response(status=500, text="Unexpected QVR response format")
        elif hasattr(response, "content"):
            body = response.content
            if hasattr(response, "headers") and "content-type" in response.headers:
                content_type = response.headers["content-type"]
    except Exception as ex:
        _LOGGER.warning("Failed to fetch recording payload: %s", ex)
        return web.Response(
            status=502,
            text=f"Failed to retrieve recording: {ex}",
        )

    if body:
        disp = "attachment" if request.query.get("download") == "true" else "inline"
        fn = request.query.get("filename") or "recording.mp4"
        return web.Response(
            body=body,
            content_type=content_type,
            headers={
                "Content-Disposition": f'{disp}; filename="{fn}"',
            },
        )

    return web.Response(status=500, text="Unexpected response")


async def _handle_snapshot_request(request: web.Request) -> web.StreamResponse:
    """Serve camera snapshot for thumbnails."""
    try:
        if not request[KEY_AUTHENTICATED]:
            return web.Response(status=401)
    except (KeyError, TypeError):
        return web.Response(status=401)

    hass = request.app[KEY_HASS]
    data = hass.data.get(DOMAIN)
    if not data:
        return web.Response(status=404, text="QVR Surveillance not configured")

    client = data.get(DATA_CLIENT)
    if not client:
        return web.Response(status=503, text="QVR Surveillance client unavailable")

    camera_guid = request.match_info["camera"]

    try:
        import asyncio
        loop = asyncio.get_event_loop()
        img = await loop.run_in_executor(None, lambda: client.get_snapshot(camera_guid))
    except Exception as ex:
        _LOGGER.debug("Snapshot failed for %s: %s", camera_guid, ex)
        return web.Response(status=502, text=str(ex))

    if img and len(img) > 0:
        return web.Response(
            body=img,
            content_type="image/jpeg",
            headers={"Cache-Control": "max-age=60"},
        )
    return web.Response(status=404, text="No snapshot")
