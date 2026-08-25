# ADVERSARIAL CODE REVIEW — public release v1 scripts
**Date:** 2026-08-25 · **Reviewer:** Claude Fable 5 (Claude Code, on the D:\ box)
**Scope:** the four scripts in `OFFGRID_PUBLIC_RELEASE/code/`, written by a
chat-mode model with no hardware access. Fixes applied in `05_SCRIPTS/`;
the as-shipped originals are preserved in git history (commit "Import
OFFGRID public release v1 as shipped") and in `OFFGRID_PUBLIC_RELEASE/`.

## How claims were verified (not vibes)

| Assumption | Verified against |
|---|---|
| Meshtastic packet dict, topics, `sendText`, `myInfo.my_node_num` | The actual installed library source (`meshtastic` from PyPI, in a scratch venv) |
| kiwix-serve `/suggest` params + JSON keys, article URL scheme | kiwix-tools official docs + libkiwix suggestion JSON template (GitHub) |
| VE.Direct framing, field scales, checksum, CS/ERR codes | Victron VE.Direct text-protocol spec (as documented in the whitepaper) |
| Parser correctness | Unit test with synthetic frames: valid, bit-flipped, hex-interleaved, chunk-split (see 05_SCRIPTS tests noted in BUILD_LOG) |

Still **unverified**: anything needing hardware — live VE.Direct stream, a
real Meshtastic node, a running kiwix-serve. Those are the group's
cable-in-hand tests.

---

## lora_oracle.py — 1 breaking bug, 2 real risks

| # | Severity | Finding | Fix |
|---|---|---|---|
| O1 | **BREAKS ?med** | Article fetch built `<root>/<path>` — no book name, no `/content` prefix. 404 on any current kiwix-serve; the suggest `path` ("A/Dehydration") is book-relative. | Fetch `/content/<book>/<path>`, fall back to legacy `/<book>/<path>` for old servers. |
| O2 | High | All command work (kiwix ~20 s, Ollama up to 120 s) ran **inside the pubsub callback**, which executes on the meshtastic library's worker thread — stalling packet processing for the whole radio while a lookup runs. | Callback now only validates + rate-limits + enqueues; a main-loop worker does the slow part and sends the reply. |
| O3 | Medium | Used suggestion `label`, which carries `<b>…</b>` highlight markup → HTML would go out over the radio in the 200 chars. | Use `value` (plain title); strip tags if falling back to label. |
| O4 | Medium | `?power` reported `latest.json` with no age check — a monitor that died Tuesday reads as live data Friday. | Reply appends `STALE <n>min — monitor down?` past 5 minutes. |
| O5 | Low | `latest.json` could be read mid-write (torn JSON → spurious "no data"). | Fixed on the writer side (power_monitor now writes atomically). |
| O6 | Low | `INVENTORY.csv` looked in CWD only; manifest puts it in `00_INVENTORY/`. | Candidate list: CWD, then `../00_INVENTORY/INVENTORY.csv`. |
| O7 | Info | DM check `packet["to"] == my_node_num`, portnum string compare, `sendText(destinationId=int)` — **all confirmed correct** against library source. Library also drops self-echoed packets itself. | No change. |

## power_monitor.py — the protocol was trusted too much

| # | Severity | Finding | Fix |
|---|---|---|---|
| P1 | High | **No checksum validation.** VE.Direct frames end in a mod-256 checksum byte; the shipped line-parser ignored it, so EMI (this thing lives next to an inverter) could corrupt a digit and log 1.3 V as 13 V — and the band logic acts on those numbers. | Byte-level state machine implementing the documented framing; frames that don't sum to 0 are dropped and counted, never parsed. Unit-tested with synthetic + corrupted frames. |
| P2 | High | Readline parsing also breaks on VE.Direct **HEX records** (`:...` lines devices interleave) and on checksum bytes that happen to be `\n`/`\r`. | The state machine skips hex records per spec; raw bytes, no readline. |
| P3 | Medium | Port auto-detect globbed `/dev/...` — useless on Windows, where the first bench test will actually happen. | `serial.tools.list_ports` (cross-platform); prefers the FTDI "VE Direct cable" signature; `--list-ports` shows VID:PID. |
| P4 | Medium | Any serial hiccup (cable bump, USB reset) killed the process. Fine under systemd, bad on a bench. | Reconnect loop with 5 s backoff. |
| P5 | Medium | Band started as `GREEN` before any evidence; under charge with no SOC it would report GREEN forever on day one. | Starts `UNKNOWN`; also holds last band when charge current flows (not just when PV > 5 W). |
| P6 | Low | `latest.json` written non-atomically (see O5). | Temp file + `os.replace()`. |
| P7 | Low | CS/ERR logged as raw codes ("3", "33"). | Translated (BULK, PV INPUT VOLTAGE TOO HIGH…); ERR ≠ OK prints a loud one-time warning — err 33 is the §2.2 controller-killer showing up in telemetry. |
| P8 | Info | All field scales (V mV, I mA, SOC ‰, H20 0.01 kWh) — **confirmed correct** as shipped. | No change. |

## verify_checksums.py — correct, but not portable and not crash-proof

| # | Severity | Finding | Fix |
|---|---|---|---|
| V1 | High | Index keys used OS path separators: an index built on the Windows array reports **every file MISSING** when checked on the Pi. This project's whole flow is Windows array ↔ Pi. | Keys stored as forward-slash (`as_posix()`); old backslash indexes tolerated on read. |
| V2 | High | During `check`, an unreadable file (failing sector — the exact thing we're hunting) raised OSError and **killed the whole scan**. Build handled it; check didn't. | Caught per-file: `READ ERROR` line, counted, nonzero exit; scan continues. |
| V3 | Medium | Index written in place: Ctrl-C mid-write destroys the previous index after an hours-long scan. | Temp file + `os.replace()`. |
| V4 | Low | If the index lives inside the archive, it indexes/flags itself forever. | Index (and its temp file) excluded from the walk. |
| V5 | Low | `check` printed nothing for hours on a big archive (looks hung); malformed index rows crashed it. | Progress heartbeat every 200 files; bad rows skipped with a warning. |

## safety_router.py — sound design, holes in the fence

| # | Severity | Finding | Fix |
|---|---|---|---|
| S1 | High | Reloading fence missed caliber-phrased questions: "what's a safe **9mm load**?" hit no keyword and fell through to GENERAL_MODEL — the exact failure §9 exists to prevent. | New pattern rule: caliber (`.308`, `9mm`, `acp/magnum/creedmoor/...`) **AND** intent word (`load/charge/powder/grain/recipe...`) → RETRIEVAL_ONLY. Caliber alone (holster questions) stays free. |
| S2 | Medium | `"voc"` as a substring fenced "vocabulary", "advocate"... | Whole-word regex `\bvoc\b`. |
| S3 | Medium | Medical list missed high-frequency terms (fever, dehydration, hypothermia, frostbite, common drug names…). | ~20 additions across medical/canning/electrical/structural/water lists. All additions TIGHTEN the fence; nothing was loosened. |
| S4 | Low | `str \| None` annotation crashes import on Python < 3.10. | `from __future__ import annotations` (all scripts). |
| S5 | Info | Added `--test`: 14 canonical routings as an executable contract, so future keyword edits that break the fence fail loudly. | New. |

## New in 05_SCRIPTS (not review items)

- **pi_agent.py** — minimal jailed coding agent (Ollama), ships disabled.
  The jail is honestly documented as a seatbelt, not a prison: path tools
  can't leave the scratch root, but `run_python` is real code execution —
  OS-level isolation is out of scope for a starter script and the docstring
  says so in bold instead of pretending.
- **agent_examples/** — 4 known-good snippets (MicroPython blink, ADC
  divider with the 3.3 V warning, Pi 5 gpiozero, minimal VE.Direct).
- **make_skeleton.py** — rebuilds the §13 tree after a bare clone.
- **02_CORPORA/seed_qa/** — distillation corpus + rules (six-domain seeds
  are pointers only, never novel numbers).
- **02_CORPORA/reference_tables/WIRING_DIAGRAMS_SOLAR.md** — pre-drawn
  series/parallel diagrams incl. the 4-panels-in-one-string controller-killer
  warning. Retrieval content: the model shows it, never adapts it.

## For chat-mode adjudication (per the standing agreement)

Safety-architecture deltas in this pass, all in the tightening direction:
S1 caliber rule, S2 voc fix, S3 keyword additions, seed_qa rules 1–3,
wiring doc's "display, never adapt" serving rule. Nothing loosened; the
Oracle's DM-only / 200-char / retrieval-only invariants are untouched.
Known accepted false-positives ("testing"-style substring collisions were
screened out; "burning smell" → medical remains, by design).
