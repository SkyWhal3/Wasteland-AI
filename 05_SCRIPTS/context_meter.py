#!/usr/bin/env python3
"""
context_meter.py — how much of the model's context window are you using?

    python context_meter.py                 # every model Ollama has, in a table
    python context_meter.py qwen3:4b        # one model, with the warnings

WHY THIS EXISTS — read this part, it is the actual problem:

A language model has a fixed context window. Go past it and it does NOT
error. It silently drops the oldest part of the conversation and answers
anyway, sounding exactly as confident as before. You find out because it
"forgot" something you told it two messages ago.

On this stack that is a safety issue, not an annoyance. If the first thing
you said was "I'm at 6,000 ft" and the question ten messages later is a
canning time, the altitude is the part that quietly fell out of the window.

And there is a second trap stacked on the first: **Ollama's default context
is far smaller than the model's.** A model advertising 32k routinely runs at
2k or 4k because nobody set `num_ctx`. You get 1/8th of the window you think
you have, with no message telling you so. This script's main job is to show
you that gap.

WHAT TO DO ABOUT IT
  * Raise num_ctx (Modelfile, API option, or Open WebUI's advanced params)
  * But watch RAM: the KV cache grows with context length. On a Pi, a large
    window can push you into swap or an OOM kill — which on a solar-powered
    node is a power problem as well as a computing one. Raise it deliberately,
    then measure.
  * Start a fresh chat for a new topic. Cheapest fix there is.

Pure standard library plus requests (already in requirements.txt).
"""

from __future__ import annotations

import sys

try:
    import requests
except ImportError:
    print("requests missing. Run:  pip install -r requirements.txt", file=sys.stderr)
    sys.exit(2)

OLLAMA_URL = "http://127.0.0.1:11434"

# Bands for the readout. Percent of the effective window in use.
WARN_AT = 0.75
FULL_AT = 0.90


# ----------------------------- formatting -----------------------------------

def human(n: int) -> str:
    """4096 -> '4k'. Keeps the readout short enough for a status line."""
    if n >= 1000:
        k = n / 1024
        return f"{k:.0f}k" if k >= 10 or k == int(k) else f"{k:.1f}k"
    return str(n)


def bar(used: int, limit: int, width: int = 20) -> str:
    if limit <= 0:
        return "?" * width
    filled = min(width, int(width * used / limit))
    return "#" * filled + "." * (width - filled)


def readout(used: int, limit: int) -> str:
    """The one-line status: '4736/8k 58% [#########...........]'."""
    if not limit:
        return f"{used} tokens / limit unknown"
    pct = used / limit
    flag = "  FULL - older turns are being dropped" if pct >= FULL_AT else \
           "  getting full" if pct >= WARN_AT else ""
    return f"{used}/{human(limit)} {pct:.0%} [{bar(used, limit)}]{flag}"


def estimate_tokens(text: str) -> int:
    """Rough token estimate for text you have not sent yet: ~4 chars/token
    for English prose, fewer for code. This is a PLANNING number only —
    the real count comes back from the API (see usage_from_response)."""
    return max(1, len(text) // 4)


def usage_from_response(data: dict) -> tuple[int, int]:
    """(prompt_tokens, generated_tokens) from an Ollama reply. These are
    exact — Ollama counts them for you, so never estimate after the fact."""
    return int(data.get("prompt_eval_count") or 0), int(data.get("eval_count") or 0)


# ----------------------------- querying Ollama ------------------------------

def model_limits(model: str, url: str = OLLAMA_URL) -> dict:
    """What the model was TRAINED with vs what Ollama is actually GIVING it.

    Returns {'trained': int|None, 'configured': int|None, 'effective': int}.
    'configured' is num_ctx if this model has one pinned; when it is None,
    Ollama falls back to its own built-in default, which is small.
    """
    out = {"trained": None, "configured": None, "effective": 0}
    try:
        r = requests.post(f"{url}/api/show", json={"model": model}, timeout=10)
        r.raise_for_status()
        data = r.json()
    except (requests.RequestException, ValueError):
        return out

    # The trained window is reported as "<architecture>.context_length".
    for key, value in (data.get("model_info") or {}).items():
        if key.endswith(".context_length"):
            try:
                out["trained"] = int(value)
            except (TypeError, ValueError):
                pass
            break

    # A pinned num_ctx shows up in the parameters blob (Modelfile PARAMETER).
    for line in str(data.get("parameters") or "").splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0] == "num_ctx":
            try:
                out["configured"] = int(parts[1])
            except ValueError:
                pass

    out["effective"] = out["configured"] or out["trained"] or 0
    return out


def list_models(url: str = OLLAMA_URL) -> list:
    try:
        r = requests.get(f"{url}/api/tags", timeout=10)
        r.raise_for_status()
        return [m["name"] for m in r.json().get("models", [])]
    except (requests.RequestException, ValueError, KeyError):
        return []


# --------------------------------- CLI --------------------------------------

def report(model: str) -> None:
    lim = model_limits(model)
    print(f"\n{model}")
    print(f"  trained context   {human(lim['trained']) if lim['trained'] else '?'}"
          f"   (what the model can do)")
    if lim["configured"]:
        print(f"  pinned num_ctx    {human(lim['configured'])}"
              f"   (what this Modelfile asks for)")
        if lim["trained"] and lim["configured"] < lim["trained"] / 2:
            print("  NOTE: you are using less than half the model's window.")
    else:
        print("  pinned num_ctx    (none)   <-- Ollama's own default applies,")
        print("                             and it is much smaller than the")
        print("                             number above. Anything past it is")
        print("                             DROPPED SILENTLY, not refused.")
        print("  Fix: set num_ctx in a Modelfile, in the API options, or in")
        print("       Open WebUI's advanced parameters. Then watch RAM — the")
        print("       KV cache grows with the window, and on a Pi that is a")
        print("       power and OOM question, not just a memory one.")


def main() -> None:
    if len(sys.argv) > 1:
        report(sys.argv[1])
        return
    models = list_models()
    if not models:
        print(f"No models found (is `ollama serve` running at {OLLAMA_URL}?)")
        print("\nDemo of the status readout this module provides:")
        for used, limit in ((512, 8192), (6100, 8192), (7800, 8192)):
            print("  " + readout(used, limit))
        return
    for m in models:
        report(m)


if __name__ == "__main__":
    main()
