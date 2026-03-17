# Quickstart

Pick up and go reference. No fluff.

---

## First-Time Setup

### Any node (ThinkStation, Pi2, Pi3)

```bash
git clone https://github.com/jag18729/reticulum-mesh.git
cd reticulum-mesh
pip3 install --user --break-system-packages rns lxmf psutil websockets
```

---

## Pi2 — Hub Setup (do once)

```bash
# 1. Append server interface to RNS config
cat config/rns-tcp-server.conf >> ~/.reticulum/config

# 2. Restrict port to Tailscale only
sudo ufw allow in on tailscale0 to any port 4242 proto tcp
sudo ufw deny 4242

# 3. Install and start rnsd as a persistent systemd service
mkdir -p ~/.config/systemd/user
cat > ~/.config/systemd/user/rnsd.service << 'EOF'
[Unit]
Description=Reticulum Network Stack Daemon
After=network-online.target
Wants=network-online.target

[Service]
ExecStart=/home/rafaeljg/.local/bin/rnsd
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
EOF
systemctl --user daemon-reload && systemctl --user enable --now rnsd
```

---

## ThinkStation — Client Setup (do once)

```bash
# 1. Append client interface to RNS config
cat config/rns-tcp-client.conf >> ~/.reticulum/config

# 2. Install rnsd as a persistent systemd service
mkdir -p ~/.config/systemd/user
cat > ~/.config/systemd/user/rnsd.service << 'EOF'
[Unit]
Description=Reticulum Network Stack Daemon (ThinkStation)
After=network-online.target
Wants=network-online.target

[Service]
ExecStart=/home/johnmarston/.local/bin/rnsd
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
EOF
systemctl --user daemon-reload && systemctl --user enable --now rnsd

# Verify: should show ESTAB connection to 100.111.113.35:4242
ss -tnp | grep 4242
```

> **Why rnsd as a service?** All suite tools (monitor, rexec, watchdog, chat) connect to a
> shared RNS instance. If that instance was started before the TCP interface was in the config,
> it won't route to Pi3. Running rnsd as a systemd service ensures it always starts with the
> correct config and auto-restarts on crash.

---

## Pi3 (Vandine) — Full Deploy (do once, on Pi3)

```bash
git clone https://github.com/jag18729/reticulum-mesh.git
cd reticulum-mesh
bash setup/vandine-pi3.sh
# installs deps, writes ~/.reticulum/config, starts beacon + rexec as systemd services
```

> **Note on Pi3 relocation:** Pi3 is currently on WiFi at Vandine (192.168.2.233 / Tailscale
> 100.119.105.10). When it moves to its permanent rack location and switches to Ethernet, the
> IP will change but the Tailscale IP and mesh identity stay the same — no reconfiguration
> needed on ThinkStation or Pi2.

---

## Register Pi3 on ThinkStation (do once, after Pi3 is up)

```bash
cd ~/reticulum-mesh

# Discover Pi3's hash (wait ~30s, Ctrl+C when it appears)
python3 discover.py

# Save it (Pi3's actual beacon hash)
python3 monitor.py --add pi3 643b501dce6bcd85971bab5f26a3fbbd

# Verify
python3 monitor.py
```

---

## Watchdog Cron (ThinkStation — do once)

```bash
crontab -e
# Add this line:
*/5 * * * * cd ~/reticulum-mesh && python3 watchdog.py >> ~/.reticulum-mesh/watchdog.log 2>&1
```

---

## OpenClaw Bridge on Pi2 (do once)

```bash
mkdir -p ~/.config/systemd/user
cat > ~/.config/systemd/user/openclaw-bridge.service << 'EOF'
[Unit]
Description=OpenClaw LXMF Bridge
After=network.target

[Service]
ExecStart=python3 /home/rafaeljg/reticulum-mesh/openclaw_bridge.py
WorkingDirectory=/home/rafaeljg/reticulum-mesh
Restart=always
RestartSec=10

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now openclaw-bridge.service
```

---

## Prometheus Exporter (ThinkStation — do once)

```bash
# Run as a service
cat > ~/.config/systemd/user/mesh-prometheus.service << 'EOF'
[Unit]
Description=Reticulum Mesh Prometheus Exporter
After=rnsd.service

[Service]
ExecStart=python3 /home/johnmarston/reticulum-mesh/prometheus_exporter.py
WorkingDirectory=/home/johnmarston/reticulum-mesh
Restart=always
RestartSec=10

[Install]
WantedBy=default.target
EOF
systemctl --user daemon-reload && systemctl --user enable --now mesh-prometheus

# Add to Pi1's /etc/prometheus/prometheus.yml:
# scrape_configs:
#   - job_name: 'reticulum_mesh'
#     scrape_interval: 60s
#     static_configs:
#       - targets: ['100.126.232.42:9877']
```

---

## Daily Commands

### Fleet dashboard
```bash
cd ~/reticulum-mesh
python3 monitor.py                   # all saved peers
python3 monitor.py pi3               # specific node
python3 monitor.py --interval 10     # faster refresh
```

### Remote shell into Pi3
```bash
python3 rexec.py shell pi3
# remote$ uptime
# remote$ df -h
# remote$ exit
```

### Run a single command on Pi3
```bash
python3 rexec.py run pi3 uptime
python3 rexec.py run pi3 "df -h /"
python3 rexec.py run pi3 "systemctl --user status rns-beacon"
```

### Chat

Pi3's chat listener runs as a headless service (`rns-chat.service`) — always on,
receive-only. For two-way interactive chat you need a live terminal on Pi3.

