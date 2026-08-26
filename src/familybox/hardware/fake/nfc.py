"""Controllable NFC reader for development and tests."""

from __future__ import annotations

from threading import RLock

from familybox.hardware.interfaces import NfcReader, UidValue, normalize_uid


class FakeNfcReader(NfcReader):
    def __init__(self, uid: UidValue | None = None) -> None:
        self._lock = RLock()
        self._uid = normalize_uid(uid) if uid is not None else None
        self._closed = False

    def place_tag(self, uid: UidValue) -> str:
        normalized = normalize_uid(uid)
        with self._lock:
            self._ensure_open()
            self._uid = normalized
        return normalized

    # A friendly alias for interactive development scripts.
    set_tag = place_tag

    def remove_tag(self) -> str | None:
        with self._lock:
            self._ensure_open()
            previous, self._uid = self._uid, None
        return previous

    def read_uid(self, timeout_seconds: float = 0.2) -> str | None:
        del timeout_seconds
        with self._lock:
            self._ensure_open()
            return self._uid

    def close(self) -> None:
        with self._lock:
            self._closed = True
            self._uid = None

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("fake NFC reader is closed")
