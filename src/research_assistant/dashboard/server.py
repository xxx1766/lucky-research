"""A tiny localhost-only HTTP server for the live dashboard.

``/dashboard serve`` runs this: every request regenerates the dashboard from
current on-disk state (so it always reflects the latest ideas/papers), and the
served page carries a ``<meta refresh>`` so the browser re-polls on a cadence.
No new dependencies — stdlib ``http.server`` — and it binds to ``127.0.0.1``
only, never ``0.0.0.0``: this is a personal-machine dev surface, not a public
service.
"""
from __future__ import annotations

from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from research_assistant.dashboard import collect
from research_assistant.dashboard.render import render_html

# Loopback only — the dashboard exposes local research state and must not be
# reachable from the network.
_HOST = "127.0.0.1"


def _make_handler(refresh_seconds: int):
    class _Handler(BaseHTTPRequestHandler):
        # Silence the default one-line-per-request stderr spam.
        def log_message(self, *_args):  # noqa: D401, ANN001
            pass

        def _serve_html(self, *, body: bool) -> None:
            try:
                html = render_html(
                    collect(today=date.today()), refresh_seconds=refresh_seconds
                )
                payload = html.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(payload)))
                # Live data — never let a browser/proxy cache the page.
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                if body:
                    self.wfile.write(payload)
            except Exception as exc:  # pragma: no cover - defensive
                msg = f"dashboard regeneration failed: {exc}".encode()
                self.send_response(500)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(msg)))
                self.end_headers()
                if body:
                    self.wfile.write(msg)

        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/favicon.ico":
                self.send_response(204)
                self.end_headers()
                return
            self._serve_html(body=True)

        def do_HEAD(self) -> None:  # noqa: N802
            self._serve_html(body=False)

    return _Handler


def serve(port: int, refresh_seconds: int) -> int:
    """Start the live dashboard server (blocking until Ctrl-C).

    Returns a process exit code: 0 on a clean Ctrl-C, non-zero if the port is
    unavailable.
    """
    try:
        httpd = ThreadingHTTPServer((_HOST, port), _make_handler(refresh_seconds))
    except OSError as exc:
        print(f"could not bind {_HOST}:{port} — {exc}")
        print("  (is another dashboard already running? try a different --port)")
        return 1

    url = f"http://{_HOST}:{port}/"
    print(f"dashboard live at {url}", flush=True)
    print(
        f"  regenerates from disk on every request · auto-refresh every {refresh_seconds}s",
        flush=True,
    )
    print("  press Ctrl-C to stop", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        httpd.server_close()
    return 0
