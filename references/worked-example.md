# Worked example: a specification whose reviews would not converge

A real pass through the method, with the numbers. The artifact was a ~1,300-line architecture
specification, not code, which is worth noting: the technique is about structure, not language.

## The symptom

Findings per review round, across two separate loops:

```
17, 11, 5, 3, 7, 3, 3, 4, 6, 7, 5, 6, 7, 3, 0
15, 8, 7, 3, 2, 3, 4, 3
```

Not convergence. A random walk in a 2–4 band, across twenty-three passes, several of them with an
independent outside model. Worse, a structural scope error was discovered only at pass fifteen and
forced a large re-plan: a capability the whole design depended on had been deferred to a later phase.

## Step 0: measure the loop before diagnosing the findings

One review log recorded the decisive number almost in passing:

> of nine engineering findings, three are fixed, six are amended but do not close under
> composition, and the amendments introduced seven new findings.

Closed 3, opened 7. **Gain 2.33.** A loop with gain above 1 does not converge no matter how good the
individual fixes are. Nobody had computed this number a second time, and it was the strongest
available evidence that the loop, not the findings, was the problem.

A second corroborating measurement: when a *third* model reviewed the same document for the first
time, it produced thirteen findings of which six were entirely new — findings two incumbent
reviewers had never raised across many rounds. Marginal value of another pass by the same voice was
near zero; marginal value of a different lens was high. Pass count is not coverage.

## Step 1: name the shape

Five of the six findings only the fresh voice caught shared a shape: *section X was amended, section
Y that references X was not.*

The scope error had the same shape. A phase-one deliverable produced records carrying evidence
*references*, while the component that captured the referenced content sat in a deferred phase.
Nobody walked the edge between the two sections.

Shape, stated mechanically:

> **A component may not depend on a component built in a later phase.**

No judgment required. No reference to the specific bug. Evaluable over a graph.

The human insight that originally found it — "does deferring this destroy value, or merely delay
it?" — took fifteen passes to reach. The graph property needed no insight at all. That gap is the
whole point of step 1: **find the mechanical shadow of the human judgment.**

## Step 2: surface structure that already existed

The specification already assigned components to phases, in prose. It already bound every acceptance
criterion to a named test. The information existed; it was not addressable.

The structure added was one Markdown table: component, defining section, phase, reversibility class,
dependencies. No new facts, only existing facts made parseable. A separate sidecar file was
considered and rejected, because the specification was declared the single authority and a second
file would have become a competing one.

The reversibility column is the exception worth noting: it encoded the *human* judgment
(`additive` vs `destroyed-if-delayed`) as a second, separate rule. You cannot compute it, but you
can require it to be declared, and then check that nothing marked `destroyed-if-delayed` sits in a
deferred phase. The graph rule finds the defect; the declared judgment stops it being re-deferred.

## Step 4: prove it against history

A generator took the current registry and mechanically reversed the documented scope change,
producing the artifact as fifteen review passes had seen it. Derived, not hand-written, so it could
not be tuned in the rule's favour.

The rule fired six times on that fixture, and those six edges corresponded to **three separately
discovered findings**:

| Rule firing | How it was originally found |
|---|---|
| consumer → deferred evidence component | The scope error. Fifteen passes and a re-plan. |
| publish record → deferred evidence, deferred citation | A different reviewer, once, fixed in isolation |
| product capability → deferred vault, deferred writer | Part of the scope-error argument |

One rule, under a second, catching what had cost weeks — and catching a case that had been fixed in
isolation without anyone examining the general form. On the *current* registry the same rule fires
zero times, which is what makes it a regression test rather than a coincidence.

## Steps 5–6: what the adversary found

The checker was reviewed by an independent model with one instruction: *hunt hardest for anything
that makes this report CLEAN while a real defect is present.*

**Round one: eleven critical findings.** The important ones:

- The regression used blind exit-code inversion. It passed whenever *any* rule fired — so the
  central rule could be entirely dead while an unrelated finding kept the step green.
- Table rows that failed to match the expected pattern were skipped silently. A row-count assertion
  existed but incremented only *after* the skip, so it could never detect an omission.
- Criteria were discovered only via already-valid test names, so deleting a test name removed the
  criterion from the input set entirely. The check got *quieter* as the artifact got worse.
- Phase values were never validated against the phases the document actually declared, so a typo
  created a component in a nonexistent phase and every comparison against it silently passed.

It also **refuted a suspicion the author had raised** — that only checking direct edges would miss
transitive violations. With scalar ranks, any path from earlier to later must contain at least one
directly increasing edge, so direct checking suffices for detection. Worth recording: an adversary
that only confirms your worries is not doing its job.

**Round two, after fixes: four critical findings**, two of them newly introduced by the fixes. One
was a genuine logic inversion the author had written: a comparison that returned "later" in the wrong
direction, which would have raised a false violation on a dependency the document explicitly declared.

Gain across the checker's own loop was roughly 0.9 — converging, but barely, while it *felt*
comfortable. The instrument disagreed with the intuition, which is the argument for having it.

## Step 7: the finding no parser could reach

Round two's sharpest finding was that the registry was **not faithful** — a whole phase's components
had no rows, while the documentation claimed the table covered every component.

No amount of parser hardening reaches that. It is a completeness problem, and completeness of a
hand-maintained table can only be asserted. The fix was to generate the table from a source of
record, so coverage became true by construction. Every parser fix before that had been treating a
symptom of hand-maintenance.

## Step 8: the claim that was false

The documentation for the check asserted:

> "A component added to this specification without a row here fails C5."

False. The checker validated the rows that existed and could not know about a row nobody wrote. That
sentence was written into the authority document *one turn after* diagnosing "unconditional claims
where a bounded one is true" as the project's recurring defect, and it took an adversarial reviewer
to catch it. Then a second, similar overclaim ("every component the specification names") survived
into the next round.

Assume you will do this. Re-read your own documentation hunting for claims the code does not honour.

## Net

- One rule, expressible in a sentence, retroactively caught three findings including one that had
  survived fifteen reviews.
- Fifteen defects in the checker itself, found across two adversarial rounds, three of which would
  have let it report all-clear while broken.
- Two false claims by the author, in the artifact, about the checker's own guarantees.

The rule was the easy part.
