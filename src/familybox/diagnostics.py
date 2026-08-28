"""Read-only Raspberry Pi readiness checks for bench assembly."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class DiagnosticCheck:
    """One independently actionable hardware-readiness result."""

    name: str
    ok: bool
    detail: str


def read_pi_model(path: Path = Path("/proc/device-tree/model")) -> str | None:
    """Read the device-tree model without importing Raspberry Pi libraries."""

    try:
        model = path.read_bytes().decode("utf-8", errors="replace").strip("\x00\r\n ")
    except OSError:
        return None
    return model or None


def computer_model(
    hardware_mode: str,
    model_path: Path = Path("/proc/device-tree/model"),
) -> str:
    """Return a useful model label for the administration UI."""

    if hardware_mode != "raspberry_pi":
        return "Development computer (simulated hardware)"
    return read_pi_model(model_path) or "Raspberry Pi (model unavailable)"


def collect_pi_diagnostics(root: Path = Path("/")) -> list[DiagnosticCheck]:
    """Inspect a running Pi or a mounted test root without changing it."""

    model = read_pi_model(root / "proc/device-tree/model")
    checks = [
        DiagnosticCheck(
            "Raspberry Pi model",
            model is not None and model.startswith("Raspberry Pi"),
            model or "missing /proc/device-tree/model",
        )
    ]

    spi_path = root / "dev/spidev0.0"
    checks.append(
        DiagnosticCheck(
            "SPI0 device",
            spi_path.exists(),
            str(spi_path) if spi_path.exists() else "missing /dev/spidev0.0",
        )
    )

    gpio_devices = sorted(path.name for path in (root / "dev").glob("gpiochip*"))
    checks.append(
        DiagnosticCheck(
            "GPIO character device",
            bool(gpio_devices),
            ", ".join(gpio_devices) if gpio_devices else "no /dev/gpiochip* device",
        )
    )

    audio_cards = _read_text(root / "proc/asound/cards")
    checks.append(
        DiagnosticCheck(
            "MAX98357A audio card",
            audio_cards is not None and "MAX98357A" in audio_cards,
            "MAX98357A listed by ALSA"
            if audio_cards is not None and "MAX98357A" in audio_cards
            else "MAX98357A not listed in /proc/asound/cards",
        )
    )

    config_path = _boot_config_path(root)
    config = _read_text(config_path) if config_path is not None else None
    active_lines = _active_config_lines(config or "")
    checks.extend(
        (
            DiagnosticCheck(
                "SPI boot configuration",
                "dtparam=spi=on" in active_lines,
                "dtparam=spi=on is active"
                if "dtparam=spi=on" in active_lines
                else "missing active dtparam=spi=on",
            ),
            DiagnosticCheck(
                "MAX98357A boot overlay",
                "dtoverlay=max98357a,no-sdmode" in active_lines,
                "dtoverlay=max98357a,no-sdmode is active"
                if "dtoverlay=max98357a,no-sdmode" in active_lines
                else "missing active dtoverlay=max98357a,no-sdmode",
            ),
        )
    )
    return checks


def render_diagnostics(checks: Sequence[DiagnosticCheck]) -> str:
    """Render stable, copyable output for a bench troubleshooting session."""

    return "\n".join(
        f"{'PASS' if check.ok else 'FAIL'}  {check.name}: {check.detail}" for check in checks
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check FamilyBox Raspberry Pi device and boot configuration",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("/"),
        help="inspect another mounted root filesystem instead of /",
    )
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args(argv)
    checks = collect_pi_diagnostics(args.root)
    if args.json:
        print(json.dumps([asdict(check) for check in checks], indent=2))
    else:
        print(render_diagnostics(checks))
    return 0 if all(check.ok for check in checks) else 1


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _boot_config_path(root: Path) -> Path | None:
    candidates = (root / "boot/firmware/config.txt", root / "boot/config.txt")
    return next((path for path in candidates if path.is_file()), None)


def _active_config_lines(config: str) -> set[str]:
    return {
        line.strip()
        for line in config.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }


if __name__ == "__main__":
    raise SystemExit(main())
