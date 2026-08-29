"""Server-rendered administration site and small JSON control surface."""

from __future__ import annotations

import asyncio
import shutil
import socket
import tempfile
import time
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from pathlib import Path
from typing import Annotated, Any, Protocol
from urllib.parse import quote

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from familybox import __version__
from familybox.config import Settings
from familybox.content.local import (
    SUPPORTED_ARTWORK_EXTENSIONS,
    SUPPORTED_AUDIO_EXTENSIONS,
    LocalContentError,
    LocalContentProvider,
)
from familybox.diagnostics import computer_model
from familybox.domain.models import ContentTrack, Device
from familybox.hardware.interfaces import (
    AudioOutput,
    ButtonController,
    NfcReader,
    PowerMonitor,
    VolumeController,
)
from familybox.persistence.database import Database
from familybox.playback.manager import PlaybackManager, PlaybackStatus


class PlayerServiceView(Protocol):
    detected_uid: str | None
    last_unknown_uid: str | None
    button_error: str | None
    volume_error: str | None

    async def refresh_tag_assignment(self, uid: str) -> None: ...


class NfcServiceView(Protocol):
    last_error: str | None


class FamilyBoxRuntimeView(Protocol):
    settings: Settings
    database: Database
    local_content: LocalContentProvider
    playback: PlaybackManager
    nfc: NfcServiceView
    player: PlayerServiceView
    nfc_reader: NfcReader
    buttons: ButtonController
    volume: VolumeController
    audio_output: AudioOutput
    power_monitor: PowerMonitor
    started_monotonic: float


Lifespan = Callable[[FastAPI], AbstractAsyncContextManager[None]]

_WEB_ROOT = Path(__file__).resolve().parent
_NOTICES: dict[str, tuple[str, str]] = {
    "imported": ("success", "The audio is stored on this box."),
    "updated": ("success", "Your changes are saved."),
    "deleted": ("success", "The local content was removed."),
    "assigned": ("success", "The tag is assigned and works immediately."),
    "unassigned": ("success", "The tag assignment was removed."),
}


