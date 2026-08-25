---
question: How do I make a Python script start at boot and restart if it crashes (Raspberry Pi)?
answer_model: claude-fable-5
date: 2026-08-25
domain: code
serve_via: rag
human_verified: false
sources: [05_SCRIPTS/README.md §5]
---

Use a systemd service — it starts the script at boot, restarts it on crash,
and collects its output in the journal.

**The template** (as root: `/etc/systemd/system/power-monitor.service`):

```ini
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
```

**Commands**

    sudo systemctl daemon-reload          # after creating/editing the file
    sudo systemctl enable --now power-monitor
    systemctl status power-monitor        # is it running? last lines of output
    journalctl -u power-monitor -f        # follow the log live
    sudo systemctl restart power-monitor  # after editing the script

**The three classic gotchas**

1. **WorkingDirectory matters**: scripts that write relative files
   (power_log.csv, latest.json) write them THERE. Oracle and monitor must
   agree on the directory or ?power finds no data.
2. **Use the venv's python** in ExecStart (full path), not bare `python3` —
   the service doesn't run your shell profile, so `source activate` never
   happened.
3. **User= must own the serial port**: that user needs to be in the
   `dialout` group or you get Permission denied on /dev/ttyUSB0.
