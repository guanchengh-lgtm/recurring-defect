---
name: recurring-defect
description: Convert a defect that keeps coming back into a mechanical check that catches its whole class forever. Use this whenever a bug, review finding, or mistake has appeared more than once; whenever someone says "this keeps happening", "we fixed this before", "didn't we already solve this", "add a lint rule", "add a CI check", or "how do we stop this recurring"; whenever review or fix rounds keep producing findings without converging; and in any post-mortem where the right fix is systemic rather than another patch. Applies to code, specifications, documentation, configuration and schemas alike.
---

# Recurring defect → mechanical check

A defect that has appeared twice will appear again. Fixing the third instance costs the same as the first two and buys nothing, because the mechanism that produces them is untouched. This skill converts the *class* into a check that runs forever.

The hard part is not writing the rule. It is (a) finding the right thing to check, and (b) knowing the check works. Most of what follows is about (b), because a check nobody has attacked will report all-clear while broken, and a broken check is worse than no check: people trust it.

## When this applies, and when it doesn't

Build machinery when the defect is a **class**. Evidence:

- The same *shape* of problem has appeared two or more times, in different places.
- A review or fix loop is producing findings round after round without converging.
- Someone can describe the mistake as a pattern ("we keep forgetting X when we change Y").

Skip this for a genuine one-off. Machinery has a carrying cost, and a rule that fires once and never again is worse than the fix it replaced.

**If there is loop history, measure it before you decide.** Count findings closed versus findings introduced per round. If a round closes 3 and opens 7, the ratio is 2.33 and the loop is the problem, not the findings — no amount of further patching converges. That single number is often the strongest argument for stopping and building the check.

## Observability fork, then size and form

Deciding *that* it is a class is not the same as deciding *how much* to build or *which form* the
check takes. This is the step most easily skipped and the one that most often makes the method a
bad trade.

**First decide whether the miss is observable in an artifact** — code, a specification, or
CI-visible structure. Size and form come only after that fork. If the miss is not observable there,
**never select lint or CI as the check**, and do **not** pick Full or Light: those sizes assume CI
or in-repo check machinery that cannot see the event.

### Lifecycle-only miss → refuse-hook (not Full/Light CI)

When the miss exists only at a lifecycle event — cleanup, spawn, or done — select a **refuse-hook
at that event**. The hook must refuse the illegal state itself (for example, refuse to spawn a
worker assigned the wrong slice). An optional/skippable flag, a reminder, or an unhooked checklist
is not a hook and is insufficient. A documented routine is allowed only alongside the refuse-hook;
it may cover residual cases the hook cannot see but cannot substitute for refusal at the event.
Name what the hook still cannot observe and measure that residual. Do not claim 100% coverage.
Scale is the hook, residual measurement, optional paired routine, and a claims file — not CI
wiring, not a fixture generator for a gate that cannot observe the event.

### Artifact-observable miss → size Full / Light / Neither, then form

The full method produces a lot: structure, checker, fixture generator, regression assertion, CI
wiring, adversarial rounds. Measured on matched tasks, running it fully cost **3-4x the tokens and
6-12x the wall clock** of a competent ad-hoc fix. On a spec whose review loop had run twenty-three
rounds, that was clearly worth it. On a config check where a good engineer had already produced a
solid answer in a fraction of the time, the extra bought real but marginal findings at twelve times
the cost. Over-building is a failure mode, not thoroughness.

Only after the miss is artifact-observable, pick by blast radius, and pick before step 1:

- **Full method** — the check will gate CI, or the artifact is one that others depend on and cannot
  easily inspect: a specification, a shared schema, a deploy manifest, an interface contract.
  Recurrence is expensive here and a wrong check is worse than none, so the verification steps earn
  their cost.
- **Light** — a recurring annoyance in code you own, where a wrong check costs an afternoon. Do
  steps 1-3 and 5: name the shape, surface the structure, write the rule, fail closed. If a
  historical instance is still reachable in version control, check it out instead of building a
  generator. One fresh reader instead of adversarial rounds.
- **Neither** — one occurrence, or the fix is a one-liner in a place nobody else touches. Do the
  small fix and say why you are not building more.

State which you picked and why, in one line. That lets a reader overrule you cheaply, and it stops
the method running on autopilot — which is the specific way this skill turns into waste.

## Three output forms

Not every class becomes a gate. The observability fork above already decided whether the miss is in
an artifact. Only then select a form: a rule or advisory may inspect that artifact; if the miss is
not observable there, **never select lint or CI as the check**. Decide early, because steps 4–8
apply differently to each, and shipping the wrong form is how checks get ignored or distrusted.

