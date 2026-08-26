from __future__ import annotations

import json
import socket
import threading
from pathlib import Path
from uuid import uuid4

import pytest

from familybox.playback.mpv import MpvClient, MpvCommandError, MpvUnavailableError


@pytest.fixture
def socket_path():
    path = Path("/tmp") / f"familybox-test-{uuid4().hex}.sock"
    yield path
    path.unlink(missing_ok=True)


def test_reuses_one_ipc_connection_for_multiple_commands(socket_path):
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(str(socket_path))
    server.listen(1)
    received = []

    def serve():
        connection, _ = server.accept()
        with connection, connection.makefile("rwb") as stream:
            for data in (False, 73):
                request = json.loads(stream.readline())
                received.append(request)
                stream.write(
                    json.dumps(
                        {
                            "request_id": request["request_id"],
                            "error": "success",
                            "data": data,
                        }
                    ).encode()
                    + b"\n"
                )
                stream.flush()

    thread = threading.Thread(target=serve)
    thread.start()
    client = MpvClient(socket_path=socket_path, manage_process=False)

    assert client.get_property("pause") is False
    assert client.get_property("volume") == 73
    client.close()
    thread.join(timeout=2)
    server.close()

    assert [request["command"] for request in received] == [
        ["get_property", "pause"],
        ["get_property", "volume"],
    ]
    assert thread.is_alive() is False


def test_raises_clear_error_when_mpv_rejects_a_command(socket_path):
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(str(socket_path))
    server.listen(1)

    def serve():
        connection, _ = server.accept()
        with connection, connection.makefile("rwb") as stream:
            request = json.loads(stream.readline())
            stream.write(
                json.dumps(
                    {
                        "request_id": request["request_id"],
                        "error": "property unavailable",
                    }
                ).encode()
                + b"\n"
            )
            stream.flush()

    thread = threading.Thread(target=serve)
    thread.start()
    client = MpvClient(socket_path=socket_path, manage_process=False)

    with pytest.raises(MpvCommandError, match="property unavailable"):
        client.get_property("missing")

    client.close()
    thread.join(timeout=2)
    server.close()


def test_removes_verified_stale_socket_before_starting(socket_path):
    stale_server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    stale_server.bind(str(socket_path))
    stale_server.close()
    client = MpvClient(
        socket_path=socket_path,
        executable="/definitely/missing/mpv",
    )

    with pytest.raises(MpvUnavailableError, match="unable to start"):
        client.start()

    assert socket_path.exists() is False


def test_refuses_to_replace_an_active_ipc_socket(socket_path):
    active_server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    active_server.bind(str(socket_path))
    active_server.listen(1)
    client = MpvClient(socket_path=socket_path)

    with pytest.raises(MpvUnavailableError, match="already active"):
        client.start()

    assert socket_path.exists() is True
    active_server.close()
