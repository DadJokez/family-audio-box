"""Controllable fake power monitor."""

from familybox.hardware.interfaces import PowerMonitor, PowerStatus


class FakePowerMonitor(PowerMonitor):
    def __init__(self, initial: PowerStatus | None = None) -> None:
        self._status = initial or PowerStatus()
        self._closed = False

    def set_status(
        self,
        *,
        external_power: bool | None = None,
        battery_percent: float | None = None,
        shutdown_requested: bool = False,
    ) -> None:
        self._ensure_open()
        self._status = PowerStatus(external_power, battery_percent, shutdown_requested)

    def status(self) -> PowerStatus:
        self._ensure_open()
        return self._status

    def close(self) -> None:
        self._closed = True

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("fake power monitor is closed")
