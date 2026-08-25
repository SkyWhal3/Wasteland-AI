# Wasteland AI

**A ~10 W always-on knowledge node + an on-demand 70B-class workstation, all
inside ~1 kWh/day of Colorado December sun.** The big box sleeps; the library
never does.

An off-grid knowledge server you can actually build: offline Wikipedia + WikEM
emergency medicine + iFixit + your own PDFs on a Raspberry Pi, solar-powered,
with a local LLM as the search interface — reachable over Meshtastic from
miles out. DM the node `?med tourniquet` and get verbatim WikEM back over LoRa.

## The part worth arguing about

The AI is **not allowed to freelance on dangerous topics**. Six domains —
medical, ammo reloading, canning, electrical sizing, structural, water
dosing — are hard-routed to retrieval-only: verbatim source + citation, no
generation. Enforced by [a router you can audit in two minutes](05_SCRIPTS/safety_router.py)
(`python safety_router.py --test` shows the contract), not by a prompt asking
nicely.

## What's in this repo

This repo is the **public release subset** — docs and code only. The
[.gitignore](.gitignore) is a whitelist: the full build's inventory, radio
configs (private keys!), logs, models, and corpora live in the same folder
tree locally but *cannot* be committed by accident.

| Path | What |
|---|---|
| [00_DOCS/MANIFEST.md](00_DOCS/MANIFEST.md) | **The build doc.** December power math (with the GHI-vs-POA trap), 12 V/24 V fork, cold-Voc rules, battery economics, Meshtastic security reality check, build order |
| [00_DOCS/CODE_REVIEW_2026-08-25.md](00_DOCS/CODE_REVIEW_2026-08-25.md) | Adversarial review findings on the v1 scripts, and what was fixed |
| [00_DOCS/SECURITY.md](00_DOCS/SECURITY.md) | Threat model: the radio keyhole, who can query you (allowlist), malware reality, login hardening, seizure trade-offs |
| [05_SCRIPTS/](05_SCRIPTS/) | The working code (below) — see its [README](05_SCRIPTS/README.md) for Pi setup, step by step |

| Script | What it does |
|---|---|
| `verify_checksums.py` | Fingerprints the archive so bit rot can't hide (Windows↔Pi portable) |
| `power_monitor.py` | Victron VE.Direct telemetry: checksum-validated frames, CSV log, GREEN/YELLOW/RED/BLACK band |
| `lora_oracle.py` | The mesh bot: `?power` `?med` `?find` `?ask`, DM-only, 200-char cap, rate-limited |
| `safety_router.py` | Classifies every question before any model runs; `--test` is the executable contract |
| `pi_agent.py` | Minimal coding agent jailed to a scratch SSD (ships disabled — read its docstring) |
| `make_skeleton.py` | Rebuilds the full folder tree after a bare clone |

## Status

- Build doc adversarially reviewed by three different AI models, revised twice.
- All four v1 scripts reviewed against library source + protocol specs and
  fixed; the VE.Direct parser is unit-tested against synthetic frames.
- **Still needs cable-in-hand testing:** live VE.Direct stream, a real
  Meshtastic node, `?med` against a running kiwix-serve (the known-fragile
  seam — kiwix URL schemes drift between versions). That's where you come in.

**Run it. Break it. File issues.**

## License

[MIT](LICENSE). Fork it, adapt it to your site, share what you learn.
