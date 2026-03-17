"""
Watchdog — dead man's switch for Pi3 (Vandine).

Runs on ThinkStation as a cron job every 5 minutes.
Polls Pi3's beacon. On consecutive failures → Telegram alert via control-plane.py.
On recovery → sends recovery alert. Persists state to avoid repeat alerts.

Usage:
  python3 watchdog.py [--peer pi3] [--threshold 3] [--timeout 15]

Cron (add with: crontab -e):
  */5 * * * * cd ~/reticulum-mesh && python3 watchdog.py >> ~/.reticulum-mesh/watchdog.log 2>&1
"""

import RNS
import sys
import time
import json
import socket
import argparse
import subprocess
import threading
from pathlib import Path

sys.path.insert(0, ".")
from lib.identity import load_or_create_identity, resolve_peer, load_peers
from lib.common import APP_NAME, wait_for_path

STATE_FILE = Path.home() / ".reticulum-mesh" / "watchdog-state.json"
CONTROL_PLANE = Path.home() / ".openclaw" / "control-plane.py"


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {}


def save_state(state: dict):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


def send_telegram(message: str) -> bool:
    """Fire a Telegram alert via control-plane.py send pi2 whale-watcher."""
    try:
        result = subprocess.run(
            ["python3.14", str(CONTROL_PLANE), "send", "pi2", "whale-watcher", message],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            print(f"[alert sent] {message}")
            return True
        print(f"[alert failed] exit={result.returncode} {result.stderr.strip()}")
        return False
    except Exception as e:
        print(f"[alert error] {e}")
        return False


def poll_beacon(dest_hash_hex: str, timeout: float = 15.0) -> bool:
    """Return True if beacon responds to a stats request."""
    dest_hash = bytes.fromhex(dest_hash_hex)

    if not wait_for_path(dest_hash, timeout=timeout):
        return False

    remote_id = RNS.Identity.recall(dest_hash)
    if not remote_id:
        return False

    destination = RNS.Destination(
        remote_id, RNS.Destination.OUT, RNS.Destination.SINGLE, APP_NAME, "beacon"
    )

    responded = threading.Event()
    success = [False]

    def on_response(receipt):
        if receipt.response:
            success[0] = True
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
    return success[0]


def main():
    parser = argparse.ArgumentParser(description="Beacon watchdog for Pi3 Vandine")
    parser.add_argument("--peer", default="pi3", help="Peer name or hash to watch (default: pi3)")
    parser.add_argument("--threshold", type=int, default=3,
                        help="Consecutive failures before alerting (default: 3)")
    parser.add_argument("--timeout", type=float, default=15.0,
                        help="Per-poll timeout in seconds (default: 15)")
    args = parser.parse_args()

    # Resolve peer hash
    hash_hex = resolve_peer(args.peer)
    if not hash_hex:
        peers = load_peers()
        if not peers:
            print(f"[watchdog] Peer '{args.peer}' not found. Register with: python3 monitor.py --add pi3 <hash>")
            sys.exit(1)
        # If --peer is 'pi3' and not in peers, try first available
        hash_hex = list(peers.values())[0]
        print(f"[watchdog] Peer '{args.peer}' not found, using first saved peer.")

    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] Watchdog checking peer '{args.peer}' ({hash_hex[:16]}...)")

    RNS.Reticulum()
    load_or_create_identity()

    reachable = poll_beacon(hash_hex, timeout=args.timeout)

    state = load_state()
    peer_state = state.get(args.peer, {"failures": 0, "alerted": False, "last_ok": None})

    if reachable:
        print(f"[{ts}] Beacon reachable — OK")
        was_alerted = peer_state.get("alerted", False)
        peer_state = {"failures": 0, "alerted": False, "last_ok": time.time()}
        state[args.peer] = peer_state
        save_state(state)

        if was_alerted:
            send_telegram(f"✅ Pi3 Vandine beacon recovered ({args.peer})")
    else:
        failures = peer_state.get("failures", 0) + 1
        peer_state["failures"] = failures
        alerted = peer_state.get("alerted", False)
        print(f"[{ts}] Beacon unreachable — failure #{failures}")

        if failures >= args.threshold and not alerted:
            msg = f"⚠️ Pi3 Vandine beacon unreachable ({failures} consecutive failures)"
            if send_telegram(msg):
                peer_state["alerted"] = True

        state[args.peer] = peer_state
        save_state(state)


if __name__ == "__main__":
    main()
