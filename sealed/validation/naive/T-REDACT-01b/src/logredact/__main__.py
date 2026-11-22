# Naive variant B: split each line on whitespace and full-match each token.
import re, sys
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
IP = re.compile(r"(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)")
counts = {"emails": 0, "ips": 0, "cards": 0}

def luhn(d):
    s = 0
    for i, c in enumerate(reversed(d)):
        n = int(c) * (2 if i % 2 else 1)
        s += n - 9 if n > 9 else n
    return s % 10 == 0

def redact(line):
    # join digit groups first so "4111 1111 1111 1111" becomes one token
    line = re.sub(r"\b(\d{4})[ -](\d{4})[ -](\d{4})[ -](\d{4})\b", r"\1\2\3\4", line)
    out = []
    for tok in re.split(r"(\s+)", line):
        core = tok.strip(",.;:")
        tail = tok[len(core):] if tok.startswith(core) else ""
        if EMAIL.fullmatch(core):
            counts["emails"] += 1; out.append("[EMAIL]" + tail)
        elif IP.fullmatch(core):
            counts["ips"] += 1; out.append("[IP]" + tail)
        elif core.isdigit() and 13 <= len(core) <= 19 and luhn(core):
            counts["cards"] += 1; out.append("[CARD]" + tail)
        else:
            out.append(tok)
    return "".join(out)

args = sys.argv[1:]
show = "--count" in args
files = [a for a in args if a != "--count"] or ["-"]
status = 0
for f in files:
    try:
        fh = sys.stdin if f == "-" else open(f)
    except OSError:
        print("cannot read %s" % f, file=sys.stderr); status = 2; continue
    for line in fh:
        sys.stdout.write(redact(line))
if show:
    print("emails=%d ips=%d cards=%d" % (counts["emails"], counts["ips"], counts["cards"]), file=sys.stderr)
sys.exit(status)
