#!/usr/bin/env python3
"""A stand-in for `claude -p ... --output-format json`, for testing run_build.py.

It never calls a model. It answers from the message it is given:
  * a message containing "ASK-ME" gets back a question;
  * the task text of T-FAKE-01 / T-FAKE-01-CR, or "/speckit-implement", makes it
    write src/fakepkg/__main__.py (with a bug if FAKE_BUG is set, until it is
    sent the checker's follow-up);
  * anything else gets "Done.".
FAKE_FAIL_ONCE=<file> makes the first call fail as a usage limit would.
Every call is appended to FAKE_CALLS as one JSON line.
"""

import json
import os
import sys
import uuid
from pathlib import Path


def main(argv):
    message = argv[argv.index("-p") + 1]
    session = argv[argv.index("--resume") + 1] if "--resume" in argv else "sess-" + uuid.uuid4().hex[:8]
    with open(os.environ["FAKE_CALLS"], "a") as handle:
        handle.write(json.dumps({"argv": argv, "message": message, "session": session}) + "\n")

    fail_flag = os.environ.get("FAKE_FAIL_ONCE")
    if fail_flag and not Path(fail_flag).exists():
        Path(fail_flag).write_text("failed once")
        print(json.dumps({"is_error": True, "result": "Claude usage limit reached", "session_id": session}))
        return 1

    if "ASK-ME" in message:
        result = "Before I continue: should names be case-sensitive?"
    elif "Build fakepkg" in message or "CR-FEATURE" in message or message.startswith("/speckit-implement") \
            or message.startswith("I ran the examples") or message.startswith("Please continue"):
        buggy = os.environ.get("FAKE_BUG") and not message.startswith("I ran the examples")
        if os.environ.get("FAKE_BUG") == "always":
            buggy = True
        greeting = "helo" if buggy else "hello"
        extra = "\n    if '--cr' in sys.argv: print('changed')" if "CR-FEATURE" in message else ""
        pkg = Path("src/fakepkg")
        pkg.mkdir(parents=True, exist_ok=True)
        (pkg / "__init__.py").write_text("")
        (pkg / "__main__.py").write_text(
            "import sys\nif __name__ == '__main__':%s\n    print('%s')\n" % (extra, greeting))
        result = "I implemented it. All done."
    else:
        result = "Done."
    print(json.dumps({"is_error": False, "result": result, "session_id": session,
                      "total_cost_usd": 0.01, "duration_api_ms": 1200,
                      "usage": {"output_tokens": 7}}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
