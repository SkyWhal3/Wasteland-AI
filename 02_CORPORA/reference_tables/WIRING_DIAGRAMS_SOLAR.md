# SOLAR + BATTERY WIRING — SERIES vs PARALLEL, WITH DIAGRAMS

```
PROVENANCE
  source:         MANIFEST v3 §2.2 / §2.6 (worked examples + margin rules),
                  panel datasheet values quoted there, standard DC circuit law
  drawn by:       claude-fable-5, 2026-08-25
  human_verified: NO — a person with a multimeter must check this against
                  their actual hardware before wiring anything
  serving rule:   this file is RETRIEVAL content (manifest §9.4 electrical).
                  The AI may DISPLAY it. It may not "adapt" the numbers.
```

**Why this file exists:** a small model asked to *draw* a wiring diagram will
draw a confident wrong one. So the diagrams are pre-drawn and verified once,
and the model's only job is to *find and show* this file. If your exact case
isn't here, the answer is "not in the library" — add the case, don't improvise.

---

## 1. The one-sentence physics

- **SERIES** (chain them + to −): **voltages ADD, current stays the same.**
- **PARALLEL** (all + together, all − together): **currents ADD, voltage stays the same.**

Same energy either way — you're choosing *what number gets big*, and the wire,
fuses, and controller limits all care which one it is.

| | 2 panels SERIES | 2 panels PARALLEL |
|---|---|---|
| Voltage | 2× one panel | same as one panel |
| Current | same as one panel | 2× one panel |
| Wire thickness needed | thinner (low amps) | thicker (double amps) |
| Wakes controller in dim light | earlier (high V) | later |
| Danger to controller | **over-VOLTAGE in cold** | over-current (usually just clips) |
| One panel shaded | drags the whole string | other panel keeps working |

**The killer rule (manifest §2.2):** exceeding the controller's **wattage** is
harmless clipping. Exceeding its **VOLTAGE** kills it dead, not under warranty.
Cold panels make MORE voltage — check Voc at your coldest morning, not at 25 °C:

```
Voc_cold = Voc_datasheet × [1 + BetaVoc × (T_min − 25)]
(BetaVoc unknown? use −0.3%/°C:  ×1.165 at −30 °C,  ×1.195 at −40 °C)
DESIGN RULE: cold Voc stays under 80% of the controller's max. 100 V
controller → stay under 80 V. Margin is cheap; controllers aren't.
```

---

## 2. TWO PANELS IN SERIES (voltage adds)

One jumper: panel A's MINUS into panel B's PLUS. The two outer leads go to
the controller (through a disconnect/breaker — see §6).

```
      [ PANEL A ]                 [ PANEL B ]
       (+)   (−)                   (+)   (−)
        │     │                     │     │
        │     └──────► plugs into ──┘     │
        │           (series jumper:       │
        │            A− to B+)            │
        ▼                                 ▼
   ARRAY (+) ──► to controller PV+   ARRAY (−) ──► to controller PV−
```

Example (Renogy 200W, Voc 29.6 V, Imp 8 A): two in series
= **59.2 V at 8 A**. Cold at −30 °C ≈ **69 V** → passes the 80 V rule on a
100 V controller. This is the manifest's approved config for that panel.

---

## 3. TWO PANELS IN PARALLEL (current adds)

No panel-to-panel jumper. Instead, **MC4 Y-branch connectors** join like to
like: both PLUSES into one Y, both MINUSES into the other Y.

```
      [ PANEL A ]                 [ PANEL B ]
       (+)   (−)                   (+)   (−)
        │     │                     │     │
        │     │      ┌──────────────┘     │
        └─────┼──┐   │   ┌────────────────┘
              │  │   │   │
              │ [Y+ branch]        [Y− branch]
              │   (2-to-1)          (2-to-1)
              │      │                 │
              ▼      ▼                 ▼
          ARRAY (+) ──► PV+       ARRAY (−) ──► PV−
```

