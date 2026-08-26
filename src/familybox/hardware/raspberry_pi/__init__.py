"""Raspberry Pi hardware adapters.

Imports in this package are safe on development computers.  Third-party GPIO
and CircuitPython modules are loaded only when a concrete adapter is created.
"""

from familybox.hardware.raspberry_pi.audio import (
    Max98357aAudioOutput,
    RaspberryPiAudioOutput,
)
from familybox.hardware.raspberry_pi.controls import (
    BUTTON_PINS,
    ENCODER_A_PIN,
    ENCODER_B_PIN,
    ENCODER_PUSH_PIN,
    GpioButtonController,
    GpioVolumeController,
)
from familybox.hardware.raspberry_pi.nfc import Pn532NfcReader, RaspberryPiNfcReader
from familybox.hardware.raspberry_pi.power import RaspberryPiPowerMonitor

__all__ = [
    "BUTTON_PINS",
    "ENCODER_A_PIN",
    "ENCODER_B_PIN",
    "ENCODER_PUSH_PIN",
    "GpioButtonController",
    "GpioVolumeController",
    "Max98357aAudioOutput",
    "Pn532NfcReader",
    "RaspberryPiAudioOutput",
    "RaspberryPiNfcReader",
    "RaspberryPiPowerMonitor",
]
