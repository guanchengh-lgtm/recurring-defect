# Adversary prompt template

Give this to an independent reviewer: a different model, a colleague, or a subagent with no stake in
the checker. The person who wrote a check cannot see its blind spots, because the blind spots are
made of the same assumptions.

Two rounds minimum. The second round matters as much as the first, because fixes introduce defects —
in the worked example, two of round two's four critical findings were newly created by round one's
repairs.

## Template

> You are a brutally honest technical reviewer. Be direct, terse, adversarial. No compliments. Just
> the problems.
>
> ## What to read
>
> 1. `<path to the checker>`
> 2. `<path to the structure it parses>` — read only the relevant section, not the whole file
> 3. `<path to the derived regression fixture>` and its generator
> 4. `<path to the CI configuration>`
>
> ## Context
>
> `<one paragraph: what defect class this catches, and the evidence that the class is real —
> ideally the loop-gain number or the count of prior occurrences>`
>
> **Everything now rests on this check being correct. If it is wrong, it will report green and be
> trusted anyway. That is the risk you are being paid to find.**
>
> ## Scope — answer each explicitly
>
> `<3-5 specific questions about the parts you are least sure of. Name functions and line numbers.
> Include at least one where you suspect a problem, and at least one where you believe the code is
> right — an adversary that only confirms your worries is not working.>`
>
> ## Hunt hardest for
>
> - Anything that makes this report CLEAN while a real defect of the target class is present.
> - Input that is silently skipped, dropped, or collapsed before it is validated or counted.
> - Whether the regression assertion can pass while the central rule is dead.
> - Whether empty, missing, or malformed input is distinguishable from a clean result.
> - Whether the documentation claims anything the code does not deliver.
> - Regressions introduced by recent fixes that were not present before.
>
> ## Output format
>
> Mark each finding `[P1]` (critical: the checker is wrong, or reports clean while broken) or `[P2]`
> (advisory). Give file:line. Propose the concrete fix.
>
> End your response with a single literal line, exactly:
>
> `VERDICT: <one sentence on whether this check can be trusted as a gate>`

## Re-review rounds

For round two, keep the structure and add:

> This is a RE-REVIEW. You previously returned `<N>` findings and this verdict: `<quote it>`.
> The file has been rewritten. Verify each claimed fix actually holds — do not take any claim on
> trust — and find what the rewrite broke or still misses.
>
> ## Claimed fixes — verify each, one line per item, HELD or NOT HELD
>
> `<numbered list of what you changed and why you believe it works>`

The HELD / NOT HELD format is worth the words. It forces a verdict per claim instead of a general
impression, and it surfaces partial fixes that a prose summary would round up to "fixed."

## Practical notes

- **Demand a literal `VERDICT:` line.** Long reviews get truncated by transport or timeout; a
  missing sentinel makes truncation detectable instead of silent.
- **Write the prompt to a file and point the tool at it**, rather than inlining a long string.
- **Run the reviewer read-only.** It should have no write path to the artifact under review.
- **Do not accept findings on authority.** Two of the strongest findings in the worked example were
  verifiable against the source document in one grep each, and one earlier reviewer suggestion was
  wrong. Check before you act.
- **Track loop gain on the checker too.** If round two introduces roughly as many problems as round
  one closed, stop patching and look for the structural fix — usually generating the data instead of
  hand-maintaining it.