def create_web_app(*, lifespan: Lifespan | None = None) -> FastAPI:
    """Create the HTTP application; runtime dependencies arrive in lifespan."""

    app = FastAPI(
        title="FamilyBox",
        version=__version__,
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,
    )
    app.mount("/static", StaticFiles(directory=_WEB_ROOT / "static"), name="static")
    templates = Jinja2Templates(directory=_WEB_ROOT / "templates")

    @app.get("/", include_in_schema=False)
    async def root() -> RedirectResponse:
        return RedirectResponse("/now-playing", status_code=307)

    @app.get("/healthz", response_class=JSONResponse)
    async def health(request: Request) -> dict[str, str]:
        runtime = _runtime(request)
        runtime.database.connection.execute("SELECT 1").fetchone()
        return {"status": "ok", "version": __version__}

    @app.get("/now-playing", response_class=HTMLResponse)
    async def now_playing(request: Request) -> HTMLResponse:
        runtime = _runtime(request)
        context = await _base_context(request, runtime, active_page="now-playing")
        return templates.TemplateResponse(
            request=request,
            name="now_playing.html",
            context=context,
        )

    @app.get("/library", response_class=HTMLResponse)
    async def library(request: Request) -> HTMLResponse:
        runtime = _runtime(request)
        context = await _base_context(request, runtime, active_page="library")
        context["contents"] = _content_cards(runtime.database)
        return templates.TemplateResponse(
            request=request,
            name="library.html",
            context=context,
        )

    @app.post("/library/import")
    async def import_content(
        request: Request,
        title: Annotated[str, Form(min_length=1, max_length=160)],
        audio_files: Annotated[list[UploadFile], File()],
        artwork: Annotated[UploadFile | None, File()] = None,
    ) -> RedirectResponse:
        runtime = _runtime(request)
        try:
            with tempfile.TemporaryDirectory(
                prefix="upload-", dir=runtime.settings.cache_dir
            ) as temporary:
                staging = Path(temporary)
                sources: list[Path] = []
                for index, upload in enumerate(audio_files):
                    sources.append(await _save_audio_upload(upload, staging / str(index)))
                artwork_path = (
                    await _save_artwork_upload(artwork, staging / "artwork")
                    if artwork is not None and artwork.filename
                    else None
                )
                content = await asyncio.to_thread(
                    runtime.local_content.import_content,
                    sources,
                    title=title,
                    artwork=artwork_path,
                )
        except (LocalContentError, OSError, ValueError) as exc:
            return _error_redirect("/library", exc)
        return RedirectResponse(
            f"/library/{content.id}?notice=imported",
            status_code=303,
        )

    @app.get("/library/{content_id}", response_class=HTMLResponse)
    async def content_detail(request: Request, content_id: str) -> HTMLResponse:
        runtime = _runtime(request)
        content = runtime.database.get_content(content_id)
        if content is None:
            return await _error_page(
                templates,
                request,
                runtime,
                404,
                "That story is not here.",
                "It may have been removed from this player.",
            )
        tracks = runtime.database.list_content_tracks(content_id)
        context = await _base_context(request, runtime, active_page="library")
        context.update(
            {
                "content": content,
                "tracks": [_track_view(track) for track in tracks],
            }
        )
        return templates.TemplateResponse(
            request=request,
            name="content_detail.html",
            context=context,
        )

    @app.post("/library/{content_id}/edit")
    async def edit_content(
        request: Request,
        content_id: str,
        title: Annotated[str, Form(min_length=1, max_length=160)],
        artwork: Annotated[UploadFile | None, File()] = None,
    ) -> RedirectResponse:
        runtime = _runtime(request)
        try:
            with tempfile.TemporaryDirectory(
                prefix="artwork-", dir=runtime.settings.cache_dir
            ) as temporary:
                artwork_path = (
                    await _save_artwork_upload(artwork, Path(temporary))
                    if artwork is not None and artwork.filename
                    else None
                )
                await asyncio.to_thread(
                    runtime.local_content.update_content,
                    content_id,
                    title=title,
                    artwork=artwork_path,
                )
        except KeyError:
            raise HTTPException(status_code=404, detail="Content not found") from None
        except (LocalContentError, OSError, ValueError) as exc:
            return _error_redirect(f"/library/{content_id}", exc)
        return RedirectResponse(
            f"/library/{content_id}?notice=updated",
            status_code=303,
        )

    @app.post("/library/{content_id}/delete")
    async def delete_content(request: Request, content_id: str) -> RedirectResponse:
        runtime = _runtime(request)
        if runtime.playback.current_content_id == content_id:
            await asyncio.to_thread(runtime.playback.stop)
        try:
            deleted = await asyncio.to_thread(runtime.local_content.delete, content_id)
        except (LocalContentError, OSError) as exc:
            return _error_redirect(f"/library/{content_id}", exc)
        if not deleted:
            raise HTTPException(status_code=404, detail="Content not found")
        return RedirectResponse("/library?notice=deleted", status_code=303)

    @app.get("/artwork/{content_id}", response_class=FileResponse)
    async def artwork_file(request: Request, content_id: str) -> FileResponse:
        runtime = _runtime(request)
        content = runtime.database.get_content(content_id)
        if content is None or not content.artwork_path:
            raise HTTPException(status_code=404, detail="Artwork not found")
        path = _safe_media_path(runtime.settings.media_dir, content.artwork_path)
        if not path.is_file():
            raise HTTPException(status_code=404, detail="Artwork not found")
        return FileResponse(path)

    @app.get("/tags", response_class=HTMLResponse)
    async def tags(request: Request) -> HTMLResponse:
        runtime = _runtime(request)
        context = await _base_context(request, runtime, active_page="tags")
        observation = runtime.database.get_last_unknown_tag()
        context.update(
            {
                "last_unknown_uid": observation.uid if observation else None,
                "contents": runtime.database.list_content(),
                "tags": _tag_views(runtime.database),
            }
        )
        return templates.TemplateResponse(
            request=request,
            name="tags.html",
            context=context,
        )

    @app.post("/tags/assign")
    async def assign_tag(
        request: Request,
        uid: Annotated[str, Form(min_length=2, max_length=64)],
        content_id: Annotated[str, Form(min_length=1, max_length=64)],
        name: Annotated[str, Form(max_length=100)] = "",
    ) -> RedirectResponse:
        runtime = _runtime(request)
        if runtime.database.get_content(content_id) is None:
            return _error_redirect("/tags", ValueError("Choose content from this box"))
        try:
            tag = runtime.database.assign_tag(uid, content_id, name.strip() or None)
            await runtime.player.refresh_tag_assignment(tag.uid)
        except ValueError as exc:
            return _error_redirect("/tags", exc)
        return RedirectResponse("/tags?notice=assigned", status_code=303)

    @app.post("/tags/{uid}/delete")
    async def unassign_tag(request: Request, uid: str) -> RedirectResponse:
        runtime = _runtime(request)
        try:
            deleted = runtime.database.unassign_tag(uid)
            if deleted:
                await runtime.player.refresh_tag_assignment(uid)
        except ValueError as exc:
            return _error_redirect("/tags", exc)
        if not deleted:
            raise HTTPException(status_code=404, detail="Tag not found")
        return RedirectResponse("/tags?notice=unassigned", status_code=303)

    @app.get("/device", response_class=HTMLResponse)
    async def device(request: Request) -> HTMLResponse:
        runtime = _runtime(request)
        context = await _base_context(request, runtime, active_page="device")
        context["device"] = _device_view(runtime)
        context["dev_endpoints"] = runtime.settings.dev_endpoints
        return templates.TemplateResponse(
            request=request,
            name="device.html",
            context=context,
        )

    @app.get("/api/status", response_class=JSONResponse)
    async def api_status(request: Request) -> dict[str, Any]:
        runtime = _runtime(request)
        return {
            "playback": await _playback_view(runtime),
            "nfc": _nfc_view(runtime),
        }

    @app.post("/api/controls/{action}", response_class=JSONResponse)
    async def playback_control(request: Request, action: str) -> dict[str, Any]:
        runtime = _runtime(request)
        controls = {
            "toggle": runtime.playback.toggle_pause,
            "play": runtime.playback.resume,
            "pause": runtime.playback.pause,
            "next": runtime.playback.next,
            "previous": runtime.playback.previous,
        }
        control = controls.get(action)
        if control is None:
            raise HTTPException(status_code=404, detail="Unknown playback control")
        await asyncio.to_thread(control)
        return {
            "playback": await _playback_view(runtime),
            "nfc": _nfc_view(runtime),
        }

    @app.post("/api/volume", response_class=JSONResponse)
    async def volume_control(
        request: Request,
        volume: Annotated[float, Form(ge=0, le=100)],
    ) -> dict[str, Any]:
        runtime = _runtime(request)
        await asyncio.to_thread(runtime.playback.set_volume, volume)
        return {
            "playback": await _playback_view(runtime),
            "nfc": _nfc_view(runtime),
        }

    @app.post("/api/dev/nfc", response_class=JSONResponse)
    async def fake_nfc_present(
        request: Request,
        uid: Annotated[str, Form(min_length=2, max_length=64)],
    ) -> dict[str, str]:
        runtime = _runtime(request)
        _require_dev_hardware(runtime)
        place_tag = getattr(runtime.nfc_reader, "place_tag", None)
        if not callable(place_tag):
            raise HTTPException(status_code=409, detail="NFC reader is not simulated")
        try:
            normalized = place_tag(uid)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {"uid": str(normalized)}

    @app.post("/api/dev/nfc/remove", response_class=JSONResponse)
    async def fake_nfc_removed(request: Request) -> dict[str, str | None]:
        runtime = _runtime(request)
        _require_dev_hardware(runtime)
        remove_tag = getattr(runtime.nfc_reader, "remove_tag", None)
        if not callable(remove_tag):
            raise HTTPException(status_code=409, detail="NFC reader is not simulated")
        return {"uid": remove_tag()}

    return app


