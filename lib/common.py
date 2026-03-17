"""Shared helpers used across the suite."""

import RNS
import time

APP_NAME = "mesh_suite"


def make_destination(identity: RNS.Identity, aspect: str, direction=RNS.Destination.IN):
    return RNS.Destination(
        identity,
        direction,
        RNS.Destination.SINGLE,
        APP_NAME,
        aspect,
    )


def wait_for_path(dest_hash: bytes, timeout: float = 10.0) -> bool:
    if RNS.Transport.has_path(dest_hash):
        return True
    RNS.Transport.request_path(dest_hash)
    deadline = time.time() + timeout
    while time.time() < deadline:
        if RNS.Transport.has_path(dest_hash):
            return True
        time.sleep(0.2)
    return False


def open_link(identity: RNS.Identity, dest_hash: bytes, aspect: str) -> RNS.Link | None:
    remote_id = RNS.Identity.recall(dest_hash)
    if not remote_id:
        return None
    destination = make_destination(identity, aspect, RNS.Destination.OUT)
    return RNS.Link(destination)
