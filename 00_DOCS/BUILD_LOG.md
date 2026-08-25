# BUILD LOG

One entry per work session. Newest on top. Every hardware change also gets a
same-day Layer 0 row (manifest §15 — no exceptions).

---

## 2026-08-25 (latest+2) — all eight skills + context metering

- **Seven more skills written**, completing the roster: solar-commissioning,
  node-dark-triage, charging-triage, radio-wont-transmit, vehicle-wont-start,
  water-source-decision, wound-triage. All eight wired into the router with
  ordered triggers (first match wins, most specific vocabulary first) and
  pinned by SKILL_TEST — now 28/28 contract tests.
- Writing those tests exposed **three real fence gaps**, all now tightened:
  "series or parallel" only matched when the word "panel" followed, so
  "should I wire my panels in series or parallel?" was reaching the model;
  medical missed stitches/laceration/puncture/deep cut; water missed
  "safe to drink"/"drinkable"/"potable". The self-test earning its keep —
  found by writing expectations, not by re-reading code.
- The two fenced skills (wound-triage, water-source-decision) contain no
  treatment, dose, or contact time of any kind, by design. wound-triage's
  value is the assessment ORDER and the red-flag list, ending in the honest
  line: if you are asking whether this needs a doctor and one is reachable,
  the answer is yes.
- **NEW context_meter.py**, answering "how does a user know the window is
  filling up." The real hazard is not a missing readout: past its window
  Ollama **silently drops the oldest messages** instead of erroring, and its
  default window sits far below what models support (a 32k model commonly
  runs at 2k-4k because num_ctx was never set). The tool prints trained
  window vs pinned num_ctx so that gap is visible, and supplies the
  4736/8k 58% [####......] readout.
- **pi_agent.py** now requests num_ctx explicitly, prints that readout after
  every step, and STOPS before overflow — an agent loop that overflows drops
  the task description itself and keeps working amnesiac. Token counts come
  from Ollama's own prompt_eval_count/eval_count, never estimated.
- seed_qa/005 documents the trap, the fix, and the RAM/OOM caveat for the Pi.

## 2026-08-25 (latest+1) — skills layer + provisional seventh fenced domain

- **New corpus type: `02_CORPORA/skills/`** — procedural overlays that tell the
  model what to ASK before answering, which document to open, and what never to
  generate. Answers the "how does it know anything about a Honda EU2000i"
  problem: it doesn't, and a bigger model wouldn't either — the skill makes it
  ask which machine and open that manual instead of inventing a jet number.
  Format spec + rules in `skills/README.md`; exemplar `generator-service.md`
  written (won't-start triage leading with the low-oil cutoff, oil, altitude
  jetting, CO, backfeed, load/storage).
- Rules locked in: procedure in the skill, numbers in the manual; **pointers
  only in the fenced domains**; the router runs first and a skill can never
  change a route; categorical prohibitions allowed, computed values not. The
  README states plainly that **the router is code-enforced and skills are only
  instruction-enforced** — so anything lethal belongs in the fence, not in a
  skill's `never_generate`.
- **safety_router.py**: `Decision.skill` added (additive, never overrides a
  route); `match_skill()` + `SKILL_TRIGGERS`; part-number-shaped questions
  (main jet, jet kit, plug gap, oil capacity, valve clearance) now route to
  ARTIFACT_LOOKUP so the answer is a filename+page rather than a prompt-level
  hope; `SKILL_TEST` table added — 21/21 contract tests pass.
- **PROVISIONAL seventh fenced domain `generator_safety`** (CO siting +
  backfeeding into building wiring). Both kill people annually and neither was
  cleanly covered by the six. Implemented as a pure tightening — nothing
  previously fenced became unfenced. **For chat-mode adjudication:** whether
  MANIFEST §9 names this a seventh domain or folds CO into medical and backfeed
  into electrical. The protection is live either way.
- Still open from earlier: MANIFEST tier-table edits, AUTHORIZED_SENDERS
  default-deny. Collection task queued: owner's manuals for generators/inverters
  actually in reach (EU2000i/2200i, Predator 3500, Champion dual-fuel) into
  02_CORPORA/datasheets/power/ with INVENTORY rows — the skill needs real PDFs
  to point at.

## 2026-08-25 (latest) — public build guide published

- `OFFGRID_PUBLIC_EDITION.md` (chat-mode's group-facing build doc, until now
  git-ignored and unpublished) promoted to **`00_DOCS/BUILD_GUIDE.md`** with six
  code-sync fixes: repo + QUICKSTART pointers and a doc-map, the six-script
  inventory, the `AUTHORIZED_SENDERS` allowlist and why it matters, corrected
  `?power` sample output (+ STALE), the `--demo` no-hardware path, the kiwix
  book-name trap as a build-order warning, and a "check your closet before your
  wallet" Tier 1 note (a mini PC + ~$120 RAM runs 30B-A3B — the NUC lesson,
  generalized). Prose and philosophy left untouched: chat-mode's voice.
