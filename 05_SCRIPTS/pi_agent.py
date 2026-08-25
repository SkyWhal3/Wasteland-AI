#!/usr/bin/env python3
"""
pi_agent.py — a minimal coding agent for the offline stack.

WHAT IT IS: a loop. The local model (via Ollama) is given a task and a
toolbox; it replies with ONE tool call as JSON; the tool runs; the result
goes back into the conversation; repeat until it calls done() or hits the
step limit. That is the entire trick behind every coding agent — this file
is deliberately small enough to read in one sitting, because out there
YOU are the one maintaining it.

THE JAIL: every file tool resolves its path inside AGENT_ROOT and refuses
to step outside (symlinks included). Point AGENT_ROOT at the sacrificial
scratch SSD (e.g. /mnt/agent-ssd/work) and the agent can shred its own
sandbox all day without touching the archive.

THE JAIL IS A SEATBELT, NOT A PRISON — read this part:
run_python() executes real code with your user's real permissions. A
hallucinated `shutil.rmtree(os.path.expanduser("~"))` is NOT stopped by
path checks on the file tools. The threat model here is a small model
being clumsy, not an adversary. So: run this as an unprivileged user,
keep AGENT_ROOT on the drive you can afford to lose, review code before
promoting it out of the sandbox, and keep backups (manifest §15). True
sandboxing of arbitrary code needs OS-level isolation (a container, a
separate user, a separate machine) — a starter script cannot give you
that, and pretending otherwise would be worse than saying it plainly.

EXAMPLES: EXAMPLES_DIR is a read-only shelf of known-good snippets
(MicroPython, GPIO, VE.Direct...). The system prompt tells the model to
read an example before writing similar code — a 4B model copying a good
pattern beats a 4B model improvising. Same idea as the seed_qa corpus
(02_CORPORA/seed_qa): worked answers distilled from bigger models get
RETRIEVED, not re-derived.

SCOPE: this agent writes code. It does not answer questions — questions
go through safety_router.py and the Oracle. Do not wire this to the radio.

Usage:
    python pi_agent.py "write micropython for a pico that blinks the LED"
    (set AGENT_MODEL in the config block first; it ships disabled)
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    import requests
except ImportError:
    print("requests missing. Run:  pip install -r requirements.txt", file=sys.stderr)
    sys.exit(2)

import context_meter

# ----------------------------- CONFIG ---------------------------------------
OLLAMA_URL = "http://127.0.0.1:11434"
AGENT_MODEL = None            # None = disabled (safe default).
                              # Good picks: "qwen2.5-coder:7b" (Tier 1) or
                              # "qwen2.5-coder:3b" (Pi 5, slow but works).
AGENT_ROOT = Path(__file__).resolve().parent / "agent_scratch"
                              # ^ CHANGE THIS to the scratch SSD mount on the
                              # Pi, e.g. Path("/mnt/agent-ssd/work")
EXAMPLES_DIR = Path(__file__).resolve().parent / "agent_examples"
MAX_STEPS = 12                # hard ceiling per task
RUN_TIMEOUT_S = 30            # run_python wall-clock limit
MAX_TOOL_OUTPUT = 2000        # chars of tool output fed back to the model
AGENT_NUM_CTX = "auto"        # "auto" = size it from the model's trained
                              # window and the RAM actually free right now
                              # (see context_meter.recommend_ctx), or pin an
                              # integer. Context window REQUESTED from Ollama.
                              # Set
                              # explicitly on purpose: Ollama's own default is
                              # much smaller than most models support, and an
                              # agent loop fills a window fast. Too small and
                              # early steps get silently dropped mid-task; too
                              # large and the KV cache eats RAM a Pi does not
                              # have. Run context_meter.py for your real
                              # numbers, then tune this and measure.
MAX_FILE_BYTES = 256_000      # per-file cap: a looping model can't fill the SSD
TRANSCRIPT = Path("agent_transcript.jsonl")   # full audit log, one JSON/line
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a careful coding agent on an off-grid Raspberry Pi.
You work in small steps: write a file, run it, read the error, fix it.

Reply with EXACTLY ONE JSON object and nothing else, in this shape:
{"thought": "one sentence of plan", "tool": "<name>", "args": {...}}

Tools:
- list_files {}                          list sandbox files and the example shelf
- read_example {"name": "..."}           read a known-good example. DO THIS before
                                         writing similar code — copy good patterns.
- read_file {"path": "..."}              read a sandbox file
- write_file {"path": "...", "content": "..."}   create/overwrite a sandbox file
- run_python {"path": "..."}             run a sandbox .py here with CPython.
                                         NOTE: MicroPython code for a Pico will
                                         NOT run here (no `machine` module). For
                                         those: write the file, then call done()
                                         and say it needs on-device testing.
- done {"summary": "..."}                finish and report what you built

All paths are relative to your sandbox. You cannot touch anything outside it.
Keep files small. Test what is testable. Do not invent hardware pinouts — if a
pinout is not in an example, say so in your done() summary instead of guessing."""


