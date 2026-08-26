"""Tests for meshtastic_probe's pure logic — firmware parsing, PSK grading,
and the checklist evaluator. No radio, no serial port, no meshtastic library
needed: importing the module must work bare (its hardware imports are lazy),
which is itself the first thing this file proves.

Run from anywhere:  python 05_SCRIPTS/tests/test_probe.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import meshtastic_probe as mp   # noqa: E402  (bare import IS a test: lazy deps)

# ---------------------------------------------------------------------------
# firmware version parsing
# ---------------------------------------------------------------------------
assert mp.fw_tuple("2.7.20.5cd9b0e") == (2, 7, 20)
assert mp.fw_tuple("v2.5.0") == (2, 5, 0)
assert mp.fw_tuple(None) == ()
assert mp.fw_tuple("garbage") == ()
assert mp.fw_at_least("2.7.20.5cd9b0e") is True
assert mp.fw_at_least("2.5.0") is True          # boundary: exactly the minimum
assert mp.fw_at_least("2.4.3") is False         # one minor version too old
assert mp.fw_at_least("1.3.99") is False
assert mp.fw_at_least("weird-build") is None    # unreadable ≠ failed

# ---------------------------------------------------------------------------
# PSK grading — never reveals key material, only classifies it
# ---------------------------------------------------------------------------
assert mp.classify_psk(b"")[0] == "off"
assert mp.classify_psk(b"\x00")[0] == "off"
assert mp.classify_psk(b"\x01")[0] == "default"
assert mp.classify_psk(b"\x05")[0] == "simple"
assert mp.classify_psk(b"A" * 16)[0] == "custom"
assert mp.classify_psk(b"B" * 32)[0] == "custom"
assert mp.classify_psk(b"C" * 7)[0] == "odd"
# the human string must describe, not disclose: feed a recognizable key and
# make sure its bytes never appear in the output
secret = b"SUPERSECRETKEY!!"          # 16 bytes -> "custom"
grade, human = mp.classify_psk(secret)
assert "SUPERSECRET" not in human and secret.hex() not in human

# ---------------------------------------------------------------------------
# evaluate(): the checklist grader
# ---------------------------------------------------------------------------

def statuses(report):
    return [r[0] for r in mp.evaluate(report)]

def find(report, item_substr):
    return [r for r in mp.evaluate(report) if item_substr in r[1]]

# A node configured exactly per the T-Deck checklist: recent firmware, US,
# public primary + private secondary, coarse position. Must be mesh-ready.
good = {
    "firmware": "2.7.20.5cd9b0e",
    "region": "US",
    "tx_enabled": True,
    "battery": 87, "voltage": 4.02,
    "bluetooth": True,
    "nodes_heard": 1,
    "channels": [
        {"index": 0, "role": "PRIMARY", "name": "",
         "psk_class": "default", "psk_human": "the well-known default key (public)",
         "position_precision": 13},
        {"index": 1, "role": "SECONDARY", "name": "group",
         "psk_class": "custom", "psk_human": "custom AES-256 key",
         "position_precision": 13},
    ],
}
rows = mp.evaluate(good)
assert mp.worst_status(rows) == 0, rows
assert not any(s == "FAIL" for s in statuses(good))
# default key on the PRIMARY channel is normal, so it must be INFO, not a scold
assert find(good, "ch0")[0][0] == "INFO"

# Factory-fresh node: region UNSET means it literally will not transmit.
fresh = dict(good, region="UNSET")
assert any(r[0] == "FAIL" and r[1] == "region" for r in mp.evaluate(fresh))
assert mp.worst_status(mp.evaluate(fresh)) == 1

# Ancient firmware fails the 2.5 checklist line
old = dict(good, firmware="2.3.2.abc")
assert any(r[0] == "FAIL" and r[1] == "firmware" for r in mp.evaluate(old))

# Encryption OFF anywhere is a FAIL — worse than the default key
naked = dict(good, channels=[
    {"index": 0, "role": "PRIMARY", "name": "",
     "psk_class": "off", "psk_human": "encryption OFF - plaintext"}])
assert mp.worst_status(mp.evaluate(naked)) == 1

# No private secondary yet -> WARN that names the missing piece
solo = dict(good, channels=[good["channels"][0]])
private_rows = [r for r in mp.evaluate(solo) if r[1] == "private channel"]
assert private_rows and private_rows[0][0] == "WARN"

# Full-precision position on an enabled channel -> WARN (checklist says LOW)
loud = dict(good, channels=[dict(good["channels"][1], position_precision=32)])
pos_rows = [r for r in mp.evaluate(loud) if "position" in r[1]]
assert pos_rows and pos_rows[0][0] == "WARN"

# A report where nothing could be read still renders SOMETHING and never crashes
assert mp.evaluate({}) != []

# ---------------------------------------------------------------------------
# RX check (the antenna "speedtest"): summarize + grade, no radio needed
# ---------------------------------------------------------------------------

# A healthy metro-mesh listen: many packets, many distinct nodes
busy = [{"node": f"!n{i % 7}", "rssi": -90 - i, "snr": 5.0 - i} for i in range(14)]
s = mp.summarize_rx(busy, 120.0)
assert s["packets"] == 14 and s["unique_nodes"] == 7
assert s["rssi_min"] <= s["rssi_med"] <= s["rssi_max"]
assert s["pkt_per_min"] == 7.0
assert mp.grade_rx(s)[0] == "GOOD"

# Dead air -> SILENT (and stats stay None instead of crashing)
quiet = mp.summarize_rx([], 120.0)
assert quiet["packets"] == 0 and quiet["rssi_med"] is None
assert mp.grade_rx(quiet)[0] == "SILENT"

# Review-tightened rule: ONE node with genuinely healthy SNR is a working
# antenna (RF-quiet terrain must not send anyone to disassemble a good SMA)
one_loud = [{"node": "!rooftop", "rssi": -60, "snr": 12.0}] * 9
assert mp.grade_rx(mp.summarize_rx(one_loud, 120.0))[0] == "GOOD"

# The actual damaged-antenna signature: a single node at the decode floor
one_floor = [{"node": "!rooftop", "rssi": -112, "snr": -19.5}] * 4
assert mp.grade_rx(mp.summarize_rx(one_floor, 120.0))[0] == "WEAK"

# Two distinct nodes, even at the floor, prove the RX path passes RF
two_floor = [{"node": "!a", "rssi": -113, "snr": -20.0},
             {"node": "!b", "rssi": -111, "snr": -19.75}]
assert mp.grade_rx(mp.summarize_rx(two_floor, 120.0))[0] == "GOOD"

# MQTT: off is PASS, on is FAIL — the bridge-cleanup verification
with_mqtt_off = dict(good, mqtt_enabled=False)
assert any(r[0] == "PASS" and r[1] == "mqtt" for r in mp.evaluate(with_mqtt_off))
with_mqtt_on = dict(good, mqtt_enabled=True)
assert any(r[0] == "FAIL" and r[1] == "mqtt" for r in mp.evaluate(with_mqtt_on))
assert mp.worst_status(mp.evaluate(with_mqtt_on)) == 1

# Packets missing one metric (older firmware quirks) must not crash the math
mixed = [{"node": "!a", "rssi": -100, "snr": None},
         {"node": "!b", "rssi": None, "snr": -7.5},
         {"node": "!c", "rssi": -88, "snr": 3.25}]
m = mp.summarize_rx(mixed, 60.0)
assert m["unique_nodes"] == 3 and m["snr_best"] == 3.25 and m["rssi_min"] == -100

print("test_probe: all assertions passed")
