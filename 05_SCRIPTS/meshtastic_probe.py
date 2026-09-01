#!/usr/bin/env python3
"""
meshtastic_probe.py — read-only health check for any Meshtastic node on USB.

    python meshtastic_probe.py                  # find the radio, probe it, grade it
    python meshtastic_probe.py --list-ports     # what serial ports exist right now
    python meshtastic_probe.py --port COM7      # probe a specific port
    python meshtastic_probe.py --backup         # probe, then save the node's full
                                                #   config to 04_CONFIG/meshtastic/
    python meshtastic_probe.py --listen 120     # antenna RX check: sit silent for
                                                #   N seconds and grade what's heard
    python meshtastic_probe.py --raw            # also dump everything we could read

WHY THIS EXISTS:

The first radio this project touches is a BORROWED one (a group member's
Heltec WiFi LoRa 32 V4). The polite way to handle borrowed hardware is the
same as the safe way to handle any hardware: look, don't touch. So this
script is read-only by design —

  * it never changes a single setting on the node
  * it never transmits anything over the air (reading config is local
    serial traffic between the PC and the board; it does not key the radio)
  * it never prints encryption keys — only whether a key is the well-known
    default or a real custom one

What it DOES do is answer, in one command, every question on the
first-power-up checklist: firmware version, region, channel/encryption
posture, position precision, battery — and grades each answer PASS / WARN /
FAIL so you know whether the node is ready for the mesh or needs attention.

Exit codes: 0 = probed, no FAILs · 1 = probed, at least one FAIL ·
2 = could not probe (no device / no library / no port).

One hardware warning that belongs everywhere it can possibly be printed:
a powered Meshtastic node beacons on its own schedule. NEVER power a LoRa
board without its antenna attached — transmitting into nothing can burn
out the power amplifier. (28 dBm into an open circuit is how a $30 board
becomes a $30 paperweight.)

Dependencies: pyserial + meshtastic (both already in requirements.txt).
The imports are lazy, same pattern as lora_oracle.py, so --help and the
self-testable helpers work on a machine with nothing installed.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import re
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Project geography (script lives in 05_SCRIPTS/, repo root is one up)
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parents[1]
BACKUP_DIR = REPO_ROOT / "04_CONFIG" / "meshtastic"

# The handoff checklist says firmware 2.5 or newer before a node joins the mesh.
MIN_FIRMWARE = (2, 5)

# USB IDs seen on Meshtastic dev boards. Used only to *suggest* a port.
KNOWN_USB_VIDS = {
    0x10C4: "Silicon Labs CP210x",
    0x1A86: "WCH CH340/CH9102",
    0x303A: "Espressif native USB",
    0x239A: "Adafruit TinyUSB (nRF52840: T114, RAK4631, T-Echo)",
}


# ---------------------------------------------------------------------------
# Pure helpers — no hardware, no imports beyond stdlib. These are what the
# test suite exercises, so the grading logic is proven before a radio exists.
# ---------------------------------------------------------------------------

def fw_tuple(version: str | None) -> tuple[int, ...]:
    """'v2.7.20.abc123' -> (2, 7, 20). Junk and None -> () (never crashes)."""
    if not version:
        return ()
    out: list[int] = []
    for piece in str(version).lstrip("vV").split("."):
        # all-digits pieces only: "2.7.20.5cd9b0e" ends in a git hash, and a
        # hash that happens to start with a digit must not become a number
        if not re.fullmatch(r"\d+", piece):
            break
        out.append(int(piece))
    return tuple(out)


def fw_at_least(version: str | None, minimum: tuple[int, ...] = MIN_FIRMWARE) -> bool | None:
    """True/False against the checklist minimum; None if unparseable."""
    parsed = fw_tuple(version)
    if not parsed:
        return None
    return parsed >= minimum


def classify_psk(psk: bytes) -> tuple[str, str]:
    """
    Grade a channel key WITHOUT revealing it. Returns (grade, plain English).

    Meshtastic PSK semantics: empty or a single 0x00 byte = no encryption;
    a single 0x01 = THE default key every Meshtastic device ships with;
    a single 0x02–0xFF = 'simple' keys (default key with one byte changed —
    still public knowledge); 16 or 32 bytes = a real custom AES key.
    """
    if len(psk) == 0 or psk == b"\x00":
        return "off", "encryption OFF - plaintext"
    if psk == b"\x01":
        return "default", "the well-known default key (public)"
    if len(psk) == 1:
        return "simple", "default-derived 'simple' key (still public)"
    if len(psk) == 16:
        return "custom", "custom AES-128 key"
    if len(psk) == 32:
        return "custom", "custom AES-256 key"
    return "odd", f"nonstandard {len(psk)}-byte key"


def evaluate(report: dict) -> list[tuple[str, str, str]]:
    """
    Turn a probe report into checklist rows: (STATUS, item, detail).
    STATUS is PASS / WARN / FAIL / INFO. Pure function -> fully testable.
    """
    rows: list[tuple[str, str, str]] = []

    # -- firmware ----------------------------------------------------------
    fw = report.get("firmware")
    ok = fw_at_least(fw)
    if ok is None:
        rows.append(("WARN", "firmware", "could not read a version string"))
    elif ok:
        rows.append(("PASS", "firmware", f"{fw} (checklist minimum is 2.5)"))
    else:
        rows.append(("FAIL", "firmware", f"{fw} is older than 2.5 - update before mesh use"))

    # -- region ------------------------------------------------------------
    region = report.get("region")
    if region in (None, "", "UNSET"):
        rows.append(("FAIL", "region", "UNSET - the radio will not transmit at all "
                                       "(the #1 'my node is silent' cause)"))
    elif region == "US":
        rows.append(("PASS", "region", "US (915 MHz ISM)"))
    else:
        rows.append(("WARN", "region", f"{region} - not US; wrong band for Colorado"))

    # -- transmit enabled --------------------------------------------------
    tx = report.get("tx_enabled")
    if tx is False:
        rows.append(("WARN", "tx_enabled", "transmit disabled - fine on a bench, "
                                           "useless on a mesh"))
    elif tx is True:
        rows.append(("PASS", "tx_enabled", "radio may transmit"))

    # -- channels ----------------------------------------------------------
    channels = report.get("channels") or []
    have_private_secondary = False
    for ch in channels:
        label = f"ch{ch.get('index')} {ch.get('role', '?').lower()}" \
                + (f" '{ch['name']}'" if ch.get("name") else "")
        grade = ch.get("psk_class")
        detail = ch.get("psk_human", "")
        if grade == "off":
            rows.append(("FAIL", label, detail + " - anyone can read AND inject"))
        elif grade in ("default", "simple"):
            if ch.get("role") == "PRIMARY":
                # The public LongFast mesh is SUPPOSED to use the default key -
                # that's how you talk to strangers. Just never say anything
                # private on it.
                rows.append(("INFO", label, detail + " - normal for the public mesh"))
            else:
                rows.append(("WARN", label, detail + " - a secondary channel "
                                            "should have a real key"))
        elif grade == "custom":
            rows.append(("PASS", label, detail))
            if ch.get("role") == "SECONDARY":
                have_private_secondary = True
        elif grade == "odd":
            rows.append(("WARN", label, detail))

        # Position precision rides per-channel. 32 bits = your exact position.
        prec = ch.get("position_precision")
        if prec is not None and grade != "off":
            if prec == 0:
                rows.append(("INFO", label + " position", "not shared on this channel"))
            elif prec >= 32:
                rows.append(("WARN", label + " position",
                             "FULL precision - checklist wants LOW (coarse) precision"))
            else:
                rows.append(("PASS", label + " position", f"coarse ({prec} bits)"))

    if channels and not have_private_secondary:
        rows.append(("WARN", "private channel",
                     "no secondary channel with a custom key yet - the group "
                     "plan wants one (random PSK, shared by QR in person)"))

    # -- housekeeping ------------------------------------------------------
    batt = report.get("battery")
    if batt is not None:
        status = "WARN" if batt < 20 else "INFO"
        volts = report.get("voltage")
        rows.append((status, "battery",
                     f"{batt}%" + (f" ({volts:.2f} V)" if volts else "")))

    bt = report.get("bluetooth")
    if bt is True:
        rows.append(("INFO", "bluetooth", "on - handy for the phone app, "
                                          "turn off later to save power"))
    elif bt is False:
        rows.append(("INFO", "bluetooth", "off"))

    # MQTT republishes mesh traffic to an internet broker. Off is the only
    # acceptable steady state; a deliberate bridge (CAMP_DEPLOYMENT's "Utah
    # door") is a time-boxed exception whose CLEANUP this check verifies —
    # after any bridge, a probe must come back clean.
    mqtt = report.get("mqtt_enabled")
    if mqtt is True:
        rows.append(("FAIL", "mqtt", "ENABLED - this node republishes mesh "
                     "traffic to an internet broker. Off unless deliberately "
                     "bridging (and off again the moment that ends)."))
    elif mqtt is False:
        rows.append(("PASS", "mqtt", "off"))

    heard = report.get("nodes_heard")
    if heard is not None:
        rows.append(("INFO", "mesh neighbors",
                     f"{heard} node(s) in the node DB"
                     + (" (just itself - expected on a solo bench)" if heard <= 1 else "")))

    return rows


def worst_status(rows: list[tuple[str, str, str]]) -> int:
    """Exit code from checklist rows: FAIL anywhere -> 1, else 0."""
    return 1 if any(r[0] == "FAIL" for r in rows) else 0


# ---------------------------------------------------------------------------
# RX quality — the "LoRa speedtest", receive half. Pure functions first so the
# grading is testable without a radio; the listener that feeds them is below.
# ---------------------------------------------------------------------------

def summarize_rx(samples: list[dict], seconds: float) -> dict:
    """
    Boil packet samples ({'node': id, 'rssi': dBm, 'snr': dB}) down to stats.
    RSSI = raw received power; SNR = how far above the noise the signal sits.
    LoRa demodulates below the noise floor — on the LongFast preset the
    floor is about -20 dB SNR. That number is LONGFAST-TYPICAL, not a
    universal LoRa constant: faster presets need much better SNR, slower
    ones decode a little deeper. Grade against the preset you're running.
    """
    rssis = sorted(s["rssi"] for s in samples if s.get("rssi") is not None)
    snrs = sorted(s["snr"] for s in samples if s.get("snr") is not None)
    per_node: dict = {}
    for s in samples:
        node = s.get("node") or "?"
        best = per_node.get(node)
        if best is None or (s.get("snr") is not None
                            and (best.get("snr") is None or s["snr"] > best["snr"])):
            per_node[node] = {"snr": s.get("snr"), "rssi": s.get("rssi")}
    mid = len(rssis) // 2
    return {
        "seconds": seconds,
        "packets": len(samples),
        "unique_nodes": len(per_node),
        "per_node": per_node,
        "rssi_min": rssis[0] if rssis else None,
        "rssi_med": rssis[mid] if rssis else None,
        "rssi_max": rssis[-1] if rssis else None,
        "snr_best": snrs[-1] if snrs else None,
        "pkt_per_min": round(len(samples) / (seconds / 60.0), 1) if seconds else 0.0,
    }


def grade_rx(summary: dict) -> tuple[str, str]:
    """
    (verdict, plain English) from an RX summary. Honest thresholds
    (tightened per external review, 2026-08-25):

    - SILENT: zero over-the-air packets. On a metro mesh that is almost
      never real quiet — suspect the antenna path (or a truly dead hour).
    - WEAK: only floor-scraping signal from at most one node. The classic
      damaged-antenna signature: a bare IPEX pad still hears the loudest
      rooftop neighbor, barely, and nothing else.
    - GOOD: two-plus distinct nodes, OR one node with genuinely healthy
      SNR (>= -8 dB) — because in RF-quiet terrain a single strong
      neighbor is a working antenna, and grading it WEAK would send
      someone to disassemble a healthy SMA.

    RX-good implies TX-good only as a FIRST FILTER: reciprocity holds for
    antennas, but water-filled coax, a connector that passes RX and arcs
    on TX, or a twisted pigtail can all break the shortcut. The one-
    traceroute-after-GOOD step in RADIO_BENCH_TEST.md is the proof.
    """
    if summary["packets"] == 0:
        return ("SILENT", "heard nothing over the air. Either the mesh is in a "
                          "dead hour or the antenna path is broken - listen "
                          "longer, and if still silent, open the case and check "
                          "the IPEX pigtail is seated on the board.")
    best = summary.get("snr_best")
    if summary["unique_nodes"] >= 2 or (best is not None and best >= -8):
        return ("GOOD", f"{summary['unique_nodes']} node(s) heard, best SNR "
                        f"{best} dB - the RX path works. Reciprocity suggests "
                        "TX works too; confirm with ONE traceroute (a damaged "
                        "feedline can pass RX and still fail TX).")
    return ("WEAK", "a single node at the LongFast decode floor - the classic "
                    "damaged-antenna signature. Compare with a known-good "
                    "session (or listen from open ground) before trusting "
                    "this antenna.")


def listen_rx(port: str, seconds: int) -> dict | None:
    """
    Passive RX monitor: open the node, TRANSMIT NOTHING, and tally every
    packet that arrives over the air for N seconds. This is the safe half of
    an antenna check — you can run it on a suspect antenna without risking
    the power amplifier, because listening never keys the radio.
    """
    import time

    from pubsub import pub
    import meshtastic.serial_interface

    samples: list[dict] = []
    my_num = {"n": None}

    def _on_rx(packet=None, interface=None):
        if not isinstance(packet, dict):
            return
        # Only packets that actually crossed the air carry rx metrics;
        # our own node's local packets do not count as reception.
        if packet.get("from") == my_num["n"]:
            return
        rssi, snr = packet.get("rxRssi"), packet.get("rxSnr")
        if rssi is None and snr is None:
            return
        samples.append({"node": packet.get("fromId") or packet.get("from"),
                        "rssi": rssi, "snr": snr})

    pub.subscribe(_on_rx, "meshtastic.receive")
    print(f"Opening {port} for a {seconds}s silent listen (no transmissions)...")
    iface = meshtastic.serial_interface.SerialInterface(devPath=port)
    try:
        my_num["n"] = getattr(getattr(iface, "myInfo", None), "my_node_num", None)
        start = time.monotonic()
        while time.monotonic() - start < seconds:
            time.sleep(1)
            elapsed = int(time.monotonic() - start)
            if elapsed and elapsed % 15 == 0:
                print(f"  ...{elapsed}s, {len(samples)} packets heard")
    finally:
        pub.unsubscribe(_on_rx, "meshtastic.receive")
        iface.close()
    return summarize_rx(samples, float(seconds))


def render_rx(summary: dict) -> None:
    verdict, why = grade_rx(summary)
    print(f"\n=== RX check: {summary['packets']} packets / "
          f"{summary['unique_nodes']} nodes in {int(summary['seconds'])}s "
          f"({summary['pkt_per_min']}/min) ===")
    if summary["packets"]:
        print(f"  RSSI dBm  min {summary['rssi_min']} | median {summary['rssi_med']} "
              f"| max {summary['rssi_max']}")
        print(f"  best SNR  {summary['snr_best']} dB")
        loudest = sorted(summary["per_node"].items(),
                         key=lambda kv: (kv[1]["snr"] is not None, kv[1]["snr"]),
                         reverse=True)[:5]
        print("  loudest neighbors (best traceroute targets):")
        for node, m in loudest:
            print(f"    {node}  snr {m['snr']} dB  rssi {m['rssi']} dBm")
    print(f"\n  verdict: {verdict} - {why}")


# ---------------------------------------------------------------------------
# Hardware side — everything below needs pyserial/meshtastic and a real node.
# ---------------------------------------------------------------------------

def list_serial_ports(verbose: bool = True) -> list:
    """Show every serial port and flag the ones that smell like a dev board."""
    try:
        from serial.tools import list_ports
    except ImportError:
        print("pyserial is not installed. In your venv:  pip install -r requirements.txt")
        return []
    ports = sorted(list_ports.comports(), key=lambda p: p.device)
    if verbose:
        if not ports:
            print("No serial ports at all. First suspect: the USB cable - many are "
                  "charge-only, and a charge-only cable powers the board up while "
                  "showing you nothing. ESP32-S3 boards (Heltec V4, T-Deck) use "
                  "native USB and need NO driver on Windows 10/11; boards with a "
                  "bridge chip may need the CP210x or CH340/CH9102 driver - an "
                  "unknown device in Device Manager is the tell.")
        for p in ports:
            hint = KNOWN_USB_VIDS.get(p.vid or 0, "")
            print(f"  {p.device}  {p.description}" + (f"  <- {hint} (likely a dev board)" if hint else ""))
    return ports


def pick_port(explicit: str | None) -> str | None:
    """Use --port if given; otherwise auto-pick IF exactly one candidate exists."""
    if explicit:
        return explicit
    ports = list_serial_ports(verbose=False)
    candidates = [p for p in ports if (p.vid or 0) in KNOWN_USB_VIDS]
    if len(candidates) == 1:
        return candidates[0].device
    if not candidates:
        print("No likely dev-board serial port found.\n")
        list_serial_ports(verbose=True)
        return None
    print("More than one candidate port - tell me which with --port:")
    list_serial_ports(verbose=True)
    return None


def _enum_name(enum_cls, value, fallback: str) -> str:
    """Protobuf enum int -> its NAME, defensively (proto layouts move around)."""
    try:
        return enum_cls.Name(value)
    except Exception:
        return fallback


def probe(port: str) -> tuple[dict, dict]:
    """
    Connect over serial, READ ONLY, and build the report dict that evaluate()
    grades. Returns (report, raw) where raw holds the underlying objects for
    --raw dumping. Every field is optional - firmware differences must never
    crash the probe.
    """
    import meshtastic.serial_interface  # lazy, like lora_oracle

    # Proto modules moved in meshtastic-python 2.3; support both homes.
    try:
        from meshtastic.protobuf import config_pb2
    except ImportError:  # older library layout
        from meshtastic import config_pb2  # type: ignore

    print(f"Opening {port} (read-only probe - no settings will be changed)...")
    iface = meshtastic.serial_interface.SerialInterface(devPath=port)
    report: dict = {}
    raw: dict = {}
    try:
        # --- identity ----------------------------------------------------
        my_num = getattr(getattr(iface, "myInfo", None), "my_node_num", None)
        me = (getattr(iface, "nodesByNum", None) or {}).get(my_num, {}) if my_num else {}
        user = me.get("user", {})
        report["node_id"] = user.get("id")
        report["node_name"] = user.get("longName")
        report["short_name"] = user.get("shortName")
        report["hw_model"] = user.get("hwModel")
        metrics = me.get("deviceMetrics", {})
        report["battery"] = metrics.get("batteryLevel")
        report["voltage"] = metrics.get("voltage")

        # --- firmware ----------------------------------------------------
        meta = getattr(iface, "metadata", None)
        report["firmware"] = getattr(meta, "firmware_version", None)

        # --- radio config ------------------------------------------------
        local = getattr(iface, "localNode", None)
        cfg = getattr(local, "localConfig", None)
        lora = getattr(cfg, "lora", None)
        if lora is not None:
            report["region"] = _enum_name(
                config_pb2.Config.LoRaConfig.RegionCode, lora.region, str(lora.region))
            report["tx_enabled"] = bool(getattr(lora, "tx_enabled", True))
            report["tx_power"] = getattr(lora, "tx_power", None)
            if getattr(lora, "use_preset", False):
                report["modem_preset"] = _enum_name(
                    config_pb2.Config.LoRaConfig.ModemPreset,
                    lora.modem_preset, str(lora.modem_preset))
            report["hop_limit"] = getattr(lora, "hop_limit", None)
        bt = getattr(cfg, "bluetooth", None)
        if bt is not None:
            report["bluetooth"] = bool(getattr(bt, "enabled", False))
        mod = getattr(local, "moduleConfig", None)
        mqtt = getattr(mod, "mqtt", None)
        if mqtt is not None:
            report["mqtt_enabled"] = bool(getattr(mqtt, "enabled", False))

        # --- channels ----------------------------------------------------
        channels = []
        for ch in (getattr(local, "channels", None) or []):
            try:
                role = _enum_name(type(ch).Role, ch.role, str(ch.role))
            except Exception:
                role = str(getattr(ch, "role", "?"))
            if role == "DISABLED":
                continue
            psk = bytes(getattr(ch.settings, "psk", b""))
            grade, human = classify_psk(psk)
            entry = {
                "index": getattr(ch, "index", None),
                "role": role,
                "name": getattr(ch.settings, "name", "") or "",
                "psk_class": grade,
                "psk_human": human,
            }
            mod = getattr(ch.settings, "module_settings", None)
            if mod is not None and hasattr(mod, "position_precision"):
                entry["position_precision"] = mod.position_precision
            channels.append(entry)
        report["channels"] = channels

        # --- who else is out there --------------------------------------
        nodes = getattr(iface, "nodes", None) or {}
        report["nodes_heard"] = len(nodes)

        raw["myInfo"] = getattr(iface, "myInfo", None)
        raw["metadata"] = meta
        raw["localConfig"] = cfg
        raw["nodes"] = nodes
    finally:
        iface.close()
    return report, raw


def backup_config(port: str) -> Path | None:
    """
    Freeze the node's full config to 04_CONFIG/meshtastic/ BEFORE anyone
    changes anything - the first rule of borrowed hardware. Shells out to the
    official CLI because --export-config is its stable, supported interface.

    The export CONTAINS THE REAL CHANNEL KEYS. That is exactly why 04_CONFIG
    is on the .gitignore whitelist's deny side - it can never reach GitHub.
    """
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = BACKUP_DIR / f"node_backup_{stamp}.yaml"
    print(f"Exporting full node config -> {dest}")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "meshtastic", "--port", port, "--export-config"],
            capture_output=True, text=True, timeout=120)
    except Exception as e:
        print(f"Could not run the meshtastic CLI ({e}).")
        return None
    text = result.stdout or ""
    if result.returncode != 0 or len(text.strip()) < 40:
        print("Export FAILED - nothing written. CLI said:\n"
              + (result.stderr or text or "(no output)"))
        return None
    dest.write_text(text, encoding="utf-8")
    print(f"Saved {len(text):,} bytes. This file holds radio keys - it stays "
          "local (04_CONFIG is blocked from git by the whitelist).")
    return dest


# ---------------------------------------------------------------------------
# Report rendering
# ---------------------------------------------------------------------------

def render(report: dict, rows: list[tuple[str, str, str]]) -> None:
    name = report.get("node_name") or "(unnamed node)"
    ident = report.get("node_id") or "?"
    hw = report.get("hw_model") or "unknown hardware"
    print(f"\n=== {name}  [{ident}]  {hw} ===")
    extras = []
    if report.get("modem_preset"):
        extras.append(f"preset {report['modem_preset']}")
    if report.get("tx_power") is not None:
        extras.append(f"tx_power {report['tx_power']} dBm")
    if report.get("hop_limit") is not None:
        extras.append(f"hops {report['hop_limit']}")
    if extras:
        print("    " + " | ".join(extras))
    print()
    for status, item, detail in rows:
        print(f"  [{status:>4}] {item}: {detail}")
    fails = sum(1 for r in rows if r[0] == "FAIL")
    warns = sum(1 for r in rows if r[0] == "WARN")
    print(f"\n  verdict: {'NOT mesh-ready' if fails else 'mesh-ready'}"
          f" ({fails} fail, {warns} warn)")


def main() -> int:
    ap = argparse.ArgumentParser(description="Read-only Meshtastic node health check")
    ap.add_argument("--port", help="serial port (e.g. COM7); default: auto-detect")
    ap.add_argument("--list-ports", action="store_true", help="list serial ports and exit")
    ap.add_argument("--backup", action="store_true",
                    help="after probing, export full config to 04_CONFIG/meshtastic/")
    ap.add_argument("--listen", type=int, metavar="SECONDS",
                    help="passive antenna RX check: listen silently for N "
                         "seconds and grade what was heard (transmits nothing)")
    ap.add_argument("--raw", action="store_true", help="also dump raw structures")
    args = ap.parse_args()

    if args.list_ports:
        list_serial_ports(verbose=True)
        return 0

    port = pick_port(args.port)
    if not port:
        return 2

    if args.listen:
        try:
            summary = listen_rx(port, args.listen)
        except ImportError as e:
            print(f"Missing radio dependency ({e}). In your venv: "
                  "pip install -r requirements.txt")
            return 2
        except Exception as e:
            print(f"Could not listen on {port}: {e}")
            return 2
        render_rx(summary)
        return 0 if grade_rx(summary)[0] == "GOOD" else 1

    try:
        report, raw = probe(port)
    except ImportError as e:
        print(f"Missing radio dependency ({e}). In your venv: "
              "pip install -r requirements.txt")
        return 2
    except Exception as e:
        print(f"Could not probe {port}: {e}\n"
              "Is another program (phone app over USB, a second script) holding "
              "the port? Only one process can own a serial port at a time.")
        return 2

    rows = evaluate(report)
    render(report, rows)

    if args.raw:
        print("\n--- raw ---")
        for key, value in raw.items():
            print(f"\n[{key}]\n{value}")

    if args.backup:
        backup_config(port)

    return worst_status(rows)


if __name__ == "__main__":
    sys.exit(main())