def _runtime(request: Request) -> FamilyBoxRuntimeView:
    runtime = getattr(request.app.state, "runtime", None)
    if runtime is None:
        raise RuntimeError("FamilyBox runtime has not started")
    return runtime  # type: ignore[no-any-return]


async def _base_context(
    request: Request,
    runtime: FamilyBoxRuntimeView,
    *,
    active_page: str,
) -> dict[str, Any]:
    device = runtime.database.get_device(runtime.settings.device_id) or Device(
        id=runtime.settings.device_id,
        name=runtime.settings.device_name,
    )
    playback = await _playback_view(runtime)
    hardware = _hardware_views(runtime)
    return {
        "request": request,
        "active_page": active_page,
        "device": device,
        "device_short_id": device.id.split("-", maxsplit=1)[0].upper(),
        "hardware_ok": all(item["ok"] for item in hardware),
        "status": playback,
        "nfc": _nfc_view(runtime),
        "flash": _flash(request),
    }


async def _playback_view(runtime: FamilyBoxRuntimeView) -> dict[str, Any]:
    status = await asyncio.to_thread(runtime.playback.status)
    content = (
        runtime.database.get_content(status.content_id) if status.content_id is not None else None
    )
    tracks = (
        runtime.database.list_content_tracks(status.content_id)
        if status.content_id is not None
        else []
    )
    track = tracks[status.track_index] if status.track_index < len(tracks) else None
    saved = (
        runtime.database.get_playback_state(runtime.settings.device_id, content.id)
        if content is not None
        else None
    )
    state_label = "Ready"
    if content is not None:
        state_label = "Finished" if status.completed else "Paused" if status.paused else "Playing"
    return {
        "content_id": status.content_id,
        "title": status.title,
        "track_title": track.title if track else None,
        "track_number": status.track_index + 1 if content else None,
        "track_count": status.track_count,
        "position_seconds": status.position_seconds,
        "position_label": _format_duration(status.position_seconds),
        "duration_seconds": status.duration_seconds,
        "duration_label": _format_duration(status.duration_seconds),
        "progress_percent": _progress_percent(status),
        "paused": status.paused,
        "playing": content is not None and not status.paused,
        "completed": status.completed,
        "state_label": state_label,
        "volume": status.volume,
        "provider": content.provider if content else None,
        "artwork_url": f"/artwork/{content.id}" if content and content.artwork_path else None,
        "resume_label": _relative_time(saved.updated_at.timestamp())
        if saved
        else "No position yet",
    }


