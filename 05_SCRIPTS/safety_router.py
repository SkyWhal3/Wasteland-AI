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

Or import it:
    from safety_router import route
    decision = route(question)   # -> Decision(route, domain, instruction)

Extend the keyword lists as you find gaps — misrouting toward MORE caution is
free; misrouting toward less is the failure mode.
"""

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
    ],
    "reloading": [
        "grains of", "powder charge", "load data", "reload", "handload",
        "varget", "h4350", "imr", "hodgdon", "unique", "bullseye", "primer",
        "brass", "case capacity", "seating depth", "headspace", "max load",
        "starting load", "gr.", "grain load",
    ],
    "canning": [
        "canning", "pressure can", "water bath", "botulism", "headspace jar",
        "processing time", "pint jar", "quart jar", "preserve at altitude",
        "psi for", "canner",
    ],
    "electrical_sizing": [
        "ampacity", "wire gauge for", "awg for", "fuse size", "fuse for",
        "breaker size", "busbar", "wire size", "how many amps can",
        "charge voltage for", "absorption voltage", "float voltage",
        "series or parallel panel", "string voltage", "voc",
    ],
    "structural": [
        "load bearing", "span for", "joist", "beam size", "rafter",
        "rigging", "working load limit", "wll", "sling angle", "anchor for",
        "pressure vessel", "compressed gas", "crane", "hoist",
    ],
    "water_dosing": [
        "bleach per", "chlorine dose", "ppm chlorine", "purify water",
        "water treatment dose", "iodine tablets", "contact time",
        "calcium hypochlorite",
    ],
}

# ---------------- artifact lookups (layer 0/3: files, not prose) -------------
ARTIFACT_TRIGGERS = [
    "pinout", "datasheet", "schematic", "wiring diagram", "part number",
    "spec sheet", "service manual", "torque spec", "where is my", "which bin",
    "do i have a", "in my inventory", "gpio map", "register map",
]
# Things that look like part numbers: SX1262, NRF52840, 74HC14, LM7805...
PART_NUMBER_RE = re.compile(r"\b[A-Za-z]{2,4}\d{2,6}[A-Za-z0-9]*\b")

# ---------------- corpus-flavored questions (worth RAG over the library) -----
RAG_TRIGGERS = [
    "according to", "wikem", "wikipedia", "ifixit", "field manual",
    "my notes", "my documents", "the manifest", "hesperian", "appropedia",
    "how do i repair", "how to fix", "steps to", "procedure for",
]


@dataclass
class Decision:
    route: str          # RETRIEVAL_ONLY | ARTIFACT_LOOKUP | RAG | GENERAL_MODEL
    domain: str | None  # which safety domain fired, if any
    instruction: str    # what the answering system must do


def route(question: str) -> Decision:
    q = question.lower()

    # 1) Safety fence first. Always first.
    for domain, keywords in RETRIEVAL_ONLY_DOMAINS.items():
        if any(k in q for k in keywords):
            return Decision(
                "RETRIEVAL_ONLY", domain,
                f"[{domain}] Show the authoritative source VERBATIM with "
                f"citation (source, edition, page). No generation, no "
                f"interpolation, no unit conversion. If no source is in the "
                f"archive, say so — 'not in the library' is a safe answer; "
                f"an invented one is not.")

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


def main():
    if len(sys.argv) < 2:
        print('Usage: python safety_router.py "your question here"')
        sys.exit(1)
    q = " ".join(sys.argv[1:])
    d = route(q)
    print(f"QUESTION : {q}")
    print(f"ROUTE    : {d.route}" + (f"  (domain: {d.domain})" if d.domain else ""))
    print(f"POLICY   : {d.instruction}")


if __name__ == "__main__":
    main()
