# reticulum-mesh

I built this because I needed a way to reach a remote node at my mom's house that didn't depend on the thing that might be broken. Tailscale is great until it isn't. SSH is great until you don't know the IP. Prometheus is great until the node goes silent and you're not sure if it's the node or the network.

This is a communication layer for my homelab — not just monitoring, but a full encrypted mesh where every node has a permanent cryptographic identity, I can shell into Pi3 at Vandine from my couch, get Telegram alerts when it goes dark, and eventually message it from my phone without a server in the middle.

Built on [Reticulum Network Stack](https://reticulum.network/).

```
Vandine                          Home
  Pi3 ──TCP out──► Pi2 :4242 ◄── ThinkStation
  beacon              hub               monitor / rexec / watchdog
  rexec             (rnsd)              prometheus_exporter
  chat
```

---

## Why I Built This Instead of Using the Usual Stack

**The address is the cryptographic identity.**
Pi3's address is derived directly from its public key — no certificate authority, no DNS, no cloud account. It's permanent and unforgeable. SSH requires knowing the IP and managing keys separately. This doesn't.

**It's genuinely transport-independent.**
Most "mesh" tools are VPNs that still phone home to a coordination server. Reticulum works over TCP, LoRa radio, serial, audio tones. The same `beacon.py` running over Tailscale TCP today works unchanged over a LoRa radio if the internet goes down. I didn't write transport-specific code — I wrote mesh code.

**It's a full stack, not just monitoring.**
Prometheus + Grafana + SSH scripts is useful but brittle. I wanted encrypted remote shell that works without knowing the IP, a dead man's switch with stateful alert/recovery, P2P chat, and Prometheus metrics — all sharing one identity file, one peer registry, one transport layer.

**The phone becomes a first-class mesh node.**
[Sideband](https://github.com/markqvist/Sideband) + LXMF means my phone gets its own cryptographic address on the mesh. Not a push notification consumer — an actual peer. I can text Pi3 directly, or text the bridge and have it routed through my AI pipeline to Telegram. No Matrix server. No always-on middleman.

> Most homelab monitoring is surveillance of your infrastructure.
> This is a communication layer for it.

---

## What's In Here

| Tool | What it does |
|---|---|
| `beacon.py` | Broadcasts CPU / RAM / disk / uptime over the mesh |
| `monitor.py` | Live fleet dashboard — polls all beacons |
| `rexec.py` | Remote shell and single-command execution |
| `chat.py` | P2P encrypted chat between any two nodes |
| `discover.py` | Listens for announces, builds a peer directory |
| `watchdog.py` | Dead man's switch — Telegram alert if a node goes dark |
| `openclaw_bridge.py` | LXMF ↔ OpenClaw/Telegram gateway |
| `prometheus_exporter.py` | Exposes beacon metrics on `:9877` for Prometheus |

---

## Setup

### Requirements

```bash
pip3 install --user --break-system-packages rns lxmf psutil websockets
```

### Hub node (do once)

```bash
# Fill in your hub's listen port in config/rns-tcp-server.conf, then:
cat config/rns-tcp-server.conf >> ~/.reticulum/config

# Restrict port to your VPN subnet
sudo ufw allow in on tailscale0 to any port 4242 proto tcp
sudo ufw deny 4242

# Run rnsd as a persistent service
# (see docs/QUICKSTART.md for the full unit file)
systemctl --user enable --now rnsd
```

### Workstation / other clients (do once)

```bash
# Fill in your hub IP and port in config/rns-tcp-client.conf, then:
cat config/rns-tcp-client.conf >> ~/.reticulum/config
systemctl --user enable --now rnsd
```

### Remote node — one-shot deploy

```bash
git clone https://github.com/jag18729/reticulum-mesh.git
cd reticulum-mesh
HUB_HOST=<hub_tailscale_ip> HUB_PORT=4242 bash setup/vandine-pi3.sh
```

### Register a peer

```bash
python3 discover.py                        # wait for node, grab hash
python3 monitor.py --add mynode <hash>
```

---

## Daily Usage

```bash
python3 monitor.py                         # fleet dashboard
python3 rexec.py shell mynode              # remote shell
python3 rexec.py run mynode "df -h /"      # single command
python3 chat.py mynode                     # chat
python3 watchdog.py --peer mynode          # manual watchdog check
curl localhost:9877/metrics                # Prometheus metrics
```

---

## Dead Man's Switch

```bash
# crontab -e
*/5 * * * * cd ~/reticulum-mesh && python3 watchdog.py >> ~/.reticulum-mesh/watchdog.log 2>&1
```

Fires a Telegram alert via OpenClaw after N consecutive failures. Sends recovery when back online. State persisted to avoid repeat alerts.

Set your OpenClaw token:
```bash
export OPENCLAW_TOKEN=your_token_here
```

---

## Sideband — Phone as Mesh Node (Phase 3)

[Sideband](https://github.com/markqvist/Sideband) connects a phone directly to the mesh over the same TCP interface. Messages route through `openclaw_bridge.py` → whale-watcher → Telegram.

Config in Sideband: `TCP Client` → `<hub_ip>:4242`

---

## Docs

- [`docs/QUICKSTART.md`](docs/QUICKSTART.md) — full setup, service management, tips
- [`docs/CHECKLIST.md`](docs/CHECKLIST.md) — phase-by-phase progress tracker
- [`docs/ROADMAP.md`](docs/ROADMAP.md) — phased plan and future considerations
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — transport diagram and data flows

---

## Structure

```
reticulum-mesh/
├── beacon.py
├── monitor.py
├── rexec.py
├── chat.py
├── discover.py
├── watchdog.py
├── openclaw_bridge.py
├── prometheus_exporter.py
├── lib/
│   ├── common.py          # shared RNS helpers
│   └── identity.py        # persistent identity + peer registry
├── config/
│   ├── rns-tcp-client.conf   # fill in hub IP/port
│   └── rns-tcp-server.conf   # fill in hub port
├── setup/
│   └── vandine-pi3.sh        # one-shot remote node deploy
└── docs/
    ├── QUICKSTART.md
    ├── CHECKLIST.md
    ├── ROADMAP.md
    └── ARCHITECTURE.md
```

---

## Important

```
~/.reticulum-mesh/identity    — permanent mesh keypair
~/.reticulum-mesh/peers.json  — name → hash registry
~/.reticulum/config           — RNS interface config (contains your hub IP)
```

> **Back up `~/.reticulum-mesh/identity` on every node.** It is the node's permanent address on the mesh. Losing it means losing the address permanently — all saved peer entries pointing to it become stale.
>
> **Never commit `~/.reticulum/config`** — it contains your real network IPs.
