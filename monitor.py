"""
Fleet monitor — polls beacons and displays a live system stats dashboard.

Usage:
  python3 monitor.py                      # poll all saved beacon peers
  python3 monitor.py <name_or_hash> ...   # poll specific beacons
  python3 monitor.py --add pi3 <hash>     # save a beacon
"""

import RNS
import sys
import time
import json
import argparse
import threading
from datetime import datetime

sys.path.insert(0, ".")
from lib.identity import load_or_create_identity, save_peer, resolve_peer, load_peers
from lib.common import APP_NAME, wait_for_path

results: dict = {}
results_lock = threading.Lock()


def format_uptime(seconds: int) -> str:
    d, r = divmod(int(seconds), 86400)
    h, r = divmod(r, 3600)
    m, s = divmod(r, 60)
    if d:
        return f"{d}d {h}h {m}m"
    if h:
        return f"{h}h {m}m"
    return f"{m}m {s}s"


def bar(pct: float, width=20) -> str:
    filled = int(pct / 100 * width)
    return "[" + "#" * filled + "." * (width - filled) + f"] {pct:.1f}%"


def poll_beacon(name: str, dest_hash_hex: str):
    dest_hash = bytes.fromhex(dest_hash_hex)

    if not wait_for_path(dest_hash, timeout=8):
        with results_lock:
            results[name] = {"error": "no path", "hash": dest_hash_hex}
        return

    remote_id = RNS.Identity.recall(dest_hash)
    if not remote_id:
        with results_lock:
            results[name] = {"error": "identity unknown", "hash": dest_hash_hex}
        return

    destination = RNS.Destination(
        remote_id, RNS.Destination.OUT, RNS.Destination.SINGLE, APP_NAME, "beacon"
    )

    responded = threading.Event()

    def on_response(request_receipt):
        if request_receipt.response:
            try:
                data = json.loads(request_receipt.response.decode("utf-8"))
                data["hash"] = dest_hash_hex
                data["polled_at"] = time.time()
                with results_lock:
                    results[name] = data
            except Exception as e:
                with results_lock:
                    results[name] = {"error": str(e), "hash": dest_hash_hex}
        responded.set()

    def on_failed(receipt):
        with results_lock:
            results[name] = {"error": "request failed", "hash": dest_hash_hex}
        responded.set()

    def on_link(link):
        link.request("stats", data=None,
                     response_callback=on_response,
                     failed_callback=on_failed,
                     timeout=10)

    link = RNS.Link(destination)
    link.set_link_established_callback(on_link)
    responded.wait(timeout=15)


def display(beacons: dict):
    print("\033[2J\033[H", end="")  # clear screen
    print(f"Reticulum Fleet Monitor  —  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    for name, data in sorted(results.items()):
        print(f"  Node: {name}  [{data.get('hash','')[:16]}...]")
        if "error" in data:
            print(f"    !! {data['error']}\n")
            continue

        host = data.get("hostname", "?")
        uptime = format_uptime(data["uptime_s"]) if "uptime_s" in data else "?"
        print(f"    host={host}  uptime={uptime}")

        if "cpu_pct" in data:
            print(f"    CPU  {bar(data['cpu_pct'])}")
            print(f"    RAM  {bar(data['ram_pct'])}  {data['ram_used_mb']}MB / {data['ram_total_mb']}MB")
            print(f"    Disk {bar(data['disk_pct'])}  {data['disk_used_gb']}GB / {data['disk_total_gb']}GB")
        elif "load_avg" in data:
            la = data["load_avg"]
            print(f"    Load avg: {la[0]} {la[1]} {la[2]}")

        if "temps_c" in data:
            temps = "  ".join(f"{k}:{v}°C" for k, v in data["temps_c"].items())
            print(f"    Temp: {temps}")

        age = time.time() - data.get("polled_at", time.time())
        print(f"    (polled {int(age)}s ago)\n")

    if not results:
        print("  No data yet — waiting for beacons...\n")

    print("Press Ctrl+C to exit.")


def poll_all(beacons: dict, interval: int):
    while True:
        threads = [
            threading.Thread(target=poll_beacon, args=(name, h), daemon=True)
            for name, h in beacons.items()
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=20)
        display(beacons)
        time.sleep(interval)


def main():
    parser = argparse.ArgumentParser(description="Fleet monitor")
    parser.add_argument("targets", nargs="*", help="Beacon names or hashes")
    parser.add_argument("--add", nargs=2, metavar=("NAME", "HASH"), help="Save a beacon peer")
    parser.add_argument("--interval", type=int, default=30, help="Poll interval in seconds")
    args = parser.parse_args()

    if args.add:
        save_peer(args.add[0], args.add[1])
        return

    RNS.Reticulum()
    load_or_create_identity()

    saved = load_peers()
    if args.targets:
        beacons = {t: resolve_peer(t) for t in args.targets}
    else:
        beacons = saved

    if not beacons:
        print("No beacons specified. Use --add NAME HASH to register one.")
        sys.exit(1)

    print(f"Monitoring {len(beacons)} beacon(s)...")
    try:
        poll_all(beacons, args.interval)
    except KeyboardInterrupt:
        print("\nMonitor stopped.")


if __name__ == "__main__":
    main()
