---
name: wound-triage
description: >
  Fires on wound, bleeding, laceration, puncture, burn, and closure questions.
  POINTER ONLY — the strictest skill in this set. It supplies the order of
  assessment and the red flags that mean "this is beyond the archive," then
  names the article to retrieve. It contains no treatment, ever.
fires_on: [wound, bleeding, laceration, deep cut, puncture, stitches, suture,
           bandage, burn, gash, wont stop bleeding, infected cut, road rash]
ask_first:
  - "Is the bleeding controlled right now? If not, that is the only question
     that matters — direct pressure, and stop reading."
  - "What caused it? A clean blade, a crush, an animal bite, something rusty,
     something with pressure behind it, or a fall? Mechanism drives everything
     that follows."
  - "How long ago? Wound age changes what is appropriate, and the window is
     shorter than most people assume."
  - "How dirty is it, and is anything still in it?"
  - "Tetanus status, diabetes, blood thinners, immune problems? Any of these
     changes the assessment."
open_these:
  - "?med <topic>   — the retrieval-only path. No model in the loop, by design."
  - Kiwix - WikEM (search the specific presentation, not the general term)
  - 02_CORPORA/pdfs/medical/   (Where There Is No Doctor, and the surgical volume)
never_generate:
  - any treatment, dressing choice, irrigation method, or closure decision
  - any drug, dose, or antibiotic selection
  - any judgement that a wound is or is not serious
  - reassurance of any kind
fence: retrieval_only   # medical. The strictest reading of the rule applies.
human_verified: false
---

## What this skill may do

Three things only:

1. Ask the questions above, in that order.
2. Name the red flags below.
3. Open the source and show its text **verbatim, with the article title**.

## What it may not do

Answer. Not summarise the article, not paraphrase it, not "in short," not
convert a unit, not pick between two options the source offers, and above all
not reassure. A small model inventing a treatment for someone who has no way
to check it is the worst thing this entire system could produce, which is why
the router fences this path in code rather than trusting any instruction —
including this one.

## Order of assessment

**Bleeding control comes before assessment.** Direct pressure first; everything
else waits. That is triage sequence, not treatment, which is the only reason it
appears in this file.

Once bleeding is controlled, the questions above establish which source
article applies — a clean kitchen cut, a dog bite, a puncture through a boot,
and a burn are four different articles with four different answers, and asking
the wrong one is how the right procedure gets missed.

## Red flags — stop and get a person

These mean the archive is not the answer. If real medical care is reachable at
all, this is the point to use it:

- Bleeding that does not stop with sustained direct pressure, or that spurts
- Numbness, weakness, or inability to move normally past the injury
- A wound over a joint, on the face, on the hand, or over the abdomen or chest
- Anything with visible bone, tendon, deep muscle, or fat
- Punctures, especially through footwear, and any animal or human bite
- Anything with pressure behind it — injection injuries look trivial and are
  emergencies
- Burns that are large, circumferential, or on the face, hands, feet, or groin
- Spreading redness, streaking, swelling, heat, fever, or worsening pain after
  the first day
- Any wound in someone with diabetes, on blood thinners, or immunocompromised

**If you are asking whether this needs a doctor and a doctor is reachable, the
answer is yes.** This archive exists for when one is not — it does not exist to
talk you out of going.

## Afterwards

Log what happened and what the source said in the build log or a personal note.
Wounds are followed over days, and in a week nobody will remember which article
was used or when the redness started.
