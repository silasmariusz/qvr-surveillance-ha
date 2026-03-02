"""
QVR API response types.

All API methods return Result – never raise. Error details are in Result.error.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class Result:
    """Wrapper for API responses. ok=True means success; error is populated on failure."""

    ok: bool
    """True if the request succeeded."""
    data: dict | list | bytes | str | None = None
    """Response body: dict/list for JSON, bytes for binary (snapshot, recording), str for text."""
    error: str = ""
    """Error message when ok=False."""

    def unwrap(self) -> dict | list | bytes | str:
        """Return data or raise; prefer checking .ok in API wrapper context."""
        if not self.ok:
            raise ValueError(self.error)
        if self.data is None:
            raise ValueError("Result has no data")
        return self.data


def ok_result(data: dict | list | bytes | str | None) -> Result:
    """Create a successful Result."""
    return Result(ok=True, data=data, error="")


def err_result(error: str, data: Any = None) -> Result:
    """Create a failed Result."""
    return Result(ok=False, data=data, error=error)
