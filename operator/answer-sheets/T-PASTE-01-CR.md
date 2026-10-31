# T-PASTE-01-CR: answer sheet (change request)

Read `README.md` in this folder first. Reply verbatim. The entries of
`T-PASTE-01.md` still apply to behaviour the change request does not touch.

| Entry | The agent asks about... | Reply (verbatim) |
| --- | --- | --- |
| I1 | a paste with both `burn_after_reading` and `expires_in` | Both apply: the paste disappears at whichever comes first. |
| I2 | whether the `201` response to `POST /pastes` should also show the new options | Yes: include `"burn_after_reading"` and `"protected"` in the `201` response too. |
| I3 | whether passwords are case-sensitive | Yes. The password must match exactly, including upper and lower case. |
