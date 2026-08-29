from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import replace
from typing import Any

from fastapi.testclient import TestClient

import familybox.runtime as runtime_module
from familybox.config import Settings
from familybox.hardware.fake import FakeButtonController, FakeVolumeController
from familybox.hardware.interfaces import ButtonAction
from familybox.hardware.unavailable import (
    UnavailableAudioOutput,
    UnavailableButtonController,
    UnavailableNfcReader,
    UnavailablePowerMonitor,
    UnavailableVolumeController,
)
from familybox.main import create_app
from familybox.runtime import FamilyBoxRuntime


def _wait_for(predicate: Callable[[], bool], timeout: float = 1.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("condition was not reached before timeout")


def _import_story(client: TestClient, title: str = "The Railway Children") -> str:
    response = client.post(
        "/library/import",
        data={"title": title},
        files=[
            ("audio_files", ("01-arrival.mp3", b"chapter one", "audio/mpeg")),
            ("audio_files", ("02-journey.m4b", b"chapter two", "audio/mp4")),
        ],
        follow_redirects=False,
    )
    assert response.status_code == 303
    return response.headers["location"].split("/", maxsplit=3)[2].split("?", maxsplit=1)[0]


def test_pages_health_and_local_import(settings: Settings) -> None:
    app = create_app(settings)
    with TestClient(app) as client:
        assert client.get("/healthz").json()["status"] == "ok"
        for path, marker in (
            ("/now-playing", "The story on this box"),
            ("/library", "Stories stored on this box"),
            ("/tags", "What each object plays"),
            ("/device", "Test player"),
        ):
            response = client.get(path)
            assert response.status_code == 200
            assert marker in response.text

        assert "Development computer (simulated hardware)" in client.get("/device").text

        content_id = _import_story(client)
        detail = client.get(f"/library/{content_id}")
        assert detail.status_code == 200
        assert "The Railway Children" in detail.text
        assert "01-arrival" in detail.text
        assert "02-journey" in detail.text
        assert (settings.media_dir / content_id / "001.mp3").is_file()
        assert (settings.media_dir / content_id / "002.m4b").is_file()


def test_unknown_tag_assignment_starts_and_removal_pauses(settings: Settings) -> None:
    app = create_app(settings)
    with TestClient(app) as client:
        content_id = _import_story(client, "A Child's Garden of Verses")
        runtime: FamilyBoxRuntime = client.app.state.runtime

        placed = client.post("/api/dev/nfc", data={"uid": "04:A1:B2:C3:D4:E5:80"})
        assert placed.status_code == 200
        assert placed.json()["uid"] == "04A1B2C3D4E580"
        _wait_for(lambda: runtime.database.get_last_unknown_tag() is not None)

        tags_page = client.get("/tags")
        assert "04A1B2C3D4E580" in tags_page.text
        assigned = client.post(
            "/tags/assign",
            data={
                "uid": "04A1B2C3D4E580",
                "content_id": content_id,
                "name": "Wooden fox",
            },
            follow_redirects=False,
        )
        assert assigned.status_code == 303
        _wait_for(lambda: runtime.playback.current_content_id == content_id)
        assert runtime.playback.status().paused is False

        response = client.post("/api/volume", data={"volume": "37"})
        assert response.status_code == 200
        assert response.json()["playback"]["volume"] == 37

        client.post("/api/dev/nfc/remove")
        _wait_for(lambda: runtime.playback.status().paused)
        state = runtime.database.get_playback_state(settings.device_id, content_id)
        assert state is not None


def test_complete_simulated_player_flow_survives_restart(settings: Settings) -> None:
    uid = "04A1B2C3D4E580"
    app = create_app(settings)
    with TestClient(app) as client:
        content_id = _import_story(client, "Restartable Story")
        runtime: FamilyBoxRuntime = client.app.state.runtime
        assert isinstance(runtime.buttons, FakeButtonController)
        assert isinstance(runtime.volume, FakeVolumeController)

        client.post("/api/dev/nfc", data={"uid": uid})
        _wait_for(lambda: runtime.database.get_last_unknown_tag() is not None)
        assigned = client.post(
            "/tags/assign",
            data={"uid": uid, "content_id": content_id, "name": "Blue figure"},
            follow_redirects=False,
        )
        assert assigned.status_code == 303
        _wait_for(lambda: runtime.playback.current_content_id == content_id)

        runtime.buttons.press(ButtonAction.NEXT)
        _wait_for(lambda: runtime.playback.status().track_index == 1)
        runtime.volume.rotate(2)
        _wait_for(lambda: runtime.playback.status().volume == 60)
        runtime.buttons.press(ButtonAction.PLAY_PAUSE)
        _wait_for(lambda: runtime.playback.status().paused)
        runtime.buttons.press(ButtonAction.PLAY_PAUSE)
        _wait_for(lambda: not runtime.playback.status().paused)

        runtime.playback.seek(12)
        client.post("/api/dev/nfc/remove")
        _wait_for(lambda: runtime.playback.status().paused)
        saved = runtime.database.get_playback_state(settings.device_id, content_id)
        assert saved is not None
        assert saved.track_index == 1
        assert saved.position_seconds >= 12

    restarted_app = create_app(settings)
    with TestClient(restarted_app) as client:
        restarted: FamilyBoxRuntime = client.app.state.runtime
        client.post("/api/dev/nfc", data={"uid": uid})
        _wait_for(lambda: restarted.playback.current_content_id == content_id)
        status = restarted.playback.status()
        assert status.track_index == 1
        assert status.position_seconds >= 12
        assert status.paused is False


def test_edit_unassign_and_delete_workflows(settings: Settings) -> None:
    app = create_app(settings)
    with TestClient(app) as client:
        content_id = _import_story(client)

        edited = client.post(
            f"/library/{content_id}/edit",
            data={"title": "Railway Stories"},
            files={"artwork": ("cover.jpg", b"jpeg bytes", "image/jpeg")},
            follow_redirects=False,
        )
        assert edited.status_code == 303
        runtime: Any = client.app.state.runtime
        content = runtime.database.get_content(content_id)
        assert content.title == "Railway Stories"
        assert (settings.media_dir / content_id / "cover.jpg").is_file()
        assert client.get(f"/artwork/{content_id}").content == b"jpeg bytes"

        runtime.database.assign_tag("01020304", content_id, "Card")
        unassigned = client.post("/tags/01020304/delete", follow_redirects=False)
        assert unassigned.status_code == 303
        assert runtime.database.get_tag("01020304") is None

        deleted = client.post(f"/library/{content_id}/delete", follow_redirects=False)
        assert deleted.status_code == 303
        assert runtime.database.get_content(content_id) is None
        assert not (settings.media_dir / content_id).exists()


def test_dev_hardware_endpoints_are_hidden_when_disabled(settings: Settings) -> None:
    disabled = replace(settings, dev_endpoints=False)
    app = create_app(disabled)
    with TestClient(app) as client:
        assert client.post("/api/dev/nfc", data={"uid": "01020304"}).status_code == 404


def test_pi_hardware_failures_leave_diagnostic_ui_available(
    settings: Settings,
    monkeypatch: Any,
) -> None:
    def fail_initialization(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise RuntimeError("bench wiring fault")

    for adapter_name in (
        "Pn532NfcReader",
        "GpioButtonController",
        "GpioVolumeController",
        "RaspberryPiPowerMonitor",
        "Max98357aAudioOutput",
    ):
        monkeypatch.setattr(runtime_module, adapter_name, fail_initialization)

    pi_settings = replace(settings, hardware_mode="raspberry_pi", audio_mode="fake")
    app = create_app(pi_settings)
    with TestClient(app) as client:
        response = client.get("/device")
        assert response.status_code == 200
        assert "Needs attention" in response.text
        assert "bench wiring fault" in response.text

        runtime: FamilyBoxRuntime = client.app.state.runtime
        assert isinstance(runtime.nfc_reader, UnavailableNfcReader)
        assert isinstance(runtime.buttons, UnavailableButtonController)
        assert isinstance(runtime.volume, UnavailableVolumeController)
        assert isinstance(runtime.power_monitor, UnavailablePowerMonitor)
        assert isinstance(runtime.audio_output, UnavailableAudioOutput)
