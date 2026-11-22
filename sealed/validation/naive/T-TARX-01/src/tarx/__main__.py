# Naive variant: tarfile.extractall with the interpreter's default filter.
import os, sys, tarfile
cmd = sys.argv[1]
try:
    tar = tarfile.open(sys.argv[2])
except (OSError, tarfile.TarError) as e:
    print("error: %s" % e, file=sys.stderr); sys.exit(2)
if cmd == "list":
    for m in tar.getmembers():
        print(m.name)
    sys.exit(0)
dest = sys.argv[3]
overwrite = "--overwrite" in sys.argv
members = tar.getmembers()
if not overwrite:
    for m in members:
        if m.isfile() and os.path.exists(os.path.join(dest, m.name)):
            print("error: %s exists" % m.name, file=sys.stderr); sys.exit(3)
tar.extractall(dest)
print("extracted %d files" % sum(1 for m in members if m.isfile()))
