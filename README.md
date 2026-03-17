# reticulum-mesh

A communication layer for a two-site homelab — not just monitoring, but a full encrypted mesh that lets you reach, command, and talk to remote nodes over an independent channel that doesn't depend on the thing that might be broken.

Built on [Reticulum Network Stack](https://reticulum.network/). Runs alongside Tailscale. When Tailscale has a bad day, this keeps working.

```
Vandine                          Home
  Pi3 ──TCP out──► Pi2 :4242 ◄── ThinkStation
  beacon                hub                monitor / rexec / watchdog
  rexec              (rnsd)               prometheus_exporter
  chat
```

---

## Why This Instead of the Usual Stack

**The address is the cryptographic identity.**
Pi3's address (`643b501d...`) is derived directly from its public key — no certificate authority, no DNS, no Tailscale account, no registration. It's cryptographically unforgeable and works anywhere on any transport. SSH + Prometheus requires knowing the IP and managing keys separately. This doesn't.

**It's genuinely transport-independent.**
Most "mesh" tools are VPNs in disguise — they still phone home to a coordination server. Reticulum works over TCP, LoRa radio, serial, audio tones, I2C. The same `beacon.py` running over Tailscale TCP today works unchanged over a LoRa radio if the internet goes down. The code doesn't know or care what's underneath.

**It's a full stack, not just monitoring.**
Prometheus + Grafana + SSH scripts is useful but brittle. This gives you encrypted remote shell, dead man's switch with stateful alert/recovery, P2P chat, Prometheus metrics, and an AI pipeline hook — all sharing one identity file, one peer registry, one transport layer.

**Phase 3 makes your phone a first-class mesh node.**
[Sideband](https://github.com/markqvist/Sideband) + LXMF means the phone gets its own cryptographic address on the mesh. Not a push notification consumer — an actual peer. Text Pi3 directly, or text the bridge and have it routed to Telegram through whale-watcher. No Matrix server. No XMPP. No always-on middleman.

**It fits exactly.**
Zabbix and Nagios are designed for enterprise teams. This is ~800 lines of Python that does exactly what a 6-node two-site lab needs. When Pi3 moves to a new rack, nothing changes. When a new node is added, one script deploys it.

> Most homelab monitoring is surveillance of your infrastructure.
> This is a communication layer for it.

---

## Nodes

| Node | Role | Tailscale IP |
|---|---|---|
| Pi2 | RNS hub (`rnsd :4242`) | 100.111.113.35 |
| Pi3 | Remote node — Vandine | 100.119.105.10 |
| ThinkStation | Control / monitoring | 100.126.232.42 |

---

## Suite

| Tool | What it does |
|---|---|
| `beacon.py` | Broadcasts CPU / RAM / disk / uptime over the mesh |
| `monitor.py` | Live fleet dashboard — polls all beacons |
| `rexec.py` | Remote shell and single-command execution |
| `chat.py` | P2P encrypted chat between any two nodes |
| `discover.py` | Listens for announces, builds a peer directory |
| `watchdog.py` | Dead man's switch — Telegram alert if Pi3 goes dark |
| `openclaw_bridge.py` | LXMF ↔ OpenClaw/Telegram gateway (Pi2) |
| `prometheus_exporter.py` | Exposes beacon metrics on `:9877` for Prometheus |

---

## Quick Start

### Requirements

```bash
pip3 install --user --break-system-packages rns lxmf psutil websockets
```

### Pi2 — hub (do once)

```bash
cat config/rns-tcp-server.conf >> ~/.reticulum/config
sudo ufw allow in on tailscale0 to any port 4242 proto tcp && sudo ufw deny 4242
# install rnsd as a systemd user service — see docs/QUICKSTART.md
systemctl --user enable --now rnsd
```

### ThinkStation (do once)

```bash
cat config/rns-tcp-client.conf >> ~/.reticulum/config
systemctl --user enable --now rnsd   # see QUICKSTART for unit file
```

### Pi3 / any remote node (do once)

```bash
git clone https://github.com/jag18729/reticulum-mesh.git
cd reticulum-mesh
bash setup/vandine-pi3.sh
```

### Register a peer

```bash
python3 discover.py               # wait for node to appear, grab hash
python3 monitor.py --add pi3 <hash>
```

---

## Daily Usage

```bash
# Fleet dashboard
python3 monitor.py

# Remote shell into Pi3
python3 rexec.py shell pi3

# Single remote command
python3 rexec.py run pi3 "df -h /"

# Chat
python3 chat.py pi3

# Watchdog (also runs as cron every 5m)
python3 watchdog.py --peer pi3

# Prometheus metrics
curl localhost:9877/metrics
```

---

## Watchdog Cron

```bash
# crontab -e
*/5 * * * * cd ~/reticulum-mesh && python3 watchdog.py >> ~/.reticulum-mesh/watchdog.log 2>&1
```

Fires a Telegram alert via OpenClaw after 3 consecutive failures. Sends recovery alert when back online.

---

## Sideband (Phase 3)

[Sideband](https://github.com/markqvist/Sideband) connects your phone to the mesh over the same TCP interface. Messages route through `openclaw_bridge.py` on Pi2 → whale-watcher → Telegram.

Config in Sideband: `TCP Client` → `100.111.113.35:4242`

---

## Docs

- [`docs/QUICKSTART.md`](docs/QUICKSTART.md) — setup, commands, tips, service management
- [`docs/CHECKLIST.md`](docs/CHECKLIST.md) — phase-by-phase progress tracker
- [`docs/ROADMAP.md`](docs/ROADMAP.md) — phased plan, live node registry, future considerations
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — transport diagram, data flows, RNS config reference

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
│   ├── rns-tcp-client.conf
│   └── rns-tcp-server.conf
├── setup/
│   └── vandine-pi3.sh     # one-shot remote node deploy
└── docs/
    ├── QUICKSTART.md
    ├── ROADMAP.md
    └── ARCHITECTURE.md
```

---

## State

```
~/.reticulum/config           — RNS interface config
~/.reticulum-mesh/identity    — permanent mesh keypair (back this up)
~/.reticulum-mesh/peers.json  — name → hash registry
```

> **Back up `~/.reticulum-mesh/identity`** on every node. Losing it means losing your mesh address permanently.
