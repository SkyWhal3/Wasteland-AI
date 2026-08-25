# BUILD LOG

One entry per work session. Newest on top. Every hardware change also gets a
same-day Layer 0 row (manifest §15 — no exceptions).

---

## 2026-08-25 (latest+6) — Yamaha, the Generac wall, and STORAGE.md

- **Yamaha EF2000iS** collected (archive.org) — the other camping standard
  alongside the Honda EU. Moves from gap to covered.
- **Modern Generac 9–26 kW: five attempts, all refused.** Generac's own CDN
  truncates; the Norwall PIM mirror truncates identically; electricgenerators-
  direct returns 403. `fetch_doc.py` refused every one, so nothing corrupt
  entered the archive — but the document is genuinely missing and is now
  logged as a **browser job** with known-good sources named, not as a vague
  gap. Worth noting the tool did exactly its job five times in a row.
- **NEW `00_DOCS/STORAGE.md`**, answering the RAID10 question with measured
  numbers. The three findings worth keeping:
  1. **Everything that keeps a person alive fits in ~60 GB.** A single 2 TB
     NVMe holds the full library, toolchain and every runnable model. Storage
     is not this project's constraint; collection effort and power are.
  2. **RAID10 cannot detect silent corruption.** Two copies, no checksums,
     no way to know which is right when they disagree — and a rebuild can
     propagate the bad one. For a decade-scale archive the answer is a
     checksumming filesystem (ZFS/btrfs), or two plain drives plus
     `verify_checksums.py`, which is detect-and-repair done by hand and works
     on any OS with no special hardware.
  3. **An array does not fit the power budget.** Four spinning drives are
     20–40 W continuous = 480–960 Wh/day against ~1,020 Wh/day of December
     production. RAID is a grid-tied answer, so storage splits by power
     domain: redundant master on mains, single-NVMe node off-grid holding
     nothing unique, cold copy on **spinning rust — not SSD**, because
     unpowered NAND leaks charge and fails silently in a drawer.
- Bit-rot index rebuilt.

## 2026-08-25 (latest+5) — engines, battery skill, adaptive context, credits

Acting on Grok's field-scenario review plus the contributor and context
questions.

- **`fetch_doc.py`** — the truncation lesson productized. Validates HTTP
  status, Content-Length, `%PDF` header AND `%%EOF` trailer before writing
  anything into the archive, and says plainly that a refused download is the
  correct outcome. Used for everything below.
- **Engine-level manuals** (`datasheets/power/engines/`): Honda
  GX120/GX160/GX200 owner's, the **Honda GX160 SERVICE manual** (teardown
  level, 11.8 MB — the prize), and three Briggs & Stratton operator manuals.
  Rationale, now written into GENERATOR_INDEX: in the wasteland the badge
  falls off and you are left with an engine. Clone engines (Predator,
  Champion, 168F/170F) follow the GX pattern closely enough that its service
  manual is often the best procedure available — with the standing caveat
  that the numbers are Honda's until confirmed against the clone's own docs.
- **generator-service: the full spark procedure**, per Grok's scenario. Wire
  and boot inspection → continuity check with a meter (including the flex
  test that finds a broken conductor inside intact insulation) → grounded-plug
  spark test with the vapour warning → reading the plug → the no-spark branch.
  Number-free throughout; plug gap, coil resistance and coil air gap all route
  back to the manual. Also added an "if the basics were already ruled out"
  branch so the checklist does not re-ask answered questions.
- **NEW skill `battery-health`** (9th), for the flooded-lead-at-half-capacity
  case. Chemistry-first, because equalization is routine on flooded, prohibited
  on most AGM, and dangerous on lithium. Names sulfation-from-chronic-
  undercharging as a *charging* problem wearing a *battery* costume, insists on
  per-cell specific gravity over voltage, is honest that recovery odds are poor
  on a months-dead bank, and refuses to endorse desulfator gadgets. All
  equalization numbers retrieval-only; `equalization voltage` / `specific
  gravity` / `desulfat` added to the electrical fence. Router now 30/30.
- **Adaptive context.** `context_meter.recommend_ctx()` now computes the actual
  fp16 KV-cache cost from the model's own reported architecture
  (2 x layers x kv_heads x head_dim x ctx x 2 bytes) against RAM free right
  now, and picks the largest power-of-two window fitting in 25% of it.
  `pi_agent` defaults to `AGENT_NUM_CTX = "auto"`. Answers the 32k/64k/128k
  question with arithmetic instead of a rule of thumb — and documents why
  bigger is not automatically better: KV RAM and prefill time are both linear
  in context, and long-context attention degrades in the middle.
