"""Serve exactly one synthetic audit HTML file on this host's Tailscale address.

No directories, answer keys, or other files are served. The service itself has no password;
access depends on Tailscale's network policy. Stop it with Ctrl-C in its owning terminal.
"""

from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

TAILSCALE_ADDRESS = "100.122.128.11"


class AuditHandler(BaseHTTPRequestHandler):
    def _respond(self, *, head: bool = False) -> None:
        if urlsplit(self.path).path not in {"/", "/review-ko.html"}:
            self.send_error(404, "Not found")
            return
        content = self.server.audit_content
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'")
        self.end_headers()
        if not head:
            self.wfile.write(content)

    def do_GET(self) -> None:
        self._respond()

    def do_HEAD(self) -> None:
        self._respond(head=True)

    def do_POST(self) -> None:
        self.send_error(405, "Read-only")

    def log_message(self, format: str, *args) -> None:
        pass


def make_server(host: str, port: int, content: bytes) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((host, port), AuditHandler)
    server.audit_content = content
    return server


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, required=True, help="single synthetic HTML page")
    parser.add_argument("--port", type=int, default=8795)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("port must be in 1..65535")
    try:
        content = args.file.read_bytes()
        server = make_server(TAILSCALE_ADDRESS, args.port, content)
    except OSError as exc:
        parser.exit(2, f"cannot serve page: {exc}\n")
    print(
        f"Serving only {args.file.name} on http://{TAILSCALE_ADDRESS}:{args.port}/ "
        "(Tailscale policy applies; no application password).",
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
