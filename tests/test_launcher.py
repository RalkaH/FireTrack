# tests/test_launcher.py
"""Тесты запуска как программы: выбор порта и распознавание своего сервера."""
import socket

import run


def test_busy_port_detected():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen(1)
        port = sock.getsockname()[1]
        assert run.port_is_free(port) is False
    assert run.port_is_free(port) is True


def test_foreign_server_is_not_firetrack():
    """На свободном порту и на чужом сервере FireTrack не определяется."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    assert run.is_firetrack(port, timeout=0.2) is False


def test_api_title_matches_launcher_check(client):
    """Запускатель узнает свой сервер по заголовку API: он не должен разойтись с main.py."""
    assert "средств пожаротушения" in client.get("/openapi.json").json()["info"]["title"]
    assert client.get("/health").json() == {"status": "ok"}
