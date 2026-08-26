"""Debounced NFC presence service."""

from __future__ import annotations

import asyncio
import inspect
import logging
from collections.abc import Awaitable, Callable
from contextlib import suppress
from typing import Protocol, TypeAlias

from familybox.domain.events import PlayerEvent, TagPresent, TagRemoved, UnknownTag
from familybox.hardware.interfaces import NfcReader, normalize_uid

logger = logging.getLogger(__name__)


class TagLookup(Protocol):
    def resolve_tag(self, uid: str) -> object | None: ...

    def observe_unknown_tag(self, uid: str) -> object | None: ...


EventHandler: TypeAlias = Callable[[PlayerEvent], Awaitable[None] | None]


class NfcService:
    """Turn noisy PN532 polls into stable presence/removal domain events."""

    def __init__(
        self,
        reader: NfcReader,
        repository: TagLookup,
        *,
        poll_interval_seconds: float = 0.1,
        present_confirmations: int = 2,
        removal_confirmations: int = 2,
    ) -> None:
        if poll_interval_seconds <= 0:
            raise ValueError("NFC poll interval must be positive")
        if present_confirmations < 1 or removal_confirmations < 1:
            raise ValueError("NFC debounce confirmations must be positive")
        self.reader = reader
        self.repository = repository
        self.poll_interval_seconds = poll_interval_seconds
        self.present_confirmations = present_confirmations
        self.removal_confirmations = removal_confirmations

        self._listeners: list[EventHandler] = []
        self._visible_uid: str | None = None
        self._candidate_uid: str | None = None
        self._candidate_reads = 0
        self._absent_reads = 0
        self._stop = asyncio.Event()
        self._running = False
        self.last_error: str | None = None

    @property
    def visible_uid(self) -> str | None:
        return self._visible_uid

    def subscribe(self, handler: EventHandler) -> Callable[[], None]:
        self._listeners.append(handler)

        def unsubscribe() -> None:
            with suppress(ValueError):
                self._listeners.remove(handler)

        return unsubscribe

    async def process_reading(self, uid: str | bytes | bytearray | memoryview | None) -> None:
        """Process one raw poll result; public for deterministic fake-hardware tests."""

        canonical = normalize_uid(uid) if uid is not None else None
        if canonical == self._visible_uid:
            self._candidate_uid = None
            self._candidate_reads = 0
            self._absent_reads = 0
            return

        if canonical is None:
            self._candidate_uid = None
            self._candidate_reads = 0
            if self._visible_uid is None:
                return
            self._absent_reads += 1
            if self._absent_reads >= self.removal_confirmations:
                removed_uid, self._visible_uid = self._visible_uid, None
                self._absent_reads = 0
                await self._emit(TagRemoved(uid=removed_uid))
            return

        self._absent_reads = 0
        if canonical == self._candidate_uid:
            self._candidate_reads += 1
        else:
            self._candidate_uid = canonical
            self._candidate_reads = 1
        if self._candidate_reads < self.present_confirmations:
            return

        previous_uid = self._visible_uid
        self._visible_uid = canonical
        self._candidate_uid = None
        self._candidate_reads = 0
        if previous_uid is not None:
            await self._emit(TagRemoved(uid=previous_uid))
        await self._announce_present(canonical)

    async def _announce_present(self, uid: str) -> None:
        await self._emit(TagPresent(uid=uid))
        content = self.repository.resolve_tag(uid)
        if content is None:
            self.repository.observe_unknown_tag(uid)
            await self._emit(UnknownTag(uid=uid))

    async def recheck_current_tag(self) -> None:
        """Re-resolve a visible tag after the parent assigns it in the UI."""

        if self._visible_uid is not None:
            await self._announce_present(self._visible_uid)

    async def _emit(self, event: PlayerEvent) -> None:
        logger.info(
            "NFC event",
            extra={"event_type": type(event).__name__, "uid": getattr(event, "uid", None)},
        )
        for listener in tuple(self._listeners):
            try:
                result = listener(event)
                if inspect.isawaitable(result):
                    await result
            except Exception:
                logger.exception(
                    "NFC event listener failed",
                    extra={"event_type": type(event).__name__},
                )

    async def poll_once(self) -> None:
        uid = await asyncio.to_thread(self.reader.read_uid, self.poll_interval_seconds)
        await self.process_reading(uid)

    async def run(self) -> None:
        if self._running:
            raise RuntimeError("NFC service is already running")
        self._running = True
        self._stop.clear()
        try:
            while not self._stop.is_set():
                loop = asyncio.get_running_loop()
                started_at = loop.time()
                try:
                    await self.poll_once()
                    self.last_error = None
                except Exception as exc:
                    self.last_error = str(exc)
                    logger.exception("NFC poll failed")
                remaining = self.poll_interval_seconds - (loop.time() - started_at)
                if remaining > 0:
                    with suppress(TimeoutError):
                        await asyncio.wait_for(self._stop.wait(), timeout=remaining)
        finally:
            self._running = False

    def stop(self) -> None:
        self._stop.set()

    def close(self) -> None:
        self.stop()
        self.reader.close()