def _nfc_view(runtime: FamilyBoxRuntimeView) -> dict[str, Any]:
    last_unknown = runtime.database.get_last_unknown_tag()
    return {
        "uid": runtime.player.detected_uid,
        "last_unknown_uid": last_unknown.uid if last_unknown else None,
    }


def _content_cards(database: Database) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    for content in database.list_content():
        tracks = database.list_content_tracks(content.id)
        known_durations = [track.duration_seconds for track in tracks]
        total_duration = (
            sum(duration for duration in known_durations if duration is not None)
            if tracks and all(duration is not None for duration in known_durations)
            else None
        )
        cards.append(
            {
                "id": content.id,
                "title": content.title,
                "content_type": content.content_type.value,
                "artwork_path": content.artwork_path,
                "track_count": len(tracks),
                "total_duration_label": _format_duration(total_duration),
            }
        )
    return cards


def _track_view(track: ContentTrack) -> dict[str, Any]:
    return {
        "id": track.id,
        "title": track.title,
        "filename": Path(track.local_path or "").name,
        "duration_label": _format_duration(track.duration_seconds),
    }


def _tag_views(database: Database) -> list[dict[str, Any]]:
    views: list[dict[str, Any]] = []
    for tag in database.list_tags():
        content = database.get_content(tag.content_id)
        views.append(
            {
                "uid": tag.uid,
                "name": tag.name,
                "content_id": tag.content_id,
                "content_title": content.title if content else "Missing content",
            }
        )
    return views


