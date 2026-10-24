Build a command-line tool that reads a CSV file of shared group expenses and prints who owes whom in order to settle up. The CSV has a header row with columns payer, amount, description. The participant list is supplied separately as a comma-separated argument. Every participant owes an equal share of the group total. The tool computes each person's net balance and prints a minimal list of payments that settles every balance to zero. All money is handled in whole cents and rounding must never lose or invent money: the payments printed must sum exactly to the total imbalance. Malformed input (missing file, unknown payer not in the participant list, non-numeric or negative amount, empty participant list) must produce a clear error on stderr and a non-zero exit code. Python 3, standard library only.

Run it as `python -m splitter EXPENSES.csv --participants NAMES`, with the package `splitter` under `src/`. Each payment is printed on its own line as `PAYER pays PAYEE AMOUNT`, with the amount to two decimal places.

Examples, where `trip.csv` contains a header row and the single row `Alice,30.00,Hotel`:

```
$ python -m splitter trip.csv --participants Alice,Bob
Bob pays Alice 15.00

$ python -m splitter missing.csv --participants Alice,Bob
(an error message on standard error; a non-zero exit status)
```
