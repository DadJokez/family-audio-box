"""Best-effort Raspberry Pi power status without claiming battery telemetry.

The OnOff SHIM owns GPIO4 and GPIO17 and is intentionally not driven here.  Its
daemon performs the power cut after Linux shuts down cleanly.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import suppress
from pathlib import Path

from familybox.hardware.interfaces import PowerMonitor, PowerStatus


class RaspberryPiPowerMonitor(PowerMonitor):
    def __init__(
        self,
        *,
        power_supply_root: Path | str = "/sys/class/power_supply",
        shutdown_requested: Callable[[], bool] | None = None,
    ) -> None:
        self._root = Path(power_supply_root)
        self._shutdown_requested = shutdown_requested or (lambda: False)
        self._closed = False

    def status(self) -> PowerStatus:
        if self._closed:
            raise RuntimeError("power monitor is closed")

        online_values: list[bool] = []
        battery_percent: float | None = None
        if self._root.is_dir():
            for supply in self._root.iterdir():
                supply_type = self._read(supply / "type")
                if supply_type == "Battery" and battery_percent is None:
                    capacity = self._read(supply / "capacity")
                    if capacity is not None:
                        with suppress(ValueError):
                            battery_percent = min(100.0, max(0.0, float(capacity)))
                elif supply_type in {"Mains", "USB", "USB_C", "USB_PD"}:
                    online = self._read(supply / "online")
                    if online in {"0", "1"}:
                        online_values.append(online == "1")

        external_power = any(online_values) if online_values else None
        return PowerStatus(
            external_power=external_power,
            battery_percent=battery_percent,
            shutdown_requested=bool(self._shutdown_requested()),
        )

    @staticmethod
    def _read(path: Path) -> str | None:
        try:
            return path.read_text(encoding="utf-8").strip()
        except (OSError, UnicodeError):
            return None

    def close(self) -> None:
        self._closed = True