# ------------------------------- the jail -----------------------------------

def _jailed(rel_path: str) -> Path:
    """Resolve a path INSIDE the sandbox or refuse. resolve() flattens
    ../ tricks and symlinks before the containment check."""
    root = AGENT_ROOT.resolve()
    p = (root / str(rel_path)).resolve()
    if p != root and not p.is_relative_to(root):
        raise ValueError(f"path escapes the sandbox: {rel_path!r}")
    return p


# ------------------------------- the tools ----------------------------------

def t_list_files() -> str:
    lines = ["SANDBOX:"]
    found = False
    for p in sorted(AGENT_ROOT.rglob("*")):
        if p.is_file():
            lines.append(f"  {p.relative_to(AGENT_ROOT).as_posix()}"
                         f"  ({p.stat().st_size} B)")
            found = True
    if not found:
        lines.append("  (empty)")
    lines.append("EXAMPLES (read-only, via read_example):")
    if EXAMPLES_DIR.is_dir():
        for p in sorted(EXAMPLES_DIR.glob("*.py")):
            lines.append(f"  {p.name}")
    return "\n".join(lines)


def t_read_file(path: str) -> str:
    p = _jailed(path)
    if p.is_file() and p.stat().st_size > MAX_FILE_BYTES:
        return (f"TOOL ERROR: {path} is {p.stat().st_size} B — too big to "
                f"read whole (cap {MAX_FILE_BYTES}). Work in smaller files.")
    return p.read_text(encoding="utf-8")


