import os, re, sys

EMAIL = re.compile((r"(?<![\w.%-])" if os.environ.get("ALT_EMAIL_LB") else r"(?<![\w.%+-])")
    + r"[\w.%+-]{1,64}@[A-Za-z0-9-]{1,63}(?:\.[A-Za-z0-9-]{1,63}){1,8}")
if os.environ.get("ALT_EMAIL_UNB"):
    EMAIL = re.compile(r"(?<![\w.%-])[\w.%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
IP = re.compile(r"(?<![\d.])(?:(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\.){3}(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(?![\d]|\.\d)")
PHONE = re.compile(r"(?<![\w+])\+\d{8,15}(?!\d)")
CARD = re.compile(r"(?<![\d-])\d(?:[ -]?\d){12,18}(?![\d])")

def luhn(d):
    t = 0
    for i, c in enumerate(reversed(d)):
        n = int(c)
        if i % 2:
            n *= 2
            if n > 9: n -= 9
        t += n
    return t % 10 == 0

counts = dict(emails=0, ips=0, cards=0, phones=0)

def red(line):
    def e(m): counts["emails"] += 1; return "[EMAIL]"
    def p(m): counts["phones"] += 1; return "[PHONE]"
    def i(m): counts["ips"] += 1; return "[IP]"
    def c(m):
        d = re.sub(r"[ -]", "", m.group(0))
        if luhn(d):
            counts["cards"] += 1; return "[CARD]"
        return m.group(0)
    line = EMAIL.sub(e, line)
    line = PHONE.sub(p, line)
    line = IP.sub(i, line)
    line = CARD.sub(c, line)
    return line

def write_out(path, text):
    # Alternative safe choice: remove whatever is there, then create exclusively.
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o644)
    with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
        f.write(text)

def main():
    args = sys.argv[1:]
    count = False; out_dir = None; files = []
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--count": count = True
        elif a == "--out-dir": i += 1; out_dir = args[i]
        elif a.startswith("--out-dir="): out_dir = a.split("=", 1)[1]
        else: files.append(a)
        i += 1
    status = 0
    if out_dir is not None:
        if not files:
            sys.stderr.write("error: --out-dir requires FILE arguments\n"); return 2
        os.makedirs(out_dir, exist_ok=True)
        n = 0
        for f in files:
            try:
                with open(f, encoding="utf-8", errors="surrogateescape", newline="") as h:
                    text = "".join(red(l) for l in h)
            except OSError:
                sys.stderr.write("error: %s: cannot read\n" % f); status = 2
                if os.environ.get("ALT_STOP"): return 2
                continue
            write_out(os.path.join(out_dir, os.path.basename(f)), text); n += 1
        if status and os.environ.get("ALT_NOSUMMARY_ON_ERR"): return status
        print("wrote %d file%s" % (n, "" if n == 1 else "s") if os.environ.get("ALT_SINGULAR") else "wrote %d files" % n)
    else:
        if not files:
            for l in sys.stdin: sys.stdout.write(red(l))
        for f in files:
            try:
                with open(f, encoding="utf-8", errors="surrogateescape", newline="") as h:
                    for l in h: sys.stdout.write(red(l))
            except OSError:
                sys.stdout.flush(); sys.stderr.write("error: %s: cannot read\n" % f); status = 2
    if count:
        sys.stderr.write("emails=%(emails)d ips=%(ips)d cards=%(cards)d phones=%(phones)d\n" % counts)
    return status

sys.exit(main())