def _device_view(runtime: FamilyBoxRuntimeView) -> dict[str, Any]:
    device = runtime.database.get_device(runtime.settings.device_id) or Device(
        id=runtime.settings.device_id,
        name=runtime.settings.device_name,
    )
    disk = shutil.disk_usage(runtime.settings.root_dir)
    hardware = _hardware_views(runtime)
    return {
        "id": device.id,
        "name": device.name,
        "hostname": runtime.settings.hostname,
        "computer_model": computer_model(runtime.settings.hardware_mode),
        "ip_address": _local_ip_address(runtime.settings.hostname),
        "disk_free": _format_bytes(disk.free),
        "disk_used_percent": round((disk.used / disk.total) * 100) if disk.total else 0,
        "uptime": _format_duration(_system_uptime(runtime.started_monotonic)),
        "software_version": __version__,
        "hardware": hardware,
        "hardware_ok": all(item["ok"] for item in hardware),
    }


def _hardware_views(runtime: FamilyBoxRuntimeView) -> list[dict[str, Any]]:
    try:
        audio = runtime.audio_output.status()
        audio_ok = audio.available
        audio_label = audio.detail or audio.device
    except Exception as exc:
        audio_ok, audio_label = False, str(exc) or type(exc).__name__
    try:
        power = runtime.power_monitor.status()
        power_label = (
            f"Battery {power.battery_percent:.0f}%"
            if power.battery_percent is not None
            else "Managed by system"
        )
        power_ok = not power.shutdown_requested
    except Exception as exc:
        power_label, power_ok = str(exc) or type(exc).__name__, False

    nfc_error = _adapter_error(runtime.nfc_reader) or runtime.nfc.last_error
    button_error = _adapter_error(runtime.buttons) or runtime.player.button_error
    volume_error = _adapter_error(runtime.volume) or runtime.player.volume_error
    control_errors = [error for error in (button_error, volume_error) if error]
    controls_status = (
        "; ".join(control_errors)
        if control_errors
        else runtime.settings.hardware_mode.replace("_", " ").title()
    )
    return [
        {
            "name": "NFC reader",
            "ok": nfc_error is None,
            "status": nfc_error or type(runtime.nfc_reader).__name__,
        },
        {"name": "Audio output", "ok": audio_ok, "status": audio_label},
        {"name": "Power", "ok": power_ok, "status": power_label},
        {"name": "Controls", "ok": not control_errors, "status": controls_status},
    ]


def _adapter_error(adapter: object) -> str | None:
    error = getattr(adapter, "error", None)
    return str(error) if error else None


async def _save_audio_upload(upload: UploadFile, directory: Path) -> Path:
    filename = Path(upload.filename or "").name
    if Path(filename).suffix.lower() not in SUPPORTED_AUDIO_EXTENSIONS:
        raise LocalContentError(f"Unsupported audio file: {filename or 'unnamed file'}")
    await asyncio.to_thread(directory.mkdir, parents=True, exist_ok=True)
    destination = directory / filename
    await _copy_upload(upload, destination)
    return destination


async def _save_artwork_upload(upload: UploadFile, directory: Path) -> Path:
    filename = Path(upload.filename or "").name
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_ARTWORK_EXTENSIONS:
        raise LocalContentError("Artwork must be a JPEG, PNG, or WebP file")
    await asyncio.to_thread(directory.mkdir, parents=True, exist_ok=True)
    destination = directory / f"cover{suffix}"
    await _copy_upload(upload, destination)
    return destination


