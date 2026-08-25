# OFFGRID Starter Code — Setup Guide (Raspberry Pi, step by step)

Four small scripts that turn the manifest into a running system:

| Script | What it does | Needs |
|---|---|---|
| `verify_checksums.py` | Fingerprints your archive so bit rot can't hide | nothing (pure Python) |
| `power_monitor.py` | Logs solar/battery data from a Victron VE.Direct cable, computes the GREEN/YELLOW/RED/BLACK band | VE.Direct-to-USB cable |
| `lora_oracle.py` | The mesh bot: `?power` `?med` `?find` `?ask` over Meshtastic, 200-char cap, rate-limited | USB Meshtastic node |
| `safety_router.py` | Classifies questions into retrieval-only / artifact-lookup / RAG / model before any AI runs | nothing |

These are **starter examples**: commented for beginners, safe by default (nothing
switches relays or hardware), and meant to be read as much as run. Test everything
before relying on it.

---

## 0. One-time Pi setup

```bash
sudo apt update && sudo apt full-upgrade -y
sudo apt install -y python3-venv python3-pip git

# Let your user talk to USB serial devices (radio, VE.Direct cable):
sudo usermod -a -G dialout $USER
# Log out and back in (or reboot) for that to take effect.
```

Create a virtual environment (keeps these packages away from the system Python):

```bash
python3 -m venv ~/offgrid-env
source ~/offgrid-env/bin/activate      # do this in every new terminal
pip install -r requirements.txt
```

Enable the Pi's built-in hardware watchdog (reboots a frozen Pi automatically):

```bash
echo 'dtparam=watchdog=on' | sudo tee -a /boot/firmware/config.txt
sudo sed -i 's/^#RuntimeWatchdogSec=.*/RuntimeWatchdogSec=15/' /etc/systemd/system.conf
sudo reboot
```

---

## 1. verify_checksums.py — protect the archive

Build an index the first time (from your archive root):

```bash
python verify_checksums.py build /path/to/ARCHIVE --index checksums.csv
```

Verify any time after (yearly minimum, or let a cron job do it):

```bash
python verify_checksums.py check /path/to/ARCHIVE --index checksums.csv
```

Any `MISMATCH` line = a file changed or rotted since indexing. Restore it from
another copy, then rebuild the index.

---

## 2. power_monitor.py — solar telemetry

Plug the VE.Direct-to-USB cable into the controller and the Pi, then:

```bash
python power_monitor.py --list-ports     # find the port if auto-detect fails
python power_monitor.py                  # run with defaults
```

It writes two things:
- `power_log.csv` — one row per reading (timestamp, volts, amps, PV watts, band)
- `latest.json` — the current snapshot, which `lora_oracle.py` reads for `?power`

**Honest limitation, read this:** a solar charge controller reports *voltage*, not
state of charge. LiFePO4 voltage is nearly flat from 90% down to 20%, so the band
estimate from voltage alone is crude, and the script only trusts it when the battery
is resting (not charging). For real SOC, add a shunt monitor (e.g. Victron SmartShunt
— it speaks the same VE.Direct protocol; plug it into a second USB port and run a
second copy of this script pointed at it).

---

## 3. lora_oracle.py — the mesh bot

Plug your Meshtastic node into the Pi via USB. Make sure `kiwix-serve` is running if
you want `?med` (default assumed: `http://127.0.0.1:8080`, book `wikem_en_all`).

```bash
python lora_oracle.py
```

From another node, send a **direct message** to the Pi's node:

```
?help
?power
?med dehydration
?find sx1262
```

Defaults are deliberately conservative:
- **DM-only** — it ignores channel traffic so it can never spam the public mesh
- **200-character cap**, enforced in code
- **60-second rate limit per sender**
- `?ask` (the AI path) is **OFF** until you set `OLLAMA_MODEL` in the config block

**Test on a private channel/DM before this thing lives anywhere near LongFast.
Airtime is a commons.**

---

## 4. safety_router.py — try the classifier

```bash
python safety_router.py "how much Varget for a 168gr .308 load?"
# -> RETRIEVAL_ONLY (reloading): show manufacturer table verbatim, cite edition.

python safety_router.py "what's the pinout of the sx1262?"
# -> ARTIFACT_LOOKUP: return filename + page from the datasheet tree.
```

It's a keyword classifier — extend the lists at the top as you find gaps. The point
is architectural: **the question gets routed before any model runs**, so the six
dangerous domains physically cannot reach the "creative" path.

---

## 5. Run at boot (systemd)

Example for the power monitor (repeat the pattern for the oracle):

```bash
sudo tee /etc/systemd/system/power-monitor.service > /dev/null <<'EOF'
[Unit]
Description=OFFGRID power monitor (VE.Direct)
After=multi-user.target

[Service]
User=pi
WorkingDirectory=/home/pi/offgrid/code
ExecStart=/home/pi/offgrid-env/bin/python power_monitor.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now power-monitor
journalctl -u power-monitor -f        # watch it live
```

(Adjust `User`, paths to match your setup.)

---

## Troubleshooting

- **`Permission denied: /dev/ttyUSB0`** → you skipped the `dialout` group step, or
  didn't log out afterward.
- **Two USB serial devices fighting** (radio + VE.Direct on one Pi): use the stable
  paths in `/dev/serial/by-id/` instead of `ttyUSB0/1` — set them in each script's
  config block.
- **`?med` returns nothing** → is kiwix-serve running? `curl http://127.0.0.1:8080`
  from the Pi. Is the book name in the config block exactly what kiwix shows?
- **Oracle never replies** → confirm you sent a *direct message*, not a channel
  message. That's a feature.
