# T-TARX-01: answer sheet

Read `README.md` in this folder first. Reply verbatim.

| Entry | The agent asks about... | Reply (verbatim) |
| --- | --- | --- |
| I1 | what to do when DEST does not exist | Create it, including any missing parent directories. |
| I2 | what happens to files already extracted when a conflict is found (partial extraction?) | Check for conflicts before writing anything. If any file would be overwritten, extract nothing at all and exit with status 3. |
| I3 | whether to keep timestamps / file metadata | Keep each file's modification time from the archive. |
