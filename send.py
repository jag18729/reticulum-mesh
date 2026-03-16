"""
Send a message to a Reticulum destination over TCP mesh.
Usage: python3 send.py <destination_hash> <message>
"""

import RNS
import sys
import time
import argparse


APP_NAME = "mesh_node"


def delivery_callback(receipt):
    if receipt.status == RNS.PacketReceipt.DELIVERED:
        print("Message delivered.")
    else:
        print("Delivery failed or timed out.")


def main(dest_hash_hex: str, message: str, config_path=None):
    RNS.Reticulum(config_path)

    identity = RNS.Identity()
    dest_hash = bytes.fromhex(dest_hash_hex)

    if not RNS.Transport.has_path(dest_hash):
        print("Path unknown, requesting...")
        RNS.Transport.request_path(dest_hash)
        timeout = 10
        while not RNS.Transport.has_path(dest_hash) and timeout > 0:
            time.sleep(0.5)
            timeout -= 0.5

    if not RNS.Transport.has_path(dest_hash):
        print("Could not find path to destination.")
        sys.exit(1)

    remote_identity = RNS.Identity.recall(dest_hash)
    destination = RNS.Destination(
        remote_identity,
        RNS.Destination.OUT,
        RNS.Destination.SINGLE,
        APP_NAME,
        "node",
    )

    link = RNS.Link(destination)
    link.set_link_established_callback(lambda l: send_on_link(l, message))

    time.sleep(5)


def send_on_link(link, message):
    packet = RNS.Packet(link, message.encode("utf-8"))
    receipt = packet.send()
    receipt.set_delivery_callback(delivery_callback)
    print(f"Sent: {message}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Send a message over Reticulum")
    parser.add_argument("destination", help="Destination hash (hex)")
    parser.add_argument("message", help="Message to send")
    parser.add_argument("--config", help="Path to RNS config dir", default=None)
    args = parser.parse_args()
    main(args.destination, args.message, args.config)
