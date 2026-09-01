"""Smoke test: every script imports against the REAL installed libraries
(meshtastic, pyserial, requests), plus behavior checks on the safety-
critical helpers. Needs `pip install -r requirements.txt` first.

Run from anywhere:  python 05_SCRIPTS/tests/test_smoke.py
Uses a temp directory for anything it writes; touches nothing in the repo.
"""
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

# Scrub real messaging credentials from THIS process before anything runs:
# a dev box with live Twilio/SMTP env vars must never let a test suite past
# the credential gates and onto the network. (Found the hard way — the only
# thing that stopped a live API call was the test's deliberately fake
# number. Tests prove gates; they must not depend on the machine's env.)
for _var in ("TWILIO_ACCOUNT_SID", "TWILIO_API_KEY_SID", "TWILIO_API_KEY_SECRET",
             "TWILIO_AUTH_TOKEN", "TWILIO_FROM_NUMBER",
             "ORACLE_SMTP_HOST", "ORACLE_SMTP_USER", "ORACLE_SMTP_PASS",
             "ORACLE_ALLOWLIST"):
    os.environ.pop(_var, None)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import lora_oracle          # noqa: E402
import make_skeleton        # noqa: E402,F401  (import IS the test)
import meshtastic_probe     # noqa: E402,F401  (hardware imports must stay lazy)
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

    # ?med window targeting: captions/chrome cut, Management section wins
    fake = ('<h1>Burns</h1><div class="thumb tright"><div class="thumbinner">'
            '<div class="thumbcaption">Cross-sectional anatomy of burns</div>'
            '</div></div><p>Background prose here.</p>'
            '<h2><span class="mw-headline" id="Management">Management</span></h2>'
            '<p>Cool the burn. Remove rings.</p>'
            '<h2>References</h2><p>License boilerplate junk.</p>')
    sec, txt = lora_oracle._article_text(fake)
    assert sec.endswith("MANAGEMENT") and txt.startswith("Cool the burn"), (sec, txt)
    assert "junk" not in txt, "the section window must stop at the next heading"
    fake2 = '<div class="thumbcaption">Anatomy diagram</div><p>Body text.</p>'
    sec2, txt2 = lora_oracle._article_text(fake2)
    assert sec2 == "" and "Anatomy" not in txt2 and "Body text." in txt2, txt2
    fake3 = ('<h1>T</h1><h2>General Management</h2><p>Warm the core.</p>'
             '<h2>See Also</h2><p>x</p>')
    sec3, txt3 = lora_oracle._article_text(fake3)
    assert sec3 == "§MANAGEMENT" and txt3.strip() == "Warm the core.", (sec3, txt3)

    # ?med paging: walked pages, nothing lost in the cracks, clamped pages
    long_text = ("Alpha beta gamma. " * 30).strip()
    parts, n = [], 1
    while True:
        b, p, t = lora_oracle._page_window(long_text, 100, n)
        parts.append(b)
        if p == t:
            break
        n += 1
    assert " ".join(" ".join(parts).split()) == long_text, \
        "walking the pages must reconstruct the article verbatim"
    assert all(b == b.strip() and b in long_text for b in parts)
    b9, p9, t9 = lora_oracle._page_window(long_text, 100, 99)
    assert (p9, t9) == (t, t), "page past the end clamps to the last page"
    assert lora_oracle._page_window("short.", 100, 3) == ("short.", 1, 1)

    # ORACLE_ALLOWLIST parsing: !hex, 0xhex, decimal, "*", unset
    assert lora_oracle._parse_allowlist(None) is None
    assert lora_oracle._parse_allowlist("  ") is None
    assert lora_oracle._parse_allowlist("*") == "*"
    assert lora_oracle._parse_allowlist("!ba0618fd,0xAB, 77") == {0xBA0618FD, 0xAB, 77}

    # router: caliber+intent fences; caliber alone stays free
    d = safety_router.route("what's a safe 9mm load?")
    assert d.route == "RETRIEVAL_ONLY" and d.domain == "reloading", d
    d = safety_router.route("what's the best 9mm holster material?")
    assert d.route == "GENERAL_MODEL", d

    # ?ask gateway: the fence routes BEFORE any brain, cloud or local — a
    # fenced question never reaches a model, and none of this needs network
    r = lora_oracle.handle("?ask is this mushroom edible?")
    assert r.startswith("FENCED (plant_edibility)"), r
    r = lora_oracle.handle("?ask pediatric ibuprofen dose?")
    assert r.startswith("FENCED (medical)") and "?med" in r, r
    r = lora_oracle.handle("?ask what's the pinout of the sx1262?")
    assert r.startswith("Spec/part question"), r
    # unfenced question, both brains unconfigured -> honest refusal, no crash
    assert lora_oracle.NET_BACKEND is None and lora_oracle.OLLAMA_MODEL is None
    r = lora_oracle.handle("?ask what species is this purple flower?")
    assert r.startswith("ASK: no uplink"), r
    # ?net reports the shipped-disabled state without probing anything
    assert "disabled" in lora_oracle.handle("?net")

    # ?sms/?email — the outside-world door. Gate ONE is allowlist mode, so
    # every assertion here resolves before any network could be touched.
    r = lora_oracle.handle("?sms ethan call mom im fine")
    assert r.startswith("SMS: needs an AUTHORIZED_SENDERS"), r
    r = lora_oracle.handle("?email ethan hi")
    assert r.startswith("EMAIL: needs an AUTHORIZED_SENDERS"), r
    # explicitly-open "*" is STILL refused — open nodes don't text the world
    lora_oracle.AUTHORIZED_SENDERS = "*"
    assert lora_oracle.handle("?sms ethan hi").startswith("SMS: needs"), "star"
    # allowlist active but nothing configured -> config gates, still offline
    lora_oracle.AUTHORIZED_SENDERS = {123}
    try:
        assert lora_oracle.handle("?sms ethan hi").startswith("SMS: no contacts")
        lora_oracle.SMS_CONTACTS["ethan"] = "+15555550100"
        assert "credentials" in lora_oracle.handle("?sms ethan hi")
        lora_oracle.EMAIL_CONTACTS["ethan"] = "e@example.com"
        assert "credentials" in lora_oracle.handle("?email ethan hi")
    finally:
        lora_oracle.AUTHORIZED_SENDERS = None
        lora_oracle.SMS_CONTACTS.clear()
        lora_oracle.EMAIL_CONTACTS.clear()

    # Packet modes: byte-exact, suffix inside the budget, fenced pins ultra
    one = lora_oracle.packetize("short answer", "ultra")
    assert len(one) == 1 and "[1/" not in one[0]
    assert len(one[0].encode("utf-8")) <= lora_oracle.MAX_BYTES

    long_text = ("the carburetor bowl gasket seals the float chamber against "
                 "the bowl flange and hardens with ethanol fuel over seasons ") * 6
    parts = lora_oracle.packetize(long_text, "compact")
    assert 2 <= len(parts) <= lora_oracle.MAX_PARTS, len(parts)
    for i, p in enumerate(parts):
        assert len(p.encode("utf-8")) <= lora_oracle.MAX_BYTES, (i, p)
        assert p.endswith(f"[{i + 1}/{len(parts)}]"), p

    # multibyte discipline: '°' is two bytes and must never straddle a slice
    for p in lora_oracle.packetize("°" * 500, "compact"):
        assert len(p.encode("utf-8")) <= lora_oracle.MAX_BYTES
        p.encode("utf-8").decode("utf-8")     # raises if a char was split

    # compact on short text: one clean packet, no pointless [1/1]
    single = lora_oracle.packetize("short", "compact")
    assert len(single) == 1 and "[1/1]" not in single[0]
    # ultra ignores length: always exactly one clipped packet
    assert len(lora_oracle.packetize(long_text, "ultra")) == 1

    # provenance: a FENCED ?ask pins ultra even when compact was requested
    lora_oracle._REPLY["mode"] = None
    r = lora_oracle.handle("?ask compact is this mushroom edible?")
    assert r.startswith("FENCED (plant_edibility)"), r
    assert lora_oracle._REPLY["mode"] == "ultra"
    # ?med pins ultra before it does anything else
    lora_oracle._REPLY["mode"] = None
    lora_oracle.handle("?med tourniquet")
    assert lora_oracle._REPLY["mode"] == "ultra"
    # a no-brain ?ask never grants compact
    lora_oracle._REPLY["mode"] = None
    r = lora_oracle.handle("?ask compact what species is this purple flower?")
    assert r.startswith("ASK: no uplink"), r
    assert lora_oracle._REPLY["mode"] != "compact"

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

    # oracle allowlist gate: None and "*" admit all; a set admits only members
    assert lora_oracle._authorized(123) is True
    lora_oracle.AUTHORIZED_SENDERS = "*"
    assert lora_oracle._authorized(999) is True
    lora_oracle.AUTHORIZED_SENDERS = {42}
    assert lora_oracle._authorized(42) is True
    assert lora_oracle._authorized(123) is False
    lora_oracle.AUTHORIZED_SENDERS = None

print("smoke: ALL PASS")
