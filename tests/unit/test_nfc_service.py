from __future__ import annotations

import asyncio
import time

from familybox.content.base import PlayableContent, PlayableTrack
from familybox.domain.events import TagPresent, TagRemoved, UnknownTag
from familybox.domain.models import Content, PlaybackState
from familybox.hardware.fake import FakeButtonController, FakeNfcReader, FakeVolumeController
from familybox.hardware.interfaces import ButtonAction, VolumeEvent
from familybox.playback.fake import FakePlaybackEngine
from familybox.playback.manager import PlaybackManager
from familybox.services.nfc import NfcService
from familybox.services.player import PlayerService


class TagRepository:
    def __init__(self) -> None:
        self.known: set[str] = set()
        self.observations: list[str] = []

    def resolve_tag(self, uid: str):
        return object() if uid in self.known else None

    def observe_unknown_tag(self, uid: str):
        self.observations.append(uid)


async def test_debounces_presence_duplicates_and_removal():
    repository = TagRepository()
    reader = FakeNfcReader()
    service = NfcService(reader, repository, present_confirmations=2, removal_confirmations=2)
    events = []
    service.subscribe(events.append)

    await service.process_reading("04:A1:B2:C3")
    assert events == []
    await service.process_reading("04:A1:B2:C3")

    assert [type(event) for event in events] == [TagPresent, UnknownTag]
    assert all(event.uid == "04A1B2C3" for event in events)
    assert repository.observations == ["04A1B2C3"]

    await service.process_reading("04:A1:B2:C3")
    await service.process_reading(None)
    assert len(events) == 2
    await service.process_reading(None)

    assert isinstance(events[-1], TagRemoved)
    assert events[-1].uid == "04A1B2C3"
    assert service.visible_uid is None


async def test_switching_tags_emits_removed_before_new_presence():
    repository = TagRepository()
    repository.known.update({"01020304", "AABBCCDD"})
    service = NfcService(FakeNfcReader(), repository, present_confirmations=1)
    events = []
    service.subscribe(events.append)

    await service.process_reading("01020304")
    await service.process_reading("AABBCCDD")

    assert [type(event) for event in events] == [TagPresent, TagRemoved, TagPresent]
    assert [event.uid for event in events] == ["01020304", "01020304", "AABBCCDD"]


async def test_recheck_makes_a_new_assignment_effective_without_replacing_tag():
    repository = TagRepository()
    service = NfcService(FakeNfcReader(), repository, present_confirmations=1)
    events = []
    service.subscribe(events.append)
    await service.process_reading("DEADBEEF")
    repository.known.add("DEADBEEF")

    await service.recheck_current_tag()

    assert [type(event) for event in events] == [TagPresent, UnknownTag, TagPresent]
    assert repository.observations == ["DEADBEEF"]


async def test_player_starts_pauses_and_resumes_from_tag_presence():
    content = Content(
        id="book",
        title="Story",
        provider="local",
        provider_reference="book",
    )

    class Repository(TagRepository):
        def __init__(self):
            super().__init__()
            self.known.add("01020304")
            self.states: dict[tuple[str, str], PlaybackState] = {}

        def resolve_tag(self, uid: str):
            return content if uid in self.known else None

        def get_playback_state(self, device_id: str, content_id: str):
            return self.states.get((device_id, content_id))

        def save_playback_state(self, state: PlaybackState):
            self.states[(state.device_id, state.content_id)] = state
            return state

    class Provider:
        provider_name = "local"

        def resolve(self, selected: Content):
            return PlayableContent(
                selected,
                (PlayableTrack("track", selected.id, 0, "One", "/media/one.mp3"),),
            )

    repository = Repository()
    nfc = NfcService(FakeNfcReader(), repository, present_confirmations=1, removal_confirmations=1)
    engine = FakePlaybackEngine()
    playback = PlaybackManager(
        engine, repository, device_id="box-a", progress_interval_seconds=3600
    )
    player = PlayerService(
        nfc=nfc,
        repository=repository,
        providers={"local": Provider()},  # type: ignore[dict-item]
        playback=playback,
    )
    nfc.subscribe(player.handle_event)

    await nfc.process_reading("01020304")
    assert engine.snapshot().paused is False
    await nfc.process_reading(None)
    assert engine.snapshot().paused is True
    await nfc.process_reading("01020304")
    assert engine.snapshot().paused is False
    assert playback.current_content_id == "book"

    repository.known.remove("01020304")
    await player.refresh_tag_assignment("01020304")
    assert engine.snapshot().paused is True
    playback.shutdown()


async def test_physical_control_loops_retry_after_transient_driver_errors():
    class Repository(TagRepository):
        def __init__(self) -> None:
            super().__init__()
            self.states: dict[tuple[str, str], PlaybackState] = {}

        def get_playback_state(self, device_id: str, content_id: str):
            return self.states.get((device_id, content_id))

        def save_playback_state(self, state: PlaybackState):
            self.states[(state.device_id, state.content_id)] = state
            return state

    class FlakyButtons(FakeButtonController):
        def __init__(self) -> None:
            super().__init__()
            self.calls = 0

        def read_action(self, timeout_seconds: float = 0.2) -> ButtonAction | None:
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("temporary button fault")
            return super().read_action(timeout_seconds)

    class FlakyVolume(FakeVolumeController):
        def __init__(self) -> None:
            super().__init__()
            self.calls = 0

        def read_event(self, timeout_seconds: float = 0.2) -> VolumeEvent | None:
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("temporary encoder fault")
            return super().read_event(timeout_seconds)

    repository = Repository()
    nfc = NfcService(FakeNfcReader(), repository, poll_interval_seconds=0.01)
    engine = FakePlaybackEngine()
    playback = PlaybackManager(
        engine,
        repository,
        device_id="box-a",
        progress_interval_seconds=3600,
    )
    buttons = FlakyButtons()
    volume = FlakyVolume()
    buttons.press(ButtonAction.PLAY_PAUSE)
    volume.rotate(1)
    player = PlayerService(
        nfc=nfc,
        repository=repository,
        providers={},
        playback=playback,
        buttons=buttons,
        volume=volume,
        control_poll_seconds=0.01,
    )

    await player.start()

    def wait_for_volume_change() -> None:
        deadline = time.monotonic() + 1.5
        while engine.snapshot().volume != 55 and time.monotonic() < deadline:
            time.sleep(0.01)

    await asyncio.to_thread(wait_for_volume_change)

    assert engine.snapshot().volume == 55
    assert buttons.calls >= 2
    assert volume.calls >= 2
    assert player.button_error is None
    assert player.volume_error is None
    await player.stop()
