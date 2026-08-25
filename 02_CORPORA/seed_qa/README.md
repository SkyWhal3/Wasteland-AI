# seed_qa — distilled answers from frontier models, served by retrieval

**The idea:** while the grid is up, big models (Fable 5, Opus 5...) write
worked answers to the questions this system will get asked offline. Those
answers are saved HERE as files, ingested into the RAG index (Open WebUI
Knowledge → collection "seed_qa"), and the small local model *retrieves and
cites* them instead of re-deriving from its own 3B-parameter memory. A 4B
model quoting a Fable 5 worked example beats a 4B model improvising, every
time. That's the whole distillation trick — no fine-tuning required.

## File format

One question per file, named `NNN_short_slug.md`:

```markdown
---
question: the question, phrased the way a person would ask it
answer_model: claude-fable-5          # who wrote the answer
date: 2026-08-25
domain: code | power | comms | general | <one of the six safety domains>
serve_via: rag | retrieval_only
human_verified: false                 # flip to true ONLY after a person checks
sources: [paths or citations the answer leans on]
---

The answer.
```

## THE RULES (safety architecture — do not loosen casually)

1. **The six §9 domains (medical, reloading, canning, electrical sizing,
   structural, water dosing): a seed may contain POINTERS and already-
   human-reviewed project data ONLY.** Never novel numbers — no doses, no
   charge weights, no processing times, no fuse sizes invented by a model,
   however large. Big models hallucinate too; they just do it with better
   grammar. For those domains the seed says *where the authoritative table
   lives*, and `serve_via: retrieval_only`.
2. **`human_verified: false` means UNVERIFIED and stays visible in the
   answer.** A person who checks a seed against reality flips the flag and
   adds their initials to `sources`.
3. **Cite or die:** every seed ends up quoted by a small model. If the seed
   itself doesn't say where its facts came from, the citation chain is
   theater.
4. New seeds welcome — especially "we hit this exact problem and solved it"
   write-ups. Those beat anything a model generates.

## Ingest

Open WebUI → Workspace → Knowledge → create "seed_qa" → upload this folder's
`.md` files (re-upload changed files after edits). Point the Tier-0/Tier-1
model's RAG at that collection. The safety router still runs in front.
