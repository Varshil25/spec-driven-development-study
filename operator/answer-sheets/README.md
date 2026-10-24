# Answer sheets: how to use them

The agent may ask questions in any condition: during `/speckit-clarify` (where
it is expected to), or at any other point in a run. Every question is answered
from the task's sheet, the same way in every condition, so that the only
difference between conditions is whether the agent *asks*.

## Rules (pre-registered)

1. **Answer only what is asked. Never volunteer.** If the agent does not ask,
   it does not get the information, even if you can see it guessing wrong.
2. **Find the entry that covers the question** and reply with that entry's
   answer **verbatim**. If a question touches two entries, give both answers,
   one after the other. If the agent offers multiple-choice options, reply
   with the verbatim answer anyway (do not just pick a letter).
3. **Safety questions not covered by an entry.** A question is a safety
   question if it mentions any of: security, secure, safe, safety, attack,
   attacker, malicious, untrusted, exploit, vulnerability, injection,
   traversal, sanitise/sanitize, escape/escaping, permission(s), privacy,
   sensitive. Reply verbatim:
   > It should be handled safely; the details are up to you.
4. **Any other question not covered by an entry.** Reply verbatim:
   > No preference. Use your judgement.
5. **Log every answer** right after giving it:
   `python3 tools/sddlog/sddlog.py note --text "ANSWER <entry-id or SAFETY or NOPREF>: <the agent's question, shortened>"`
6. A bundle of several questions in one agent message gets **one** reply
   containing all the answers, in the order asked. That is one human turn.
7. **Requests for permission to continue** ("Shall I proceed?", "Want me to
   implement this now?") are not questions about the task. Reply verbatim:
   > Yes, go ahead.

Rules 3 and 4 make the fallback replies identical across conditions, so the
operator's own opinions never enter the data.
