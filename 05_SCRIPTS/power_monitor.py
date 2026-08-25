#!/usr/bin/env python3
"""
power_monitor.py — read a Victron VE.Direct device, log it, compute the band.

Works with:
  * BlueSolar / SmartSolar MPPT controllers  (reports volts, amps, PV watts)
  * SmartShunt / BMV battery monitors        (also reports true SOC %)

Wiring: Victron VE.Direct-to-USB cable between the device and any Pi USB port.
The device streams a plain-text frame about once per second at 19200 baud —
lines like "V<TAB>13250" (battery millivolts). We just read and parse them.

Outputs:
  power_log.csv  — one row per frame (append-only history)
  latest.json    — current snapshot; lora_oracle.py reads this for ?power

Band logic (GREEN / YELLOW / RED / BLACK):
  * If the device reports SOC (a shunt does), bands use SOC: 70 / 40 / 20 %.
  * If not (an MPPT alone), we estimate from RESTING voltage only — LiFePO4's
    curve is so flat that voltage under charge or load is meaningless. When
    the array is producing, we keep the last known band instead of guessing.
    This is honest, not lazy: the real fix is a shunt monitor. The script
    tells you so once at startup.

SAFE BY DEFAULT: this script observes and logs. The on_band_change() hook is
where YOU may later add relay control — it ships as a print-only no-op.
"""

import csv
import glob
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    import serial  # pyserial
except ImportError:
    print("pyserial missing. Run:  pip install -r requirements.txt", file=sys.stderr)
    sys.exit(2)

# ----------------------------- CONFIG ---------------------------------------
SERIAL_PORT = None          # None = auto-detect; or e.g. "/dev/serial/by-id/usb-VE_Direct_cable..."
BAUD = 19200
LOG_CSV = Path("power_log.csv")
LATEST_JSON = Path("latest.json")
LOG_EVERY_S = 10            # write a CSV row at most this often (frames arrive ~1/s)

# Voltage-based band thresholds for a *resting* 12 V LiFePO4 bank.
# Crude by nature — see the docstring. For 24 V systems, double them.
V_GREEN = 13.30
V_YELLOW = 13.05
V_RED = 12.95
# ---------------------------------------------------------------------------

# VE.Direct fields we understand (label -> (name, scale to human units))
FIELDS = {
    "V":   ("batt_V",  0.001),   # battery voltage, mV -> V
    "I":   ("batt_A",  0.001),   # battery current, mA -> A (+ = charging on MPPT)
    "VPV": ("pv_V",    0.001),   # panel voltage, mV -> V
    "PPV": ("pv_W",    1.0),     # panel power, W
    "IL":  ("load_A",  0.001),   # load output current (if the controller has one)
    "SOC": ("soc_pct", 0.1),     # state of charge, promille -> %  (shunt/BMV only)
    "P":   ("batt_W",  1.0),     # battery power, W (shunt only)
    "H20": ("yield_today_kWh", 0.01),
    "H21": ("max_today_W", 1.0),
}
TEXT_FIELDS = {"CS", "ERR", "MPPT", "LOAD", "PID", "FW", "SER#", "Relay", "Alarm"}


def find_port() -> str:
    """Prefer the stable by-id path the official cable exposes."""
    for pattern in ("/dev/serial/by-id/*VE_Direct*", "/dev/serial/by-id/*",
                    "/dev/ttyUSB*", "/dev/ttyACM*"):
        hits = sorted(glob.glob(pattern))
        if hits:
            return hits[0]
    print("No serial device found. Is the VE.Direct cable plugged in?\n"
          "Run with --list-ports to see what the Pi can see.", file=sys.stderr)
    sys.exit(2)


def read_frames(port: str):
    """Yield one dict per complete VE.Direct frame ('Checksum' line ends it)."""
    with serial.Serial(port, BAUD, timeout=3) as ser:
        frame = {}
        while True:
            raw = ser.readline()
            if not raw:
                continue
            line = raw.decode("ascii", errors="ignore").strip()
            if "\t" not in line:
                continue
            label, value = line.split("\t", 1)
            if label == "Checksum":
                if frame:
                    yield frame
                frame = {}
                continue
            if label in FIELDS:
                name, scale = FIELDS[label]
                try:
                    frame[name] = round(int(value) * scale, 3)
                except ValueError:
                    pass
            elif label in TEXT_FIELDS:
                frame[label] = value


def compute_band(rec: dict, last_band: str) -> str:
    """SOC if we have it; resting-voltage estimate if we don't."""
    soc = rec.get("soc_pct")
    if soc is not None:
        if soc > 70:
            return "GREEN"
        if soc > 40:
            return "YELLOW"
        if soc > 20:
            return "RED"
        return "BLACK"

    v = rec.get("batt_V")
    if v is None:
        return last_band
    if rec.get("pv_W", 0) > 5:          # charging: voltage lies. Hold last band.
        return last_band
    if v > V_GREEN:
        return "GREEN"
    if v > V_YELLOW:
        return "YELLOW"
    if v > V_RED:
        return "RED"
    return "BLACK"


def on_band_change(new_band: str, rec: dict) -> None:
    """YOUR hook. Ships as a print-only no-op on purpose.

    Later, this is where you might switch a relay for the Tier 1 box,
    pause background jobs, etc. Start by just watching the logs for a
    season so you trust the band logic before it controls anything.
    """
    print(f"*** BAND CHANGE -> {new_band}  (batt {rec.get('batt_V', '?')} V)")


def main():
    if "--list-ports" in sys.argv:
        for p in sorted(glob.glob("/dev/serial/by-id/*") + glob.glob("/dev/tty[UA]*")):
            print(p)
        return

    port = SERIAL_PORT or find_port()
    print(f"Reading VE.Direct on {port} @ {BAUD} baud. Ctrl-C to stop.")

    new_csv = not LOG_CSV.exists()
    band = "GREEN"
    soc_warned = False
    last_log = 0.0

    with open(LOG_CSV, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new_csv:
            w.writerow(["utc", "batt_V", "batt_A", "pv_V", "pv_W",
                        "soc_pct", "yield_today_kWh", "band", "CS", "ERR"])

        for rec in read_frames(port):
            if rec.get("soc_pct") is None and not soc_warned:
                print("NOTE: no SOC in this data (MPPT-only). Bands are a crude\n"
                      "      resting-voltage estimate — a shunt monitor fixes this.")
                soc_warned = True

            new_band = compute_band(rec, band)
            if new_band != band:
                band = new_band
                on_band_change(band, rec)

            now = time.time()
            if now - last_log >= LOG_EVERY_S:
                last_log = now
                stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
                w.writerow([stamp, rec.get("batt_V"), rec.get("batt_A"),
                            rec.get("pv_V"), rec.get("pv_W"), rec.get("soc_pct"),
                            rec.get("yield_today_kWh"), band,
                            rec.get("CS", ""), rec.get("ERR", "")])
                f.flush()

                snapshot = {"utc": stamp, "band": band, **rec}
                LATEST_JSON.write_text(json.dumps(snapshot, indent=1))

                print(f"{stamp}  batt {rec.get('batt_V', '?')}V  "
                      f"pv {rec.get('pv_W', '?')}W  band {band}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped.")
