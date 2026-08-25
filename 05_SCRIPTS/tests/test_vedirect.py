"""Unit test: the VE.Direct frame parser — no hardware needed.

Run from anywhere:  python 05_SCRIPTS/tests/test_vedirect.py
Builds protocol-correct frames (checksummed per the Victron spec), then
corrupts, interleaves, and splits them to prove the parser only ever
yields valid frames.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import power_monitor as pm  # noqa: E402


def frame(fields):
    """Build a valid frame: \\r\\nLABEL\\tVALUE ... \\r\\nChecksum\\t<byte>
    where the byte makes the whole frame sum to 0 mod 256."""
    body = b""
    for k, v in fields:
        body += b"\r\n" + k + b"\t" + v
    body += b"\r\nChecksum\t"
    c = (256 - (sum(body) % 256)) % 256
    return body + bytes([c])


good = frame([(b"V", b"13250"), (b"PPV", b"120"), (b"CS", b"3")])

# 1. valid frame parses, values scale correctly
out = list(pm.frames_from_bytes([good]))
assert len(out) == 1 and out[0]["V"] == "13250" and out[0]["CS"] == "3", out
rec = pm.to_record(out[0])
assert rec["batt_V"] == 13.25 and rec["pv_W"] == 120, rec

# 2. a single corrupted digit -> checksum fails -> frame dropped, not parsed
bad = bytearray(good)
bad[good.index(b"13250")] = ord("9")     # 13250 -> 93250
assert list(pm.frames_from_bytes([bytes(bad)])) == []

# 3. interleaved HEX record (':....\n') is skipped; following frame still valid
assert len(list(pm.frames_from_bytes([b":A0102000543\n" + good]))) == 1

# 4. arbitrary serial chunk boundaries don't matter
assert len(list(pm.frames_from_bytes([good[:5], good[5:11], good[11:]]))) == 1

# 5. two frames back to back
assert len(list(pm.frames_from_bytes([good + frame([(b"V", b"13300")])]))) == 2

# 6. mid-stream attach: garbage prefix poisons only the FIRST frame
assert len(list(pm.frames_from_bytes([b"garbage", good + good]))) == 1

print("vedirect parser: ALL 6 TESTS PASS")
