"""
Remote command execution over Reticulum.
Run rexec-server on the remote node, then send commands from anywhere on the mesh.

SECURITY: server only accepts connections from identities in its allowlist.
          Use --allow <hash> to whitelist your control node.

Usage:
  Server:  python3 rexec.py server [--allow <your_hash>]
  Client:  python3 rexec.py run <name_or_hash> <command>
  Client:  python3 rexec.py shell <name_or_hash>   (interactive)
"""

import RNS
import sys
import time
import json
import subprocess
import threading
import argparse

sys.path.insert(0, ".")
from lib.identity import load_or_create_identity, resolve_peer, save_peer
from lib.common import APP_NAME, make_destination, wait_for_path

TIMEOUT = 30


# ── Server ──────────────────────────────────────────────────────────────────

def run_command(cmd: str) -> dict:
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=TIMEOUT
        )
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": "timeout", "returncode": -1}
    except Exception as e:
        return {"stdout": "", "stderr": str(e), "returncode": -1}


def make_exec_handler(allowed_hashes: set):
    def handler(path, data, request_id, link_id, remote_identity, requested_at):
        if allowed_hashes:
            if remote_identity is None:
                return json.dumps({"stderr": "identity required", "returncode": 403}).encode()
            caller = RNS.prettyhexrep(remote_identity.hash)
            if caller not in allowed_hashes:
                return json.dumps({"stderr": f"denied: {caller}", "returncode": 403}).encode()

        cmd = data.decode("utf-8") if data else ""
        print(f"[rexec] exec: {cmd!r}")
        result = run_command(cmd)
        return json.dumps(result).encode("utf-8")

    return handler


def server_mode(allowed_hashes: set):
    import socket
    RNS.Reticulum()
    identity = load_or_create_identity()
    destination = make_destination(identity, "rexec")
    destination.register_request_handler(
        "exec",
        response_generator=make_exec_handler(allowed_hashes),
        allow=RNS.Destination.ALLOW_ALL,
    )
    destination.announce()
    print(f"rexec server on {socket.gethostname()}")
    print(f"Address: {RNS.prettyhexrep(destination.hash)}")
    if allowed_hashes:
        print(f"Allowed: {', '.join(allowed_hashes)}")
    else:
        print("[!] WARNING: no --allow set — accepting commands from anyone")
    print("Listening...\n")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nServer stopped.")


# ── Client ───────────────────────────────────────────────────────────────────

def run_remote(dest_hash_hex: str, cmd: str) -> dict | None:
    dest_hash = bytes.fromhex(dest_hash_hex)
    if not wait_for_path(dest_hash):
        print("No path to destination.")
        return None

    remote_id = RNS.Identity.recall(dest_hash)
    if not remote_id:
        print("Cannot recall remote identity.")
        return None

    destination = RNS.Destination(
        remote_id, RNS.Destination.OUT, RNS.Destination.SINGLE, APP_NAME, "rexec"
    )

    if not wait_for_path(destination.hash):
        print("No path to rexec destination.")
        return None

    result_box = [None]
    done = threading.Event()

    def on_response(receipt):
        if receipt.response:
            try:
                result_box[0] = json.loads(receipt.response.decode("utf-8"))
            except Exception as e:
                result_box[0] = {"stderr": str(e), "returncode": -1}
        done.set()

    def on_fail(receipt):
        result_box[0] = {"stderr": "request failed", "returncode": -1}
        done.set()

    def on_link(link):
        link.identify(identity)
        time.sleep(0.2)
        link.request("exec", data=cmd.encode("utf-8"),
                     response_callback=on_response,
                     failed_callback=on_fail,
                     timeout=TIMEOUT + 5)

    link = RNS.Link(destination)
    link.set_link_established_callback(on_link)
    done.wait(timeout=TIMEOUT + 10)
    return result_box[0]


identity = None  # set in main


def run_cmd_mode(dest_hash_hex: str, cmd: str):
    result = run_remote(dest_hash_hex, cmd)
    if result is None:
        sys.exit(1)
    if result.get("stdout"):
        print(result["stdout"], end="")
    if result.get("stderr"):
        print(result["stderr"], end="", file=sys.stderr)
    sys.exit(result.get("returncode", 0))


def shell_mode(dest_hash_hex: str):
    print(f"rexec shell -> {dest_hash_hex[:16]}...  (type 'exit' to quit)\n")
    while True:
        try:
            cmd = input("remote$ ").strip()
        except EOFError:
            break
        if cmd.lower() in ("exit", "quit"):
            break
        if not cmd:
            continue
        result = run_remote(dest_hash_hex, cmd)
        if result is None:
            print("[!] No response")
            continue
        if result.get("stdout"):
            print(result["stdout"], end="")
        if result.get("stderr"):
            print(result["stderr"], end="", file=sys.stderr)


def main():
    global identity
    parser = argparse.ArgumentParser(description="Remote command execution over Reticulum")
    sub = parser.add_subparsers(dest="mode")

    srv = sub.add_parser("server", help="Start rexec server")
    srv.add_argument("--allow", nargs="*", default=[], metavar="HASH",
                     help="Allowed caller hashes (omit to allow all — not recommended)")

    run_p = sub.add_parser("run", help="Run a single command")
    run_p.add_argument("target", help="Name or hash")
    run_p.add_argument("command", nargs=argparse.REMAINDER, help="Command to run")

    sh = sub.add_parser("shell", help="Interactive remote shell")
    sh.add_argument("target", help="Name or hash")
    sh.add_argument("--save", metavar="NAME", help="Save this target under a name")

    args = parser.parse_args()

    if args.mode == "server":
        server_mode(set(args.allow))

    elif args.mode in ("run", "shell"):
        RNS.Reticulum()
        identity = load_or_create_identity()
        dest_hash = resolve_peer(args.target)

        if args.mode == "run":
            cmd = " ".join(args.command)
            run_cmd_mode(dest_hash, cmd)
        else:
            if args.save:
                save_peer(args.save, dest_hash)
            shell_mode(dest_hash)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
