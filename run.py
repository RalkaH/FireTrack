# run.py (v1.0)
"""
Запуск FireTrack как обычной программы: сервер плюс браузер.

Скрипт поднимает сервер, ждет, пока он ответит, и открывает интерфейс в браузере.
Если FireTrack уже запущен, просто открывает браузер. Если порт занят другой
программой, берет следующий свободный. Запускается ярлыком ``FireTrack.bat``,
остановка: закрыть окно с сервером.

Настройки (переменные окружения):

* ``FIRETRACK_HOST`` — адрес, по умолчанию ``127.0.0.1`` (только этот компьютер).
  Чтобы открывать систему с других компьютеров в сети, укажите ``0.0.0.0``.
* ``FIRETRACK_PORT`` — первый порт для проверки, по умолчанию ``8000``.
"""
import json
import os
import socket
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
HOST = os.getenv("FIRETRACK_HOST", "127.0.0.1")
FIRST_PORT = int(os.getenv("FIRETRACK_PORT", "8000"))
PORTS_TO_TRY = 20


def local_url(port: int) -> str:
    """Адрес интерфейса на этом компьютере."""
    return f"http://127.0.0.1:{port}"


def is_firetrack(port: int, timeout: float = 1.0) -> bool:
    """
    Проверяет, что на порту отвечает именно FireTrack.

    Args:
        port (int): Порт.
        timeout (float): Сколько ждать ответа, секунд.

    Returns:
        bool: True, если проверка работоспособности и заголовок API совпали.
    """
    try:
        with urllib.request.urlopen(f"{local_url(port)}/health", timeout=timeout) as resp:
            healthy = json.loads(resp.read().decode("utf-8")).get("status") == "ok"
        with urllib.request.urlopen(f"{local_url(port)}/openapi.json", timeout=timeout) as resp:
            title = json.loads(resp.read().decode("utf-8")).get("info", {}).get("title", "")
        return healthy and "средств пожаротушения" in title
    except (urllib.error.URLError, OSError, ValueError):
        return False


def port_is_free(port: int) -> bool:
    """Проверяет, можно ли занять порт."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE if os.name == "nt" else socket.SO_REUSEADDR, 1)
        try:
            sock.bind((HOST, port))
            return True
        except OSError:
            return False


def open_browser_when_ready(port: int, attempts: int = 60) -> None:
    """Ждет запуска сервера и открывает браузер."""
    for _ in range(attempts):
        if is_firetrack(port):
            webbrowser.open(local_url(port))
            return
        time.sleep(0.5)
    print("Сервер не ответил за 30 секунд. Откройте адрес вручную:", local_url(port))


def main() -> None:
    """Находит порт, запускает сервер и браузер."""
    # База и резервные копии ищутся относительно папки проекта
    os.chdir(BASE_DIR)

    for port in range(FIRST_PORT, FIRST_PORT + PORTS_TO_TRY):
        if is_firetrack(port):
            print("FireTrack уже запущен, открываю браузер")
            webbrowser.open(local_url(port))
            return
        if port_is_free(port):
            break
    else:
        print(f"Нет свободного порта в диапазоне {FIRST_PORT}-{FIRST_PORT + PORTS_TO_TRY - 1}")
        raise SystemExit(1)

    import uvicorn

    print(f"FireTrack: {local_url(port)}. Чтобы остановить сервер, закройте это окно.")
    threading.Thread(target=open_browser_when_ready, args=(port,), daemon=True).start()
    uvicorn.run("main:app", host=HOST, port=port, log_level="warning")


if __name__ == "__main__":
    main()
