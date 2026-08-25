#!/usr/bin/env python3
"""
power_monitor.py — read a Victron VE.Direct device, log it, compute the band.

Works with:
  * BlueSolar / SmartSolar MPPT controllers  (reports volts, amps, PV watts)
  * SmartShunt / BMV battery monitors        (also reports true SOC %)

Wiring: Victron VE.Direct-to-USB cable between the device and any USB port.
The device streams a plain-text frame about once per second at 19200 baud —
fields like "V<TAB>13250" (battery millivolts). Every frame ends with a
checksum byte, and this script VERIFIES it: a frame corrupted by serial
noise (EMI next to an inverter is real) is dropped, never half-parsed.
Runs on the Pi (/dev/ttyUSB0) and on Windows (COM3) — port auto-detect
uses pyserial's cross-platform port list.

Outputs:
  power_log.csv  — one row per logging interval (append-only history)
  latest.json    — current snapshot; lora_oracle.py reads this for ?power
                   (written atomically so a reader never sees half a file)

Band logic (GREEN / YELLOW / RED / BLACK):
  * If the device reports SOC (a shunt does), bands use SOC: 70 / 40 / 20 %.
  * If not (an MPPT alone), we estimate from RESTING voltage only — LiFePO4's
    curve is so flat that voltage under charge or load is meaningless. While
    the array is producing (or charge current is flowing) we keep the last
    known band instead of guessing, and before the first trustworthy reading
    the band is honestly "UNKNOWN". The real fix is a shunt monitor; the
    script tells you so once at startup.

SAFE BY DEFAULT: this script observes and logs. The on_band_change() hook is
where YOU may later add relay control — it ships as a print-only no-op.
"""

import csv
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    import serial  # pyserial
    from serial.tools import list_ports
except ImportError:
    print("pyserial missing. Run:  pip install -r requirements.txt", file=sys.stderr)
    sys.exit(2)

# ----------------------------- CONFIG ---------------------------------------
SERIAL_PORT = None          # None = auto-detect; or pin it, e.g. "COM4" on
                            # Windows, or on the Pi the stable path
                            # "/dev/serial/by-id/usb-VictronEnergy_VE_Direct_cable..."
BAUD = 19200
LOG_CSV = Path("power_log.csv")
LATEST_JSON = Path("latest.json")
LOG_EVERY_S = 10            # write a CSV row at most this often (frames ~1/s)
RECONNECT_WAIT_S = 5        # cable unplugged / USB hiccup -> retry, don't die

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

# Human names for the controller's CS (charge state) and ERR codes, straight
# from the VE.Direct spec. ERR 33 is the §2.2 controller-killer — too much
# string voltage — so it gets shouted about, not just logged.
CHARGE_STATES = {"0": "OFF", "2": "FAULT", "3": "BULK", "4": "ABSORPTION",
                 "5": "FLOAT", "7": "EQUALIZE", "245": "WAKE-UP",
                 "247": "AUTO-EQUALIZE", "252": "EXTERNAL-CONTROL"}
ERROR_CODES = {"0": "OK", "2": "BATTERY VOLTAGE TOO HIGH",
               "17": "CHARGER OVERHEATED", "18": "CHARGER OVER-CURRENT",
               "19": "CURRENT REVERSED", "20": "BULK TIME LIMIT",
               "26": "TERMINALS OVERHEATED",
               "33": "PV INPUT VOLTAGE TOO HIGH — check string config NOW",
               "34": "PV INPUT CURRENT TOO HIGH",
               "38": "PV INPUT SHUTDOWN"}


# ------------------------- VE.Direct frame parser ---------------------------
# Protocol framing (Victron "VE.Direct Protocol" whitepaper):
#   * every field is   <CR><LF><label><TAB><value>
#   * a frame ends with the field  <CR><LF>Checksum<TAB><byte>
#   * the sum of EVERY byte in the frame, including that final checksum byte,
#     is 0 modulo 256 — that is the integrity check
#   * the device may interleave HEX-protocol records (':' ... newline); they
#     are not part of any text frame and don't count toward its checksum
# A frame that doesn't sum to zero is dropped whole. On a mid-stream connect,
# the first (partial) frame always fails and is dropped — that's correct.

_TAB, _CR, _LF, _COLON = 0x09, 0x0D, 0x0A, ord(":")
_WAIT, _KEY, _VALUE, _CHECKSUM, _HEX = range(5)


def frames_from_bytes(chunks):
    """Yield one {label: value-string} dict per checksum-VALID frame.

    `chunks` is any iterable of bytes objects (serial reads, test data...).
    Kept separate from the serial port so it can be unit-tested without
    hardware — feed it synthetic frames and corrupt them on purpose.
    """
    state = _WAIT
    total = 0                    # running byte sum for the current frame
    key = bytearray()
    value = bytearray()
    fields = {}
    dropped = 0

    for chunk in chunks:
        for b in chunk:
            if state == _HEX:            # inside a hex record: skip to newline
                if b == _LF:
                    state = _WAIT
                continue
            if b == _COLON and state != _CHECKSUM:
                state = _HEX             # hex record starts; not summed
                continue

            total = (total + b) & 0xFF

            if state == _WAIT:
                if b == _LF:             # a new "<label>" starts after \r\n
                    state, key = _KEY, bytearray()
            elif state == _KEY:
                if b == _TAB:
                    if bytes(key) == b"Checksum":
                        state = _CHECKSUM
                    else:
                        state, value = _VALUE, bytearray()
                elif b == _CR:           # malformed line — resync
                    state = _WAIT
                else:
                    key.append(b)
            elif state == _VALUE:
                if b == _CR:             # this CR opens the NEXT field
                    fields[key.decode("ascii", "ignore")] = \
                        value.decode("ascii", "ignore")
                    state = _WAIT
                else:
                    value.append(b)
            else:  # _CHECKSUM — b was the checksum byte, already in `total`
                if total == 0 and fields:
                    yield fields
                else:
                    dropped += 1
                    if dropped in (1, 10) or dropped % 100 == 0:
                        print(f"  (dropped {dropped} corrupt frame(s) — "
                              f"noise on the serial line)", file=sys.stderr)
                fields = {}
                total = 0
                state = _WAIT


