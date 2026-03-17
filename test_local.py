"""
Local loopback test — runs a receiver and sender in the same process.
Verifies that Reticulum messaging works end-to-end over the local transport.
"""

import RNS
import time
import threading

APP_NAME = "mesh_node"

received = []


def make_packet_callback():
    def callback(message, packet):
        text = message.decode("utf-8")
        print(f"[RECEIVER] Got message: '{text}'")
        received.append(text)
    return callback


def link_established(link):
    remote_id = link.get_remote_identity()
    label = RNS.prettyhexrep(remote_id.hash) if remote_id else "unknown"
    print(f"[RECEIVER] Link established from {label}")
    link.set_packet_callback(make_packet_callback())


def sender_thread(recv_identity, message, delay=1.5):
    time.sleep(delay)

    destination = RNS.Destination(
        recv_identity,
        RNS.Destination.OUT,
        RNS.Destination.SINGLE,
        APP_NAME,
        "node",
    )

    def on_link(link):
        time.sleep(0.3)
        packet = RNS.Packet(link, message.encode("utf-8"))
        packet.send()
        print(f"[SENDER] Sent: '{message}'")

    link = RNS.Link(destination)
    link.set_link_established_callback(on_link)


def main():
    RNS.Reticulum()

    # Receiver
    recv_identity = RNS.Identity()
    destination = RNS.Destination(
        recv_identity,
        RNS.Destination.IN,
        RNS.Destination.SINGLE,
        APP_NAME,
        "node",
    )
    destination.set_link_established_callback(link_established)
    destination.announce()

    dest_hash = destination.hash
    print(f"[RECEIVER] Listening at {RNS.prettyhexrep(dest_hash)}\n")

    # Sender (in a thread so announce has time to propagate)
    t = threading.Thread(target=sender_thread, args=(recv_identity, "hello from local test"), daemon=True)
    t.start()

    # Wait for message
    deadline = time.time() + 10
    while time.time() < deadline:
        if received:
            break
        time.sleep(0.2)

    if received:
        print("\nTest PASSED.")
    else:
        print("\nTest FAILED — no message received within timeout.")


if __name__ == "__main__":
    main()
