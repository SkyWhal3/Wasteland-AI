---
question: Why did the AI forget what I told it? How do I know when the context window is full?
answer_model: claude-opus-5
date: 2026-08-25
domain: code
serve_via: rag
human_verified: false
sources: [05_SCRIPTS/context_meter.py]
---

**The short version: it did not "forget," it was truncated — and nothing told
you.** A model has a fixed context window. Past it, Ollama drops the oldest
messages and answers anyway, with exactly the same confidence. No error, no
warning.

On this stack that matters more than usual. If your first message was "I'm at
6,000 ft" and your tenth is a canning question, the altitude is precisely the
part that fell out of the window.

**The second trap, stacked on the first:** Ollama's default context is far
smaller than what the model supports. A model advertising 32k routinely runs at
2k or 4k because nobody set `num_ctx`. You are getting a fraction of the window
you think you have.

## See your real numbers

```bash
python 05_SCRIPTS/context_meter.py            # every model Ollama has
python 05_SCRIPTS/context_meter.py qwen3:4b   # one model, with warnings
```

It prints the **trained** window (what the model can do) against the **pinned
`num_ctx`** (what Ollama is actually giving it). The gap between those two
numbers is the bug most people never find.

## Fix it

- **Ollama API / scripts:** pass `"options": {"num_ctx": 8192}`. `pi_agent.py`
  does this explicitly and prints a usage bar after every step, stopping the
  run before the window overflows rather than working amnesiac.
- **Modelfile:** `PARAMETER num_ctx 8192`, then `ollama create`.
- **Open WebUI:** the per-model advanced parameters include the context length.
  Set it there or every chat inherits the small default.

## But do not just crank it up

The KV cache grows with the window, and it lives in RAM. On a Pi 5 a large
context can push you into swap or get the process OOM-killed — which on a
solar-powered node is a **power** problem as much as a computing one, because
the box burns watts thrashing and then dies anyway.

Raise it deliberately, one step at a time, and watch memory while you do.

## Habits that beat configuration

- **New topic, new chat.** The cheapest fix in existence.
- **Front-load the constraints that must not be lost** (altitude, voltage,
  exact model numbers) and restate them in the question that depends on them.
- **Retrieval beats conversation.** A cited chunk pulled fresh costs a few
  hundred tokens; forty turns of history costs thousands and degrades. This is
  the whole argument for the library sitting under the librarian.
