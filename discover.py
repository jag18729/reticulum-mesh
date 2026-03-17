"""
Peer discovery — listens for announces and builds a live peer directory.
Useful for finding nodes on the mesh without knowing their hashes in advance.

Usage:
  python3 discover.py           # listen and display discovered nodes
  python3 discover.py --save    # auto-save discovered nodes by hostname
  python3 discover.py --json    # output JSON (for scripting)
"""

import RNS
import sys
import time
import json
import argparse
import threading
from datetime import datetime

sys.path.insert(0, ".")
from lib.identity import load_or_create_identity, save_peer
from lib.common import APP_NAME

peers: dict = {}  # hash_hex -> {first_seen, last_seen, hops, rssi, snr}
peers_lock = threading.Lock()


def on_announce(destination_hash, announced_identity, app_data, announce_packet):
    h = RNS.prettyhexrep(destination_hash)
    now = time.time()
    hops = RNS.Transport.hops_to(destination_hash)

    with peers_lock:
        if h not in peers:
            peers[h] = {"first_seen": now, "hash": h, "hops": hops}
            label = app_data.decode("utf-8", errors="replace") if app_data else h[:16]
            peers[h]["label"] = label
            ts = datetime.now().strftime("%H:%M:%S")
            print(f"[{ts}] NEW  {h[:16]}...  hops={hops}  label={label!r}")
        else:
            peers[h]["last_seen"] = now
            peers[h]["hops"] = hops


def display_all():
    with peers_lock:
        if not peers:
            print("No peers discovered yet.")
            return
        print(f"\n{'Hash (short)':<20} {'Hops':<6} {'Label':<24} First seen")
        print("-" * 72)
        for h, info in sorted(peers.items(), key=lambda x: x[1]["first_seen"]):
            short = h[:16] + "..."
            first = datetime.fromtimestamp(info["first_seen"]).strftime("%H:%M:%S")
            print(f"{short:<20} {info['hops']:<6} {info.get('label',''):<24} {first}")


def announce_self(identity, interval: int):
    """Periodically announce ourselves so others can discover us."""
    while True:
        time.sleep(interval)


def main():
    parser = argparse.ArgumentParser(description="Reticulum peer discovery")
    parser.add_argument("--save", action="store_true", help="Auto-save discovered peers by label")
    parser.add_argument("--json", action="store_true", help="Dump peers as JSON on exit")
    parser.add_argument("--duration", type=int, default=0,
                        help="Stop after N seconds (0 = run forever)")
    args = parser.parse_args()

    RNS.Reticulum()
    identity = load_or_create_identity()

    # Announce ourselves
    import socket
    from lib.common import make_destination
    hostname = socket.gethostname().encode("utf-8")
    destination = make_destination(identity, "beacon")
    destination.announce(app_data=hostname)

    # Register announce handler for our app
    RNS.Transport.register_announce_handler(
        RNS.AnnounceHandler(
            aspect_filter=f"{APP_NAME}.beacon",
            received_announce_callback=on_announce,
        )
    )

    print(f"Listening for announces on aspect: {APP_NAME}.beacon")
    print("Press Ctrl+C to stop.\n")

    try:
        if args.duration:
            time.sleep(args.duration)
        else:
            while True:
                time.sleep(1)
    except KeyboardInterrupt:
        pass

    display_all()

    if args.save:
        with peers_lock:
            for h, info in peers.items():
                label = info.get("label", h[:8])
                save_peer(label, h)

    if args.json:
        with peers_lock:
            print(json.dumps(peers, indent=2))


if __name__ == "__main__":
    main()
