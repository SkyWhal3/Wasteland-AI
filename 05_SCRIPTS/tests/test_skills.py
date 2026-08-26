"""Contract tests for the skills layer's radio telegrams.

Every skill in 02_CORPORA/skills/ carries a one-line `radio_payload:` in its
frontmatter — the "if only one packet gets through" version of its procedure.
The oracle serves it whenever the router matches the skill, so these strings
ARE radio traffic: the byte budget is a hard contract, not a style rule.

Budget arithmetic: a payload may be served behind the longest fence tag,
"FENCED (electrical_sizing). " (28 chars). 200-byte payloads + 28 <= 228,
inside the radio's 230-byte ceiling with no clipping. A payload that needs
clipping would truncate mid-procedure — that is a test failure, not a
runtime nicety.

Run from anywhere:  python 05_SCRIPTS/tests/test_skills.py
No network, no radio, no mocks — the router and oracle run for real.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import lora_oracle       # noqa: E402
import safety_router     # noqa: E402

SKILLS = Path(__file__).resolve().parents[2] / "02_CORPORA" / "skills"
LONGEST_FENCE_TAG = "FENCED (electrical_sizing). "


def frontmatter(path: Path) -> dict:
    """The frontmatter's single-line fields, dumb-parsed the same way the
    oracle parses them — if this parser and the oracle's disagree, that is
    itself a bug worth failing on."""
    fields, dashes = {}, 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip() == "---":
            dashes += 1
            if dashes == 2:
                break
        elif ":" in line and not line.startswith((" ", "-", "#")):
            key, _, val = line.partition(":")
            fields[key.strip()] = val.split("  #")[0].strip().strip('"')
    return fields


skill_files = sorted(p for p in SKILLS.glob("*.md") if p.name != "README.md")
assert len(skill_files) >= 9, f"expected the full roster, found {len(skill_files)}"

for path in skill_files:
    fm = frontmatter(path)
    name = path.stem

    # every skill declares its radio discipline, and it is ultra
    assert fm.get("radio") == "ultra", f"{name}: radio must be 'ultra', got {fm.get('radio')!r}"

    payload = fm.get("radio_payload")
    assert payload, f"{name}: missing radio_payload"
    assert len(payload) >= 40, f"{name}: payload suspiciously short ({len(payload)} chars)"
    assert payload == " ".join(payload.split()), f"{name}: payload has stray whitespace"

    # the budget, including the worst-case fence prefix
    raw = payload.encode("utf-8")
    assert len(raw) <= 200, f"{name}: payload {len(raw)} bytes > 200"
    fenced = (LONGEST_FENCE_TAG + payload).encode("utf-8")
    assert len(fenced) <= lora_oracle.MAX_BYTES, f"{name}: fenced form {len(fenced)} bytes"

    # ultra really means one packet, unclipped: packetize must return the
    # payload byte-identical (clipping would truncate mid-procedure)
    assert lora_oracle.packetize(payload, "ultra") == [payload], f"{name}: payload got clipped"

    # the oracle's own loader reads the same value this test parsed
    assert lora_oracle._skill_payload(name) == payload, f"{name}: loader/test disagree"

# loader edge cases: unknown skill and no skill are both quiet Nones
assert lora_oracle._skill_payload("no-such-skill") is None
assert lora_oracle._skill_payload(None) is None

# e2e through the REAL router and oracle — no network is touched, because
# the telegram returns before either brain is consulted:

# unfenced skill match -> the telegram, verbatim, pinned to ultra
lora_oracle._REPLY["mode"] = None
r = lora_oracle.handle("?ask why won't my predator 3500 start?")
assert r == lora_oracle._skill_payload("generator-service"), r
assert lora_oracle._REPLY["mode"] == "ultra"

# `?ask compact` does not override a skill telegram
lora_oracle._REPLY["mode"] = None
r = lora_oracle.handle("?ask compact why won't my predator 3500 start?")
assert r == lora_oracle._skill_payload("generator-service"), r
assert lora_oracle._REPLY["mode"] == "ultra"

# fenced skill match -> warning tag first, then the telegram, one packet
lora_oracle._REPLY["mode"] = None
r = lora_oracle.handle("?ask deep cut on my hand, does it need stitches?")
assert r.startswith("FENCED (medical). WOUND:"), r
assert len(r.encode("utf-8")) <= lora_oracle.MAX_BYTES, f"fenced reply {len(r.encode())} bytes"
assert lora_oracle._REPLY["mode"] == "ultra"

# fenced with NO skill -> the original generic fence line still stands
r = lora_oracle.handle("?ask pediatric ibuprofen dose?")
assert r.startswith("FENCED (medical):") and "?med" in r, r

# spec questions keep the ?find redirect — a fixed telegram must not
# swallow an artifact lookup
r = lora_oracle.handle("?ask what oil does my honda eu2000i take?")
assert r.startswith("Spec/part question"), r

# every skill the router can name resolves to a real telegram, so the
# radio path can never match a skill and then find nothing to say
for skill_name in safety_router.SKILL_TRIGGERS:
    assert lora_oracle._skill_payload(skill_name), f"router names {skill_name}, no payload"

print(f"test_skills: OK ({len(skill_files)} skills, all telegrams within budget)")