**A rule that gates.** Artifact-observable only. The class is decidable from structure, with few
enough false positives that people accept a red build. Most of this skill assumes this form.

**An advisory rule that reports.** Artifact-observable only. The class is real, but its true
boundary is not cleanly separable from legitimate cases. In the worked example, a rule flagging
unconditional claims ("never", "always", "guaranteed") went from 189 hits to 51 after narrowing —
and many of the 51 were *correct* absolutes. The actual defect was absolutes about runtime
behaviour under failure, which is not lexically separable from absolutes about policy. It shipped
advisory: it turns a 1,300-line document into a 51-line reading list, which is worth having and is
not automation. Say plainly which it is; a noisy rule wired to a gate teaches people to ignore the
gate, and that costs you the good rules too.

**A routine with a refuse-hook.** Use this only when the miss is not observable in an artifact but
an actual lifecycle event is: cleanup, spawn, or done. Refuse-hooks are not a form for
artifact-observable misses. The hook at that event must refuse the illegal state itself (for
example, refuse to spawn a worker assigned the wrong slice). An optional/skippable flag, a
reminder, or an unhooked checklist is not a hook and is insufficient. For every refuse-hook, name
what the hook still cannot observe and measure that residual. A documented routine is allowed only
alongside the refuse-hook; it may cover the residual but cannot substitute for refusal at the
event. Do not claim 100% coverage.

If you cannot say which form you are building, what artifact makes the miss observable, or which
lifecycle event refuses it and what residual is measured, you have not finished step 1.

## The method

### 1. Name the shape, not the instance

The instance is "the knowledge track was deferred but something in phase one needed it." The shape is **"a consumer depends on a producer built later."** The shape is what a machine can evaluate.

The test for a good shape: can you state it as a property that could be true or false of the artifact, without reference to the specific bug? If you can only describe it as a story, keep abstracting.

This matters because the shape is usually broader than anyone realised. In the worked example, one rule expressing "no dependency on a later phase" retroactively caught *three* separately-discovered findings, one of which had taken fifteen review passes to surface. Nobody had seen they were the same defect.

### 2. Surface structure the artifact already implies

Look for information the artifact already carries informally, and make it addressable.

This is the step people get wrong by doing too much. If you find yourself designing a new taxonomy, stop: you are inventing information rather than surfacing it, and the result will drift from the artifact it describes. In the worked example the specification already assigned components to phases in prose and already bound acceptance criteria to test names. The registry added no facts; it made existing facts parseable.

Signs you are surfacing rather than inventing:
- You can point at the prose each row came from.
- A reviewer would say "yes, that's what it already says."
- The structure would be redundant if the artifact were written differently.

Signs you are inventing:
- You are making judgment calls to fill fields.
- The structure encodes a decision nobody has taken.
- You need a meeting to agree on the values.

Inventing is not always wrong, but it is a different, larger job. Say so out loud rather than smuggling it in.

### 3. Write the rule

Usually small. The work was in steps 1 and 2.

Prefer rules that need no insight from the reader. In the worked example, the reversibility judgment ("does deferring this destroy value or merely delay it?") took fifteen review passes for a human to reach — but the *graph* property that exposed it needed no insight at all. Find the mechanical shadow of the human judgment. Encode the judgment separately if you can, as a second rule, so it cannot be quietly reversed later.

If the rule turns out to be noisy or undecidable at this point, go back to *Three output forms* and
ship it advisory or as a routine with a refuse-hook. That is a legitimate result, not a failure —
what is not legitimate is gating on a rule you privately know is noisy or using a routine without
refusal at the observable lifecycle event.

### 4. Prove the rule catches the original bug

**This is the step that separates a real check from a reassuring one.** Do not skip it.

Construct a fixture representing the artifact *as it was before the historical fix*, and assert your rule fires on it — with an exact count, not merely "fails."

**Derive the fixture mechanically; never hand-write it.** Write a small generator that takes the current artifact and reverses the documented change. A hand-written fixture is unfalsifiable evidence: you wrote it knowing the rule, so of course the rule catches it. A derived fixture cannot be tuned in the rule's favour, and it stays in sync as the artifact evolves.

The generator should assert its own expectations too — that every component it meant to move was actually found, that the round-trip preserves the row count. Otherwise a parser regression shrinks the fixture through the same bug it is meant to catch, and the regression quietly passes.

If your rule does *not* fire on history, you built the wrong rule. That is a good outcome discovered cheaply. Return to step 1.

