"""Environment-backed application configuration."""

from __future__ import annotations

import os
import socket
import uuid
from dataclasses import dataclass
from pathlib import Path


def _env_path(name: str, default: Path) -> Path:
    return Path(os.environ.get(name, str(default))).expanduser().resolve()


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class Settings:
    """All mutable deployment choices, collected at the process boundary."""

    root_dir: Path
    media_dir: Path
    data_dir: Path
    cache_dir: Path
    logs_dir: Path
    database_path: Path
    mpv_socket_path: Path
    device_id: str
    device_name: str
    hostname: str
    hardware_mode: str = "fake"
    audio_mode: str = "fake"
    mpv_binary: str = "mpv"
    web_host: str = "0.0.0.0"
    web_port: int = 8080
    progress_save_interval: float = 60.0
    nfc_poll_interval: float = 0.15
    nfc_present_samples: int = 2
    nfc_removed_samples: int = 3
    log_level: str = "INFO"
    json_logs: bool = True
    dev_endpoints: bool = False

    @classmethod
    def from_env(cls) -> Settings:
        """Build settings with safe development defaults.

        The Pi installer sets ``FAMILYBOX_ROOT=/srv/familybox`` and
        ``FAMILYBOX_HARDWARE=raspberry_pi``. A source checkout defaults to a
        disposable, git-ignored ``.familybox`` directory and fake hardware.
        """

        checkout_root = Path.cwd() / ".familybox"
        root = _env_path("FAMILYBOX_ROOT", checkout_root)
        data = _env_path("FAMILYBOX_DATA_DIR", root / "data")
        cache = _env_path("FAMILYBOX_CACHE_DIR", root / "cache")
        hostname = socket.gethostname().split(".", maxsplit=1)[0]
        configured_device_id = os.environ.get("FAMILYBOX_DEVICE_ID")
        device_id = configured_device_id or str(
            uuid.uuid5(uuid.NAMESPACE_DNS, f"familybox:{hostname}")
        )

        settings = cls(
            root_dir=root,
            media_dir=_env_path("FAMILYBOX_MEDIA_DIR", root / "media"),
            data_dir=data,
            cache_dir=cache,
            logs_dir=_env_path("FAMILYBOX_LOGS_DIR", root / "logs"),
            database_path=_env_path("FAMILYBOX_DATABASE", data / "familybox.db"),
            mpv_socket_path=_env_path("FAMILYBOX_MPV_SOCKET", cache / "mpv.sock"),
            device_id=device_id,
            device_name=os.environ.get("FAMILYBOX_DEVICE_NAME", hostname),
            hostname=os.environ.get("FAMILYBOX_HOSTNAME", hostname),
            hardware_mode=os.environ.get("FAMILYBOX_HARDWARE", "fake").strip().lower(),
            audio_mode=os.environ.get(
                "FAMILYBOX_AUDIO",
                "mpv"
                if os.environ.get("FAMILYBOX_HARDWARE", "fake").strip().lower() == "raspberry_pi"
                else "fake",
            )
            .strip()
            .lower(),
            mpv_binary=os.environ.get("FAMILYBOX_MPV_BINARY", "mpv"),
            web_host=os.environ.get("FAMILYBOX_WEB_HOST", "0.0.0.0"),
            web_port=int(os.environ.get("FAMILYBOX_WEB_PORT", "8080")),
            progress_save_interval=float(os.environ.get("FAMILYBOX_PROGRESS_SAVE_INTERVAL", "60")),
            nfc_poll_interval=float(os.environ.get("FAMILYBOX_NFC_POLL_INTERVAL", "0.15")),
            nfc_present_samples=int(os.environ.get("FAMILYBOX_NFC_PRESENT_SAMPLES", "2")),
            nfc_removed_samples=int(os.environ.get("FAMILYBOX_NFC_REMOVED_SAMPLES", "3")),
            log_level=os.environ.get("FAMILYBOX_LOG_LEVEL", "INFO").upper(),
            json_logs=_env_bool("FAMILYBOX_JSON_LOGS", True),
            dev_endpoints=_env_bool("FAMILYBOX_DEV_ENDPOINTS", False),
        )
        settings.validate()
        settings.ensure_directories()
        return settings

    def validate(self) -> None:
        if self.hardware_mode not in {"fake", "raspberry_pi"}:
            raise ValueError("FAMILYBOX_HARDWARE must be 'fake' or 'raspberry_pi'")
        if self.audio_mode not in {"fake", "mpv"}:
            raise ValueError("FAMILYBOX_AUDIO must be 'fake' or 'mpv'")
        if not 1 <= self.web_port <= 65535:
            raise ValueError("FAMILYBOX_WEB_PORT must be between 1 and 65535")
        if self.progress_save_interval <= 0:
            raise ValueError("FAMILYBOX_PROGRESS_SAVE_INTERVAL must be positive")
        if self.nfc_present_samples < 1 or self.nfc_removed_samples < 1:
            raise ValueError("NFC debounce sample counts must be positive")

    def ensure_directories(self) -> None:
        for directory in (
            self.root_dir,
            self.media_dir,
            self.data_dir,
            self.cache_dir,
            self.logs_dir,
            self.database_path.parent,
            self.mpv_socket_path.parent,
        ):
            directory.mkdir(parents=True, exist_ok=True)