def to_record(fields: dict) -> dict:
    """Convert a raw frame's strings into scaled, human-unit values."""
    rec = {}
    for label, val in fields.items():
        if label in FIELDS:
            name, scale = FIELDS[label]
            try:
                rec[name] = round(int(val) * scale, 3)
            except ValueError:
                pass
        elif label in TEXT_FIELDS:
            rec[label] = val
    return rec


# ------------------------------ serial plumbing -----------------------------

def find_port() -> str:
    """Auto-detect the VE.Direct cable, cross-platform.

    The official cable is an FTDI chip that announces itself as
    'VE Direct cable', so we look for that first, then any FTDI device,
    then fall back to 'the only serial port there is'.
    """
    ports = list(list_ports.comports())
    for p in ports:
        desc = f"{p.description or ''} {p.product or ''}".lower()
        if "ve direct" in desc or "ve_direct" in desc:
            return p.device
    for p in ports:
        if p.vid == 0x0403:              # FTDI vendor id
            return p.device
    if len(ports) == 1:
        return ports[0].device
    print("Could not auto-detect the VE.Direct cable. Ports seen:", file=sys.stderr)
    for p in ports:
        print(f"  {p.device}  {p.description}", file=sys.stderr)
    if not ports:
        print("  (none — is the cable plugged in?)", file=sys.stderr)
    print("Set SERIAL_PORT in the config block at the top of this script.\n"
          "On the Pi, prefer the stable /dev/serial/by-id/... path.", file=sys.stderr)
    sys.exit(2)


def serial_chunks(port: str):
    """Yield raw byte chunks from the serial port forever."""
    with serial.Serial(port, BAUD, timeout=3) as ser:
        while True:
            data = ser.read(512)
            if data:
                yield data


# ------------------------------- band logic ---------------------------------

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
    # Voltage only means something at REST. Charging inflates it; heavy
    # discharge sags it (which at least fails in the safe direction).
    # PV production or real charge current -> hold the last verdict.
    if rec.get("pv_W", 0) > 5 or abs(rec.get("batt_A", 0)) > 0.5:
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


# --------------------------------- output -----------------------------------

def write_latest(snapshot: dict) -> None:
    """Atomic write: lora_oracle.py may read this file at any moment, so we
    write to a temp file and os.replace() it — readers see old or new,
    never a torn half-file."""
    tmp = LATEST_JSON.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(snapshot, indent=1), encoding="utf-8")
    os.replace(tmp, LATEST_JSON)


def main():
    if "--list-ports" in sys.argv:
        ports = list(list_ports.comports())
        for p in ports:
            vid = f"{p.vid:04x}:{p.pid:04x}" if p.vid else "----:----"
            print(f"{p.device:16} {vid}  {p.description}")
        if not ports:
            print("No serial ports found.")
        return

    new_csv = not LOG_CSV.exists()
    band = "UNKNOWN"            # honest until the first trustworthy reading
    soc_warned = False
    last_log = 0.0
    err_warned = ""

    with open(LOG_CSV, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new_csv:
            w.writerow(["utc", "batt_V", "batt_A", "pv_V", "pv_W", "soc_pct",
                        "yield_today_kWh", "band", "charge_state", "error"])

        while True:                              # reconnect loop
            port = SERIAL_PORT or find_port()
            print(f"Reading VE.Direct on {port} @ {BAUD} baud. Ctrl-C to stop.")
            try:
                for fields in frames_from_bytes(serial_chunks(port)):
                    rec = to_record(fields)

                    if rec.get("soc_pct") is None and not soc_warned:
                        print("NOTE: no SOC in this data (MPPT-only). Bands are a\n"
                              "      crude resting-voltage estimate — a shunt\n"
                              "      monitor (SmartShunt) fixes this.")
                        soc_warned = True

                    cs = CHARGE_STATES.get(rec.get("CS", ""), rec.get("CS", ""))
                    err = ERROR_CODES.get(rec.get("ERR", ""), rec.get("ERR", ""))
                    if err not in ("", "OK") and err != err_warned:
                        print(f"!!! CONTROLLER ERROR: {err}")
                        err_warned = err

                    new_band = compute_band(rec, band)
                    if new_band != band:
                        band = new_band
                        on_band_change(band, rec)

                    now = time.time()
                    if now - last_log >= LOG_EVERY_S:
                        last_log = now
                        stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
                        w.writerow([stamp, rec.get("batt_V"), rec.get("batt_A"),
                                    rec.get("pv_V"), rec.get("pv_W"),
                                    rec.get("soc_pct"), rec.get("yield_today_kWh"),
                                    band, cs, err])
                        f.flush()
                        write_latest({"utc": stamp, "band": band,
                                      "charge_state": cs, "error": err, **rec})
                        print(f"{stamp}  batt {rec.get('batt_V', '?')}V  "
                              f"pv {rec.get('pv_W', '?')}W  {cs or '-'}  band {band}")
            except serial.SerialException as e:
                print(f"Serial error ({e}). Reconnecting in {RECONNECT_WAIT_S} s...",
                      file=sys.stderr)
                time.sleep(RECONNECT_WAIT_S)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped.")