def t_write_file(path: str, content: str) -> str:
    if len(str(content).encode("utf-8")) > MAX_FILE_BYTES:
        return (f"TOOL ERROR: content exceeds {MAX_FILE_BYTES} B — "
                f"split the work into smaller files.")
    target = _jailed(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"wrote {len(content)} chars to {path}"


def t_read_example(name: str) -> str:
    p = EXAMPLES_DIR / Path(str(name)).name        # flat shelf, no traversal
    if not p.is_file():
        return "TOOL ERROR: no such example. Call list_files to see the shelf."
    return p.read_text(encoding="utf-8")


def t_run_python(path: str) -> str:
    target = _jailed(path)
    if not target.is_file():
        return f"TOOL ERROR: no such file: {path}"
    try:
        # -I = isolated mode: ignores user site-packages and env vars, so the
        # run is a little more predictable. cwd is the sandbox.
        p = subprocess.run([sys.executable, "-I", str(target)],
                           cwd=AGENT_ROOT, capture_output=True, text=True,
                           timeout=RUN_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        return f"TOOL ERROR: timed out after {RUN_TIMEOUT_S}s (infinite loop?)"
    out = (f"exit={p.returncode}\n"
           f"stdout:\n{p.stdout or '(empty)'}\n"
           f"stderr:\n{p.stderr or '(empty)'}")
    return out


TOOLS = {
    "list_files": t_list_files,
    "read_file": t_read_file,
    "write_file": t_write_file,
    "read_example": t_read_example,
    "run_python": t_run_python,
}


# ------------------------------- the loop -----------------------------------

_num_ctx = 8192      # resolved at task start; _chat sends it to Ollama


def _chat(messages: list) -> tuple:
    """Returns (content, prompt_tokens, generated_tokens). The counts come
    from Ollama itself, so they are exact rather than estimated."""
    r = requests.post(f"{OLLAMA_URL}/api/chat",
                      json={"model": AGENT_MODEL, "messages": messages,
                            "stream": False,
                            "options": {"temperature": 0.2,
                                        "num_ctx": _num_ctx}},
                      timeout=600)
    r.raise_for_status()
    data = r.json()
    used, made = context_meter.usage_from_response(data)
    return data["message"]["content"], used, made


def _extract_json(text: str) -> dict:
    """Small models love wrapping JSON in prose or ``` fences. Take the
    outermost {...} and parse that."""
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object found in reply")
    return json.loads(text[start:end + 1])


def _log(entry: dict) -> None:
    entry["ts"] = datetime.now().isoformat(timespec="seconds")
    with open(TRANSCRIPT, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def run_task(task: str) -> None:
    AGENT_ROOT.mkdir(parents=True, exist_ok=True)
    limits = context_meter.model_limits(AGENT_MODEL, OLLAMA_URL)
    if AGENT_NUM_CTX == "auto":
        rec = context_meter.recommend_ctx(AGENT_MODEL, OLLAMA_URL)
        ctx_limit = rec["recommended"] or 8192
        note = rec.get("why", "")
    else:
        ctx_limit = int(AGENT_NUM_CTX)
        note = "pinned in the config block"
    globals()["_num_ctx"] = ctx_limit
    print(f"Sandbox: {AGENT_ROOT}")
    print(f"Context: {context_meter.human(ctx_limit)}"
          + (f" of a {context_meter.human(limits['trained'])} model"
             if limits["trained"] else "")
          + (f"   ({note})" if note else ""))
    if limits["trained"] and ctx_limit > limits["trained"]:
        print("  NOTE: that is more than this model was trained for.")
    print(f"Task:    {task}\n")
    _log({"event": "task_start", "task": task, "model": AGENT_MODEL})

    msgs = [{"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"TASK: {task}"}]

    for step in range(1, MAX_STEPS + 1):
        try:
            content, ctx_used, ctx_made = _chat(msgs)
        except requests.RequestException as e:
            print(f"Ollama unreachable ({e}). Is `ollama serve` running?",
                  file=sys.stderr)
            return
        msgs.append({"role": "assistant", "content": content})
        _log({"event": "model", "step": step, "content": content,
              "ctx_used": ctx_used, "ctx_limit": ctx_limit})

        # Context readout every step. History accumulates fast here, and past
        # the window Ollama drops the OLDEST messages first — which in an agent
        # loop means the task description itself. Stop rather than continue
        # working amnesiac.
        total = ctx_used + ctx_made
        print(f"      ctx {context_meter.readout(total, ctx_limit)}")
        if ctx_limit and total >= ctx_limit * context_meter.FULL_AT:
            print("")
            print(f"STOPPING at step {step}: context is nearly full. Going on "
                  f"would silently drop the start of this task, including the "
                  f"task itself. Whatever exists so far is in {AGENT_ROOT}. "
                  f"Either raise AGENT_NUM_CTX (watch RAM) or restart with a "
                  f"smaller, more specific task.")
            _log({"event": "context_stop", "step": step, "used": total,
                  "limit": ctx_limit})
            return

        try:
            action = _extract_json(content)
            tool = action.get("tool")
            args = action.get("args") or {}
        except (ValueError, json.JSONDecodeError) as e:
            feedback = (f"TOOL ERROR: your reply was not one valid JSON "
                        f"object ({e}). Reply with exactly one JSON object.")
            msgs.append({"role": "user", "content": feedback})
            print(f"[{step}] (reply was not valid JSON — asked again)")
            continue

        thought = str(action.get("thought", ""))[:100]
        print(f"[{step}] {tool}  {json.dumps(args)[:110]}")
        if thought:
            print(f"      ↳ {thought}")

        if tool == "done":
            summary = str(args.get("summary", "(no summary)"))
            print(f"\nDONE: {summary}")
            _log({"event": "done", "step": step, "summary": summary})
            print(f"Files are in {AGENT_ROOT}. Review before using anywhere real.")
            return

        fn = TOOLS.get(str(tool))
        if fn is None:
            result = f"TOOL ERROR: unknown tool {tool!r}. Tools: {list(TOOLS)}"
        else:
            try:
                result = str(fn(**args))
            except Exception as e:   # bad args, jail refusal, IO errors —
                result = f"TOOL ERROR: {type(e).__name__}: {e}"   # feed back

        result = result[:MAX_TOOL_OUTPUT]
        msgs.append({"role": "user", "content": f"TOOL RESULT:\n{result}"})
        _log({"event": "tool", "step": step, "tool": tool, "result": result})
        time.sleep(0.1)   # be gentle to a Pi

    print(f"\nStep limit ({MAX_STEPS}) reached without done(). "
          f"Inspect {TRANSCRIPT} and the sandbox to see where it wandered.")


def main():
    if AGENT_MODEL is None:
        print("pi_agent is DISABLED (AGENT_MODEL=None), on purpose.\n"
              "To enable: pull a coder model in Ollama (e.g. "
              "`ollama pull qwen2.5-coder:3b`),\n"
              "set AGENT_MODEL in the config block, and point AGENT_ROOT at "
              "the scratch SSD.\nRead the docstring first — especially the "
              "seatbelt-not-a-prison part.")
        sys.exit(2)
    if len(sys.argv) < 2:
        print('Usage: python pi_agent.py "task description"')
        sys.exit(1)
    run_task(" ".join(sys.argv[1:]))


if __name__ == "__main__":
    main()
