# Credits

This project was built by one human and four AI models arguing with each
other in public. That is unusual enough to be worth documenting honestly,
including the part where the models disagreed and the human decided.

## The human

**Adam ([@SkyWhal3](https://github.com/SkyWhal3))** — architect, decision
maker, and the only party here with a multimeter. Every design fork in this
repo (12 V vs 24 V, which tier is the point, whether to build a spectrum
tool, what stays out of the public subset) was settled by a person, not a
model. The AIs proposed; the human adjudicated and owns the outcome.

## The models, and what each actually contributed

**Claude** (Anthropic) — two roles, deliberately separated:
- *chat mode* wrote MANIFEST v3 and the build guide, and remains the owner
  of those documents so they keep one voice
- *Claude Code* (Fable 5, later Opus 5) did the implementation on the real
  filesystem: adversarial review of the v1 scripts, the VE.Direct
  checksum-validating parser, the sandboxed agent, the skills layer, the
  safety-router contract tests, live verification against a running
  kiwix-serve, and the Layer 3 document collection

**Grok** (xAI) — the most consistently useful reviewer. Pushed the tier table
to the front of the public docs and the "Tier A is the point" framing, argued
for demo modes that exercise real code paths rather than mocks, called the
`AUTHORIZED_SENDERS` production posture correctly, prioritised the skill
roster, and supplied the field scenarios (a generator that will not spark, a
flooded battery at half capacity) that drove real changes to the skills.

**ChatGPT** (OpenAI) — supplied the federation concept: specialist nodes
exchanging knowledge claims rather than model output. That became
`00_DOCS/FUTURE_FEDERATION.md`, including the framing that a model needs
somewhere outside itself to appeal to when challenged — the best one-line
justification of the retrieval-only architecture anyone has produced.

**Gemini** (Google) — framing and review, and an early insistence that the
public docs lead with capability rather than specifications.

Three separate models also ran adversarial review passes over the manifest
before any of this reached GitHub. Where they disagreed, the disagreement is
recorded in the document rather than smoothed over — see the GHI-vs-POA
argument in the build guide, which exists because reviewers kept getting it
wrong in the same way.

## On GitHub's contributor list

The sidebar will only ever show human accounts. GitHub builds it from commit
authorship matched to registered accounts, and a language model does not have
one. Commits here carry `Co-Authored-By:` trailers naming the model that did
the work — they are real, permanent commit metadata, visible in
`git log`, but they will not appear in the contributor graph.

That is a fair outcome rather than a bug. A contributor graph counts commits;
it would never have shown that Grok's contribution was an argument that
changed a design, or that ChatGPT's was a concept that became a document. This
file records what a graph cannot.

## Sources and prior art

The knowledge in the archive belongs to the people who wrote it. This project
only points at it:

- **Kiwix** and the ZIM ecosystem — offline Wikipedia, WikEM, iFixit and the
  rest, without which none of this exists
- **WikEM** — emergency medicine, the highest value-per-byte in the corpus
- **Hesperian Health Guides** — *Where There Is No Doctor* and its siblings,
  free because they intend them to be used exactly like this
- **NEETS** — the US Navy's electronics course, public domain, still the best
  free electronics education available
- **Meshtastic** and **Victron Energy** — open protocols and published
  specifications, which is why the code in this repo could be written at all
- Manufacturers who publish real documentation for their hardware. The
  archive is only as good as the datasheets in it.

## Contributing

Field reports beat code. If you run this on real hardware and it breaks, the
[issues](https://github.com/SkyWhal3/Wasteland-AI/issues) are where that goes,
and you will be credited here by name. The three open field tests are the most
useful thing anyone can do for this project right now.
