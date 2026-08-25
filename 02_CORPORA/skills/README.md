# skills — procedures for handling a class of question

A skill is **not knowledge.** The corpus holds knowledge. A skill holds the
*procedure for answering*: when it applies, **what to ask the human first**,
which files to open, and what must never be generated.

This is the layer that gives a small model field judgment it cannot reason its
way to on its own. A 4 B model will never spontaneously think *"I should ask
what altitude they're at"* — but it can retrieve a file that tells it to.

## Why this exists (the failure it prevents)

Ask any model "what oil does a Honda EU2000i take?" and it answers `10W-30`,
confidently, and it's right — so you learn to trust it. Then ask "what main jet
for 10,000 ft?" and it invents a part number with **exactly the same
confidence**. A bigger model does not fix this; it makes the invented part
number more plausible. Model size buys reasoning, never specificity.

The fix isn't a smarter model. It's a checklist that makes the model ask which
generator you actually have, and then open that manual.

## Format

One skill per file, `kebab-case-name.md`:

```markdown
---
name: generator-service
description: >
  One or two lines describing WHEN this fires. This is the text that gets
  matched/embedded — write it as the situations it covers, not as a title.
fires_on: [short, keyword, list, for, the, dumb, matcher]
ask_first:
  - The disambiguating questions, in priority order.
  - "Which exact model?" is almost always first.
open_these:
  - concrete/paths/in/the/corpus.pdf
  - "?find <part>  — the Layer 0 inventory lookup"
never_generate: [the specific things a model must not invent here]
fence: none | retrieval_only   # does §9 apply to any part of this?
human_verified: false
---

Body: the ordered procedure. Most-common-cause first. Keep it short enough
that a small model can hold it in context alongside the actual question.
```

## THE RULES

1. **Procedure in the skill; numbers in the manual.** A skill may say "check
   the oil spec on page 3 of the manual." It may not say what the oil spec is.
   The moment a skill starts carrying values, it becomes a second, unversioned,
   un-checksummed copy of the corpus that silently goes stale.
2. **In the six fenced domains (§9): questions and pointers ONLY, never
   content.** A wound-triage skill says "ask whether bleeding is controlled,
   then open WikEM/Hemorrhage." It never contains a treatment. A skill that
   smuggled generated medical text past the fence would be worse than no skill.
3. **The safety router runs FIRST, always.** A skill augments a routing
   decision; it can never change one. Fenced stays fenced.
4. **Categorical prohibitions are allowed; computed values are not.** "Never
   run a generator indoors, including a garage with the door open" is a bright
   line that cannot be wrong. "Keep it N feet away" is a number — that comes
   from the source.
5. **`human_verified: false` until a person checks it against reality**, same
   as `seed_qa/`.

## Honest limitation — read this before trusting skills

**The router is enforced in code. Skills are enforced by instruction.**

That's a real difference in strength and this project doesn't blur it. The six
fenced domains are protected by `safety_router.py`, which no prompt can talk
its way around. A skill's `never_generate` list is a much weaker guarantee — it
makes a cooperative model behave better; it does not make bad output
impossible.

So: anything that can kill someone belongs in the **fence**, not in a skill's
`never_generate`. Skills are for the large middle ground where a wrong answer
is expensive, embarrassing, or sends you down a two-hour rabbit hole — not
lethal.

## How they get used

`safety_router.py` matches a skill by keyword and returns its name alongside
the routing decision (`Decision.skill`). The answering system loads that one
file, follows `ask_first` before answering, and opens what `open_these` names.
For RAG setups, ingest this folder as its own collection so `description`
matching does the same job semantically.

## Roster

| Skill | Covers | Status |
|---|---|---|
| `generator-service` | Portable generators: won't-start triage, oil, altitude/jetting, fuel, CO, backfeed | written |
| `solar-commissioning` | Wiring order, polarity check, series/parallel, fuse placement, MPPT vs PWM | planned |
| `node-dark-triage` | The knowledge node is offline — working backwards from no lights | planned |
| `charging-triage` | Battery isn't charging; reading the bands and the MPPT's own error codes | planned |
| `radio-wont-transmit` | LoRa node silent: antenna, PA rail, region/preset, config | planned |
| `vehicle-wont-start` | The obvious checks, then the FSM page pointer | planned |
| `water-source-decision` | What's the source → which treatment applies (pointer-only endpoint) | planned |
| `wound-triage` | What to ask, then the WikEM article (pointer-only, fenced) | planned |

Adding one? Follow the format, keep it shorter than you want to, and put the
most common cause first — that's where the value is.
