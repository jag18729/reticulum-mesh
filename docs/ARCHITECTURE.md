# Reticulum Mesh — Architecture

## Transport Overview

```
Vandine (mom's house)                    Home
┌─────────────────────────┐             ┌──────────────────────────────────────────┐
│  Pi3                    │             │  Pi2  (100.111.113.35 / Tailscale)        │
│  ├─ rns-beacon.service  │──TCP out───►│  ├─ rnsd :4242  (hub, binds 0.0.0.0)     │
│  ├─ rns-rexec.service   │             │  ├─ openclaw_bridge.service              │
│  └─ ~/.reticulum/config │             │  │   ├─ LXMF listener (mesh)             │
│      TCPClientInterface │             │  │   └─ OpenClaw WS client :18789        │
│                         │             │  └─ OpenClaw / whale-watcher :18789      │
│  UXG Pro → PA-220       │             │                                          │
│  dynamic public IP      │             │  ThinkStation                            │
│  (no port-forward       │             │  ├─ monitor.py        (fleet dashboard)  │
│   needed — outbound     │             │  ├─ watchdog.py       (cron, every 5m)   │
│   TCP only)             │             │  ├─ prometheus_exporter.py  :9877        │
└─────────────────────────┘             │  └─ ~/.reticulum/config                  │
                                        │      TCPClientInterface → Pi2:4242       │
                                        │                                          │
         Phone (Sideband) ──TCP───────►│  Pi2 :4242 (Phase 3)                    │
                                        │                                          │
                                        │  Pi1                                     │
                                        │  └─ Prometheus scrapes ThinkStation:9877 │
                                        └──────────────────────────────────────────┘
```

**Key transport properties:**
- Pi2 is the only node with an inbound listener (`TCPServerInterface :4242`)
- All other nodes dial outbound only — no port-forwarding required anywhere
- UFW on Pi2 restricts :4242 to Tailscale subnet (`100.64.0.0/10`) only
- Once both Pi3 and ThinkStation connect to Pi2, RNS routes between them automatically

---

## Component Responsibilities

### beacon.py (every node)
- Collects CPU, RAM, disk, uptime via `psutil`
- Announces its RNS destination on the `mesh_suite.beacon` aspect
- Responds to `stats` requests with a JSON payload
- Interval: 60s (configurable via `--interval`)

### monitor.py (ThinkStation)
- Reads saved peers from `~/.reticulum-mesh/peers.json`
- Spawns one thread per peer; opens an RNS Link and requests `stats`
- Renders a live terminal dashboard; refreshes every 30s

### watchdog.py (ThinkStation cron, every 5m)
- Resolves Pi3's hash from peers registry
- Polls Pi3's beacon once per invocation
- Tracks failure count in `~/.reticulum-mesh/watchdog-state.json`
- After `--threshold` (default 3) consecutive failures → fires Telegram alert
- On recovery → fires recovery alert and resets state

### openclaw_bridge.py (Pi2 systemd)
- Registers an LXMF delivery address using Pi2's mesh identity
- On inbound LXMF: forwards content to OpenClaw via WebSocket (`ws://127.0.0.1:18789`)
- Streams the agent response and sends it back as LXMF to the originating address
- Prints LXMF address on startup (add to Sideband contacts)

### prometheus_exporter.py (ThinkStation)
- Background thread polls all saved beacon peers every 60s
- HTTP server on `:9877` responds to `GET /metrics`
- Prometheus format: `mesh_cpu_percent`, `mesh_ram_percent`, `mesh_disk_percent`,
  `mesh_uptime_seconds`, `mesh_beacon_up` — all labeled `node=<name>`

### rexec.py (every node — server mode)
- Registers `rexec` destination; accepts `exec` requests
- Runs shell commands and returns stdout/stderr/returncode as JSON
- Optional allowlist (`--allow <hash>`) restricts callers to known identities

---

## Identity Model

Each node has a persistent RNS Identity stored at `~/.reticulum-mesh/identity`.

```
~/.reticulum-mesh/
├── identity          # Ed25519 keypair — permanent mesh address
├── peers.json        # name → hash_hex registry (shared across suite tools)
└── watchdog-state.json  # failure counters and alert state (watchdog only)
```

- **Never delete the identity file** — it is the node's cryptographic address on the mesh.
  Losing it means the node gets a new, unrecognized address; all saved peer entries pointing
  to it become stale.
- Peer hashes are the `BLAKE2b` hash of the identity's public key — stable as long as the
  identity file exists.

---

## Data Flows

### Beacon poll (monitor / watchdog / prometheus_exporter)

```
Requester                                Pi3
    │                                     │
    │── wait_for_path(dest_hash) ────────►│  (RNS path announcement)
    │── RNS.Link(destination) ───────────►│  link established
    │── link.request("stats") ───────────►│  handle_stats_request()
    │◄─ JSON {cpu_pct, ram_pct, ...} ─────│
    │
    └─ parse / store / display
```

### LXMF → Telegram (openclaw_bridge)

```
Phone (Sideband)                Pi2 bridge                  OpenClaw / Telegram
    │                               │                               │
    │── LXMF message ──────────────►│                               │
    │                               │── WS {"agent":"whale-watcher",│
    │                               │        "message": ...} ──────►│
    │                               │◄─ streaming response ─────────│
    │◄─ LXMF reply ─────────────────│                               │
```

### Watchdog alert

```
ThinkStation (cron)                Pi3              control-plane.py → Pi2 → Telegram
    │                               │                        │
    │── poll beacon ───────────────►│                        │
    │◄─ timeout / no path ──────────│                        │
    │                               │                        │
    │   (3 consecutive failures)    │                        │
    │── python3.14 control-plane.py send pi2 whale-watcher ──►│
    │                               │                        │── Telegram alert
```

---

## RNS Config Reference

### Pi2 (`~/.reticulum/config`) — append once

```ini
[[RNS TCP Hub]]
  type = TCPServerInterface
  enabled = yes
  listen_ip = 0.0.0.0
  listen_port = 4242
```

### Pi3 + ThinkStation (`~/.reticulum/config`) — append once

```ini
[[RNS TCP Client]]
  type = TCPClientInterface
  enabled = yes
  target_host = 100.111.113.35
  target_port = 4242
```

See `config/` directory for standalone snippets.

---

## Prometheus Scrape Config (Pi1)

Add to `/etc/prometheus/prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'reticulum_mesh'
    scrape_interval: 60s
    static_configs:
      - targets: ['<thinkstation_tailscale_ip>:9877']
        labels:
          site: home
```

Pi3 appears automatically once it is registered in `peers.json` on ThinkStation
and `prometheus_exporter.py` is running.
