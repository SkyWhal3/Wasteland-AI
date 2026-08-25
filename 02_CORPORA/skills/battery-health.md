---
name: battery-health
description: >
  Fires when a battery has lost capacity, will not hold charge, dies overnight,
  or someone is asking whether a tired bank can be recovered. Covers flooded
  lead-acid, AGM and gel, and LiFePO4 — which fail in completely different
  ways and must never be treated with each other's procedures.
fires_on: [wont hold charge, will not hold charge, lost capacity, half
           capacity, battery is dying, dead battery, sulfation, sulfated,
           equalize, equalization, desulfator, specific gravity, hydrometer,
           distilled water, battery dies overnight, old battery, load test]
ask_first:
  - "WHICH CHEMISTRY? Flooded lead-acid (has caps you can open and add water
     to), sealed AGM or gel, or lithium/LiFePO4? Every answer below changes
     with this, and applying the wrong one destroys the battery or worse."
  - "How old, and how has it lived? Deep discharges, months sitting flat, heat,
     freezing? Damage is usually history, not a defect."
  - "Resting voltage — no charger, no load, at least a few hours settled. And
     for flooded: specific gravity per cell with a hydrometer, if you have one."
  - "Was it ever actually load-tested, or is 'half capacity' an impression?"
open_these:
  - 02_CORPORA/datasheets/power/<battery>_manual.pdf   (the maker's own charge
    and equalization spec is the ONLY acceptable source for those numbers)
  - 00_DOCS/BUILD_GUIDE.md   (battery economics; lifetime cost per kWh)
  - 02_CORPORA/datasheets/power/victron_bluesolar_mppt_100-30_manual_rev12.pdf
    (charge profiles, if the charging side is suspect)
never_generate:
  - equalization voltages, currents, or durations
  - absorption, float, or charge-cutoff setpoints
  - specific-gravity thresholds
  - temperature compensation figures
  - any claim that a chemical additive or "desulfator" device will work
fence: retrieval_only   # charge parameters are a fenced domain
human_verified: false
---

## Chemistry first — nothing below is portable between types

Ask the chemistry question and get a real answer before saying anything else.
An equalization charge is routine maintenance on a flooded battery, and it
will **damage an AGM and can vent or ignite a lithium pack**. The single most
dangerous thing this skill can do is let a procedure cross chemistries.

## Flooded lead-acid — the classic case

Symptom pattern: a few months to a few years old, water has been topped up,
and it now delivers perhaps half its rated capacity.

**The likely diagnosis is sulfation from chronic undercharging or from sitting
discharged** — not a manufacturing fault. Lead sulfate forms every time the
battery discharges and normally converts back on charge; left discharged, it
hardens into crystals that no longer convert, and the plate area is simply
gone. A solar system that never quite reaches full absorption produces this
reliably, which makes it a *charging* problem wearing a *battery* costume.

What actually establishes the diagnosis:

1. **Specific gravity, per cell, with a hydrometer.** This is the real
   instrument for flooded batteries — voltage is a rumour by comparison.
   Compare cells against each other: **one cell far below the others is a
   dead cell**, and no procedure recovers that. Uniformly low across all
   cells points at state of charge or general sulfation instead.
2. **A real load test**, not an impression. "Seems weak" and "delivers 50% of
   rated amp-hours under a measured load" are different claims.
3. **Water level history.** Plates that were ever exposed to air are
   permanently damaged in the exposed area. Topping up afterwards does not
   undo it.

**Controlled equalization** — a deliberate, monitored overcharge — is the
recognised recovery attempt, and it applies **only to flooded batteries that
still take water**. The voltage, current, duration and interval come from the
**battery manufacturer's own documentation**, retrieved and shown. They are
not general knowledge and this system will not produce them.

While equalizing: it vents hydrogen, so ventilate and keep ignition sources
away; it consumes water, so check levels after; it runs the battery hot, so
watch temperature. Wear eye protection — the electrolyte is sulphuric acid.

**Be honest about the odds.** Equalization sometimes recovers a mildly
sulfated bank. It does not resurrect one that has sat flat for months, and it
does nothing for a shorted cell. On a battery only a few months old, the more
useful question is *what in the charging setup did this*, because a
replacement will die the same way.

## AGM and gel

Sealed. You cannot add water, and **most manufacturers prohibit equalization
outright** — check that battery's own manual. Recovery options are essentially
"charge it correctly and see," and the same undercharging cause applies. The
diagnosis is a load test and the answer is usually replacement.

## LiFePO4

Fails differently and almost never from sulfation. Capacity loss is usually
cycle age, heat, or **the BMS protecting itself** rather than the cells being
finished:

- A pack reading zero volts at its terminals is often a BMS that has cut off,
  not dead cells. Some require a specific reset or a wake-up charge.
- **A lithium bank refuses charge below freezing.** That reads as "won't hold
  charge" all winter and is correct behaviour — see `charging-triage`.
- Cell imbalance shows as one cell hitting its limit early and tripping the
  BMS while the pack is nowhere near full.

Never equalize lithium. Never apply a lead-acid charge profile to it. If your
charger or controller is set to a lead-acid profile, that alone can explain
the symptoms.

## Additives and "desulfator" gadgets

Treat every claim with suspicion, and note that this system will not endorse
one. If somebody wants to try, that is their call — but it goes in the build
log with a before-and-after load test, so the result is evidence rather than
a story.

## The economics, before you spend a weekend

The build guide's numbers matter here: lifetime delivered energy per dollar
puts budget LiFePO4 far ahead of anything you are likely to recover from a
tired lead bank. Recovery is worth attempting when the battery is free,
already on site, or the grid is gone. It is rarely worth it as a purchase
decision — and **salvaged lead has a genuine role as a shallow-cycled buffer**
even at reduced capacity, which is often the better use of a bank at 50%.