Example (Lumera 220W "24V" config, Voc 43.72 V, Imp 6.12 A): two in
parallel = **43.72 V at ~12.2 A**, cold ≈ 51 V → safe with huge margin.
(In SERIES these same panels hit ~102 V cold = **dead 100 V controller** —
that's why the manifest says parallel for this panel.)

---

## 4. FOUR PANELS: 2-SERIES-2-PARALLEL (2S2P) — and a warning

**⚠ The internet default you'll see pictured everywhere — all four panels
daisy-chained in ONE series string — is a controller-killer at this size.**
Four Renogy 200s in one string: 4 × 29.6 = **118 V at 25 °C, ~138 V cold**,
against a 100 V absolute limit. That diagram is fine for someone's 600 V
string inverter; it is fatal to a 100 V MPPT. Check voltage FIRST, always.

The right shape for 4 × Renogy 200W on a 100 V controller: two series PAIRS,
paralleled. Voltage of a pair, current of two pairs: **59.2 V at 16 A**
(~69 V cold — passes).

```
  STRING 1:   [ A ](+)──(−)[ B ]     string1(+)= A+   string1(−)= B−
                    series jumper

  STRING 2:   [ C ](+)──(−)[ D ]     string2(+)= C+   string2(−)= D−
                    series jumper

  string1(+) ─┐                    string1(−) ─┐
              ├─[Y+ branch]─► PV+              ├─[Y− branch]─► PV−
  string2(+) ─┘                    string2(−) ─┘
```

Rules that ride along (manifest §2.2/§2.6):
- **Both strings identical** — same panel model, same count, same tilt. Never
  mix models/configs on one MPPT; a mismatched panel drags the array off its
  power point and you lose more than you gained.
- **String fuses:** not needed at 2 parallel strings; **required at 3+**,
  rated per the panel label's "max series fuse."

---

## 5. BATTERIES

Same physics, higher stakes (a battery bank can deliver thousands of amps
into a mistake).

**PARALLEL — stay 12 V, add capacity (the usual choice here):**

```
   MAIN (+) ─────┐                              ┌───── MAIN (−)
                 │                              │
              (+)│      jumper (+ to +)         │(−)
             [ BATTERY 1 ]────────────[ BATTERY 2 ]
                    (−)────────────(+)   ← NO! see below
```

Correct parallel is **+ to + and − to −**, and you take the main leads
**diagonally** — MAIN+ from battery 1, MAIN− from battery 2 — so both
batteries share the work evenly:

```
   MAIN (+)                                   MAIN (−)
      │                                          │
   (+)│         (+ jumper)          (+)          │
  [ BATTERY 1 ]═══════════════[ BATTERY 2 ]      │
   (−)          (− jumper)          (−)──────────┘
    ╚═══════════════════════════════╝
   Result: still 12 V, twice the amp-hours.
```

**SERIES — 12 V + 12 V = 24 V (only if you chose the 24 V fork, §2.1):**

```
   MAIN (+) ── (+)[ BATTERY 1 ](−) ──jumper── (+)[ BATTERY 2 ](−) ── MAIN (−)
   Result: 24 V, same amp-hours. EVERY 12 V device now needs a converter.
```

Battery rules:
- **Identical batteries only** — same chemistry, same capacity, same age.
  An old battery in parallel with a new one quietly eats the new one.
- **Never series-connect batteries already paralleled to different systems.**
- **Fuse at the battery post** (§2.6): the inverter feed gets a 150 A ANL or
  Class T within ~7 inches of the positive post. An unfused battery short
  doesn't trip anything — it welds, then it burns.

---

## 6. ORDER OF OPERATIONS (Victron MPPT — this sequence matters)

1. Wiring happens with the array DISCONNECTED (breaker open / panels covered
   or face-down). MC4s under load arc and pit.
2. **Battery to controller FIRST.** The controller reads battery voltage at
   power-up to auto-detect 12 V vs 24 V. PV-first can mis-detect = wrong
   charge voltages.
3. Multimeter check at the PV leads BEFORE landing them: is the voltage what
   §2–§4 predicts? Is the polarity right? (Backwards polarity is the #1
   first-build mistake and some controllers don't forgive it.)
4. Then close the PV disconnect.
5. Removal is the reverse: PV off first, battery last.

---

## 7. IF YOUR CASE ISN'T ON THIS PAGE

Don't scale these pictures in your head at 2 a.m. Add your case to this file
with the math shown, have someone check it, then wire it. "Not in the
library" is a safe answer; an invented diagram is not.
