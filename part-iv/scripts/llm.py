"""llm.py: the only place a model is called (ai_specs/batch-process.md, "LLM access and cost").

Backends:
  claude    - Claude Code CLI in headless mode (default); uses the author's subscription
  anthropic - Anthropic Messages API with ANTHROPIC_API_KEY (from the environment or .env)
Select with SDKDP_BACKEND; the model with SDKDP_MODEL.
"""

import json
import os
import subprocess
import urllib.request
from pathlib import Path

BACKEND = os.environ.get("SDKDP_BACKEND", "claude")
MODEL = os.environ.get("SDKDP_MODEL", "claude-sonnet-5-5")


class LLMError(RuntimeError):
    pass


def _dotenv():
    env = Path(__file__).resolve().parents[1] / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())


def complete(system, prompt, max_tokens=4000):
    """Return (text, model_id) for one completion."""
    if BACKEND == "anthropic":
        _dotenv()
        key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("LLM_API_KEY")
        if not key:
            raise LLMError("ANTHROPIC_API_KEY not set")
        body = json.dumps({"model": MODEL, "max_tokens": max_tokens, "system": system,
                           "messages": [{"role": "user", "content": prompt}]}).encode()
        req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body, headers={
            "x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=600) as resp:
                data = json.loads(resp.read())
        except Exception as exc:
            raise LLMError(str(exc)) from exc
        return "".join(b.get("text", "") for b in data["content"]), data.get("model", MODEL)
    # Claude Code CLI: no tools, no session persistence, the system prompt replaced.
    cmd = ["claude", "-p", "--model", MODEL, "--output-format", "json", "--tools", "",
           "--no-session-persistence", "--system-prompt", system]
    proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=1200)
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        raise LLMError((proc.stderr or proc.stdout)[-500:])
    if data.get("is_error") or proc.returncode != 0:
        raise LLMError(str(data.get("result") or proc.stderr)[-500:])
    models = list((data.get("modelUsage") or {}).keys())
    return data["result"], (models[0] if models else MODEL)
