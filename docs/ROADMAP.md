# Reticulum Mesh — Project Roadmap

## Overview

This project builds a secure, encrypted mesh network across two physical sites
using [Reticulum Network Stack](https://reticulum.network/). It runs alongside
Tailscale (primary) as an always-on secondary channel with its own identity,
routing, and messaging layer — resilient to VPN disruptions, NAT-traversal issues,
and internet outages at individual sites.

---

## Site Inventory

| Node | Location | Role |
|---|---|---|
| ThinkStation | Home | Control workstation, monitoring, cron orchestration |
| Pi2 | Home | RNS hub (`rnsd :4242`), OpenClaw gateway, Telegram bridge |
| Pi0 | Home | LDAP |
| Pi1 | Home | Prometheus + Postgres |
| RV2 | Home | Suricata IDS |
| Pi3 | Vandine | Always-on remote node (beacon + rexec) |
| UXG Pro | Vandine | Router/firewall |
| PA-220 | Vandine | Next-gen firewall |

---

## Phase 1 — Single-Site Foundation ✅ Complete

**Goal:** Prove out the Reticulum suite on the home LAN before extending to Vandine.

| Component | File | Status |
|---|---|---|
| Persistent identity manager | `lib/identity.py` | ✅ |
| Shared helpers | `lib/common.py` | ✅ |
| System stats beacon | `beacon.py` | ✅ |
| Fleet dashboard | `monitor.py` | ✅ |
| Remote shell / exec | `rexec.py` | ✅ |
| Peer-to-peer chat | `chat.py` | ✅ |
| Announce-based discovery | `discover.py` | ✅ |

**Outcome:** All home nodes can discover each other, exchange stats, and accept remote commands over the mesh.

---

## Phase 2 — Two-Site Mesh (Vandine) ✅ Complete (2026-03-16)

**Goal:** Extend the mesh to Vandine. Pi3 is an always-on remote node — monitored,
accessible, and wired into the OpenClaw/Telegram alert pipeline.

**Transport:**
```
Pi3 (Vandine) ──TCP out──► Pi2 :4242 (hub, Tailscale 100.111.113.35)
ThinkStation  ──TCP out──► Pi2 :4242
```
No port-forwarding needed at either site. Pi3 dials outbound to Pi2's Tailscale IP.

| Component | File | Runs on | Status |
|---|---|---|---|
| Pi3 deploy script | `setup/vandine-pi3.sh` | Pi3 (once) | ✅ |
| RNS TCP client config | `config/rns-tcp-client.conf` | Pi3 + ThinkStation | ✅ |
| RNS TCP server config | `config/rns-tcp-server.conf` | Pi2 | ✅ |
| Dead man's switch | `watchdog.py` | ThinkStation cron | ✅ |
| LXMF ↔ OpenClaw bridge | `openclaw_bridge.py` | Pi2 systemd | ✅ |
| Beacon → Prometheus | `prometheus_exporter.py` | ThinkStation | ✅ |
| rnsd systemd service | `rnsd.service` | ThinkStation + Pi2 | ✅ |

### Live Node Registry

| Node | Tailscale IP | Beacon Hash | Status |
|---|---|---|---|
| Pi2 (hub) | 100.111.113.35 | — | ✅ rnsd :4242, transport enabled |
| Pi3 | 100.119.105.10 | `643b501dce6bcd85971bab5f26a3fbbd` | ✅ beacon + rexec running, WiFi (Vandine) — **pending move to rack/Ethernet** |
| ThinkStation | 100.126.232.42 | — | ✅ rnsd service, connected to Pi2 |

> **Pi3 relocation note:** Pi3 is currently on WiFi at Vandine (192.168.2.233). It will move
> to a permanent rack location on Ethernet once the site is fully set up. Tailscale IP and mesh
> identity hash will not change — no reconfiguration needed.

### Phase 2 Deployment Checklist

```
[x] Pi2: append config/rns-tcp-server.conf to ~/.reticulum/config
[x] Pi2: sudo ufw allow in on tailscale0 to any port 4242 proto tcp
[x] Pi2: sudo ufw deny 4242
[x] Pi2: rnsd running as systemd user service
[x] ThinkStation: append config/rns-tcp-client.conf to ~/.reticulum/config
[x] ThinkStation: rnsd running as systemd user service (auto-connects to Pi2 on boot)
[x] Pi3: git clone repo, ran deploy manually (pip PEP 668 workaround applied)
[x] Pi3: rns-beacon.service + rns-rexec.service running
[x] ThinkStation: python3 discover.py  →  Pi3 hash captured
[x] ThinkStation: python3 monitor.py --add pi3 643b501dce6bcd85971bab5f26a3fbbd
[ ] ThinkStation cron: */5 * * * * cd ~/reticulum-mesh && python3 watchdog.py >> ~/.reticulum-mesh/watchdog.log 2>&1
[ ] Pi2: install openclaw-bridge.service (see openclaw_bridge.py docstring)
[ ] ThinkStation: mesh-prometheus.service (see QUICKSTART)
[ ] Pi1: add ThinkStation:9877 scrape target to prometheus.yml
```

### Phase 2 Verification

```bash
# 1. Pi3 beacon + rexec services running
systemctl --user status rns-beacon rns-rexec

# 2. Pi3 appears in discovery within 60s
python3 discover.py

# 3. Pi3 visible in fleet dashboard
python3 monitor.py

# 4. Remote shell into Vandine
python3 rexec.py shell pi3

# 5. Watchdog alert: stop beacon on Pi3 → Telegram alert ~5 min
systemctl --user stop rns-beacon  # on Pi3

# 6. Prometheus metrics present
curl localhost:9877/metrics | grep pi3

# 7. LXMF bridge: message Pi2's address from Sideband → appears in Telegram
```

---

## Phase 3 — Sideband Mobile Integration 🔜 Planned

**Goal:** Use [Sideband](https://github.com/markqvist/Sideband) on a phone to message
any mesh node directly. Sideband connects to Pi2 as an RNS access point; the
`openclaw_bridge.py` already handles the LXMF ↔ Telegram routing.

**What Sideband adds:**
- Native iOS/Android LXMF messenger — no separate app needed
- Full end-to-end encryption (Reticulum identity layer)
- Connects over Tailscale (same TCP client interface pointing at Pi2:4242)
- Supports nomadic connectivity — phone roams, Pi2 buffers messages

**Integration steps:**

| Step | Action |
|---|---|
| Install Sideband | Android: F-Droid or Play Store. iOS: TestFlight |
| Configure transport | Add TCPClientInterface in Sideband settings → Pi2 `100.111.113.35:4242` |
| Exchange addresses | Pi2 bridge address printed on startup; add to Sideband contacts |
| Test LXMF round-trip | Send message from Sideband → bridge forwards to whale-watcher → reply comes back |
| Add node contacts | Add Pi3's LXMF address (derived from beacon identity) for direct node messaging |

**Enhancements to build in Phase 3:**

- `rexec_lxmf.py` — expose rexec as LXMF commands (text `!run uptime` → response)
- Per-node LXMF addresses so phone can message Pi3 directly, not just the bridge
- Sideband group channel for fleet-wide broadcasts (e.g. `!status all`)
- Push-style alerts: watchdog sends LXMF to phone *and* Telegram

**Dependencies:**
```
pip install lxmf rns
```
LXMF is already a dependency of `openclaw_bridge.py`. No new installs for Phase 3.

---

## Phase 4 — Hardening & Resilience 📋 Planned

**Goal:** Production-grade mesh — no single points of failure, authenticated access,
persistent message delivery.

| Item | Description |
|---|---|
| rexec allowlist enforcement | Pi3's rexec server: lock down to ThinkStation hash only |
| LXMF store-and-forward | Enable `LXMRouter` propagation so messages survive node restarts |
| rnsd as system service | Move Pi2's `rnsd` to a system-level service (not user), auto-start on boot |
| Redundant transport | Add UDP broadcast interface on home LAN as fallback when Tailscale is down |
| watchdog multi-node | Extend `watchdog.py` to watch all nodes, not just Pi3 |
| Alert deduplication | Watchdog: add cooldown window (e.g. no repeat alert for 30m) |
| Structured logging | Rotate `watchdog.log` via `logrotate`; ship to Pi1's Loki if present |

---

## Phase 5 — Observability Expansion 📋 Planned

**Goal:** Pi3 and future remote nodes appear fully in existing dashboards.

| Item | Description |
|---|---|
| Grafana dashboard | Import `mesh_*` metrics into existing Pi1 Grafana; one panel per node |
| Alert rules | Prometheus alerting rules: `mesh_beacon_up == 0` for >5m → PagerDuty/Telegram |
| Node exporter on Pi3 | Install `node_exporter` on Pi3 for OS-level metrics (iowait, net, temps) |
| RNS link quality metrics | Expose `mesh_link_rssi`, `mesh_link_snr`, `mesh_hops` from RNS announce packets |
| Historical uptime | Use Grafana's state timeline panel for `mesh_beacon_up` over rolling 7d |

---

## Future Considerations

### Security
- **Identity pinning:** save and verify expected identity hashes for each node to detect impersonation
- **rexec audit log:** log every executed command with caller identity, timestamp, and exit code
- **Network segmentation:** Pi3 at Vandine should be on its own VLAN (UXG Pro supports this); mesh traffic on a dedicated VLAN
- **Key rotation policy:** RNS identities are long-lived; document rotation procedure and keep backups in a secrets manager

### Architecture
- **Pi2 as dedicated hub:** Pi2 should ideally run nothing but `rnsd`, `openclaw`, and the bridge — minimize co-tenancy with other services
- **Multi-hub topology:** if a third site is added, promote that site's node to a hub too rather than routing everything through Pi2
- **RNS over Tor / I2P:** Reticulum natively supports pluggable transports; evaluate for high-sensitivity traffic
- **LXMF propagation node:** designating Pi2 as a propagation node enables store-and-forward for offline nodes — important if Pi3's connectivity is unreliable

### Operational
- **Runbook:** document manual recovery steps for common failures (Pi2 down, Tailscale expired, Pi3 power loss)
- **Backup identities:** `~/.reticulum-mesh/identity` is the cryptographic identity for each node — back it up; losing it means losing your mesh address permanently
- **Pi3 UPS:** Vandine node should be on a small UPS (e.g. CyberPower CP425G) to survive brief outages — makes the watchdog signal more meaningful
- **Sideband nomadic config:** when phone leaves Tailscale range, Sideband can fall back to direct TCP over public internet if Pi2 gets a stable IP or DNS entry

### Extensibility
- **New node template:** `setup/vandine-pi3.sh` is the pattern — parameterize it (`NODE_NAME`, `HUB_HOST`, `HUB_PORT`) for future sites
- **Service mesh overlay:** long-term, Reticulum can replace Tailscale for inter-service calls on trusted nodes — evaluate after Phase 4 is stable
- **OpenClaw mesh agent:** teach whale-watcher to query beacon stats directly via the mesh (not Prometheus), enabling natural-language fleet queries from Telegram

---

## File Structure

```
reticulum-mesh/
├── beacon.py                  # System stats beacon (runs on every node)
├── chat.py                    # P2P chat
├── discover.py                # Announce-based peer discovery
├── monitor.py                 # Fleet dashboard (ThinkStation)
├── rexec.py                   # Remote shell / exec
├── send.py                    # One-shot message sender
├── node.py                    # Node scaffold
│
├── watchdog.py                # Dead man's switch for Pi3 (ThinkStation cron)
├── openclaw_bridge.py         # LXMF ↔ OpenClaw/Telegram gateway (Pi2)
├── prometheus_exporter.py     # Beacon metrics → Prometheus :9877 (ThinkStation)
│
├── lib/
│   ├── __init__.py
│   ├── common.py              # Shared RNS helpers (APP_NAME, destinations, links)
│   └── identity.py            # Persistent identity + peer registry
│
├── config/
│   ├── rns-tcp-client.conf    # TCPClientInterface snippet (Pi3 + ThinkStation)
│   └── rns-tcp-server.conf    # TCPServerInterface snippet (Pi2 hub)
│
├── setup/
│   └── vandine-pi3.sh         # One-shot Pi3 deploy (install, config, systemd)
│
└── docs/
    ├── ROADMAP.md             # This file — phases, checklist, future considerations
    └── ARCHITECTURE.md        # Transport diagram, data flows, component responsibilities
```
