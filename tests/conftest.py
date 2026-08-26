from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from familybox.config import Settings


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    root = tmp_path / "familybox"
    configured = Settings(
        root_dir=root,
        media_dir=root / "media",
        data_dir=root / "data",
        cache_dir=root / "cache",
        logs_dir=root / "logs",
        database_path=root / "data" / "familybox.db",
        mpv_socket_path=root / "cache" / "mpv.sock",
        device_id=str(uuid4()),
        device_name="Test player",
        hostname="familybox-test",
        hardware_mode="fake",
        audio_mode="fake",
        progress_save_interval=0.1,
        nfc_poll_interval=0.01,
        nfc_present_samples=1,
        nfc_removed_samples=1,
        json_logs=False,
        dev_endpoints=True,
    )
    configured.ensure_directories()
    return configured
