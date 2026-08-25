# BUILD LOG

One entry per work session. Newest on top. Every hardware change also gets a
same-day Layer 0 row (manifest §15 — no exceptions).

---

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