- **NEW `CREDITS.md`** — what each model actually contributed. GitHub's
  contributor graph only counts commits matched to registered accounts, so
  Co-Authored-By trailers are real permanent commit metadata but will never
  populate the sidebar. That is fair rather than broken: a graph counts
  commits, and it could never have shown that Grok's contribution was an
  argument that changed a design.
- Bit-rot index rebuilt: 74 files.

## 2026-08-25 (latest+4) — the generator shelf

Collected for machines you might **encounter**, not only machines you own —
the scavenge column applied to documentation. 11 manuals, ~105 MB, indexed:

- **Honda EU2200i** — the camping standard and generator-service's worked
  example. (Note in the index: the EU2000i is close but NOT identical.)
- **Predator 3500** (two manual revisions) and **4400** — Harbor Freight,
  the most common portable inverter sets in the US.
- **Champion dual fuel** 3800 / 4250 / 6250 W — gasoline + propane.
- **Cummins Onan RV** — the general RV Generator Handbook plus two operator
  manuals. The camper-under-the-step case.
- **Generac air-cooled standby 7/10/13/16 kW** — propane/NG home standby.
  The abandoned-cabin case.

**A truncation catch worth recording.** Three Generac downloads came back at
exactly 8 MiB, 8 MiB and 4 MiB — powers of two, no `%%EOF` trailer. Their CDN
truncates automated requests, and a naive `read()` reported success. Had those
been indexed they would have looked like good manuals with valid checksums,
and the corruption would have surfaced the day someone needed page 41. Every
PDF is now verified for the `%PDF` header AND the `%%EOF` trailer before it is
written; the three bad files were deleted rather than kept. Retries with
chunked reads, Content-Length checks and curl all failed identically, so
modern Generac 9–26 kW is logged as a **known gap** in GENERATOR_INDEX.md
rather than papered over. The older 7–16 kW manual came through a NOAA mirror
intact and covers the same architecture.

- **NEW `generators/GENERATOR_INDEX.md`** — the coverage map, including known
  aliases and an explicit gaps list (modern Generac, Yamaha EF, engine-level
  manuals for Honda GX / Briggs / Kohler, vintage sets, diesel). It also
  carries the procedure for meeting an undocumented machine: photograph the
  data plate first, Layer 0 row the same day, get the manual while the grid
  is up.
- **generator-service now opens that index FIRST** and states plainly that
  when a machine is not on the list the engine fundamentals still apply but
  the model-specific numbers do not.
- Bit-rot index rebuilt: 68 files in 02_CORPORA.

## 2026-08-25 (latest+3) — Layer 3 collection begins; v1.4 released

- **v1.4 released** ("the skills layer"); v1.3 notes point forward. CI green.
- **38 documents / ~95 MB collected**, all checksummed into CORPUS_INDEX the
  same day (§15), all git-ignored — the repo ships blueprints, not vendor PDFs.
  - `datasheets/power/`: **Victron VE.Direct protocol whitepaper** (the spec
    power_monitor.py implements — the manifest's own named item), BlueSolar
    MPPT 100/30 manual rev 12 + datasheet (the CS/ERR tables charging-triage
    points at), NOCO Genius10, Krieger KR1100/1500/2000
  - `datasheets/radio/`: **Semtech SX1261/2 datasheet rev 1.2** + AN1200.40
    reference design, ESP32-S3 TRM + datasheet, and the full LilyGO T-Deck set
    — board schematic, both GPS variants, and the 868-915 MHz antenna data
  - `bootstrap/NEETS/`: **all 24 Navy electronics modules, 59 MB** (the
    manifest's "best free resource on this list"). One module 404'd on the
    first pass and was retried; 24/24 verified as real PDFs.
- **INVENTORY datasheet paths corrected to the real filenames.** They had been
  written aspirationally; every path now resolves to a file that exists, which
  is the difference between `?find sx1262` working and `?find sx1262` lying.
- Dogfooded `verify_checksums.py build` over 02_CORPORA: 56 files indexed.
  First real bit-rot index in the archive.
- **Blocked, needs a human with a browser:** Intel's CDN returns 403 to
  automated requests, so the NUC11TN Technical Product Spec (WAI-0005) is
  marked PENDING in the inventory rather than silently missing. It matters
  because it carries the DC input range that decides whether the NUC can run
  off the battery through a boost converter instead of an inverter.
- Not collected: generator manuals. No generator is owned yet, so
  generator-service still points at `<model>` placeholders by design — that
  shelf gets filled when there is a machine to fill it for.

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