**One-way** (ThinkStation → Pi3, Pi3 receives silently):
```bash
mesh-chat
```

**Two-way** (both sides can type):
```bash
# Terminal 1 — stop Pi3's headless service, run interactively
ssh pi3
systemctl --user stop rns-chat
cd ~/reticulum-mesh && python3 chat.py

# Terminal 2 — ThinkStation connects
mesh-chat
```

**Restore Pi3 headless listener when done:**
```bash
cd ~/reticulum-mesh && python3 rexec.py run pi3 "systemctl --user start rns-chat"
```

**Pi3 chat address:** `7732e88875f9d08b726519725ab66755`

### Discover new nodes
```bash
python3 discover.py                  # listen for announces
python3 discover.py --save           # auto-save discovered peers by hostname
python3 discover.py --duration 60    # stop after 60s
```

### Check watchdog state
```bash
cat ~/.reticulum-mesh/watchdog-state.json
tail -f ~/.reticulum-mesh/watchdog.log
```

### Prometheus metrics
```bash
curl -s localhost:9877/metrics
curl -s localhost:9877/metrics | grep pi3
curl -s localhost:9877/metrics | grep beacon_up
```

### Peer registry
```bash
python3 -c "from lib.identity import list_peers; list_peers()"
python3 monitor.py --add <name> <hash>
```

---

## Service Management (Pi3)

```bash
# Status
systemctl --user status rns-beacon rns-rexec

# Restart
systemctl --user restart rns-beacon
systemctl --user restart rns-rexec

# Logs (live)
journalctl --user -u rns-beacon -f
journalctl --user -u rns-rexec -f

# Get Pi3's beacon address
python3 -c "
import sys; sys.path.insert(0,'.')
import RNS
from lib.identity import load_or_create_identity
from lib.common import make_destination
RNS.Reticulum()
id = load_or_create_identity()
d = make_destination(id, 'beacon')
print(RNS.prettyhexrep(d.hash))
"
```

## Service Management (Pi2)

```bash
systemctl --user status rnsd openclaw-bridge
journalctl --user -u rnsd -f
journalctl --user -u openclaw-bridge -f
```

## Service Management (ThinkStation)

```bash
systemctl --user status rnsd
journalctl --user -u rnsd -f
ss -tnp | grep 4242    # verify connected to Pi2
```

---

## Sideband (Phase 3)

Install Sideband on your phone:
- Android: [F-Droid](https://f-droid.org) or Play Store — search "Sideband"
- iOS: TestFlight (search markqvist/Sideband on GitHub for link)

Configure:
1. Open Sideband → Settings → Reticulum → Add interface
2. Type: `TCP Client`  Host: `100.111.113.35`  Port: `4242`
3. Save and connect

Find Pi2 bridge address:
```bash
# On Pi2
journalctl --user -u openclaw-bridge | grep "LXMF address"
```
Add that address as a contact in Sideband. Messages go → bridge → whale-watcher → Telegram.

---

## Tips

**Node not appearing in discover?**
Confirm rnsd is running on both Pi2 and the local node, and the TCP interface is loaded:
```bash
systemctl --user status rnsd
ss -tnp | grep 4242    # should show ESTAB to 100.111.113.35:4242
```

**"No path to destination" in rexec/monitor?**
rnsd may have started with the old config (before TCP interface was added). Restart it:
```bash
systemctl --user restart rnsd
sleep 5
python3 rexec.py run pi3 hostname
```

**Watchdog fires false alerts?**
Increase `--threshold` or check that the poll timeout isn't too short for your link latency:
```bash
python3 watchdog.py --threshold 5 --timeout 20
```

**Prometheus shows no data?**
Run `prometheus_exporter.py` manually first and check:
```bash
curl localhost:9877/metrics
# All peers must be registered in ~/.reticulum-mesh/peers.json first
```

**Pi3 moving to new location?**
Tailscale IP (100.119.105.10) and mesh identity stay the same. No changes needed on
ThinkStation or Pi2. After physical move, just verify:
```bash
tailscale ping 100.119.105.10
python3 rexec.py run pi3 hostname
```

**Lost Pi3's identity file?**
Pi3 generates a new identity and its hash changes. Re-discover and update:
```bash
python3 discover.py --save
python3 monitor.py --add pi3 <new_hash>
```

**Always back up identity files:**
```bash
# On each node — do this once
cp ~/.reticulum-mesh/identity ~/.reticulum-mesh/identity.bak
```

---

## Known Nodes

| Name | Tailscale IP | Beacon Hash | Location |
|---|---|---|---|
| Pi2 (hub) | 100.111.113.35 | — | Home |
| Pi3 | 100.119.105.10 | `643b501dce6bcd85971bab5f26a3fbbd` | Vandine (moving) |
| ThinkStation | 100.126.232.42 | — | Home |

---

## File Locations

| Path | What |
|---|---|
| `~/.reticulum/config` | RNS interface config |
| `~/.reticulum-mesh/identity` | Node's permanent mesh keypair |
| `~/.reticulum-mesh/peers.json` | Saved peer name → hash registry |
| `~/.reticulum-mesh/watchdog-state.json` | Watchdog failure counters |
| `~/.reticulum-mesh/watchdog.log` | Watchdog cron output |
| `~/.config/systemd/user/rnsd.service` | rnsd autostart (ThinkStation + Pi2) |
| `~/.config/systemd/user/rns-beacon.service` | Beacon systemd unit (Pi3) |
| `~/.config/systemd/user/rns-rexec.service` | Rexec systemd unit (Pi3) |
| `~/.config/systemd/user/openclaw-bridge.service` | Bridge systemd unit (Pi2) |
