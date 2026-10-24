# T-PASTE-01: answer sheet

Read `README.md` in this folder first. Reply verbatim.

| Entry | The agent asks about... | Reply (verbatim) |
| --- | --- | --- |
| I1 | whether empty content is allowed | Not allowed: an empty content string gets 400. |
| I2 | whitespace, trailing newlines, or normalising the content | Store and return the content exactly as given, byte for byte, including leading and trailing whitespace and newlines. |
| I3 | `"expires_in": null` | Treat null the same as leaving `expires_in` out: the paste never expires. |
