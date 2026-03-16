"""
Reticulum TCP mesh node — software-only, no hardware required.
Starts a local RNS node and announces itself on the network.
"""

import RNS
import time
import argparse


APP_NAME = "mesh_node"


def packet_callback(message, packet):
    text = message.decode("utf-8")
    sender = RNS.prettyhexrep(packet.link.get_remote_destination().hash)
    print(f"[{sender}] {text}")


def link_established(link):
    print(f"Link established with {RNS.prettyhexrep(link.get_remote_destination().hash)}")
    link.set_packet_callback(packet_callback)


def main(config_path=None):
    RNS.Reticulum(config_path)

    identity = RNS.Identity()
    destination = RNS.Destination(
        identity,
        RNS.Destination.IN,
        RNS.Destination.SINGLE,
        APP_NAME,
        "node",
    )
    destination.set_link_established_callback(link_established)
    destination.announce()

    print(f"Node started. Address: {RNS.prettyhexrep(destination.hash)}")
    print("Listening... Press Ctrl+C to stop.\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reticulum mesh node")
    parser.add_argument("--config", help="Path to RNS config dir", default=None)
    args = parser.parse_args()
    main(args.config)
