---
name: water-source-decision
description: >
  Fires on drinking-water questions — is this source safe, what treatment does
  it need, which method for which hazard. POINTER ONLY. This skill decides
  which authoritative table to open; it never states a dose, a contact time,
  or a boil duration.
fires_on: [is this water safe, drinkable, potable, treat water, purify,
           filter water, creek water, stream water, well water, rainwater,
           snowmelt, boil water, water is cloudy, water treatment]
ask_first:
  - "What is the source? Surface water, a well, rain catchment, snowmelt, or a
     municipal supply that has failed? The hazards are different for each."
  - "Is it cloudy, coloured, or does it smell? Turbidity has to be dealt with
     BEFORE disinfection, and that changes the order of operations."
  - "What is upstream? Mining, agriculture, industry, roads, livestock,
     housing? In Colorado, historic mine drainage is a real and specific
     hazard, and no amount of boiling touches it."
  - "How much water, for how long, and who is drinking it — infants, pregnant
     people, and the immunocompromised change the answer."
open_these:
  - 02_CORPORA/pdfs/medical/   (WHO and CDC water treatment guidance)
  - Kiwix - WHO/CDC water treatment articles
  - "?med water treatment   — retrieval-only path, no model in the loop"
never_generate:
  - bleach or chlorine quantities, any ppm figure
  - contact times, boil durations, or altitude adjustments
  - filter pore-size claims or "this filter handles X"
  - any statement that a given source is safe to drink
fence: retrieval_only   # this entire skill sits inside a fenced domain
human_verified: false
---

## What this skill is for

Not for answering the question. For working out **which authoritative table
answers it**, and for asking the things that change which table applies.

Everything numeric here — doses, times, temperatures — comes verbatim out of
WHO, CDC, or EPA guidance, with the source named. A treatment number invented
by a language model is exactly the kind of confident, plausible, wrong answer
that hurts someone, and it is why this domain is fenced in code.

## Matching hazard to method — categorical only

These are category facts, not doses. They determine which table you need:

- **Biological hazards** (bacteria, viruses, protozoa) are what boiling and
  chemical disinfection address. Protozoal cysts are the stubborn ones and are
  the usual reason filtration enters the picture.
- **Chemical contamination — heavy metals, mine drainage, fuel, solvents,
  agricultural chemicals, salt — is NOT removed by boiling, and boiling makes
  concentration slightly worse** as water evaporates. Disinfection and
  contamination are different problems, and conflating them is the most
  dangerous mistake in this whole area.
- **Turbidity must be handled first.** Suspended sediment shields organisms
  from both chemical disinfectant and UV, so cloudy water gets settled or
  filtered *before* it is disinfected, not after. This is sequence, not dosage,
  which is why it can be stated here.
- **Altitude changes boiling.** Water boils cooler at 6,000 ft than at sea
  level, so published guidance carries altitude adjustments. Retrieve the
  adjusted figure; do not let anyone reason it out on the spot.

## The order of operations

1. Identify the source and what is upstream of it.
2. Deal with turbidity: settle, pre-filter, or both.
3. Choose the disinfection method that matches the biological hazard —
   **from the table**.
4. Apply it for the published contact time — **from the table**.
5. Store it in a way that does not re-contaminate it — also published.

Steps 3 and 4 are the retrieval. This skill gets you to them with the right
question answered; it does not supply their contents.

## When the honest answer is "do not drink this"

If the source is downstream of mine workings, an industrial site, or a
significant chemical spill, no field treatment in this archive makes it safe.
The correct output is a source change, not a procedure. Saying "not in the
library" is a safe answer here. Inventing one is not.
