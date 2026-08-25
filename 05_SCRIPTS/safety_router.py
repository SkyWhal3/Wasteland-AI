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
    decision = route(question)   # -> Decision(route, domain, instruction)

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
        "series or parallel panel", "string voltage", "voltage drop",
        "wire run", "conductor size", "panel string", "parallel strings",
        "battery cable", "inverter cable", "charge current", "c-rate",
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


@dataclass
class Decision:
    route: str          # RETRIEVAL_ONLY | ARTIFACT_LOOKUP | RAG | GENERAL_MODEL
    domain: str | None  # which safety domain fired, if any
    instruction: str    # what the answering system must do


def _fence(domain: str) -> Decision:
    return Decision(
        "RETRIEVAL_ONLY", domain,
        f"[{domain}] Show the authoritative source VERBATIM with "
        f"citation (source, edition, page). No generation, no "
        f"interpolation, no unit conversion. If no source is in the "
        f"archive, say so — 'not in the library' is a safe answer; "
        f"an invented one is not.")


def route(question: str) -> Decision:
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
    ("what's the pinout of the sx1262?",                  "ARTIFACT_LOOKUP"),
    ("do i have a spare LM7805 in my inventory?",         "ARTIFACT_LOOKUP"),
    ("how do i repair a jacket zipper?",                  "RAG"),
    ("how to fix a leaky faucet?",                        "RAG"),
    ("tell me a joke about capacitors",                   "GENERAL_MODEL"),
    ("what's the best 9mm holster material?",             "GENERAL_MODEL"),
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
    print(f"POLICY   : {d.instruction}")


if __name__ == "__main__":
    main()
