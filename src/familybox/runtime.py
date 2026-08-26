"""Dependency wiring and lifecycle for one independent FamilyBox player."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from familybox.config import Settings
from familybox.content.local import LocalContentProvider
from familybox.domain.models import Device, utc_now
from familybox.hardware.fake.audio import FakeAudioOutput
from familybox.hardware.fake.controls import FakeButtonController, FakeVolumeController
from familybox.hardware.fake.nfc import FakeNfcReader
from familybox.hardware.fake.power import FakePowerMonitor
from familybox.hardware.interfaces import (
    AudioOutput,
    ButtonController,
    NfcReader,
    PowerMonitor,
    VolumeController,
)
from familybox.hardware.raspberry_pi.audio import Max98357aAudioOutput
from familybox.hardware.raspberry_pi.controls import (
    GpioButtonController,
    GpioVolumeController,
)
from familybox.hardware.raspberry_pi.nfc import Pn532NfcReader
from familybox.hardware.raspberry_pi.power import RaspberryPiPowerMonitor
from familybox.hardware.unavailable import (
    UnavailableAudioOutput,
    UnavailableButtonController,
    UnavailableNfcReader,
    UnavailablePowerMonitor,
    UnavailableVolumeController,
)
from familybox.persistence.database import Database
from familybox.playback.fake import FakePlaybackEngine
from familybox.playback.manager import PlaybackEngine, PlaybackManager
from familybox.playback.mpv import MpvClient
from familybox.services.nfc import NfcService
from familybox.services.player import PlayerService

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class FamilyBoxRuntime:
    """Long-lived application objects owned by the FastAPI lifespan."""

    settings: Settings
    database: Database
    local_content: LocalContentProvider
    playback: PlaybackManager
    nfc: NfcService
    player: PlayerService
    nfc_reader: NfcReader
    buttons: ButtonController
    volume: VolumeController
    power_monitor: PowerMonitor
    audio_output: AudioOutput
    started_monotonic: float
    _started: bool = False

    async def start(self) -> None:
        if self._started:
            return
        self.database.initialize()
        existing = self.database.get_device(self.settings.device_id)
        self.database.save_device(
            Device(
                id=self.settings.device_id,
                name=self.settings.device_name,
                child_id=existing.child_id if existing else None,
                created_at=existing.created_at if existing else utc_now(),
            )
        )
        try:
            self.audio_output.prepare()
        except RuntimeError:
            # Keep the web UI available for bench diagnosis. The mpv engine
            # reports its own startup/playback errors independently.
            logger.exception("audio output is not ready")
        await self.player.start()
        self._started = True
        logger.info(
            "FamilyBox started",
            extra={
                "device_id": self.settings.device_id,
                "hardware_mode": self.settings.hardware_mode,
                "audio_mode": self.settings.audio_mode,
            },
        )

    async def stop(self) -> None:
        await self.player.stop()
        # These closes are idempotent and cover partial constructor/startup
        # failures before PlayerService took ownership of its adapters.
        self.nfc.close()
        self.buttons.close()
        self.volume.close()
        self.playback.shutdown()
        self._started = False
        self.audio_output.close()
        self.power_monitor.close()
        self.database.close()
        logger.info("FamilyBox stopped", extra={"device_id": self.settings.device_id})


def build_runtime(settings: Settings) -> FamilyBoxRuntime:
    """Select real or fake adapters once, at the application boundary."""

    database = Database(settings.database_path)
    local_content = LocalContentProvider(settings.media_dir, database)

    if settings.hardware_mode == "raspberry_pi":
        try:
            nfc_reader: NfcReader = Pn532NfcReader(interface="spi")
        except Exception as exc:
            logger.exception("NFC reader initialization failed")
            nfc_reader = UnavailableNfcReader(_error_message(exc))
        try:
            buttons: ButtonController = GpioButtonController()
        except Exception as exc:
            logger.exception("button controller initialization failed")
            buttons = UnavailableButtonController(_error_message(exc))
        try:
            volume: VolumeController = GpioVolumeController()
        except Exception as exc:
            logger.exception("volume controller initialization failed")
            volume = UnavailableVolumeController(_error_message(exc))
        try:
            power_monitor: PowerMonitor = RaspberryPiPowerMonitor()
        except Exception as exc:
            logger.exception("power monitor initialization failed")
            power_monitor = UnavailablePowerMonitor(_error_message(exc))
        try:
            audio_output: AudioOutput = Max98357aAudioOutput()
        except Exception as exc:
            logger.exception("audio output initialization failed")
            audio_output = UnavailableAudioOutput(_error_message(exc))
    else:
        nfc_reader = FakeNfcReader()
        buttons = FakeButtonController()
        volume = FakeVolumeController()
        power_monitor = FakePowerMonitor()
        audio_output = FakeAudioOutput(
            device="mpv system output" if settings.audio_mode == "mpv" else "simulated output"
        )

    engine: PlaybackEngine
    if settings.audio_mode == "mpv":
        engine = MpvClient(
            executable=settings.mpv_binary,
            socket_path=settings.mpv_socket_path,
        )
    else:
        engine = FakePlaybackEngine()

    playback = PlaybackManager(
        engine,
        database,
        device_id=settings.device_id,
        progress_interval_seconds=settings.progress_save_interval,
    )
    nfc = NfcService(
        nfc_reader,
        database,
        poll_interval_seconds=settings.nfc_poll_interval,
        present_confirmations=settings.nfc_present_samples,
        removal_confirmations=settings.nfc_removed_samples,
    )
    player = PlayerService(
        nfc=nfc,
        repository=database,
        providers={local_content.provider_name: local_content},
        playback=playback,
        buttons=buttons,
        volume=volume,
    )
    return FamilyBoxRuntime(
        settings=settings,
        database=database,
        local_content=local_content,
        playback=playback,
        nfc=nfc,
        player=player,
        nfc_reader=nfc_reader,
        buttons=buttons,
        volume=volume,
        power_monitor=power_monitor,
        audio_output=audio_output,
        started_monotonic=time.monotonic(),
    )


def _error_message(exc: Exception) -> str:
    return str(exc) or type(exc).__name__
