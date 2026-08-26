# Safety-architecture deltas — session 2, 2026-08-25 (for chat-mode review)

Per the standing rule: tightenings applied unilaterally, documented here for
the manifest owner's adjudication. Nothing below loosens anything.

## 1. TIGHTENED: the fence is now code-enforced on ?ask

**Before**: `lora_oracle.cmd_ask` never consulted `safety_router` — the
"medical questions belong in retrieval paths" rule was a docstring, i.e.
instruction-enforced on the human, not code-enforced on the path. A DM of
"?ask pediatric ibuprofen dose" would have gone straight to the model.

**After**: `cmd_ask` routes through `safety_router.route()` before ANY model
call. RETRIEVAL_ONLY → refusal message pointing at ?med/the library;
ARTIFACT_LOOKUP → pointed at ?find. Covered by smoke tests.

This closes a real gap and matters double now that ?ask can reach a
frontier model (below): the more persuasive the backend, the more the fence
has to be code, not vibes.

## 2. NEW: uplink gateway for ?ask (ships disabled)

`NET_BACKEND` config in lora_oracle: when set to "anthropic", with an API
key in the environment and a live uplink (cached probe), ?ask answers via a
frontier model, labeled `NET:`; otherwise falls back to local Ollama,
labeled `AI:`. New `?net` command reports which brain is on duty.

Invariants preserved:
- **Ships disabled**: `NET_BACKEND = None` and `OLLAMA_MODEL = None` remain
  the committed defaults. Enabling either is a runtime/deployment choice.
- **Fence-first**: the router runs before either backend (see §1).
- **Fallback chain ends locally**: a frontier refusal or a dead uplink
  degrades to the local model, then to retrieval commands — never to a
  second cloud model. The uplink is treated as temporary by design.
- **No keys in the repo**: the API key is read from the environment
  (`ANTHROPIC_API_KEY`); the config file holds only the env var's NAME.

For MANIFEST consideration: whether "uplink doctrine" (use greedily, depend
never; sync window; MQTT prohibition — see CAMP_DEPLOYMENT.md) deserves a
section of its own.

## 3. PROVISIONAL eighth fenced domain: plant_edibility

Same pattern as the provisional `generator_safety` domain: pure tightening,
live now, awaiting §9 formalization. Trigger case: camp-trip plant/mushroom
identification walks straight into "can I eat it", and mushroom
misidentification is lethal (amanitin). Design line: species
IDENTIFICATION stays unfenced ("what species is this flower" →
GENERAL_MODEL, covered by a self-test); INGESTION intent is fenced, and
"mushroom" fences outright. Router self-test extended 30 → 34 cases, all
passing. Open question for chat-mode: fold into `medical`, or stand alone?

## 4. Minor: ?net information disclosure

?net reveals uplink status and backend model name to any sender the oracle
answers. Under an allowlist this is group-internal telemetry; in open bench
mode it tells a stranger whether the camp has live internet. Judged
acceptable (same class as ?power revealing battery state, already
documented in SECURITY.md) — flagging for the record.
