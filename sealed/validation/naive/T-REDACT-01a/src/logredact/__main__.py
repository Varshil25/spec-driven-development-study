# Naive variant A: the regexes most tutorials give, applied with re.sub.
import re, sys
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
IP = re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b")
CARD = re.compile(r"\b\d(?:[ -]?\d){12,18}\b")

def luhn(d):
    s = 0
    for i, c in enumerate(reversed(d)):
        n = int(c) * (2 if i % 2 else 1)
        s += n - 9 if n > 9 else n
    return s % 10 == 0

counts = {"emails": 0, "ips": 0, "cards": 0}
def card(m):
    d = re.sub(r"\D", "", m.group())
    if luhn(d):
        counts["cards"] += 1
        return "[CARD]"
    return m.group()
def email(m):
    counts["emails"] += 1; return "[EMAIL]"
def ip(m):
    counts["ips"] += 1; return "[IP]"

def redact(line):
    return IP.sub(ip, CARD.sub(card, EMAIL.sub(email, line)))

args = sys.argv[1:]
show = "--count" in args
files = [a for a in args if a != "--count"]
if not files:
    for line in sys.stdin:
        sys.stdout.write(redact(line))
for f in files:
    try:
        with open(f) as fh:
            for line in fh:
                sys.stdout.write(redact(line))
    except OSError:
        print("error: cannot read " + f, file=sys.stderr)
        sys.exit(2)
    if show:
        print("emails=%d ips=%d cards=%d" % (counts["emails"], counts["ips"], counts["cards"]), file=sys.stderr)
if show and not files:
    print("emails=%d ips=%d cards=%d" % (counts["emails"], counts["ips"], counts["cards"]), file=sys.stderr)
