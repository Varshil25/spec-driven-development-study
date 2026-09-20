"""Entry point enabling `python -m splitter`.

Delegates to :func:`splitter.cli.main`, passing its return value to the process
exit code so validation/I-O failures surface as a non-zero status.
"""

import sys

from splitter.cli import main

if __name__ == "__main__":
    sys.exit(main())
