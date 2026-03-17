"""
OpenClaw Bridge — LXMF ↔ OpenClaw/Telegram gateway.

Runs on Pi2 as a systemd service.

- Listens for incoming LXMF messages on the mesh.
- Forwards them to whale-watcher via OpenClaw WebSocket API.
- Sends OpenClaw's reply back as LXMF to the originating node.

This lets you text Pi2's LXMF address from Sideband on your phone
and have the message/response flow through Telegram's whale-watcher.

Usage: python3 openclaw_bridge.py [--url ws://127.0.0.1:18789] [--agent whale-watcher]

Systemd unit (Pi2, ~/.config/systemd/user/openclaw-bridge.service):
  [Unit]
  Description=OpenClaw LXMF Bridge
  After=network.target

  [Service]
  ExecStart=python3 /home/rafaeljg/reticulum-mesh/openclaw_bridge.py
  Restart=always
  RestartSec=10

  [Install]
  WantedBy=default.target
"""

import RNS
import LXMF
import asyncio
import argparse
import json
import sys
import time
import websockets

sys.path.insert(0, ".")
from lib.identity import load_or_create_identity

BRIDGE_DISPLAY_NAME = "OpenClaw Bridge"


class OpenClawBridge:
    def __init__(self, ws_url: str, token: str, agent: str):
        self.ws_url = ws_url
        self.token = token
        self.agent = agent
        self.router: LXMF.LXMRouter | None = None
        self.lxmf_dest: LXMF.LXMFDestination | None = None

    def start(self):
        RNS.Reticulum()
        identity = load_or_create_identity()

        self.router = LXMF.LXMRouter(storagepath=None)
        self.lxmf_dest = self.router.register_delivery_identity(
            identity, display_name=BRIDGE_DISPLAY_NAME
        )
        self.router.register_delivery_callback(self._on_lxmf_message)

        addr = RNS.prettyhexrep(self.lxmf_dest.hash)
        print(f"[bridge] LXMF address : {addr}")
        print(f"[bridge] OpenClaw URL : {self.ws_url}")
        print(f"[bridge] Agent        : {self.agent}")
        print("[bridge] Ready — waiting for messages...")

        try:
            asyncio.run(self._run_forever())
        except KeyboardInterrupt:
            print("\n[bridge] Stopped.")

    def _on_lxmf_message(self, message: LXMF.LXMMessage):
        """Called by LXMF router when an inbound message arrives."""
        sender = RNS.prettyhexrep(message.source_hash)
        content = message.content.decode("utf-8", errors="replace").strip()
        print(f"[bridge] ← LXMF from {sender}: {content!r}")

        # Schedule forwarding to OpenClaw in the asyncio loop
        asyncio.create_task(self._forward_to_openclaw(sender, content, message.source_hash))

    async def _forward_to_openclaw(self, sender: str, content: str, source_hash: bytes):
        """Send content to OpenClaw agent and reply back via LXMF."""
        prompt = f"[LXMF from {sender}] {content}"
        reply_text = await self._query_openclaw(prompt)
        print(f"[bridge] → LXMF reply to {sender}: {reply_text!r}")
        self._send_lxmf_reply(source_hash, reply_text)

    async def _query_openclaw(self, message: str) -> str:
        """Send message to OpenClaw via WebSocket, return agent reply text."""
        payload = json.dumps({
            "type": "agent",
            "agent": self.agent,
            "message": message,
            "token": self.token,
        })
        try:
            async with websockets.connect(self.ws_url, open_timeout=10) as ws:
                await ws.send(payload)
                # Collect streaming response chunks until connection closes
                chunks = []
                async for raw in ws:
                    try:
                        data = json.loads(raw)
                        # OpenClaw streams payloads; extract text segments
                        for p in data.get("result", {}).get("payloads", []):
                            t = p.get("text", "")
                            if t:
                                chunks.append(t)
                        if data.get("status") in ("complete", "error", "done"):
                            break
                    except (json.JSONDecodeError, KeyError):
                        # Non-JSON chunk or keep-alive — ignore
                        pass
                if chunks:
                    return " ".join(chunks).strip()
                return "(no response)"
        except Exception as e:
            print(f"[bridge] OpenClaw error: {e}")
            return f"(bridge error: {e})"

    def _send_lxmf_reply(self, dest_hash: bytes, text: str):
        """Send an LXMF message back to the originating node."""
        if not self.router or not self.lxmf_dest:
            return
        try:
            dest_identity = RNS.Identity.recall(dest_hash)
            if not dest_identity:
                print(f"[bridge] Cannot reply — identity for {RNS.prettyhexrep(dest_hash)} not recalled")
                return
            lxm = LXMF.LXMMessage()
            lxm.destination_hash = dest_hash
            lxm.source_hash = self.lxmf_dest.hash
            lxm.content = text.encode("utf-8")
            lxm.desired_method = LXMF.LXMMessage.DIRECT
            lxm.pack()
            self.router.handle_outbound(lxm)
        except Exception as e:
            print(f"[bridge] Reply error: {e}")

    async def _run_forever(self):
        """Keep the asyncio loop alive so LXMF callbacks can schedule tasks."""
        while True:
            await asyncio.sleep(1)


def main():
    parser = argparse.ArgumentParser(description="LXMF ↔ OpenClaw bridge")
    parser.add_argument("--url", default="ws://127.0.0.1:18789",
                        help="OpenClaw WebSocket URL (default: ws://127.0.0.1:18789)")
    parser.add_argument("--token", default="ea19a109b4f1289aed457264d1bbe8b28b811727a4a5f8d9",
                        help="OpenClaw API token for Pi2")
    parser.add_argument("--agent", default="whale-watcher",
                        help="OpenClaw agent name (default: whale-watcher)")
    args = parser.parse_args()

    bridge = OpenClawBridge(ws_url=args.url, token=args.token, agent=args.agent)
    bridge.start()


if __name__ == "__main__":
    main()
