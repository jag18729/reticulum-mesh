# Reticulum Mesh — Checklists

Progress tracker across all phases. Check items off as they're completed.

---

## Phase 1 — Single-Site Foundation ✅

> Built and verified on home LAN.

- [x] Persistent identity manager (`lib/identity.py`)
- [x] Shared RNS helpers (`lib/common.py`)
- [x] System stats beacon (`beacon.py`)
- [x] Fleet dashboard (`monitor.py`)
- [x] Remote shell / exec (`rexec.py`)
- [x] P2P chat (`chat.py`)
- [x] Announce-based discovery (`discover.py`)
- [x] Local loopback test verified (`test_local.py`)

---

## Phase 2 — Two-Site Mesh (Vandine) ✅

> Pi3 deployed at Vandine. Mesh routing live via Pi2 hub.

### Infrastructure
- [x] Pi2: `rns-tcp-server.conf` appended to `~/.reticulum/config`
- [x] Pi2: UFW locked — port 4242 restricted to Tailscale subnet
- [x] Pi2: `rnsd.service` systemd user service — enabled, running
- [x] ThinkStation: `rns-tcp-client.conf` appended to `~/.reticulum/config`
- [x] ThinkStation: `rnsd.service` systemd user service — enabled, running, ESTAB to Pi2

### Pi3 Deploy
- [x] Pi3 physically connected — PA-220 port 3, Vandine
- [x] Pi3 on Tailscale — `100.119.105.10`
- [x] Repo cloned on Pi3
- [x] RNS + psutil installed (PEP 668 workaround: `--break-system-packages`)
- [x] `~/.reticulum/config` written — TCPClientInterface → Pi2:4242
- [x] `rns-beacon.service` — enabled, running
- [x] `rns-rexec.service` — enabled, running
- [x] Pi3 beacon hash registered on ThinkStation: `643b501dce6bcd85971bab5f26a3fbbd`

### Verification
- [x] Path to Pi3 found from ThinkStation (2s via Pi2 hub)
- [x] `monitor.py` — Pi3 stats visible (cpu 4.5%, ram 27.4%, disk 27.4%)
- [x] `rexec.py run pi3 uptime` — response received
- [x] `watchdog.py --peer pi3` — Beacon reachable, state file written
- [x] `prometheus_exporter.py` — `mesh_beacon_up{node="pi3"} 1` at `:9877`

### Remaining
- [ ] Watchdog cron on ThinkStation
  ```
  */5 * * * * cd ~/reticulum-mesh && python3 watchdog.py >> ~/.reticulum-mesh/watchdog.log 2>&1
  ```
- [ ] `openclaw-bridge.service` deployed on Pi2
- [ ] `mesh-prometheus.service` on ThinkStation
- [ ] Pi1 prometheus.yml — add `100.126.232.42:9877` scrape target
- [ ] Pi3 moved to permanent rack location at Vandine (Ethernet)
- [ ] Pi3 rexec `--allow` locked to ThinkStation hash only

---

## Phase 3 — Sideband Mobile Integration 🔜

> Connect phone to mesh. LXMF ↔ Telegram via openclaw_bridge.

### Prerequisites
- [ ] `openclaw-bridge.service` running on Pi2 (from Phase 2)
- [ ] Pi3 stable in permanent rack location

### Sideband Setup
- [ ] Install Sideband on phone (Android: F-Droid / Play Store — iOS: TestFlight)
  - Repo: https://github.com/markqvist/Sideband
- [ ] Configure TCP interface in Sideband: `100.111.113.35:4242`
- [ ] Retrieve Pi2 bridge LXMF address from Pi2 logs
- [ ] Add Pi2 bridge as Sideband contact
- [ ] Send test message → verify appears in Telegram via whale-watcher
- [ ] Add Pi3's LXMF address as direct contact

### Code
- [ ] `rexec_lxmf.py` — expose rexec as LXMF commands (`!run uptime` → response)
- [ ] Per-node LXMF addresses (not just the bridge)
- [ ] Push-style watchdog alerts to Sideband (in addition to Telegram)
- [ ] Sideband group channel for `!status all` fleet broadcast

---

## Phase 4 — Hardening & Resilience 📋

> Production-grade mesh. No single points of failure.

### Security
- [ ] rexec allowlist on Pi3 — restrict to ThinkStation identity hash
- [ ] rexec allowlist on Pi2 — restrict to ThinkStation identity hash
- [ ] rexec audit log — log caller identity, command, exit code, timestamp
- [ ] Rotate and back up all `~/.reticulum-mesh/identity` files to secrets manager

### Reliability
- [ ] LXMF store-and-forward — enable `LXMRouter` propagation on Pi2
- [ ] rnsd as system-level service on Pi2 (not user) — survives logout
- [ ] Redundant transport — add UDP AutoInterface on home LAN as Tailscale fallback
- [ ] Watchdog extended to all nodes (not just Pi3)
- [ ] Alert cooldown window — suppress repeat alerts within 30m

### Ops
- [ ] Rotate `watchdog.log` via logrotate
- [ ] Runbook written — manual recovery for Pi2 down, Tailscale expired, Pi3 power loss

---

## Phase 5 — Observability Expansion 📋

> Pi3 and remote nodes visible in existing Grafana dashboards.

- [ ] Grafana dashboard — import `mesh_*` metrics, one panel per node
- [ ] Prometheus alert rule — `mesh_beacon_up == 0` for >5m → Telegram
- [ ] `node_exporter` on Pi3 — OS-level metrics (iowait, net, temps)
- [ ] RNS link quality metrics — expose `mesh_link_rssi`, `mesh_hops` from announce packets
- [ ] Grafana state timeline — `mesh_beacon_up` rolling 7d uptime view

---

## Node Identity Backups ⚠️

> Do this once per node. Losing the identity file means losing the mesh address permanently.

- [ ] ThinkStation — `cp ~/.reticulum-mesh/identity ~/.reticulum-mesh/identity.bak`
- [ ] Pi2 — `cp ~/.reticulum-mesh/identity ~/.reticulum-mesh/identity.bak`
- [ ] Pi3 — `cp ~/.reticulum-mesh/identity ~/.reticulum-mesh/identity.bak`
- [ ] Store backups in 1Password or offsite

---

## Known Node Hashes

| Node | Beacon Hash | Notes |
|---|---|---|
| Pi3 | `643b501dce6bcd85971bab5f26a3fbbd` | Registered in ThinkStation peers.json |
| Pi2 | TBD | Not registered as beacon peer (hub only) |
| ThinkStation | TBD | Not registered as beacon peer (client only) |
