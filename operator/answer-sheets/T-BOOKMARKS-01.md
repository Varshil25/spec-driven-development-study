# T-BOOKMARKS-01: answer sheet

Read `README.md` in this folder first. Reply verbatim.

| Entry | The agent asks about... | Reply (verbatim) |
| --- | --- | --- |
| I1 | adding a URL that is already bookmarked (duplicates) | Don't create a duplicate. Print the id of the existing bookmark, exit with status 0, and leave the existing bookmark unchanged. |
| I2 | tag case, surrounding spaces, or repeated tags | Tags are case-insensitive. Store them trimmed and in lower case, without duplicates, and match `--tag` case-insensitively. |
| I3 | titles containing tabs or line breaks | Reject them with an error message and exit status 2, because they would break the tab-separated output. |
