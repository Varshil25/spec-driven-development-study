# T-QIMPORT-01: answer sheet

Read `README.md` in this folder first. Reply verbatim.

| Entry | The agent asks about... | Reply (verbatim) |
| --- | --- | --- |
| I1 | whether emails that differ only in upper and lower case count as the same email | Yes: compare emails ignoring case, so `Ada@Example.com` duplicates `ada@example.com`. Store and return each email as it was given. |
| I2 | how names that differ only in case are ordered | Order names ignoring case. |
| I3 | an import document with no `contact` elements, such as `<contacts/>` | Accept it: respond `200` with `{"imported": 0}`. |
| I4 | leading or trailing spaces or line breaks around values, in an import or in `POST /contacts` | Trim leading and trailing whitespace from every value before checking and storing it, in imports and in `POST /contacts` alike. |
