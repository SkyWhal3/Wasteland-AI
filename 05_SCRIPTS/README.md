# OFFGRID Starter Code — Setup Guide (step by step)

Eight small scripts that turn the manifest into a running system:

| Script | What it does | Needs |
|---|---|---|
| `verify_checksums.py` | Fingerprints your archive so bit rot can't hide | nothing (pure Python) |
| `power_monitor.py` | Logs solar/battery data from a Victron VE.Direct cable, validates every frame's checksum, computes the GREEN/YELLOW/RED/BLACK band | VE.Direct-to-USB cable |
| `lora_oracle.py` | The mesh bot: `?power` `?med` `?find` `?ask` over Meshtastic, 200-char cap, rate-limited | USB Meshtastic node |
| `safety_router.py` | Classifies questions into retrieval-only / artifact-lookup / RAG / model before any AI runs (`--test` = self-check) | nothing |
| `pi_agent.py` | Minimal coding agent, jailed to a scratch drive. **Ships disabled.** | Ollama + a coder model |
| `context_meter.py` | Shows the model's real context window vs what Ollama actually gives it, and formats the usage readout | Ollama (for live numbers) |
| `fetch_doc.py` | Downloads a document into the archive and **refuses to save a truncated one** | nothing |
| `make_skeleton.py` | Rebuilds the full §13 folder tree after a bare clone | nothing |

These are **starter examples**: commented for beginners, safe by default
(nothing switches relays or hardware), and meant to be read as much as run.
Test everything before relying on it.

**Windows note:** `verify_checksums.py`, `safety_router.py`, and
`power_monitor.py` (bench test with the cable) run fine on Windows —
port auto-detect handles `COM3`-style ports. The oracle and agent are
meant for the Pi. Windows setup is two lines (PowerShell):

```powershell
py -m venv venv
.\venv\Scripts\Activate.ps1     # blocked? Set-ExecutionPolicy -Scope Process Bypass
pip install -r requirements.txt
```

(Python 3.9 or newer, everywhere — Pi OS Bookworm ships 3.11, fine.)

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

- `MISMATCH` = a file changed or rotted since indexing. `READ ERROR` = the
  drive couldn't even read it (worse). Restore flagged files from another
  copy, then re-run `build`.
- Indexes are portable: build on the Windows array, check on the Pi.
- Keep a copy of the index on a **different drive** than the archive.

---

## 2. power_monitor.py — solar telemetry

Plug the VE.Direct-to-USB cable into the controller and any USB port, then:

```bash
python power_monitor.py --list-ports    # see every port + VID:PID
python power_monitor.py                 # run with auto-detect
```

It writes two things:
- `power_log.csv` — one row per interval (volts, amps, PV watts, charge
  state, error, band)
- `latest.json` — the current snapshot (written atomically), which
  `lora_oracle.py` reads for `?power`

Corrupt frames (serial noise) are dropped, not logged — you'll see a stderr
note if it happens a lot (check cable routing near the inverter).

**Honest limitation, read this:** a solar charge controller reports
*voltage*, not state of charge. LiFePO4 voltage is nearly flat from 90%
down to 20%, so the band estimate from voltage alone is crude; the script
only trusts it when the battery is resting (no PV, no charge current), and
reports `UNKNOWN` until it has evidence. For real SOC, add a shunt monitor
(Victron SmartShunt — same VE.Direct protocol; second USB port, second copy
of this script).

---

## 3. lora_oracle.py — the mesh bot

Plug your Meshtastic node into the Pi via USB. Make sure `kiwix-serve` is
running if you want `?med` (default assumed: `http://127.0.0.1:8080`, book
`wikem_en_all`).

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
- **60-second rate limit per sender**, silent drop (zero airtime)
- `?ask` (the AI path) is **OFF** until you set `OLLAMA_MODEL` in the config block
- Slow lookups run outside the radio callback, so the radio never stalls
- **`AUTHORIZED_SENDERS`**: unset = open mode for bench testing (loud
  warning at startup). Before the node lives on a real mesh, set it to your
  people's node numbers — `?power`/`?find` are occupancy-and-inventory
  intel you don't hand to strangers. See `00_DOCS/SECURITY.md`.

