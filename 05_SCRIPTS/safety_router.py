#!/usr/bin/env python3
"""
safety_router.py — classify every question BEFORE any model runs.

The architecture this enforces (manifest §9):

                     ┌── RETRIEVAL_ONLY   verbatim source + citation, NO model
                     │
  question → route ──┼── ARTIFACT_LOOKUP  filename + page from the datasheet tree
                     │
                     ├── RAG              cited chunks + model synthesis, labeled
                     │
                     └── GENERAL_MODEL    model output, labeled as such

Why a dumb keyword router instead of something clever: because it is auditable.
You can read every rule in this file in two minutes and know exactly which
questions can never reach the "creative" path. A wrong charge weight, a wrong
canning time, a wrong fuse size — those come from the generative path, so the
six dangerous domains are physically fenced off from it.

Use standalone:
    python safety_router.py "how much varget for a 168gr .308?"
    python safety_router.py --test        # run the built-in routing self-test

Or import it:
    from safety_router import route
    decision = route(question)   # -> Decision(route, domain, instruction, skill)

`decision.skill`, when set, names a procedure file in 02_CORPORA/skills/ that
says what to ASK before answering and which document to open. A skill never
changes a route — fenced stays fenced; it just rides along.

Extend the keyword lists as you find gaps — misrouting toward MORE caution is
free; misrouting toward less is the failure mode. Substrings match anywhere
("burn" catches "burns" but also "burning smell" — that trade is deliberate).
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass

# ---------------- the six retrieval-only domains (manifest §9) ---------------
# A hit on ANY of these forces RETRIEVAL_ONLY. Keep the lists generous:
# a false positive costs a slightly stiffer answer; a false negative can hurt
# someone.

RETRIEVAL_ONLY_DOMAINS = {
    "medical": [
        "dose", "dosage", "mg/kg", "medication", "antibiotic", "tourniquet",
        "bleeding", "fracture", "burn", "cpr", "overdose", "poison",
        "allergic", "anaphyla", "seizure", "wound", "suture", "infection",
        "symptom", "diagnos", "pediatric", "epinephrine", "insulin",
        "fever", "dehydrat", "hypothermia", "frostbite", "heatstroke",
        "heat exhaustion", "snakebite", "antivenom", "ibuprofen",
        "acetaminophen", "tylenol", "aspirin", "amoxicillin", "penicillin",
        "childbirth", "pregnan", "concussion", "splint", "first aid",
        "unconscious", "choking", "hemorrhage",
        "stitches", "laceration", "puncture", "cut on my", "deep cut",
        "scald", "abscess", "dislocat",
    ],
    "reloading": [
        "grains of", "powder charge", "load data", "reload", "handload",
        "varget", "h4350", "imr", "hodgdon", "unique", "bullseye", "primer",
        "brass", "case capacity", "seating depth", "headspace", "max load",
        "starting load", "gr.", "grain load", "titegroup", "reloder",
        "vihtavuori", "ramshot", "h110", "h335", "cfe", "autocomp",
        "trail boss", "charge weight", "compressed load",
    ],
    "canning": [
        "canning", "pressure can", "water bath", "botulism", "botulinum",
        "headspace jar", "processing time", "pint jar", "quart jar",
        "preserve at altitude", "psi for", "canner", "home canned",
        "pickling brine", "at altitude", "ball blue book", "usda guide",
    ],
    "electrical_sizing": [
        "ampacity", "wire gauge for", "awg for", "fuse size", "fuse for",
        "breaker size", "busbar", "bus bar", "wire size", "how many amps can",
        "charge voltage for", "absorption voltage", "float voltage",
        "series or parallel", "string voltage", "voltage drop",
        "wire run", "conductor size", "panel string", "parallel strings",
        "battery cable", "inverter cable", "charge current", "c-rate",
        "equalization voltage", "equalize at", "equalization charge",
        "specific gravity", "desulfat",
    ],
    "structural": [
        "load bearing", "span for", "joist", "beam size", "rafter",
        "rigging", "working load limit", "wll", "sling angle", "anchor for",
        "pressure vessel", "compressed gas", "crane", "hoist", "snow load",
        "dead load", "live load", "header size", "footing", "cantilever",
        "winch rating", "shackle", "come-along",
    ],
    "water_dosing": [
        "bleach per", "chlorine dose", "ppm chlorine", "purify water",
        "water treatment dose", "iodine tablets", "contact time",
        "calcium hypochlorite", "water purif", "boil water", "pool shock",
        "giardia", "cryptosporidium", "sodis",
        "safe to drink", "drinkable", "potable", "is this water",
    ],
    # PROVISIONAL seventh domain, added 2026-08-25. Generator CO and backfeed
    # are life-safety (both kill people every year) and neither was cleanly
    # covered by the six. This is a pure TIGHTENING — nothing that was fenced
    # became unfenced. Whether §9 of the MANIFEST names this as a seventh
    # domain or folds it into medical/electrical is the manifest owner's call.
    "generator_safety": [
        "carbon monoxide", "co poisoning", "co detector", "co alarm",
        "generator in the garage", "generator in a garage", "generator indoors",
        "generator inside", "run a generator in", "running a generator in",
        "generator ventilation", "exhaust indoors", "exhaust in the",
        "how far from the house", "how far from a window",
        "backfeed", "back-feed", "back feed", "suicide cord",
        "generator to the house", "generator into the house",
        "generator to my house", "transfer switch", "interlock kit",
        "dryer outlet", "plug the generator into",
    ],
    # PROVISIONAL eighth domain, added 2026-08-25 (session 2). The camp-trip
    # use case — "found a plant/mushroom on a hike, what is it?" — walks
    # straight into "can I eat it?", and misidentified mushrooms kill people
    # every year (a death cap looks like a straw mushroom; a false morel
    # looks like breakfast). Species IDENTIFICATION stays unfenced — naming
    # a flower is not dangerous. INGESTION is fenced: any eat/edible/forage
    # framing gets retrieval-only, and "mushroom" fences outright because in
    # a survival context the next question is always dinner. Pure tightening;
    # §9 formalization is the manifest owner's call, same as generator_safety.
    "plant_edibility": [
        "edible", "inedible", "safe to eat", "can i eat", "can you eat",
        "can we eat", "eat this plant", "eat this mushroom", "eat the berries",
        "mushroom", "toadstool", "puffball", "morel",
        "forage", "foraging", "wild edible", "wild onion", "wild berries",
        "are these berries", "berries safe",
        "amanita", "death cap", "death camas", "hemlock", "nightshade",
        "pokeweed",
    ],
}

# Pattern fences — things plain substrings can't express safely.
# 1) Reloading by caliber + intent: ".308 load", "9mm powder charge",
#    "45 acp recipe"... A caliber alone is NOT enough ("best 9mm holster"
#    stays unfenced); a context word alone is NOT enough ("load the truck").
CALIBER_RE = re.compile(
    r"\.\d{3}\b"                                   # .308  .223  .458
    r"|\b\d{1,2}(?:\.\d)?\s*mm\b"                  # 9mm  6.5 mm  10 mm
    r"|\b(?:acp|magnum|creedmoor|winchester|luger|nato|grendel|blackout)\b",
    re.I)
RELOAD_CONTEXT_RE = re.compile(
    r"\b(load|charge|powder|grain|recipe|reload|handload|work\s*up)", re.I)
# 2) Voc as a whole word only ("vocabulary" is not a solar question).
VOC_RE = re.compile(r"\bvoc\b", re.I)

# ---------------- artifact lookups (layer 0/3: files, not prose) -------------
ARTIFACT_TRIGGERS = [
    "pinout", "datasheet", "schematic", "wiring diagram", "part number",
    "spec sheet", "service manual", "torque spec", "where is my", "which bin",
    "do i have a", "in my inventory", "gpio map", "register map",
    "fuse box", "pin number", "wiring color",
    # Answers that ARE a part number in a manual — route to the document.
    # Jetting is the canonical invented-answer trap: plausible, specific, wrong.
    "main jet", "jet size", "jet kit", "high altitude kit", "oil capacity",
    "spark plug gap", "plug gap", "valve clearance", "oil type for",
]
# Things that look like part numbers: SX1262, NRF52840, 74HC14, LM7805...
PART_NUMBER_RE = re.compile(r"\b[A-Za-z]{2,4}\d{2,6}[A-Za-z0-9]*\b")

# ---------------- corpus-flavored questions (worth RAG over the library) -----
RAG_TRIGGERS = [
    "according to", "wikem", "wikipedia", "ifixit", "field manual",
    "my notes", "my documents", "the manifest", "hesperian", "appropedia",
    "how do i repair", "how to fix", "steps to", "procedure for",
    "wikihow", "gutenberg", "survivor library", "how do i make",
    "how to build",
]


# ---------------- skills: procedures for a class of question -----------------
# A skill NEVER changes a route — it rides along with one, telling the
# answering system what to ask first and which file to open. See
# 02_CORPORA/skills/README.md.
# ORDER MATTERS: first match wins, so the most specific vocabularies come
# first and the general "nothing works" skill goes last.
SKILL_TRIGGERS = {
    "wound-triage": [
        "wound", "laceration", "stitches", "suture", "deep cut", "cut on my",
        "cut myself", "gash", "puncture", "bandage", "road rash",
        "bleeding", "wont stop bleeding", "infected cut", "burn on",
        "burned my", "scald",
    ],
    "water-source-decision": [
        "safe to drink", "drinkable", "potable", "purify", "treat water",
        "water treatment", "creek water", "stream water", "well water",
        "rainwater", "snowmelt", "boil water", "water is cloudy",
        "is this water", "filter water",
    ],
    "generator-service": [
        "generator", "genset", "eu2000", "eu2200", "honda eu", "predator 3500",
        "champion dual fuel", "inverter generator", "pull start", "recoil start",
        "main jet", "jet kit", "high altitude kit", "carburetor", "carb bowl",
        "pilot jet", "spark plug", "gas cap vent", "backfeed",
        "carbon monoxide",
        # fuel-storage questions (first-flight harvest: the skill's ethanol
        # shelf-life doctrine covers them; the dumb matcher didn't)
        "stale fuel", "old gas", "gas go bad", "gas goes bad", "fuel storage",
        "fuel stabilizer", "gasoline stable", "gasoline last", "ethanol fuel",
    ],
    "radio-wont-transmit": [
        "meshtastic", "lora", "sx1262", "heltec", "t-deck", "tdeck",
        "wont transmit", "will not transmit", "no nodes", "mesh is down",
        "cant see my node", "oracle not replying", "modem preset",
    ],
    "vehicle-wont-start": [
        "wont crank", "no crank", "cranks but", "starter motor", "jump start",
        "check engine", "immobiliser", "immobilizer", "my truck", "my car",
        "alternator", "engine dies", "stalls",
    ],
    "battery-health": [
        "wont hold charge", "will not hold charge", "lost capacity",
        "half capacity", "sulfation", "sulfated", "equalize", "equalization",
        "desulfator", "specific gravity", "hydrometer", "distilled water",
        "dies overnight", "battery is dying", "load test", "dead cell",
        "flooded battery", "agm battery", "battery age",
    ],
    "charging-triage": [
        "not charging", "wont charge", "will not charge", "no charge current",
        "mppt error", "err 33", "low temp cutoff", "bms cutoff",
        "state of charge", "bulk absorption", "not making power",
    ],
    "solar-commissioning": [
        "wire my panels", "hook up panels", "series or parallel", "mc4",
        "mppt", "pwm", "charge controller", "y branch", "combiner",
        "string my panels", "commission", "solar panel",
    ],
    "node-dark-triage": [
        "node is down", "node is dark", "wont boot", "will not boot",
        "no lights", "cant ssh", "boot loop", "kiwix is down",
        "nothing responds", "unreachable", "undervolt", "pi wont",
    ],
}


def match_skill(question: str) -> str | None:
    """First skill whose triggers appear in the question, or None."""
    q = question.lower()
    for name, triggers in SKILL_TRIGGERS.items():
        if any(t in q for t in triggers):
            return name
    return None


@dataclass
class Decision:
    route: str          # RETRIEVAL_ONLY | ARTIFACT_LOOKUP | RAG | GENERAL_MODEL
    domain: str | None  # which safety domain fired, if any
    instruction: str    # what the answering system must do
    skill: str | None = None   # procedure file to load (02_CORPORA/skills/)


def _fence(domain: str) -> Decision:
    return Decision(
        "RETRIEVAL_ONLY", domain,
        f"[{domain}] Show the authoritative source VERBATIM with "
        f"citation (source, edition, page). No generation, no "
        f"interpolation, no unit conversion. If no source is in the "
        f"archive, say so — 'not in the library' is a safe answer; "
        f"an invented one is not.")


def route(question: str) -> Decision:
    """Classify, then attach any matching skill. The skill is ADDITIVE: it
    cannot change the route, so a fenced question stays fenced and merely
    gains a checklist for what to ask before retrieving."""
    decision = _classify(question)
    decision.skill = match_skill(question)
    return decision


def _classify(question: str) -> Decision:
    q = question.lower()

    # 1) Safety fence first. Always first.
    for domain, keywords in RETRIEVAL_ONLY_DOMAINS.items():
        if any(k in q for k in keywords):
            return _fence(domain)
    # 1b) Pattern fences.
    if CALIBER_RE.search(q) and RELOAD_CONTEXT_RE.search(q):
        return _fence("reloading")
    if VOC_RE.search(q):
        return _fence("electrical_sizing")

    # 2) Hardware identity questions -> files, not prose.
    if any(t in q for t in ARTIFACT_TRIGGERS) or PART_NUMBER_RE.search(question):
        return Decision(
            "ARTIFACT_LOOKUP", None,
            "Search INVENTORY.csv and the datasheet tree. Answer with a "
            "filename + page number (and bin location if physical). The "
            "model may summarize AFTER the file is on screen, labeled "
            "MODEL INFERENCE.")

    # 3) Library questions -> RAG with citations.
    if any(t in q for t in RAG_TRIGGERS):
        return Decision(
            "RAG", None,
            "Retrieve from the prose corpus, answer from the retrieved "
            "chunks, cite each. Label any model synthesis as "
            "INTERPRETATION.")

    # 4) Everything else -> the model, honestly labeled.
    return Decision(
        "GENERAL_MODEL", None,
        "Answer with the local model. Prefix MODEL INFERENCE. If the topic "
        "drifts into a safety domain mid-answer, stop and re-route.")


# ------------------------------ self-test ------------------------------------
# Auditable in one screen: these are the routes the group agreed on. If an
# edit to the lists above breaks one of these, --test fails loudly.
SELF_TEST = [
    ("how much Varget for a 168gr .308 load?",            "RETRIEVAL_ONLY"),
    ("what's a safe 9mm load with titegroup?",            "RETRIEVAL_ONLY"),
    ("pressure canning green beans at 6,000 ft?",         "RETRIEVAL_ONLY"),
    ("what fuse size for the 1100W inverter feed?",       "RETRIEVAL_ONLY"),
    ("pediatric ibuprofen dose?",                         "RETRIEVAL_ONLY"),
    ("how much bleach per gallon to purify water?",       "RETRIEVAL_ONLY"),
    ("snow load for a 12 ft rafter?",                     "RETRIEVAL_ONLY"),
    ("what is the cold-weather Voc of two panels in series?", "RETRIEVAL_ONLY"),
    ("can I run the generator in the garage with the door open?",
                                                          "RETRIEVAL_ONLY"),
    ("how do I backfeed my house with a generator?",      "RETRIEVAL_ONLY"),
    ("what's the pinout of the sx1262?",                  "ARTIFACT_LOOKUP"),
    ("do i have a spare LM7805 in my inventory?",         "ARTIFACT_LOOKUP"),
    ("how do i repair a jacket zipper?",                  "RAG"),
    ("how to fix a leaky faucet?",                        "RAG"),
    ("tell me a joke about capacitors",                   "GENERAL_MODEL"),
    ("what's the best 9mm holster material?",             "GENERAL_MODEL"),
    ("is this mushroom edible?",                          "RETRIEVAL_ONLY"),
    ("can I eat these wild berries?",                     "RETRIEVAL_ONLY"),
    ("found morels on the hike, how do i cook them?",     "RETRIEVAL_ONLY"),
    # identification WITHOUT ingestion stays open — naming a flower is safe
    ("what species is this purple five-petal flower?",    "GENERAL_MODEL"),
]


# Skills ride along with a route; these pin both.
SKILL_TEST = [
    ("what oil does my honda eu2000i take?",  "generator-service", "ARTIFACT_LOOKUP"),
    ("what main jet for 10,000 ft?",          "generator-service", "ARTIFACT_LOOKUP"),
    ("can I run the generator in the garage?", "generator-service", "RETRIEVAL_ONLY"),
    ("why won't my predator 3500 start?",     "generator-service", "GENERAL_MODEL"),
    ("should I wire my panels in series or parallel?",
                                              "solar-commissioning", "RETRIEVAL_ONLY"),
    ("my battery is not charging in the cold", "charging-triage",   "GENERAL_MODEL"),
    ("my meshtastic node wont transmit",      "radio-wont-transmit", "GENERAL_MODEL"),
    ("the node is dark, no lights at all",    "node-dark-triage",  "GENERAL_MODEL"),
    ("my truck cranks but wont fire",         "vehicle-wont-start", "GENERAL_MODEL"),
    ("is creek water safe to drink?",         "water-source-decision", "RETRIEVAL_ONLY"),
    ("deep cut on my hand, does it need stitches?",
                                              "wound-triage",      "RETRIEVAL_ONLY"),
    ("my flooded batteries only hold half capacity",
                                              "battery-health",    "GENERAL_MODEL"),
    ("how long is gasoline stable for?",       "generator-service", "GENERAL_MODEL"),
    ("what equalization voltage for a flooded battery?",
                                              "battery-health",    "RETRIEVAL_ONLY"),
    ("how do i repair a jacket zipper?",      None,                "RAG"),
]


def run_self_test() -> int:
    failures = 0
    for question, want in SELF_TEST:
        got = route(question).route
        status = "PASS" if got == want else "FAIL"
        if got != want:
            failures += 1
        print(f"{status}  {got:16} (want {want:16})  {question}")

    print("-" * 50)
    for question, want_skill, want_route in SKILL_TEST:
        d = route(question)
        ok = d.skill == want_skill and d.route == want_route
        if not ok:
            failures += 1
        print(f"{'PASS' if ok else 'FAIL'}  skill={str(d.skill):18} "
              f"{d.route:16}  {question}")

    print("-" * 50)
    print("ALL PASS" if failures == 0 else f"{failures} FAILURE(S)")
    return 0 if failures == 0 else 1


def main():
    if len(sys.argv) >= 2 and sys.argv[1] == "--test":
        sys.exit(run_self_test())
    if len(sys.argv) < 2:
        print('Usage: python safety_router.py "your question here"')
        print('       python safety_router.py --test')
        sys.exit(1)
    q = " ".join(sys.argv[1:])
    d = route(q)
    print(f"QUESTION : {q}")
    print(f"ROUTE    : {d.route}" + (f"  (domain: {d.domain})" if d.domain else ""))
    if d.skill:
        print(f"SKILL    : {d.skill}  "
              f"(02_CORPORA/skills/{d.skill}.md — ask its questions FIRST)")
    print(f"POLICY   : {d.instruction}")


if __name__ == "__main__":
    main()
