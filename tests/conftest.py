"""Общие фикстуры для тестов."""

import http.server
import threading

import pytest

PAYLOAD_SIZE = 256 * 1024  # 256 КБ


class _PayloadHandler(http.server.BaseHTTPRequestHandler):
    """Отдаёт фиксированный набор байт с корректным Content-Length."""

    payload = b"x" * PAYLOAD_SIZE

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Length", str(len(self.payload)))
        self.end_headers()
        self.wfile.write(self.payload)

    def log_message(self, format, *args):
        # Молча, чтобы не засорять вывод тестов.
        pass


@pytest.fixture
def file_url():
    """Локальный HTTP-сервер, возвращающий URL файла известного размера."""
    server = http.server.HTTPServer(("127.0.0.1", 0), _PayloadHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/file.bin"
    finally:
        server.shutdown()
        thread.join()
