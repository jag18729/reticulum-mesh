# Quickstart

Pick up and go reference. No fluff.

---

## First-Time Setup

### Any node (ThinkStation, Pi2, Pi3)

```bash
git clone https://github.com/jag18729/reticulum-mesh.git
cd reticulum-mesh
pip3 install --user rns lxmf psutil websockets
```

---

## Pi2 — Hub Setup (do once)

```bash
# 1. Append server interface to RNS config
cat config/rns-tcp-server.conf >> ~/.reticulum/config

# 2. Restrict port to Tailscale only
sudo ufw allow in on tailscale0 to any port 4242 proto tcp
sudo ufw deny 4242

# 3. Restart RNS
systemctl --user restart rnsd
# or if not running yet:
rnsd --daemon
```

---

## ThinkStation — Client Setup (do once)

```bash
# Append client interface to RNS config
cat config/rns-tcp-client.conf >> ~/.reticulum/config
```

---

## Pi3 (Vandine) — Full Deploy (do once, on Pi3)

```bash
git clone https://github.com/jag18729/reticulum-mesh.git
cd reticulum-mesh
bash setup/vandine-pi3.sh
# installs deps, writes ~/.reticulum/config, starts beacon + rexec as systemd services
```

---

## Register Pi3 on ThinkStation (do once, after Pi3 is up)

```bash
# Discover Pi3's hash
python3 discover.py
# Wait ~30s, Ctrl+C when Pi3 appears, copy its hash

# Save it
python3 monitor.py --add pi3 <hash>

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
# Create systemd user service
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
# Run as a service or add to a tmux session
python3 prometheus_exporter.py

# Add to Pi1's /etc/prometheus/prometheus.yml:
# scrape_configs:
#   - job_name: 'reticulum_mesh'
#     scrape_interval: 60s
#     static_configs:
#       - targets: ['<thinkstation_tailscale_ip>:9877']
```

---

## Daily Commands

### Fleet dashboard
```bash
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
```bash
python3 chat.py                      # listen mode (shows your address)
python3 chat.py pi3                  # open chat to pi3
```

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
journalctl --user -u rns-beacon --no-pager | grep "Address:"
```

## Service Management (Pi2)

```bash
systemctl --user status openclaw-bridge
journalctl --user -u openclaw-bridge -f
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
Check that `rnsd` is running on Pi2 and both nodes have the TCP client interface configured.
```bash
# On any node
rnsd --version     # confirm rns is installed
cat ~/.reticulum/config | grep -A4 "TCP"
```

**Path not found errors in monitor/watchdog?**
RNS needs to hear an announce from the target node first. Start (or restart) the beacon on
the remote node, then wait up to 60s for the path to propagate.

**Watchdog fires false alerts?**
Increase `--threshold` or check that the poll timeout isn't too short for your link latency:
```bash
python3 watchdog.py --threshold 5 --timeout 20
```

**Prometheus shows no data?**
Run `prometheus_exporter.py` manually first and hit `curl localhost:9877/metrics` to confirm
peers are resolving. All peers must be registered in `~/.reticulum-mesh/peers.json` first.

**rexec shell hangs?**
The remote rexec server may not be running. Check:
```bash
python3 rexec.py run pi3 echo ok      # quick connectivity test
```

**Lost Pi3's identity file?**
Pi3 will generate a new identity on next start and its hash will change.
Re-discover and update peers.json on ThinkStation:
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

## File Locations

| Path | What |
|---|---|
| `~/.reticulum/config` | RNS interface config |
| `~/.reticulum-mesh/identity` | Your node's permanent mesh keypair |
| `~/.reticulum-mesh/peers.json` | Saved peer name → hash registry |
| `~/.reticulum-mesh/watchdog-state.json` | Watchdog failure counters |
| `~/.reticulum-mesh/watchdog.log` | Watchdog cron output |
| `~/.config/systemd/user/rns-beacon.service` | Beacon systemd unit (Pi3) |
| `~/.config/systemd/user/rns-rexec.service` | Rexec systemd unit (Pi3) |
| `~/.config/systemd/user/openclaw-bridge.service` | Bridge systemd unit (Pi2) |
