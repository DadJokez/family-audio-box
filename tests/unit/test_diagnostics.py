from __future__ import annotations

import json
from pathlib import Path

from familybox.diagnostics import (
    DiagnosticStage,
    collect_pi_diagnostics,
    computer_model,
    main,
    read_pi_model,
    render_diagnostics,
)


def _complete_pi_root(root: Path) -> None:
    (root / "proc/device-tree").mkdir(parents=True)
    (root / "proc/device-tree/model").write_bytes(b"Raspberry Pi 3 Model A Plus Rev 1.0\x00")
    (root / "dev").mkdir()
    (root / "dev/spidev0.0").touch()
    (root / "dev/gpiochip0").touch()
    (root / "proc/asound").mkdir()
    (root / "proc/asound/cards").write_text(
        " 0 [MAX98357A ]: MAX98357A - MAX98357A\n",
        encoding="utf-8",
    )
    (root / "boot/firmware").mkdir(parents=True)
    (root / "boot/firmware/config.txt").write_text(
        "# FamilyBox\ndtparam=spi=on\ndtoverlay=max98357a,no-sdmode\n",
        encoding="utf-8",
    )


def test_complete_pi_root_passes_every_readiness_check(tmp_path: Path) -> None:
    _complete_pi_root(tmp_path)

    checks = collect_pi_diagnostics(tmp_path)

    assert all(check.ok for check in checks)
    assert read_pi_model(tmp_path / "proc/device-tree/model") == (
        "Raspberry Pi 3 Model A Plus Rev 1.0"
    )
    assert "PASS  SPI0 device" in render_diagnostics(checks)


def test_stages_do_not_require_components_that_are_still_boxed(tmp_path: Path) -> None:
    _complete_pi_root(tmp_path)

    base = collect_pi_diagnostics(tmp_path, DiagnosticStage.BASE)
    nfc = collect_pi_diagnostics(tmp_path, DiagnosticStage.NFC)
    audio = collect_pi_diagnostics(tmp_path, DiagnosticStage.AUDIO)

    assert [check.name for check in base] == [
        "Raspberry Pi model",
        "GPIO character device",
    ]
    assert [check.name for check in nfc] == [
        "Raspberry Pi model",
        "GPIO character device",
        "SPI boot configuration",
        "SPI0 device",
    ]
    assert len(audio) == 6


def test_missing_hardware_produces_actionable_failures(tmp_path: Path) -> None:
    (tmp_path / "boot").mkdir()
    (tmp_path / "boot/config.txt").write_text(
        "# dtparam=spi=on\ndtoverlay=max98357a\n",
        encoding="utf-8",
    )

    checks = collect_pi_diagnostics(tmp_path)

    assert not any(check.ok for check in checks)
    details = {check.name: check.detail for check in checks}
    assert details["Raspberry Pi model"] == "missing /proc/device-tree/model"
    assert details["SPI boot configuration"] == "missing active dtparam=spi=on"
    assert details["MAX98357A boot overlay"] == (
        "missing active dtoverlay=max98357a,no-sdmode"
    )


def test_model_label_distinguishes_simulation_and_pi(tmp_path: Path) -> None:
    model_path = tmp_path / "model"
    model_path.write_bytes(b"Raspberry Pi 4 Model B Rev 1.5\x00")

    assert computer_model("fake", model_path) == "Development computer (simulated hardware)"
    assert computer_model("raspberry_pi", model_path) == "Raspberry Pi 4 Model B Rev 1.5"
    assert computer_model("raspberry_pi", tmp_path / "missing") == (
        "Raspberry Pi (model unavailable)"
    )


def test_json_cli_is_script_friendly(tmp_path: Path, capsys) -> None:
    _complete_pi_root(tmp_path)

    assert main(("--root", str(tmp_path), "--stage", "base", "--json")) == 0
    payload = json.loads(capsys.readouterr().out)
    assert len(payload) == 2
    assert payload[0] == {
        "name": "Raspberry Pi model",
        "ok": True,
        "detail": "Raspberry Pi 3 Model A Plus Rev 1.0",
    }
