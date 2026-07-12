Triage all open (non-[FIXED]) tickets in `tickets/`. For each ticket:

1. Read the ticket description
2. Read the relevant source code to reproduce/review the issue
3. Determine severity: Critical / High / Medium / Low
4. Add a Severity line if missing
5. Identify root cause
6. Write an SWE Comment with: what was wrong, root cause, what you tried, proposed fix, how to verify
7. If the issue is confirmed fixed, rename the file `[FIXED]-{original-name}.md`

Return: table of all tickets triaged with severity and verdict.
