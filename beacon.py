"""
System stats beacon — broadcasts CPU, RAM, disk, uptime over the mesh.
Run this on each node (Pi3, ThinkStation, etc.) you want to monitor.

Usage: python3 beacon.py [--interval 30]
"""

import RNS
import sys
import time
import json
import socket
import argparse
import platform

sys.path.insert(0, ".")
from lib.identity import load_or_create_identity
from lib.common import APP_NAME, make_destination

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


def collect_stats() -> dict:
    stats = {
        "hostname": socket.gethostname(),
        "platform": platform.system(),
        "timestamp": time.time(),
    }

    if HAS_PSUTIL:
        vm = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        stats.update({
            "cpu_pct": psutil.cpu_percent(interval=1),
            "ram_pct": vm.percent,
            "ram_used_mb": vm.used // 1024 // 1024,
            "ram_total_mb": vm.total // 1024 // 1024,
            "disk_pct": disk.percent,
            "disk_used_gb": disk.used // 1024 ** 3,
            "disk_total_gb": disk.total // 1024 ** 3,
            "uptime_s": int(time.time() - psutil.boot_time()),
        })
        temps = {}
        try:
            for name, entries in psutil.sensors_temperatures().items():
                if entries:
                    temps[name] = round(entries[0].current, 1)
        except Exception:
            pass
        if temps:
            stats["temps_c"] = temps
    else:
        # Fallback: read /proc on Linux
        try:
            with open("/proc/uptime") as f:
                stats["uptime_s"] = int(float(f.read().split()[0]))
        except Exception:
            pass
        try:
            with open("/proc/loadavg") as f:
                parts = f.read().split()
                stats["load_avg"] = [float(parts[0]), float(parts[1]), float(parts[2])]
        except Exception:
            pass

    return stats


def handle_stats_request(path, data, request_id, link_id, remote_identity, requested_at):
    return json.dumps(collect_stats()).encode("utf-8")


def main():
    parser = argparse.ArgumentParser(description="System stats beacon")
    parser.add_argument("--interval", type=int, default=60, help="Announce interval in seconds")
    args = parser.parse_args()

    if not HAS_PSUTIL:
        print("[!] psutil not installed — limited stats. Run: pip3 install psutil")

    RNS.Reticulum()
    identity = load_or_create_identity()

    destination = make_destination(identity, "beacon")
    destination.register_request_handler(
        "stats",
        response_generator=handle_stats_request,
        allow=RNS.Destination.ALLOW_ALL,
    )
    destination.announce()

    hostname = socket.gethostname()
    print(f"Beacon started on {hostname}")
    print(f"Address: {RNS.prettyhexrep(destination.hash)}")
    print(f"Responding to stats requests. Announcing every {args.interval}s.\n")

    try:
        while True:
            destination.announce()
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nBeacon stopped.")


if __name__ == "__main__":
    main()
