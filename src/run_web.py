import errno
import os
import socket

import uvicorn

from .web import app


DEFAULT_PORT = 8080
PORT_ATTEMPTS = 100


def requested_port() -> int:
    """Return the configured starting port, defaulting to 8080."""
    value = os.getenv("WEB_PORT", str(DEFAULT_PORT))
    try:
        port = int(value)
    except ValueError as error:
        raise SystemExit(f"WEB_PORT must be an integer, got {value!r}") from error
    if not 1 <= port <= 65535:
        raise SystemExit("WEB_PORT must be between 1 and 65535")
    return port


def find_listening_socket(start_port: int, attempts: int = PORT_ATTEMPTS):
    """Bind the first available port at or above ``start_port``."""
    end_port = min(start_port + attempts, 65536)
    for port in range(start_port, end_port):
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            server_socket.bind(("127.0.0.1", port))
            server_socket.listen()
            return server_socket, port
        except OSError as error:
            server_socket.close()
            if error.errno == errno.EADDRINUSE:
                continue
            raise
    raise SystemExit(
        f"No available port found between {start_port} and {end_port - 1}. "
        "Set WEB_PORT to choose another starting port."
    )


def main():
    requested = requested_port()
    server_socket, port = find_listening_socket(requested)
    if port != requested:
        print(f"Port {requested} is in use; starting on port {port} instead.")
    print(f"DAG control panel: http://localhost:{port}")

    # This panel can control the Telegram bot and must remain local unless an
    # authenticated reverse proxy is deliberately placed in front of it.
    config = uvicorn.Config(app, host="127.0.0.1", port=port)
    server = uvicorn.Server(config)
    try:
        server.run(sockets=[server_socket])
    finally:
        server_socket.close()


if __name__ == "__main__":
    main()
