# T-BOOKMARKS-01-CR: answer sheet (change request)

Read `README.md` in this folder first. Reply verbatim. The entries of
`T-BOOKMARKS-01.md` still apply, including to imported bookmarks.

| Entry | The agent asks about... | Reply (verbatim) |
| --- | --- | --- |
| I1 | bookmarks in the import file whose URL is already in the database, or appears twice in the file | Skip them: keep the existing bookmark unchanged, and don't count them in `imported N`. |
| I2 | a row or entry in the import file that `add` would reject (for example a bad URL or a title with a tab) | Skip that one, print a warning saying which one it was to standard error, import the rest, and exit with status 2 at the end. |
| I3 | HTML export of a bookmark with an empty title | Use the URL as the link text. |
