# reticulum-mesh

Secure, encrypted mesh network across two physical sites using [Reticulum Network Stack](https://reticulum.network/). Runs alongside Tailscale as an always-on secondary channel — fleet monitoring, remote shell, P2P chat, and Telegram alerts over an independent encrypted layer.

```
Vandine                          Home
  Pi3 ──TCP out──► Pi2 :4242 ◄── ThinkStation
  beacon                hub                monitor / rexec / watchdog
  rexec              (rnsd)               prometheus_exporter
```

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