- README: BUILD_GUIDE row added, MANIFEST relabelled "the engineering reference"
  so the three docs have distinct jobs (try it / build it / reference), and the
  tier table's cash column relabelled "power side" with ranges now matching the
  guide ($400–700 / $1,100–1,900 — they had already drifted).
- The original file keeps a SUPERSEDED banner locally so future edits go to the
  published copy.

## 2026-08-25 (later) — first library content + live ?med verification

- **WikEM acquired:** `wikem_en_all_maxi_2026-07.zim` (375 MB) into
  `02_CORPORA/kiwix_zim/`, sha256 recorded in CORPUS_INDEX same-day (§15).
  kiwix-tools 3.8.1 (win-x86_64) into `03_SOFTWARE/kiwix/`.
- **`?med` verified against a live kiwix-serve** — the known-fragile seam
  closed on 3.8.1: `/content` scheme confirmed, suggest JSON exactly as
  designed. Found and fixed live: HTML entities + mojibake in snippets
  (`&lt;35Â°C` → `<35°C`), byte-aware `clip()` (the radio's limit is bytes,
  not characters), and **book-name auto-discovery** — URL names are ZIM
  filename stems (`wikem_en_all_maxi_2026-07`), not catalog names; the
  oracle now probes the configured name and heals itself from the server's
  own catalog.
- **`--demo` modes:** power_monitor (synthetic sun, labeled DEMO in every
  output) and lora_oracle (REPL — real lookups, keyboard for radio). They
  chain: monitor demo feeds `?power` in the oracle demo. Zero-hardware
  Tier-0 loop for QUICKSTART Level 1.
- README: tier table (A/B/C — Tier A is the point), WikEM screenshot,
  Help-wanted section → issues #1 #2 #3. QUICKSTART: minimum-viable node
  shopping list + demo walkthroughs.
- Deferred to chat-mode adjudication (per standing rule): Grok's proposed
  MANIFEST edits (tier table into §1, softened opening) and its
  AUTHORIZED_SENDERS default-deny proposal (open-mode-with-loud-warning
  kept for bench UX; flag if the group disagrees).

## 2026-08-25 — repo established, code reviewed, agent layer added

- Folder skeleton (§13) created at `D:\Wasteland AI`; git repo initialized
  with a **whitelist** .gitignore (public subset = docs + code; inventory,
  configs, logs, models physically can't be committed by accident).
- Commit 1: public release v1 exactly as shipped. Commit 2: adversarial
  review fixes — full findings in [CODE_REVIEW_2026-08-25.md](CODE_REVIEW_2026-08-25.md).
  Headline: `?med` article URL was broken on current kiwix-serve (fixed);
  power_monitor now validates VE.Direct checksums (EMI can't poison the
  band logic); checksum indexes are now Windows↔Pi portable; the reloading
  fence now catches caliber-phrased questions ("safe 9mm load").
- VE.Direct parser unit-tested against synthetic frames (valid / corrupted /
  hex-interleaved / chunk-split). Meshtastic + kiwix API assumptions
  verified against library source and official docs.
- NEW: `pi_agent.py` (jailed coding agent, ships disabled), `agent_examples/`,
  `seed_qa/` distillation corpus (4 seeds), `WIRING_DIAGRAMS_SOLAR.md`
  (retrieval-only diagrams incl. the 4-in-series controller-killer warning),
  `make_skeleton.py`.
- Environment: Windows 11 box, Python 3.13, git 2.53. Scripts import-tested
  against real `meshtastic`/`pyserial` in a throwaway venv.

**Open items (need hardware in hand):**
- [ ] VE.Direct cable arrives → `power_monitor.py --list-ports`, then live test
- [ ] Meshtastic node arrives → oracle DM test on a private channel
- [ ] kiwix-serve running → `?med` against the real WikEM ZIM (version seam!)
- [ ] Pi 5 deployment: venv, systemd units, watchdog
- [ ] Group release: push public subset to GitHub, tag zip as Release
