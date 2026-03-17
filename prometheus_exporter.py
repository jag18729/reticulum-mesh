"""
Prometheus Exporter — polls all beacon peers and exposes metrics on :9877.

Runs on ThinkStation. Pi1 Prometheus scrapes it.

Metrics exposed (all labeled by `node=<name>`):
  mesh_cpu_percent
  mesh_ram_percent
  mesh_disk_percent
  mesh_uptime_seconds
  mesh_beacon_up          (1 = reachable, 0 = unreachable)

Usage:
  python3 prometheus_exporter.py [--port 9877] [--interval 60]

Add to Pi1's prometheus.yml:
  scrape_configs:
    - job_name: 'reticulum_mesh'
      static_configs:
        - targets: ['<thinkstation_tailscale_ip>:9877']

Then Pi3 appears in existing dashboards alongside Pi0/Pi1/Pi2/RV2.
"""

import RNS
import sys
import time
import json
import argparse
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, ".")
from lib.identity import load_or_create_identity, load_peers
from lib.common import APP_NAME, wait_for_path

# Thread-safe store: {node_name: {metric: value}}
_metrics: dict = {}
_metrics_lock = threading.Lock()


# ── Beacon polling ────────────────────────────────────────────────────

def poll_beacon(name: str, dest_hash_hex: str, timeout: float = 15.0):
    dest_hash = bytes.fromhex(dest_hash_hex)

    if not wait_for_path(dest_hash, timeout=timeout):
        with _metrics_lock:
            _metrics[name] = {"up": 0}
        return

    remote_id = RNS.Identity.recall(dest_hash)
    if not remote_id:
        with _metrics_lock:
            _metrics[name] = {"up": 0}
        return

    destination = RNS.Destination(
        remote_id, RNS.Destination.OUT, RNS.Destination.SINGLE, APP_NAME, "beacon"
    )

    responded = threading.Event()
    result = [None]

    def on_response(receipt):
        if receipt.response:
            try:
                result[0] = json.loads(receipt.response.decode("utf-8"))
            except Exception:
                pass
        responded.set()

    def on_failed(receipt):
        responded.set()

    def on_link(link):
        link.request("stats", data=None,
                     response_callback=on_response,
                     failed_callback=on_failed,
                     timeout=10)

    link = RNS.Link(destination)
    link.set_link_established_callback(on_link)
    responded.wait(timeout=timeout)

    with _metrics_lock:
        if result[0]:
            data = result[0]
            _metrics[name] = {
                "up": 1,
                "cpu_percent": data.get("cpu_pct", float("nan")),
                "ram_percent": data.get("ram_pct", float("nan")),
                "disk_percent": data.get("disk_pct", float("nan")),
                "uptime_seconds": data.get("uptime_s", float("nan")),
            }
        else:
            _metrics[name] = {"up": 0}


def poll_loop(peers: dict, interval: int):
    """Continuously poll all beacons in a background thread."""
    while True:
        threads = [
            threading.Thread(target=poll_beacon, args=(name, h), daemon=True)
            for name, h in peers.items()
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=20)
        time.sleep(interval)


# ── Prometheus HTTP handler ───────────────────────────────────────────

HELP_LINES = {
    "mesh_beacon_up":       ("gauge", "1 if beacon is reachable, 0 otherwise"),
    "mesh_cpu_percent":     ("gauge", "CPU usage percent"),
    "mesh_ram_percent":     ("gauge", "RAM usage percent"),
    "mesh_disk_percent":    ("gauge", "Disk usage percent"),
    "mesh_uptime_seconds":  ("gauge", "Node uptime in seconds"),
}

METRIC_KEYS = [
    ("mesh_beacon_up",      "up"),
    ("mesh_cpu_percent",    "cpu_percent"),
    ("mesh_ram_percent",    "ram_percent"),
    ("mesh_disk_percent",   "disk_percent"),
    ("mesh_uptime_seconds", "uptime_seconds"),
]


def render_metrics() -> str:
    lines = []

    with _metrics_lock:
        snapshot = {k: dict(v) for k, v in _metrics.items()}

    for metric_name, (mtype, help_text) in HELP_LINES.items():
        lines.append(f"# HELP {metric_name} {help_text}")
        lines.append(f"# TYPE {metric_name} {mtype}")

    for metric_name, data_key in METRIC_KEYS:
        for node, data in sorted(snapshot.items()):
            val = data.get(data_key)
            if val is None:
                continue
            if isinstance(val, float) and val != val:  # NaN check
                continue
            lines.append(f'{metric_name}{{node="{node}"}} {val}')

    lines.append("")
    return "\n".join(lines)


class MetricsHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/metrics":
            self.send_response(404)
            self.end_headers()
            return
        body = render_metrics().encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass  # suppress access logs


# ── Main ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Reticulum beacon → Prometheus exporter")
    parser.add_argument("--port", type=int, default=9877, help="HTTP port (default: 9877)")
    parser.add_argument("--interval", type=int, default=60,
                        help="Beacon poll interval in seconds (default: 60)")
    args = parser.parse_args()

    RNS.Reticulum()
    load_or_create_identity()

    peers = load_peers()
    if not peers:
        print("No saved peers. Register beacons first: python3 monitor.py --add <name> <hash>")
        sys.exit(1)

    print(f"Polling {len(peers)} beacon(s) every {args.interval}s: {', '.join(peers)}")
    print(f"Metrics served at http://0.0.0.0:{args.port}/metrics")

    poller = threading.Thread(target=poll_loop, args=(peers, args.interval), daemon=True)
    poller.start()

    server = HTTPServer(("0.0.0.0", args.port), MetricsHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nExporter stopped.")


if __name__ == "__main__":
    main()
