# Session 3 report — 2026-09-01 — "the night the library got a radio and a phone line"

**Audience:** the project's external reviewers (Grok, chat-mode Claude, and
anyone else Adam briefs). Self-contained: you need no other context to
review this. Repo: https://github.com/SkyWhal3/Wasteland-AI — session spans
commits `a69da17..22dd999` (~17 commits), all tested and CI-green.

**Reviewing doctrine reminder:** safety architecture may be tightened
unilaterally, never loosened without review. This report marks every
loosening-adjacent change with ⚖ and asks for your ruling.

---

## The night in one paragraph

Session 3 opened with a corpus harvest and closed with a working
end-to-end system: Adam's T-Deck sent a question over LoRa to the T114
base node ("LIBRARY"), the safety router cleared it, Claude Sonnet 5
answered over the home uplink, and a one-packet radio-shaped reply landed
back on the handheld with a working `?more` conversation chain — the exact
Starlink-gateway architecture planned for the camp deployment, proven at
the house. Along the way: 15 new documents harvested with provenance, the
skills layer bound to the radio as one-packet telegrams, `?med` rebuilt
around what a field reader actually needs, and two live-fire QA nights'
worth of bugs found by real use and fixed with regression tests.

## Hardware milestones

- **Heltec T114 (nRF52840) arrived and provisioned** as `LIBRARY` / `LIBR`:
  CLIENT role, hops 3, MQTT off, position unshared, probe verdict
  mesh-ready (0 FAIL / 1 WARN — the WARN is the not-yet-created private
  camp channel, deliberate). Config backed up. Runs 24/7 on a wall brick,
  relaying as a normal mesh citizen for the ~28-node neighborhood it hears.
- **T-Deck confirmed in hand** ("ByteKhaos"). Two-node encrypted DM test
  passed both directions at SNR +7 dB. The Oracle flies under Adam's own
  callsign — the borrowed-node restriction is retired.
- The probe learned the nRF52 family (Adafruit TinyUSB VID 0x239A).
- Operations are now one double-click: a git-ignored launcher raises
  kiwix (all 3 ZIMs) + the oracle with the right environment.

## Corpus (now 104 files, all sha256-verified)

New `02_CORPORA/field_manuals/` shelf, all via the validated downloader +
pypdf title-page verification + provenance rows: FM 21-76 (1992), FM
3-05.70 (2002), FM 4-25.11 (C1), FM 21-10/MCRP 4-11.1D (2000), ST 31-91B
(1982, retrieval-only, historical), FEMA Are You Ready IS-22 (2004), CDC
wound/food/water factsheets, EPA Emergency Disinfection 2017, NIOSH 96-118
CO. Plus: Intel NUC11TN Technical Product Specification — **battery-direct
input verified from the primary source** ("12VDC to 24VDC +/-5%", p14; 12V
LiFePO4 direct = GO, 24V bank = NO-GO, charging exceeds the ceiling) — and
Powermate/Honda EB3000c generator docs. One AI-search lead was a
keyword-stuffed SEO-spam PDF from a Webflow CDN — structurally valid,
content garbage — caught by title-page reading and documented as a
standing warning. Sources lesson: FAS is behind an anti-bot wall; archive.org
metadata's `access-restricted-item` flags lending scans; stacks.cdc.gov
requires an Accept header (downloader fixed).

## Features shipped (chronological)

1. **Skill telegrams** — every skill carries `radio: ultra` +
   `radio_payload`: a ≤172-byte one-packet spine of its procedure. The
   oracle serves the telegram when the router matches a skill — before any
   model. ⚖ **(1)** On GENERAL_MODEL routes this REPLACES model prose
   (library-first doctrine; model demoted to questions no procedure
   covers). On RETRIEVAL_ONLY it rides behind the `FENCED (domain).` tag,
   replacing the generic brush-off with a fence-safe pointer. CI enforces
   the byte budget including the worst-case fence prefix.
2. **`?med` rebuilt around the field reader** (live QA findings, same
   night): page chrome (figure captions, infobox tables) cut; the verbatim
   window ⚖ **(2)** anchors at the article's Management / Application /
   Treatment section (headings collected + keyword-matched — WikEM says
   "General Management", "Application of Tourniquet"), bounded at the next
   heading; stub sections fall through; the suggestion scan prefers an
   article WITH an action section over a disambiguation stub (served title
   always displayed). **Pull-paging**: `?med burn p2` serves the next
   verbatim window, one packet per request, position shown ("2/31");
   pages are walked so each ends on a sentence/word boundary and nothing
   falls between pages. Multi-part medical remains forbidden. Every word
   radioed is the source's, in the source's order — selection got smarter,
   generation stays zero.
