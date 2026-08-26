"""Fake hardware adapters for development machines and automated tests."""

from familybox.hardware.fake.audio import FakeAudioOutput
from familybox.hardware.fake.controls import FakeButtonController, FakeVolumeController
from familybox.hardware.fake.nfc import FakeNfcReader
from familybox.hardware.fake.power import FakePowerMonitor

__all__ = [
    "FakeAudioOutput",
    "FakeButtonController",
    "FakeNfcReader",
    "FakePowerMonitor",
    "FakeVolumeController",
]