### 5. Fail closed

Separate two kinds of problem, because they need different handling:

- **Findings** — the artifact violates a rule. Reportable, gateable, exit 1.
- **Structural failures** — the checker could not do its job: input did not parse, a section was missing, a table was empty, configuration named an unknown rule. **Fatal, never gateable, exit 2.**

The reason for the split: a finding can be excluded from the gate deliberately and everyone still knows it exists. A parse failure silently empties the data and produces *zero findings*, which reads identically to "clean." Every fail-open bug in the worked example had this shape.

**Guard the guard.** CI must assert that the historical fixture still fires, with an exact rule and count:

```
check --input fixture-before-fix --expect-rule R1 --expect-count 6
```

Do **not** use blind exit-code inversion ("the fixture must fail"). Inversion passes whenever *any* rule fires, so your rule can be completely dead while an unrelated finding keeps the step green. This exact bug shipped in the worked example and was caught only by an adversarial reviewer.

### 6. Have an adversary attack the checker

The risk is asymmetric: the moment a check exists it becomes load-bearing, and if it is wrong it
reports green and gets trusted anyway. A self-reviewed checker is the default way that happens.

Give an independent reviewer (a different model, a colleague, a subagent with no stake) the checker
and this instruction:

> Hunt hardest for anything that makes this report CLEAN while a real defect of the target class is
> present.

In the worked example the first draft came back with eleven critical findings, including three
separate ways it could report all-clear while broken. The second round found four more, two of them
introduced by the fixes for the first round. See `references/adversary-prompt.md` for a template.

**Scale this to what the check carries, because it is the most expensive step here by a wide
margin.** Measured across matched runs, following this skill cost roughly 3-4x the tokens and 6-12x
the wall clock of working without it, and adversarial review was the dominant driver. That is a good
trade for a gate that will block every deploy on a load-bearing artifact forever. It is a bad trade
for a script one person runs by hand. Judge by blast radius:

- **Gates CI, or protects an artifact others depend on** — review it, up to the cap below.
- **Local convenience script, advisory-only output, or a rule you will re-derive next month** — one
  pass by a fresh reader is enough, or none. Say which you chose and why.

**Stop after three rounds.** Not as a budget cap dressed up as a rule, but because of what a third
round still finding critical problems actually tells you: the defect is in the *design*, not in the
code you keep patching. Track loop gain across rounds (findings closed versus introduced). If gain
stays at or above 1, or round three still surfaces ways the checker reports clean while broken, stop
reviewing and go to step 7 — hand-maintained structure is usually the thing generating the findings,
and generating it retires whole categories at once. Round four buys you another patch on the wrong
layer.

### 7. Prefer generation over hand-maintenance

If the structure from step 2 is maintained by hand, its *completeness* can only be asserted, never checked. A checker validates the rows that exist; it cannot know about a row nobody wrote.

That limit is reachable only by generating the structure from a source of record, so coverage becomes true by construction. When a finding is "the data is incomplete", no amount of parser hardening reaches it — every parser fix is treating a symptom of hand-maintenance.

Start hand-maintained if you must, to prove the rule earns its keep. But recognise generation as the destination, and say so where the structure is documented.

### 8. State the limits in the artifact

Write down what the check does not cover, next to the check.

This matters more than it sounds. A check that claims more than it delivers is itself an instance of the most common defect class there is — an unconditional claim where a bounded one is true. In the worked example, the first version of the documentation asserted "a component added without a row here fails the check." That was false; the checker only validated rows that existed. The claim was written *into the authority document* one turn after diagnosing that exact defect class, and an adversarial reviewer had to catch it.

Assume you will do this too. Re-read your own documentation hunting specifically for claims the code does not honour.

## The cap test

Before shipping any rule, ask: **does this remove the fuel, or limit the burn rate?**

- A rule that requires coverage, shrinks unverified surface, or makes an implicit dependency explicit **removes fuel**. It addresses the mechanism.
- A threshold that caps activity — "no more than N rounds", "fail if the file exceeds N lines", "block after N findings" — **limits the burn rate**. It suppresses the symptom while the mechanism runs, and it is usually satisfiable by doing nothing, or by reclassifying, or by not logging.

Measurements are exempt from this only if they *report* rather than *block*. A loop-gain number printed in a build log is an instrument and is valuable. The same number wired to fail the build is a cap: gain stays above 1, and now people route around it.

If your rule is a cap, you have probably not finished step 1.

## How checks report clean while broken