3. **NET gateway live** (Adam's design): `?ask` = fence → skills → Claude
   Sonnet 5 over the uplink (labeled `NET:`) → local Ollama fallback
   (`AI:`) → honest refusal. Stable radio system prompt (one packet, 160
   chars, imperative, "unsure - check the library" over guessing, and a
   backup fence echo — the model answering FENCED means a router keyword
   gap, logged and never radioed). **`?more`** threads the last Q/A back
   as real conversation turns; NET replies append `| ?more` when the
   packet has room. Wallet guard: 200 calls/UTC-day cap (≈$0.25/day worst
   case), over-cap falls back local. All brains ship disabled; operators
   enable via environment (ORACLE_ALLOWLIST / ORACLE_OLLAMA_MODEL /
   ORACLE_NET_BACKEND / ORACLE_NET_MODEL / ORACLE_NET_WORKSPACE) — node
   ids and keys never live in source. The fallback chain deliberately ends
   at the LOCAL brain, never a second cloud model.
4. ⚖ **(3) Router matching is now word-boundary, operator-approved**: the
   original match-anywhere substring rule (a documented deliberate trade)
   fenced "two-burner camp stove" as medical twice in one night of real
   use. New rule: keywords match at word boundaries plus common endings
   (burn → burns/burned/burning, never burner); `*` marks open stems
   (anaphyla*, diagnos*, ...) preserving every inflection the old rule
   caught; compounds now explicit (sunburn, windburn, burnt). 28 contract
   rows pass, including four new ones pinning both directions.

## Live evidence (verbatim radio replies)

- `?med burn` before: `...s Burns Background Normal dermal anatomy.
  Crossectial anatomy of burns, from left to right...` (figure captions)
- `?med burn` after: `WIKEM: BURN §MANAGEMENT 1/31 | Consider empirically
  treating for cyanide toxicity especially if fire was in an enclosed
  place Not Severe (Outpatient) Cold running water for 20 | FULL TEXT AT NODE`
- `?ask` over the full RF chain: `NET (no doc): At ~10-20k BTU burner, a
  20lb tank (~430,000 BTU) lasts roughly 20-40 hrs continuous burn time.
  Actual use much longer with intermittent cooking. | ?more` — and `?more`
  continued with valve/leak-check/storage guidance.

## ⚖ Adjudication requests (rule on each)

1. **Telegrams before models** — a repo-authored procedure now preempts
   model prose whenever a skill matches. Tightening in spirit (less
   generation), but it changes what `?ask` returns. Bless or bound it.
2. **`?med` section targeting** — choosing WHICH contiguous verbatim
   window to radio (Management over Background). Retrieval targeting, zero
   paraphrase — but it is a medical-serving change and deserves review.
3. **Word-boundary matching** — the one true loosening, operator-approved
   with field evidence and stem-preservation. Verify the stem list covers
   what you'd expect; propose additions freely (additions are free).
4. **FM 3-05.70 (2002)** carries a DoD distribution restriction on its
   title page (US gov agencies only; publicly circulated 20+ years; US gov
   work = no copyright). Currently LOCAL-ONLY, never served past camp
   WiFi, never in a release. Keep or delete? (FM 21-76 1992 covers the
   ground either way.)
5. **Hesperian** (Where There Is No Doctor) is CC BY-NC-SA — may an
   NC-licensed copy sit on a non-commercial community shelf, or pointer
   only?
6. **Proposed, not implemented:** a shorter per-sender rate limit for
   allowlisted senders (60s makes `?med` paging and `?more` painful for
   the one authorized human; strangers would keep 60s). This loosens a
   named invariant — your call.
7. **Proposed, not implemented:** a curated `?water` card serving the CDC/
   EPA dosing numbers verbatim from the shelf documents — the fence's
   answer to "how much bleach per gallon", human-verified before serving.

## State at report time

`main` = `22dd999`, CI green, corpus 104 files verified, tree clean.
LIBRARY on the air 24/7 (relay + oracle), NET live at the house, $83.57
API balance, cap 200/day. **v1.8 gates unchanged:** outdoor `--listen`
datapoint + first real SMS (Twilio toll-free verification still pending).
Camp ~2026-09-08; Adam is on hospital night shift (1000 WAPs by Nov 4),
so expect odd-hours sessions.
