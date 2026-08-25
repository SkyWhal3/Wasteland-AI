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

print("test_probe: all assertions passed")
