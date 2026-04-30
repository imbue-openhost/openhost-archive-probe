"""Tiny probe app that reports the visibility of /data/app_data and /data/app_archive.

On startup it writes a marker file into each tier (recording the timestamp) so
we can verify on the host that the bind mounts landed in the right place. Then
it serves a small JSON status endpoint.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import socket
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any


APP_DATA_DIR = os.environ.get("OPENHOST_APP_DATA_DIR", "/data/app_data")
APP_ARCHIVE_DIR = os.environ.get("OPENHOST_APP_ARCHIVE_DIR", "/data/app_archive")


def _stat_dir(path: str) -> dict[str, Any]:
    info: dict[str, Any] = {"path": path, "exists": os.path.isdir(path)}
    if not info["exists"]:
        return info
    try:
        st = os.statvfs(path)
        info["fs_total_bytes"] = st.f_blocks * st.f_frsize
        info["fs_free_bytes"] = st.f_bavail * st.f_frsize
    except OSError as exc:
        info["statvfs_error"] = str(exc)
    try:
        info["entries"] = sorted(os.listdir(path))
    except OSError as exc:
        info["listdir_error"] = str(exc)
    return info


def _write_marker(path: str, label: str) -> dict[str, Any]:
    """Write a small file into ``path`` with a timestamp; report success/failure."""
    out: dict[str, Any] = {"path": path, "label": label}
    if not os.path.isdir(path):
        out["wrote"] = False
        out["error"] = "directory does not exist"
        return out
    marker = os.path.join(path, "archive_probe_marker.txt")
    try:
        with open(marker, "a", encoding="utf-8") as f:
            f.write(f"{_dt.datetime.now(_dt.timezone.utc).isoformat()} {label}\n")
        out["wrote"] = True
        out["marker_path"] = marker
        try:
            out["marker_size"] = os.path.getsize(marker)
        except OSError as exc:
            out["stat_error"] = str(exc)
    except OSError as exc:
        out["wrote"] = False
        out["error"] = str(exc)
    return out


def _build_report() -> dict[str, Any]:
    env_keys = sorted(k for k in os.environ if k.startswith("OPENHOST_"))
    env = {k: os.environ[k] for k in env_keys}
    return {
        "hostname": socket.gethostname(),
        "env": env,
        "app_data": _stat_dir(APP_DATA_DIR),
        "app_archive": _stat_dir(APP_ARCHIVE_DIR),
        "marker_data": _write_marker(APP_DATA_DIR, "from-app_data"),
        "marker_archive": _write_marker(APP_ARCHIVE_DIR, "from-app_archive"),
    }


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        body = json.dumps(_build_report(), indent=2, sort_keys=True).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        # Send access log to stdout so it shows up in `docker logs`.
        print("[req]", format % args, flush=True)


def main() -> None:
    # Print a startup report so it lands in container logs.
    report = _build_report()
    print("[startup]", json.dumps(report, indent=2, sort_keys=True), flush=True)
    server = HTTPServer(("0.0.0.0", 8080), _Handler)
    print("[startup] listening on 0.0.0.0:8080", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
