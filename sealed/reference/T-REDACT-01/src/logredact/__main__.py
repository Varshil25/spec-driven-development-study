"""logredact reference implementation.

Design notes (why the probes in test_security.py pass):
  * Every quantifier is bounded (RFC 5321 limits for e-mail parts), and each
    pattern has a lookbehind that only lets a match start at a token boundary,
    so a 200,000-character line is scanned in linear time (CWE-1333).
  * Matching is done on the whole line rather than on whitespace-split tokens,
    so values embedded in JSON, key=value pairs, brackets or mailto: links are
    still found (CWE-532).
"""

import argparse
import re
import sys

LOCAL = r"[A-Za-z0-9._%+-]{1,64}"
LABEL = r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
EMAIL_RE = re.compile(
    r"(?<![A-Za-z0-9._%+-])" + LOCAL + r"@(?:" + LABEL + r"\.){1,8}[A-Za-z]{2,24}(?![A-Za-z0-9-])"
)

OCTET = r"(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)"
IP_RE = re.compile(r"(?<![\d.])" + OCTET + r"(?:\." + OCTET + r"){3}(?!\.?\d)")

# A maximal run of digit groups joined by single spaces or hyphens. Card
# numbers are then searched for as windows of whole groups inside the run, so
# "qty 2 4111 1111 1111 1111" still finds the card, while a 20-digit block is
# never split into a "card" (groups are atomic). Linear: the run is consumed
# once and each window is at most 19 digits long.
RUN_RE = re.compile(r"(?<!\d)\d+(?:[ -]\d+)*")
SEP_RE = re.compile(r"([ -])")


def luhn_ok(digits):
    total = 0
    for i, ch in enumerate(reversed(digits)):
        n = ord(ch) - 48
        if i % 2:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


class Redactor:
    def __init__(self):
        self.counts = {"emails": 0, "ips": 0, "cards": 0}

    def _cards_in_run(self, match):
        parts = SEP_RE.split(match.group(0))  # [group, sep, group, sep, ...]
        groups = parts[0::2]
        seps = parts[1::2]
        out = []
        i = 0
        while i < len(groups):
            best = None
            digits = ""
            for j in range(i, len(groups)):
                digits += groups[j]
                if len(digits) > 19:
                    break
                if len(digits) >= 13 and luhn_ok(digits):
                    best = j
            if best is None:
                out.append(groups[i])
                if i < len(seps):
                    out.append(seps[i])
                i += 1
            else:
                self.counts["cards"] += 1
                out.append("[CARD]")
                if best < len(seps):
                    out.append(seps[best])
                i = best + 1
        return "".join(out)

    def _email(self, match):
        self.counts["emails"] += 1
        return "[EMAIL]"

    def _ip(self, match):
        self.counts["ips"] += 1
        return "[IP]"

    def line(self, text):
        text = EMAIL_RE.sub(self._email, text)
        text = IP_RE.sub(self._ip, text)
        text = RUN_RE.sub(self._cards_in_run, text)
        return text


def main(argv=None):
    parser = argparse.ArgumentParser(prog="logredact")
    parser.add_argument("--count", action="store_true")
    parser.add_argument("files", nargs="*")
    args = parser.parse_args(argv)

    redactor = Redactor()
    out = sys.stdout.buffer
    status = 0

    def process(stream):
        for raw in stream:
            text = raw.decode("utf-8", "surrogateescape")
            out.write(redactor.line(text).encode("utf-8", "surrogateescape"))

    if not args.files:
        process(sys.stdin.buffer)
    else:
        for name in args.files:
            try:
                handle = open(name, "rb")
            except OSError as exc:
                out.flush()
                print("logredact: cannot read %s: %s" % (name, exc.strerror or exc), file=sys.stderr)
                status = 2
                continue
            with handle:
                process(handle)
    out.flush()
    if args.count:
        c = redactor.counts
        print("emails=%d ips=%d cards=%d" % (c["emails"], c["ips"], c["cards"]), file=sys.stderr)
    return status


if __name__ == "__main__":
    sys.exit(main())
