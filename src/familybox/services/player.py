"""Coordinate content resolution, playback, and physical controls."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Mapping
from contextlib import suppress
from typing import Protocol

from familybox.content.base import ContentProvider
from familybox.domain.events import (
    Button,
    ButtonPressed,
    PlayerEvent,
    TagPresent,
    TagRemoved,
    UnknownTag,
    VolumeChanged,
)
from familybox.domain.models import Content
from familybox.hardware.interfaces import ButtonController, VolumeController
from familybox.playback.manager import PlaybackManager
from familybox.services.nfc import NfcService

logger = logging.getLogger(__name__)


class PlayerRepository(Protocol):
    def resolve_tag(self, uid: str) -> Content | None: ...


class PlayerService:
    """The offline control plane for one independent physical player."""

    def __init__(
        self,
        *,
        nfc: NfcService,
        repository: PlayerRepository,
        providers: Mapping[str, ContentProvider],
        playback: PlaybackManager,
        buttons: ButtonController | None = None,
        volume: VolumeController | None = None,
        volume_step: int = 5,
        control_poll_seconds: float = 0.2,
    ) -> None:
        if volume_step <= 0:
            raise ValueError("volume_step must be positive")
        self.nfc = nfc
        self.repository = repository
        self.providers = dict(providers)
        self.playback = playback
        self.buttons = buttons
        self.volume = volume
        self.volume_step = volume_step
        self.control_poll_seconds = control_poll_seconds

        self.detected_uid: str | None = None
        self.last_unknown_uid: str | None = None
        self.button_error: str | None = None
        self.volume_error: str | None = None
        self._active_uid: str | None = None
        self._tasks: list[asyncio.Task[None]] = []
        self._stop = asyncio.Event()
        self._unsubscribe: Callable[[], None] | None = None
        self._running = False

    async def handle_event(self, event: PlayerEvent) -> None:
        if isinstance(event, TagPresent):
            self.detected_uid = event.uid
            await self._play_for_tag(event.uid)
        elif isinstance(event, TagRemoved):
            if self.detected_uid == event.uid:
                self.detected_uid = None
            if self._active_uid == event.uid:
                await asyncio.to_thread(self.playback.pause)
                self._active_uid = None
        elif isinstance(event, UnknownTag):
            self.detected_uid = event.uid
            self.last_unknown_uid = event.uid
        elif isinstance(event, ButtonPressed):
            await self._handle_button(event.button)
        elif isinstance(event, VolumeChanged):
            await asyncio.to_thread(self.playback.set_volume, event.value)

    async def _play_for_tag(self, uid: str) -> None:
        content = await asyncio.to_thread(self.repository.resolve_tag, uid)
        if content is None:
            if self._active_uid == uid:
                await asyncio.to_thread(self.playback.pause)
                self._active_uid = None
            return
        provider_name = (
            content.provider.value if hasattr(content.provider, "value") else str(content.provider)
        )
        provider = self.providers.get(provider_name)
        if provider is None:
            logger.error(
                "content provider is unavailable",
                extra={"provider": provider_name, "content_id": content.id},
            )
            return
        if self.playback.current_content_id == content.id:
            await asyncio.to_thread(self.playback.resume)
        else:
            playable = await asyncio.to_thread(provider.resolve, content)
            await asyncio.to_thread(self.playback.play, playable)
        self._active_uid = uid

    async def _handle_button(self, button: Button) -> None:
        actions: dict[Button, Callable[[], object]] = {
            Button.PREVIOUS: self.playback.previous,
            Button.PLAY_PAUSE: self.playback.toggle_pause,
            Button.NEXT: self.playback.next,
        }
        action = actions.get(button)
        if action is not None:
            await asyncio.to_thread(action)
        # Button.VOLUME_PUSH is intentionally surfaced but unbound in V1.

    async def refresh_tag_assignment(self, uid: str | None = None) -> None:
        """Start a newly assigned visible tag without requiring removal."""

        if uid is None or uid == self.detected_uid:
            await self.nfc.recheck_current_tag()

    async def _button_loop(self) -> None:
        assert self.buttons is not None
        while not self._stop.is_set():
            try:
                action = await asyncio.to_thread(
                    self.buttons.read_action, self.control_poll_seconds
                )
                if action is not None:
                    await self.handle_event(ButtonPressed(button=Button(action.value)))
                self.button_error = None
            except Exception as exc:
                self.button_error = str(exc)
                logger.exception("button control failed; retrying")
                await self._wait_after_control_error()

    async def _volume_loop(self) -> None:
        assert self.volume is not None
        while not self._stop.is_set():
            try:
                event = await asyncio.to_thread(self.volume.read_event, self.control_poll_seconds)
                if event is not None:
                    if event.pressed:
                        await self.handle_event(ButtonPressed(button=Button.VOLUME_PUSH))
                    if event.delta:
                        current = await asyncio.to_thread(self.playback.status)
                        desired = min(
                            100,
                            max(0, current.volume + event.delta * self.volume_step),
                        )
                        await self.handle_event(VolumeChanged(value=desired))
                self.volume_error = None
            except Exception as exc:
                self.volume_error = str(exc)
                logger.exception("volume control failed; retrying")
                await self._wait_after_control_error()

    async def _wait_after_control_error(self) -> None:
        with suppress(TimeoutError):
            await asyncio.wait_for(
                self._stop.wait(),
                timeout=max(0.5, self.control_poll_seconds),
            )

    async def start(self) -> None:
        if self._running:
            return
        self._stop.clear()
        await asyncio.to_thread(self.playback.start)
        self._unsubscribe = self.nfc.subscribe(self.handle_event)
        self._tasks = [asyncio.create_task(self.nfc.run(), name="familybox-nfc")]
        if self.buttons is not None:
            self._tasks.append(asyncio.create_task(self._button_loop(), name="familybox-buttons"))
        if self.volume is not None:
            self._tasks.append(asyncio.create_task(self._volume_loop(), name="familybox-volume"))
        self._running = True

    async def run(self) -> None:
        await self.start()
        try:
            await self._stop.wait()
        finally:
            await self.stop()

    async def stop(self) -> None:
        if not self._running:
            return
        self._stop.set()
        self.nfc.stop()
        wait_timeout = max(
            1.0,
            self.nfc.poll_interval_seconds * 3,
            self.control_poll_seconds * 3,
        )
        _, pending = await asyncio.wait(self._tasks, timeout=wait_timeout)
        for task in pending:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        if self._unsubscribe is not None:
            self._unsubscribe()
            self._unsubscribe = None
        self.nfc.close()
        if self.buttons is not None:
            self.buttons.close()
        if self.volume is not None:
            self.volume.close()
        await asyncio.to_thread(self.playback.shutdown)
        self._running = False
