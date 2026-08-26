"""PN532 NFC reader for Raspberry Pi.

SPI is the default because the PN532's I2C clock stretching is unreliable on
Raspberry Pi hardware.  I2C remains available as an explicit experimental mode
for boards where it has been verified locally.
"""

from __future__ import annotations

from typing import Any, Literal

from familybox.hardware.interfaces import NfcReader, normalize_uid


class Pn532NfcReader(NfcReader):
    """Read immutable NFC UIDs from a PN532 using CircuitPython drivers."""

    def __init__(
        self,
        *,
        interface: Literal["spi", "i2c"] = "spi",
        pn532: Any | None = None,
        debug: bool = False,
    ) -> None:
        self.interface = interface
        self._resources: list[Any] = []
        self._closed = False

        if pn532 is not None:
            self._pn532 = pn532
        elif interface == "spi":
            self._pn532 = self._create_spi_reader(debug=debug)
        elif interface == "i2c":
            self._pn532 = self._create_i2c_reader(debug=debug)
        else:
            raise ValueError(f"unsupported PN532 interface: {interface!r}")

        # Put the PN532 into normal passive target reading mode once.  This is
        # intentionally not repeated for each poll.
        self._pn532.SAM_configuration()

    def _create_spi_reader(self, *, debug: bool) -> Any:
        try:
            import board  # type: ignore[import-not-found]
            import busio  # type: ignore[import-not-found]
            import digitalio  # type: ignore[import-not-found]
            from adafruit_pn532.spi import PN532_SPI  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover - exercised on Pi
            raise RuntimeError(
                "PN532 support requires the FamilyBox 'pi' optional dependencies"
            ) from exc

        # SPI0: SCLK GPIO11, MOSI GPIO10, MISO GPIO9, CE0 GPIO8 (board.D8).
        spi = busio.SPI(board.SCK, board.MOSI, board.MISO)
        chip_select = digitalio.DigitalInOut(board.D8)
        self._resources.extend((chip_select, spi))
        return PN532_SPI(spi, chip_select, debug=debug)

    def _create_i2c_reader(self, *, debug: bool) -> Any:
        try:
            import board
            import busio
            from adafruit_pn532.i2c import PN532_I2C  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover - exercised on Pi
            raise RuntimeError(
                "PN532 support requires the FamilyBox 'pi' optional dependencies"
            ) from exc

        i2c = busio.I2C(board.SCL, board.SDA)
        self._resources.append(i2c)
        return PN532_I2C(i2c, debug=debug)

    def read_uid(self, timeout_seconds: float = 0.2) -> str | None:
        if self._closed:
            raise RuntimeError("PN532 reader is closed")
        uid = self._pn532.read_passive_target(timeout=max(timeout_seconds, 0))
        return normalize_uid(uid) if uid is not None else None

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        for resource in reversed(self._resources):
            deinit = getattr(resource, "deinit", None)
            if callable(deinit):
                deinit()
        self._resources.clear()


# Explicit platform-oriented alias for dependency injection configuration.
RaspberryPiNfcReader = Pn532NfcReader
