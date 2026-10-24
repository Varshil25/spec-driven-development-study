# T-REDACT-01: answer sheet

Read `README.md` in this folder first. Reply verbatim.

| Entry | The agent asks about... | Reply (verbatim) |
| --- | --- | --- |
| I1 | what to do when one of several files cannot be read (stop, or carry on?) | Keep going: process the remaining files, report each unreadable file on standard error, and exit with status 2 at the end. |
| I2 | how `--count` works with several files (per file, or one total?) | One summary line for the whole run, with totals across all inputs. |
| I3 | dotted numbers with more than four parts, such as `1.2.3.4.5` | That's a version number, not an IP address. Leave the whole thing unchanged. |
| I4 | digit runs longer than 19 digits, or card numbers inside longer numbers | A run of more than 19 digits is not a card number, even if part of it would pass the Luhn check. Leave it unchanged. |
