from __future__ import annotations

import pytest

from familybox.hardware.fake import (
    FakeAudioOutput,
    FakeButtonController,
    FakeNfcReader,
    FakePowerMonitor,
    FakeVolumeController,
)
from familybox.hardware.interfaces import ButtonAction, PowerStatus, normalize_uid
from familybox.hardware.raspberry_pi import (
    BUTTON_PINS,
    ENCODER_A_PIN,
    ENCODER_B_PIN,
    ENCODER_PUSH_PIN,
    GpioButtonController,
    GpioVolumeController,
    Pn532NfcReader,
)


def test_uid_normalization_and_fake_nfc_presence():
    reader = FakeNfcReader()

    assert normalize_uid("04:a1-b2 c3") == "04A1B2C3"
    assert reader.read_uid(0) is None
    assert reader.place_tag(b"\x04\xa1\xb2\xc3") == "04A1B2C3"
    assert reader.read_uid(0) == "04A1B2C3"
    assert reader.remove_tag() == "04A1B2C3"
    assert reader.read_uid(0) is None

    with pytest.raises(ValueError):
        normalize_uid("not-a-uid")


def test_fake_buttons_and_volume_are_queue_backed():
    buttons = FakeButtonController()
    volume = FakeVolumeController()

    buttons.press("next")
    volume.rotate(-2)
    volume.press()

    assert buttons.read_action(0) is ButtonAction.NEXT
    assert buttons.read_action(0) is None
    assert volume.read_event(0).delta == -1  # type: ignore[union-attr]
    assert volume.read_event(0).delta == -1  # type: ignore[union-attr]
    assert volume.read_event(0).pressed is True  # type: ignore[union-attr]


def test_fake_power_and_audio_are_controllable():
    power = FakePowerMonitor(PowerStatus(external_power=True, battery_percent=80))
    audio = FakeAudioOutput()

    assert power.status().battery_percent == 80
    power.set_status(external_power=False, battery_percent=42)
    assert power.status() == PowerStatus(external_power=False, battery_percent=42)

    audio.prepare()
    assert audio.prepared is True
    assert audio.status().available is True
    audio.close()
    assert audio.status().available is False


def test_pn532_adapter_can_be_imported_without_pi_packages_and_normalizes_uid():
    class Driver:
        configured = False

        def SAM_configuration(self):
            self.configured = True

        def read_passive_target(self, timeout):
            assert timeout == 0.25
            return bytearray(b"\x01\x02\xab\xcd")

    driver = Driver()
    reader = Pn532NfcReader(pn532=driver)

    assert driver.configured is True
    assert reader.read_uid(0.25) == "0102ABCD"
    assert BUTTON_PINS == {
        ButtonAction.PREVIOUS: 5,
        ButtonAction.PLAY_PAUSE: 6,
        ButtonAction.NEXT: 13,
    }


def test_gpio_adapters_use_specified_pins_and_internal_button_pullups():
    class Device:
        when_pressed = None
        when_rotated_clockwise = None
        when_rotated_counter_clockwise = None

        def close(self):
            pass

    buttons = {}

    def button_factory(pin, **options):
        device = Device()
        device.options = options
        buttons[pin] = device
        return device

    controller = GpioButtonController(button_factory=button_factory)
    buttons[5].when_pressed()

    assert controller.read_action(0) is ButtonAction.PREVIOUS
    assert all(device.options["pull_up"] is True for device in buttons.values())
    controller.close()

    encoder = Device()

    def encoder_factory(pin_a, pin_b, **options):
        assert (pin_a, pin_b) == (ENCODER_A_PIN, ENCODER_B_PIN)
        assert options["max_steps"] == 0
        return encoder

    volume = GpioVolumeController(
        encoder_factory=encoder_factory,
        button_factory=button_factory,
    )
    encoder.when_rotated_clockwise()
    buttons[ENCODER_PUSH_PIN].when_pressed()

    assert volume.read_event(0).delta == 1  # type: ignore[union-attr]
    assert volume.read_event(0).pressed is True  # type: ignore[union-attr]
    assert buttons[ENCODER_PUSH_PIN].options["pull_up"] is True
    volume.close()
