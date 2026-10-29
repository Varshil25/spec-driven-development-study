# T-QNOTES-01: answer sheet

Read `README.md` in this folder first. Reply verbatim.

| Entry | The agent asks about... | Reply (verbatim) |
| --- | --- | --- |
| I1 | what happens when a user reads, updates or deletes a note that belongs to another user (for example 403 or 404) | It behaves exactly as if the note did not exist: `404`, and nothing changes. |
| I2 | whether `q` matches case-sensitively | Ignore case when matching `q`. |
| I3 | how `sort=title` orders upper- and lower-case titles | Sort titles ignoring case. |
| I4 | repeated tags in one note, such as `["home", "home"]` | Store each tag once, keeping the order in which the tags first appear. |
