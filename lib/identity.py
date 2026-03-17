"""
Persistent identity management.
Saves/loads a named RNS Identity from disk so your address never changes.
Also maintains a local peer registry (name -> hash).
"""

import RNS
import json
import os

IDENTITY_DIR = os.path.expanduser("~/.reticulum-mesh")
IDENTITY_FILE = os.path.join(IDENTITY_DIR, "identity")
PEERS_FILE = os.path.join(IDENTITY_DIR, "peers.json")


def load_or_create_identity() -> RNS.Identity:
    os.makedirs(IDENTITY_DIR, exist_ok=True)
    if os.path.exists(IDENTITY_FILE):
        identity = RNS.Identity.from_file(IDENTITY_FILE)
        if identity:
            return identity
    identity = RNS.Identity()
    identity.to_file(IDENTITY_FILE)
    return identity


def load_peers() -> dict:
    if os.path.exists(PEERS_FILE):
        with open(PEERS_FILE) as f:
            return json.load(f)
    return {}


def save_peer(name: str, hash_hex: str):
    peers = load_peers()
    peers[name] = hash_hex
    os.makedirs(IDENTITY_DIR, exist_ok=True)
    with open(PEERS_FILE, "w") as f:
        json.dump(peers, f, indent=2)
    print(f"Saved peer '{name}' -> {hash_hex}")


def remove_peer(name: str):
    peers = load_peers()
    if name in peers:
        del peers[name]
        with open(PEERS_FILE, "w") as f:
            json.dump(peers, f, indent=2)
        print(f"Removed peer '{name}'")
    else:
        print(f"Peer '{name}' not found.")


def resolve_peer(name_or_hash: str) -> str:
    """Return hash hex from a name or pass through a raw hash."""
    peers = load_peers()
    if name_or_hash in peers:
        return peers[name_or_hash]
    return name_or_hash


def list_peers():
    peers = load_peers()
    if not peers:
        print("No saved peers.")
        return
    print(f"{'Name':<20} Hash")
    print("-" * 60)
    for name, h in peers.items():
        print(f"{name:<20} {h}")
