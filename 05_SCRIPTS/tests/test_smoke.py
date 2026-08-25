"""Smoke test: every script imports against the REAL installed libraries
(meshtastic, pyserial, requests), plus behavior checks on the safety-
critical helpers. Needs `pip install -r requirements.txt` first.

Run from anywhere:  python 05_SCRIPTS/tests/test_smoke.py
Uses a temp directory for anything it writes; touches nothing in the repo.
"""
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import lora_oracle          # noqa: E402
import make_skeleton        # noqa: E402,F401  (import IS the test)
import pi_agent             # noqa: E402
import power_monitor        # noqa: E402,F401
import safety_router        # noqa: E402
import verify_checksums     # noqa: E402,F401

# The oracle imports its radio deps lazily (so --demo needs no radio libs);
# prove the dependency still installs and imports for the real path:
import meshtastic.serial_interface   # noqa: E402,F401

with tempfile.TemporaryDirectory() as td:
    tmp = Path(td)

    # clip(): the 200-char radio cap holds — in CHARACTERS and in BYTES
    assert len(lora_oracle.clip("x " * 300)) == 200
    assert len(lora_oracle.clip("°" * 300).encode("utf-8")) <= 230

    # router: caliber+intent fences; caliber alone stays free
    d = safety_router.route("what's a safe 9mm load?")
    assert d.route == "RETRIEVAL_ONLY" and d.domain == "reloading", d
    d = safety_router.route("what's the best 9mm holster material?")
    assert d.route == "GENERAL_MODEL", d

    # pi_agent jail (pointed at the temp dir): escape refused, inside allowed
    pi_agent.AGENT_ROOT = tmp / "sandbox"
    pi_agent.AGENT_ROOT.mkdir()
    try:
        pi_agent._jailed("../escape.txt")
        raise SystemExit("JAIL FAILED - escape allowed")
    except ValueError:
        pass
    p = pi_agent._jailed("sub/tool.py")
    assert str(p).startswith(str(pi_agent.AGENT_ROOT.resolve())), p

    # pi_agent size caps: oversize refused before touching disk; roundtrip works
    out = pi_agent.t_write_file("big.txt", "x" * 300_000)
    assert out.startswith("TOOL ERROR"), out
    assert "wrote" in pi_agent.t_write_file("t.txt", "hi")
    assert pi_agent.t_read_file("t.txt") == "hi"

    # oracle ?power (pointed at temp latest.json): fresh -> clean; old -> STALE
    lora_oracle.LATEST_JSON = tmp / "latest.json"
    lora_oracle.LATEST_JSON.write_text(json.dumps(
        {"utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
         "band": "GREEN", "batt_V": 13.4, "pv_W": 200}))
    out = lora_oracle.cmd_power("")
    assert "BAND GREEN" in out and "STALE" not in out, out
    lora_oracle.LATEST_JSON.write_text(json.dumps(
        {"utc": "2020-01-01T00:00:00+00:00", "band": "GREEN", "batt_V": 13.4}))
    out = lora_oracle.cmd_power("")
    assert "STALE" in out, out

    # oracle allowlist gate: open mode admits all; a set admits only members
    assert lora_oracle._authorized(123) is True
    lora_oracle.AUTHORIZED_SENDERS = {42}
    assert lora_oracle._authorized(42) is True
    assert lora_oracle._authorized(123) is False
    lora_oracle.AUTHORIZED_SENDERS = None

print("smoke: ALL PASS")