async def _copy_upload(upload: UploadFile, destination: Path) -> None:
    await upload.seek(0)
    await asyncio.to_thread(_copy_upload_sync, upload.file, destination)


def _copy_upload_sync(source: Any, destination: Path) -> None:
    with destination.open("wb") as output:
        shutil.copyfileobj(source, output, length=1024 * 1024)


def _safe_media_path(media_root: Path, stored_path: str) -> Path:
    root = media_root.resolve()
    path = (root / stored_path).resolve()
    if not path.is_relative_to(root) or path == root:
        raise HTTPException(status_code=404, detail="Media not found")
    return path


def _format_duration(seconds: float | None) -> str:
    if seconds is None or seconds < 0:
        return "—"
    total = int(seconds)
    hours, remainder = divmod(total, 3600)
    minutes, remaining_seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{remaining_seconds:02d}"
    return f"{minutes}:{remaining_seconds:02d}"


def _progress_percent(status: PlaybackStatus) -> float:
    if not status.duration_seconds or status.duration_seconds <= 0:
        return 0.0
    return round(min(100.0, max(0.0, status.position_seconds / status.duration_seconds * 100)), 2)


def _relative_time(timestamp: float) -> str:
    elapsed = max(0, int(time.time() - timestamp))
    if elapsed < 10:
        return "Saved just now"
    if elapsed < 60:
        return f"Saved {elapsed} seconds ago"
    if elapsed < 3600:
        return f"Saved {elapsed // 60} minutes ago"
    return f"Saved {elapsed // 3600} hours ago"


def _format_bytes(value: int) -> str:
    amount = float(value)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if amount < 1024 or unit == "TB":
            precision = 0 if unit in {"B", "KB"} else 1
            return f"{amount:.{precision}f} {unit}"
        amount /= 1024
    return f"{amount:.1f} TB"


def _system_uptime(started_monotonic: float) -> float:
    try:
        return float(Path("/proc/uptime").read_text(encoding="utf-8").split()[0])
    except (OSError, ValueError, IndexError):
        return max(0.0, time.monotonic() - started_monotonic)


def _local_ip_address(hostname: str) -> str:
    try:
        addresses = socket.getaddrinfo(hostname, None, socket.AF_INET)
    except socket.gaierror:
        return "Not connected"
    for address in addresses:
        candidate = str(address[4][0])
        if not candidate.startswith("127."):
            return candidate
    return str(addresses[0][4][0]) if addresses else "Not connected"


def _flash(request: Request) -> dict[str, str] | None:
    notice = request.query_params.get("notice")
    if notice in _NOTICES:
        kind, message = _NOTICES[notice]
        return {"kind": kind, "message": message}
    if notice == "error":
        detail = request.query_params.get("detail", "That change could not be saved.")
        return {"kind": "error", "message": detail[:240]}
    return None


def _error_redirect(path: str, error: Exception) -> RedirectResponse:
    return RedirectResponse(
        f"{path}?notice=error&detail={quote(str(error)[:240])}",
        status_code=303,
    )


def _require_dev_hardware(runtime: FamilyBoxRuntimeView) -> None:
    if not runtime.settings.dev_endpoints or runtime.settings.hardware_mode != "fake":
        raise HTTPException(status_code=404, detail="Not found")


async def _error_page(
    templates: Jinja2Templates,
    request: Request,
    runtime: FamilyBoxRuntimeView,
    status_code: int,
    heading: str,
    detail: str,
) -> HTMLResponse:
    context = await _base_context(request, runtime, active_page="")
    context.update({"status_code": status_code, "heading": heading, "detail": detail})
    return templates.TemplateResponse(
        request=request,
        name="error.html",
        context=context,
        status_code=status_code,
    )
