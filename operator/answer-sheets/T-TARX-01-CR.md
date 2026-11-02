# T-TARX-01-CR: answer sheet (change request)

Read `README.md` in this folder first. Reply verbatim. The entries of
`T-TARX-01.md` still apply to `list` and `extract`.

| Entry | The agent asks about... | Reply (verbatim) |
| --- | --- | --- |
| I1 | the order of members in a created archive | Add them sorted by their full member path, compared as text (for example `d/a.txt`, `d/b/c.txt`, `d/z.txt`), so the same files always give the same archive. A directory comes before the files inside it. |
| I2 | empty directories | Include them as directory entries, so extracting the archive recreates them. |
| I3 | hidden files (names starting with a dot) | Include them like any other file. |
