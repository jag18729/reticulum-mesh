"""
Interactive CLI chat over Reticulum TCP mesh.
Uses persistent identity so your address never changes.

Usage:
  Listen:  python3 chat.py
  Connect: python3 chat.py <destination_name_or_hash>
  Save peer: python3 chat.py --save-peer pi3 <hash>
"""

import RNS
import sys
import time
import threading
import argparse
from datetime import datetime

sys.path.insert(0, ".")
from lib.identity import load_or_create_identity, save_peer, resolve_peer, list_peers
from lib.common import APP_NAME, make_destination, wait_for_path

active_link = None
print_lock = threading.Lock()


def ts():
    return datetime.now().strftime("%H:%M:%S")


def safe_print(msg):
    with print_lock:
        print(f"\r{msg}")
        print("> ", end="", flush=True)


def on_message(data, packet):
    text = data.decode("utf-8", errors="replace")
    safe_print(f"[{ts()}] remote: {text}")


def on_link_incoming(link):
    global active_link
    if active_link:
        link.teardown()
        return
    active_link = link
    link.set_packet_callback(on_message)
    link.set_link_closed_callback(on_link_closed)
    safe_print(f"[{ts()}] -- connected")


def on_link_closed(link):
    global active_link
    active_link = None
    safe_print(f"[{ts()}] -- disconnected")


def on_link_established_outbound(link):
    global active_link
    active_link = link
    link.set_packet_callback(on_message)
    link.set_link_closed_callback(on_link_closed)
    safe_print(f"[{ts()}] -- connected")


def input_loop():
    global active_link
    while True:
        try:
            text = input("> ").strip()
        except EOFError:
            break
        if not text:
            continue
        if text.lower() in ("/quit", "/exit", "/q"):
            if active_link:
                active_link.teardown()
            sys.exit(0)
        if active_link:
            RNS.Packet(active_link, text.encode("utf-8")).send()
            safe_print(f"[{ts()}]    you: {text}")
        else:
            safe_print("[!] Not connected.")


def listen_mode(identity):
    RNS.Reticulum()
    destination = make_destination(identity, "chat")
    destination.set_link_established_callback(on_link_incoming)
    destination.announce()
    print(f"Listening at: {RNS.prettyhexrep(destination.hash)}")
    print("Waiting for connection... Type /quit to exit.\n")
    input_loop()


def connect_mode(identity, dest_hash_hex):
    RNS.Reticulum()
    dest_hash = bytes.fromhex(dest_hash_hex)

    if not wait_for_path(dest_hash):
        print("Could not find path to destination.")
        sys.exit(1)

    remote_id = RNS.Identity.recall(dest_hash)
    if not remote_id:
        print("Could not recall remote identity.")
        sys.exit(1)

    destination = RNS.Destination(
        remote_id, RNS.Destination.OUT, RNS.Destination.SINGLE, APP_NAME, "chat"
    )
    link = RNS.Link(destination)
    link.set_link_established_callback(on_link_established_outbound)
    link.set_link_closed_callback(on_link_closed)

    print(f"Connecting to {dest_hash_hex[:16]}...")
    time.sleep(2)
    input_loop()


def main():
    parser = argparse.ArgumentParser(description="Reticulum mesh chat")
    parser.add_argument("destination", nargs="?", help="Name or hash to connect to")
    parser.add_argument("--save-peer", nargs=2, metavar=("NAME", "HASH"), help="Save a peer by name")
    parser.add_argument("--list-peers", action="store_true")
    args = parser.parse_args()

    if args.list_peers:
        list_peers()
        return

    if args.save_peer:
        save_peer(args.save_peer[0], args.save_peer[1])
        return

    identity = load_or_create_identity()

    if args.destination:
        dest_hash = resolve_peer(args.destination)
        connect_mode(identity, dest_hash)
    else:
        listen_mode(identity)


if __name__ == "__main__":
    main()