**Book names, and why you probably don't need to care:** in kiwix URLs a
book is its ZIM *filename stem* (`wikem_en_all_maxi_2026-07`), not the
catalog name (`wikem_en_all`) — the trap that 404s a first-timer. The script
probes the configured name and, if the server doesn't serve it, reads the
server's own catalog, picks the right one, and logs the swap. Verified
against kiwix-tools 3.8.1. Other versions want eyes — that's
[issue #3](https://github.com/SkyWhal3/Wasteland-AI/issues/3).

**Test on a private channel/DM before this thing lives anywhere near
LongFast. Airtime is a commons.**

---

## 4. safety_router.py — try the classifier

```bash
python safety_router.py "how much Varget for a 168gr .308 load?"
# -> RETRIEVAL_ONLY (reloading): show manufacturer table verbatim, cite edition.

python safety_router.py "what's the pinout of the sx1262?"
# -> ARTIFACT_LOOKUP: return filename + page from the datasheet tree.

python safety_router.py --test
# -> 30 canonical routings + skill matches, PASS/FAIL.
#    Run after every keyword edit; add your new expectation to the table.
```

It's a keyword classifier — extend the lists at the top as you find gaps.
The point is architectural: **the question gets routed before any model
runs**, so the six dangerous domains physically cannot reach the "creative"
path. Add your new expectation to `SELF_TEST` when you add keywords.

---

## 5. pi_agent.py — the coding agent (read before enabling)

A ~300-line agent loop: local model + five tools (list/read/write/run,
plus a read-only shelf of known-good examples in `agent_examples/`). Every
file operation is jailed to `AGENT_ROOT` — point that at the sacrificial
scratch SSD, **not** at the archive.

```bash
python pi_agent.py "write micropython for a pico that blinks the LED"
```

Ships **disabled** (`AGENT_MODEL = None`). Before enabling, read the
docstring — especially the part titled "a seatbelt, not a prison":
`run_python` executes real code with your user's real permissions. Scratch
drive, unprivileged user, review before promoting code out of the sandbox.

The agent is for *writing code*, offline. Questions go through the router
and the Oracle — do not wire the agent to the radio.

---

## 5b. context_meter.py — how full is the window?

```bash
python context_meter.py            # every model Ollama has
python context_meter.py qwen3:4b   # one model, with the warnings
```

A model past its context window does not error — it **silently drops the
oldest messages** and answers anyway. And Ollama's default window is much
smaller than most models support, so a "32k model" often runs at 2k or 4k
because nobody set `num_ctx`. This prints both numbers so you can see the gap.

`pi_agent.py` uses it: it requests `AGENT_NUM_CTX` explicitly, prints
`ctx 4736/8k 58% [#########...........]` after every step, and stops the run
before the window overflows rather than continuing with the task description
already dropped out of memory.

Raising `num_ctx` costs RAM (the KV cache scales with it) — on a Pi that is a
power and OOM question, so raise it a step at a time and watch memory.

---

## 6. Run at boot (systemd)

Example for the power monitor (repeat the pattern for the oracle):

```bash
sudo tee /etc/systemd/system/power-monitor.service > /dev/null <<'EOF'
[Unit]
Description=OFFGRID power monitor (VE.Direct)
After=multi-user.target

[Service]
User=pi
WorkingDirectory=/home/pi/offgrid/05_SCRIPTS
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

(Adjust `User` and paths. Keep the oracle and the monitor in the SAME
WorkingDirectory so `?power` finds `latest.json`.)

---

## Troubleshooting

- **`Permission denied: /dev/ttyUSB0`** → you skipped the `dialout` group
  step, or didn't log out afterward.
- **Two USB serial devices fighting** (radio + VE.Direct on one Pi): pin the
  stable paths from `/dev/serial/by-id/` in each script's config block —
  `power_monitor.py --list-ports` shows what's what.
- **`?med` returns nothing** → is kiwix-serve running? `curl http://127.0.0.1:8080`
  from the Pi. Is `KIWIX_BOOK` exactly what kiwix shows? Still stuck: see
  the "known-fragile seam" note in §3.
- **`?power` says STALE** → the oracle is fine; power_monitor.py stopped.
  `systemctl status power-monitor`.
- **Oracle never replies** → confirm you sent a *direct message*, not a
  channel message. That's a feature. Also: one query per sender per minute.
