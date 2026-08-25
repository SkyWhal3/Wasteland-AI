---
question: Should I wire my solar panels in series or parallel? What's the difference?
answer_model: claude-fable-5
date: 2026-08-25
domain: electrical_sizing
serve_via: retrieval_only
human_verified: false
sources: [02_CORPORA/reference_tables/WIRING_DIAGRAMS_SOLAR.md, 00_DOCS/MANIFEST.md §2.2]
---

SERIES (chain + to −): voltages ADD, current stays the same.
PARALLEL (+ to +, − to −): currents ADD, voltage stays the same.

The decision is made by ONE number: the string's cold-weather open-circuit
voltage (Voc) versus the charge controller's absolute maximum. Cold panels
make MORE voltage. Exceeding controller wattage just clips harmlessly;
exceeding controller VOLTAGE kills it permanently.

→ OPEN: `02_CORPORA/reference_tables/WIRING_DIAGRAMS_SOLAR.md`
   It has the diagrams (2S, 2P, 2S2P, batteries), the cold-Voc formula, the
   80% margin rule, and this project's already-reviewed worked examples:
   - Renogy 200W ×2 SERIES = 59.2 V, ~69 V cold → OK on a 100 V controller
   - Lumera 220W(24V) ×2 SERIES = ~102 V cold → NEVER on a 100 V controller
   - Lumera 220W(24V) ×2 PARALLEL = ~51 V cold → correct config
   - 4× Renogy on 100 V controller → 2S2P, never one 4-panel string

Do not adapt these numbers to a different panel. Run the formula against
YOUR panel's datasheet, show the math, and have a person check it.
