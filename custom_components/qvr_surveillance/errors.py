"""
QVR Surveillance error handling.
"""

from __future__ import annotations

import inspect
import logging
from typing import Literal

_LOGGER = logging.getLogger(__name__)

ErrorType = Literal["api", "network", "auth"]


class QVRError(Exception):
    """Base QVR error."""

    def __init__(
        self,
        msg: str,
        *,
        line: int = 0,
        cmd: str = "",
        code: int = 0,
        error_type: ErrorType = "api",
    ) -> None:
        super().__init__(msg)
        self.msg = msg
        self.line = line
        self.cmd = cmd
        self.code = code
        self.error_type = error_type


class QVRAuthError(QVRError):
    """Authentication error."""

    def __init__(self, msg: str, **kwargs) -> None:
        kwargs.setdefault("error_type", "auth")
        super().__init__(msg, **kwargs)


class QVRConnectionError(QVRError):
    """Connection / network error."""

    def __init__(self, msg: str, **kwargs) -> None:
        kwargs.setdefault("error_type", "network")
        super().__init__(msg, **kwargs)


class QVRResponseError(QVRError):
    """API response error."""

    def __init__(self, msg: str, **kwargs) -> None:
        kwargs.setdefault("error_type", "api")
        super().__init__(msg, **kwargs)


class QVRAPIError(QVRResponseError):
    """QVR API error (error_code / error_message from JSON)."""


def _log_api_error(
    line: int,
    cmd: str,
    error_type: ErrorType,
    code: int,
    msg: str,
    logger: logging.Logger | None = None,
) -> None:
    """Log API error in standard format."""
    log = logger or _LOGGER
    log.error(
        "[QVR] line %s | cmd=%s | type=%s | code=%s | msg=%s",
        line,
        cmd,
        error_type,
        code,
        msg,
    )