The catalogue below came from adversarial review of a real checker. Check yours against every line; most of these are invisible until someone attacks them.

| Failure mode | Why it reports clean |
|---|---|
| Blind exit-code inversion in the regression | Passes when your rule is dead and an unrelated rule fires |
| Input rows skipped before being counted | A "row count matches" assertion becomes unreachable as an omission detector |
| Items discovered only via already-valid patterns | Malform the item and it vanishes from the input set entirely, so the check gets *quieter* as things get worse |
| Empty input treated as no findings | A missing section, an empty table, a bad path all read as clean |
| Whole-file text search used for a scoped lookup | Prose that merely *mentions* an identifier counts as a real declaration |
| Unknown or empty configuration accepted | `--gate C11` matches nothing, gates nothing, exits 0 |
| Collections that collapse duplicates | "Exactly one owner" cannot be enforced by a set |
| Data that is self-attested | An omitted entry is invisible; only generation fixes this |
| Recursion over a graph | A long valid chain aborts the run before any real check happens |

## Deliverables

A completed pass leaves behind, scaled to the size and form you chose.

For a **rule that gates** or an **advisory rule** (miss observable in an artifact):

1. The **structure** (registry, manifest, schema, annotations) in or beside the artifact, with its coverage and limits stated.
2. The **checker**, with rules separated into gateable findings and fatal structural failures.
3. The **derived fixture** plus its generator, with the generator's own assertions. *(Light: a checked-out historical revision instead.)*
4. A **CI step** running the checker and asserting the fixture still fires by exact rule and count. *(Advisory may report without gating.)*
5. A short note in the project's durable docs: what class this catches, what it does not, and how to run it.
6. A **claims file** — see below.

For a **routine with a refuse-hook** (miss only at a lifecycle event), do **not** substitute lint or
CI. Leave behind: the refuse-hook at cleanup, spawn, or done that rejects the illegal state; a named
residual and how it is measured (never claim 100% coverage); a short note of class, residual, and
hook location; and a **claims file**. A documented routine may accompany the hook only for the residual.

### Emit claims, do not leave them to be inferred

Write a small machine-readable file recording what you actually did: the size and form you chose, the
shape you named, the rule ids (or lifecycle event and residual metric for a refuse-hook), whether the
fixture was derived or checked out, whether an adversary reviewed it and what the verdict was, and
what you deliberately skipped.

**Create it as soon as you have named the shape and picked a size — not at the end.** Steps 1 and 2
are the expensive part of this method: naming the defect's shape and spotting which structure the
artifact already implies is the analysis that took fifteen review passes for a human in the worked
example. Until you write it down it exists only in the conversation, and a session that dies during
step 3 takes it with you. Write the file with the fields you have, then fill in the rest as you go.

```json
{"size":"full","shape":"a consumer depends on a producer built in a later phase",
 "structure":"docs/spec.md section 17 component table",
 "rules":["R1","R2"],"fixture":"derived","fixture_generator":"tools/make_fixture.py",
 "regression":"exact-count","adversary_rounds":2,"adversary_verdict":"trusted",
 "skipped":["cycle detection - graph is a tree by construction"]}
```

The reason is specific and was learned the hard way. Reviewing this work afterwards means asking
"was the fixture derived or hand-written? did an adversary actually review it, or was a prompt just
written?" — and answering those by looking at filenames is unreliable. In one review of this very
method, three files named `adversary-round1/2/3.md` turned out to be unsent *prompts* containing an
unfilled `VERDICT:` placeholder, and were reported as three completed rounds. The same inspection
missed two real fixture generators because of how they were named.

If someone has to infer your intent from artifacts, they will sometimes infer wrong. Emitting the
claim costs a few lines and makes the pass auditable — and it is the same move as generating the
structure instead of scraping it, applied to your own work.

## Starter code

`references/checker-skeleton.py` and `references/fixture-generator-skeleton.py` are runnable
starting points for steps 3–5: the fail-closed exit contract (0/1/2), the exact-count regression
CLI, and a self-asserting derived-fixture generator, with the adapt-me sections marked.
`references/skeleton-selftest.sh` verifies both against the platform-spec eval fixture — run it
after any edit, and copy its shape for your own check's regression step.

## Worked example

`references/worked-example.md` walks the whole method through a real case: a specification whose review rounds oscillated for twenty-three passes, the graph rule that retroactively caught three findings including one that had survived fifteen reviews, and the two adversarial rounds that found fifteen defects in the checker itself. Read it when you want to see the shape of a real pass, especially the fail-open bugs and how they were found.
