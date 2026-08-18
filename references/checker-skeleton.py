#!/usr/bin/env python3
"""Runnable starter checker for the recurring-defect skill.

Copy this file, keep the GENERIC CORE, and replace the DEMO ADAPTER with a
parser and rules for your artifact. The demo adapter targets the platform-spec
eval fixture (evals/fixtures/platform-spec/docs/spec.md) so the whole file runs
end to end out of the box; `references/skeleton-selftest.sh` exercises it.

Exit contract (the point of this skeleton — see SKILL.md step 5):
  0  clean: every selected rule ran and produced no findings
  1  findings: the artifact violates at least one rule (gateable)
  2  structural failure: the checker could not do its job (input missing or
     malformed, unknown rule id, bad CLI combination, or ANY unexpected
     exception, including a bare sys.exit() from library code). Never
     gateable. A crash must never read as exit 1 — a regression assertion
     could not tell "rule fired wrong" from "checker died" — and a stray
     SystemExit(0) must never read as clean. The single deliberate exception:
     `-h/--help` exits 0 after printing usage, so never wire --help into a
     gate.

Regression mode (guard-the-guard, SKILL.md step 4/5):
  checker-skeleton.py --input <derived-fixture> --expect-rule R1 --expect-count 3
  Runs ONLY the named rule and exits 0 iff it fired EXACTLY that many times.
  There is deliberately no "the fixture must fail" inversion mode: inversion
  passes when any unrelated rule fires while the target rule is dead.
  --expect-count 0 is rejected for the same reason (it passes while the rule
  is dead). CI MUST run the plain gate invocation as a SEPARATE step — the
  regression invocation asserts the guard, not the artifact, and its exit
  code says nothing about other rules.

Failure-catalogue coverage (SKILL.md "How checks report clean while broken"):
  - Blind exit-code inversion ......... not implemented; exact rule+count only
  - Rows skipped before counted ....... numbered candidates, indented
                                        candidates, and heading-like lines are
                                        validated or fatal in EVERY parser
                                        state; phase prefix/suffix admit blank
                                        lines only
  - Items found via valid patterns .... components come from list position in
                                        phase blocks; malformed entries,
                                        malformed headings, and non-canonical
                                        names are fatal
  - Empty input == clean .............. missing file, missing section, zero
                                        components, empty rule set, and an
                                        empty rule REGISTRY: all exit 2
  - Whole-file search for scoped ...... dependency scan is per-component body;
                                        declarations only from section 3
  - Unknown/empty config accepted ..... unknown and duplicate rule ids and
                                        empty --rules exit 2
  - Collections collapse duplicates ... findings kept in a list; duplicate
                                        component names/phases are fatal; a
                                        rule that returns findings labeled
                                        with another rule's id is fatal
  - Self-attested data ................ NOT solved here — see LIMITS
  - Recursion over a graph ............ none; R1 is a per-edge comparison

LIMITS (what this checker cannot see — SKILL.md step 8):
  - Rows are self-attested: the checker validates components the spec
    declares; it cannot know about a component nobody listed. Generating the
    structure from a source of record is the only fix (SKILL.md step 7).
  - A dependency phrased without naming the component is invisible, and a mere
    name-mention counts as a dependency (mention ~= dependency). When two
    declared names overlap across the same text (crossed overlap), BOTH edges
    are recorded — conservative in the findings direction.
  - The demo adapter is bound to the platform-spec format (## 3. / ## 4.
    sections, `### Phase N` headings, `N. **Name.** text` entries).
  - The phase partial order is declared by the adapter (PHASES_GUARANTEED_
    FIRST below), not parsed from the spec's prose. If the artifact's
    promotion rules change, that constant must change with it — the checker
    cannot notice the drift.
  - R2 checks that criteria exist per phase and name declared phases; it does
    not judge whether the criteria are correct or sufficient.
"""

import argparse
import re
import sys
import traceback
from dataclasses import dataclass, field
from pathlib import Path

EXIT_CLEAN = 0
EXIT_FINDINGS = 1
EXIT_STRUCTURAL = 2

# ============================= GENERIC CORE =================================
# Keep this section when adapting. It owns the exit contract, the rule
# registry, regression mode, and the crash wrapper.


@dataclass
class Finding:
    """The artifact violates a rule. Reportable, gateable, exit 1."""

    rule: str
    location: str
    message: str

    def render(self) -> str:
        return f"FINDING[{self.rule}] {self.location}: {self.message}"


class StructuralFailure(Exception):
    """The checker could not do its job. Fatal, never gateable, exit 2."""


def run_rules(spec, rule_ids):
    """Run selected rules; findings accumulate in a list (never a set —
    'exactly one owner' style rules cannot be enforced by a collection that
    collapses duplicates). Every finding's rule label must match the rule that
    produced it, so a buggy rule cannot forge another rule's regression
    count."""
    findings = []
    for rid in rule_ids:
        # list() first: if a rule returns a one-shot generator, iterating it
        # for validation and then extending would silently add zero findings.
        produced = list(RULES[rid][0](spec))
        for f in produced:
            if f.rule != rid:
                raise StructuralFailure(
                    f"rule {rid} returned a finding labeled {f.rule!r} — "
                    "provenance violation"
                )
        findings.extend(produced)
    return findings


def resolve_rule_ids(rules_arg):
    """Validate rule selection. Unknown, duplicate, or empty selections are
    structural: `--rules R9` matching nothing and exiting 0 is the catalogue's
    'unknown configuration accepted' failure."""
    if not RULES:
        raise StructuralFailure("rule registry is empty — nothing can be checked")
    if rules_arg is None:
        return list(RULES)
    rule_ids = [r.strip() for r in rules_arg.split(",")]
    if not any(rule_ids) or "" in rule_ids:
        raise StructuralFailure("--rules is empty: an empty rule set gates nothing")
    if len(set(rule_ids)) != len(rule_ids):
        raise StructuralFailure(
            f"--rules contains duplicates: {rule_ids} — duplicate rules corrupt "
            "exact-count semantics"
        )
    unknown = [r for r in rule_ids if r not in RULES]
    if unknown:
        raise StructuralFailure(f"unknown rule id(s) {unknown}; known: {sorted(RULES)}")
    return rule_ids


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Fail-closed defect-class checker (recurring-defect skill skeleton).",
        epilog="Exit codes: 0 clean, 1 findings, 2 structural failure.",
    )
    parser.add_argument("--input", required=True, help="artifact to check")
    parser.add_argument(
        "--rules",
        default=None,
        help="comma-separated rule ids to run (default: all). Unknown ids are fatal.",
    )
    parser.add_argument(
        "--expect-rule",
        default=None,
        help="regression mode: rule id that must fire (requires --expect-count); "
        "runs ONLY this rule",
    )
    parser.add_argument(
        "--expect-count",
        type=int,
        default=None,
        help="regression mode: exact number of times --expect-rule must fire (> 0)",
    )
    args = parser.parse_args(argv)

    # --- CLI validation: bad configuration is structural, never "clean". ---
    if (args.expect_rule is None) != (args.expect_count is None):
        raise StructuralFailure("--expect-rule and --expect-count must be given together")
    if args.expect_count is not None and args.expect_count <= 0:
        raise StructuralFailure(
            "--expect-count must be > 0: a regression fixture that expects zero "
            "firings passes while the rule is dead (fail-open)"
        )
    rule_ids = resolve_rule_ids(args.rules)
    if args.expect_rule is not None:
        if args.expect_rule not in RULES:
            raise StructuralFailure(
                f"unknown --expect-rule {args.expect_rule!r}; known: {sorted(RULES)}"
            )
        if args.expect_rule not in rule_ids:
            raise StructuralFailure(
                f"--expect-rule {args.expect_rule} is not in the selected rule set {rule_ids}"
            )

    path = Path(args.input)
    if not path.is_file():
        raise StructuralFailure(f"input not found or not a file: {path}")
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        raise StructuralFailure(f"input unreadable: {path}: {e}")

    spec = parse_spec(text, source=str(path))

    if args.expect_rule is not None:
        # Regression mode runs ONLY the target rule: findings from other rules
        # can neither mask a dead rule nor leak into the count.
        findings = run_rules(spec, [args.expect_rule])
        for f in findings:
            print(f.render())
        hits = len(findings)
        if hits == args.expect_count:
            print(
                f"REGRESSION OK: {args.expect_rule} fired {hits} time(s) "
                f"(expected {args.expect_count})"
            )
            print(
                "note: regression mode asserts only the guard; CI must gate the "
                "artifact with a separate plain run"
            )
            return EXIT_CLEAN
        print(
            f"REGRESSION FAILED: {args.expect_rule} fired {hits} time(s), "
            f"expected exactly {args.expect_count}"
        )
        return EXIT_FINDINGS

    findings = run_rules(spec, rule_ids)
    for f in findings:
        print(f.render())
    if findings:
        print(f"{len(findings)} finding(s)")
        return EXIT_FINDINGS
    print("CLEAN: 0 findings")
    return EXIT_CLEAN


def run_wrapped(entry, argv=None) -> int:
    """Crash wrapper: anything unexpected must exit 2, not 1 and not 0.

    Python's default uncaught-exception exit code is 1 — the same as
    "findings" — which would let a crash impersonate a legitimate red gate.
    A stray SystemExit(0) from library code would impersonate CLEAN, which is
    worse. So: SystemExit(0) is honored only for an explicit -h/--help;
    argparse usage errors (SystemExit(2)) stay 2; every other SystemExit
    becomes 2; and the entry's return value must be exactly 0, 1, or 2."""
    args_seen = list(sys.argv[1:] if argv is None else argv)
    try:
        result = entry(argv)
    except StructuralFailure as e:
        print(f"STRUCTURAL FAILURE: {e}", file=sys.stderr)
        return EXIT_STRUCTURAL
    except SystemExit as e:
        if e.code == 0 and ("-h" in args_seen or "--help" in args_seen):
            return 0
        print(
            f"STRUCTURAL FAILURE: unexpected SystemExit({e.code!r})", file=sys.stderr
        )
        return EXIT_STRUCTURAL
    except Exception as e:  # noqa: BLE001 — the whole point is catching the unexpected
        traceback.print_exc()
        print(f"STRUCTURAL FAILURE (unexpected): {e!r}", file=sys.stderr)
        return EXIT_STRUCTURAL
    if type(result) is not int or result not in (
        EXIT_CLEAN,
        EXIT_FINDINGS,
        EXIT_STRUCTURAL,
    ):
        # Exact type check: 0.0 == 0 and True == 1, so membership alone would
        # let numeric impostors through (sys.exit(0.0) exits with code 1).
        print(
            f"STRUCTURAL FAILURE: entry returned {result!r}, expected 0/1/2",
            file=sys.stderr,
        )
        return EXIT_STRUCTURAL
    return result


# ============================= DEMO ADAPTER =================================
# Replace everything below for your artifact: parse_spec() must return a
# structure your rules can evaluate, and RULES maps rule ids to functions.
# The adapter parses the platform-spec format:
#   ## 3. <components section>      ## 4. <acceptance criteria section>
#   ### Phase <int> [— title]       ### Phase <int>
#   N. **Name.** description...     - criterion text — `test_name`

PHASE_RE = re.compile(r"^### Phase (\d+)(?:\s+—\s+.*)?$")
ENTRY_RE = re.compile(r"^(\d+)\. \*\*(.+?)\.\*\*\s*(.*)$")
CRITERION_RE = re.compile(r"^- (.+) — `([A-Za-z_][A-Za-z0-9_]*)`$")

# The artifact's phase partial order, declared as adapter DATA (not parsed
# from prose — the checker cannot read "phases 2 and 3 are promoted
# independently" in spec.md §3; a human encodes it here and owns the drift).
# Phases in this set are guaranteed complete before every other phase begins.
# All other phases are mutually UNORDERED, so any cross-phase dependency
# between them is a violation in BOTH directions.
PHASES_GUARANTEED_FIRST = {1}


def phase_precedes(a: int, b: int) -> bool:
    """True iff phase a is guaranteed complete before phase b begins."""
    return a in PHASES_GUARANTEED_FIRST and b not in PHASES_GUARANTEED_FIRST


@dataclass
class Component:
    name: str
    slug: str
    phase: int
    raw_block: list  # original lines, including the numbered first line
    body: str = ""  # normalized entry text used for dependency scanning
    body_raw: str = ""  # raw entry text minus the list number (fidelity checks)
    deps: list = field(default_factory=list)  # slugs, in match order


@dataclass
class Spec:
    source: str
    lines: list
    phases: dict  # num -> heading line index (section 3)
    phase_layout: dict  # num -> {"prefix": [lines], "suffix": [lines]}
    components: list
    criteria_phases: dict  # num -> [criterion test names]
    section3_span: tuple  # (start, end) line indexes, end exclusive
    section3_intro: list  # raw lines between the ## heading and the first ###

    def by_slug(self):
        return {c.slug: c for c in self.components}


def _slug(name: str) -> str:
    return re.sub(r"\s+", "-", name.strip().lower())


def _find_sections(lines, source):
    """Split on `## ` headings; require exactly one `## 3.` and one `## 4.`."""
    heads = [i for i, ln in enumerate(lines) if ln.startswith("## ")]
    spans = {}
    for pos, i in enumerate(heads):
        end = heads[pos + 1] if pos + 1 < len(heads) else len(lines)
        m = re.match(r"^## (\d+)\.", lines[i])
        if m:
            num = int(m.group(1))
            if num in spans:
                raise StructuralFailure(f"{source}: duplicate section {num}")
            spans[num] = (i, end)
    for needed, label in ((3, "components"), (4, "acceptance criteria")):
        if needed not in spans:
            raise StructuralFailure(
                f"{source}: section {needed} ({label}) missing — cannot check anything, "
                "and zero findings must not impersonate a clean result"
            )
    return spans


def _parse_phase_blocks(lines, span, source, section_label):
    """Yield (phase_num, heading_idx, block_lines). Any `###` heading inside
    the section that does not match `### Phase <int>` is fatal, and so is an
    INDENTED heading-like line: a malformed or mis-nested heading would
    otherwise silently orphan every row under it (or attach a later phase's
    rows to an earlier phase)."""
    start, end = span
    blocks = []
    i = start + 1
    intro = []
    current = None  # (num, heading_idx, [lines])
    seen = set()
    while i < end:
        ln = lines[i]
        if ln.startswith("### "):
            m = PHASE_RE.match(ln)
            if not m:
                raise StructuralFailure(
                    f"{source}:{i + 1}: malformed phase heading in {section_label}: {ln!r}"
                )
            num = int(m.group(1))
            if num in seen:
                raise StructuralFailure(
                    f"{source}:{i + 1}: duplicate phase {num} in {section_label}"
                )
            seen.add(num)
            if current:
                blocks.append(current)
            current = (num, i, [])
        elif ln.strip().startswith("#"):
            raise StructuralFailure(
                f"{source}:{i + 1}: indented or malformed heading inside "
                f"{section_label}: {ln!r}"
            )
        elif current is None:
            # Intro lines still get candidate validation: an entry-like line
            # before the first phase heading must not be absorbed as prose.
            if _looks_like_entry_candidate(ln):
                raise StructuralFailure(
                    f"{source}:{i + 1}: entry-like line before the first phase "
                    f"heading in {section_label}: {ln!r}"
                )
            if section_label == "section 4" and ln.strip():
                raise StructuralFailure(
                    f"{source}:{i + 1}: unexpected prose before the first phase "
                    f"heading in {section_label}: {ln!r}"
                )
            intro.append(ln)
        else:
            current[2].append(ln)
        i += 1
    if current:
        blocks.append(current)
    if not blocks:
        raise StructuralFailure(f"{source}: no `### Phase N` headings in {section_label}")
    return intro, blocks


def _looks_like_entry_candidate(ln: str) -> bool:
    """Anything that could plausibly be a component row: digits followed
    directly by list punctuation (`2.`, `3)`, `2..`), a numbered token with a
    missing separator (`1 **X.**`), or a bold-name token. Candidates are
    validated or fatal in EVERY parser state — never absorbed as prose or as a
    neighboring entry's continuation. A decimal number ("2.0 requests/second")
    is NOT a candidate: list punctuation is a dot not followed by a digit, or
    a closing paren — but any number-ish token followed by a bold marker is."""
    stripped = ln.strip()
    return (
        bool(re.match(r"^\d+(?:\.(?!\d)|\))", stripped))
        or bool(re.match(r"^[\d.)]+\s+\*\*", stripped))
        or stripped.startswith("**")
    )


def _parse_components(blocks, source):
    """Parse numbered entries. Candidate lines are counted BEFORE validation:
    any line that looks like it could be an entry but does not fully match is
    fatal in EVERY state (prefix, entries, suffix), so a malformed or indented
    row cannot vanish into prose or a neighboring entry's continuation."""
    components = []
    layout = {}
    phases = {}
    for num, heading_idx, block in blocks:
        phases[num] = heading_idx
        prefix, entries, suffix = [], [], []
        state = "prefix"
        for ln in block:
            if ENTRY_RE.match(ln):
                entries.append([ln])
                state = "entries"
            elif _looks_like_entry_candidate(ln):
                raise StructuralFailure(
                    f"{source}: phase {num}: line looks like a component entry but "
                    f"does not match the entry format (state={state}): {ln!r}"
                )
            elif ln.strip() == "":
                if state == "prefix":
                    prefix.append(ln)
                else:
                    suffix.append(ln)
                    state = "suffix"
            elif state == "entries" and ln[:1].isspace():
                entries[-1].append(ln)  # continuation line
            else:
                # Phase prefix/suffix admit blank lines only; prose here would
                # be a place for malformed rows to hide.
                raise StructuralFailure(
                    f"{source}: phase {num}: unexpected non-blank line outside an "
                    f"entry (state={state}): {ln!r}"
                )
        layout[num] = {"prefix": prefix, "suffix": suffix}
        for order, raw_block in enumerate(entries, start=1):
            m = ENTRY_RE.match(raw_block[0])
            declared_no = int(m.group(1))
            if declared_no != order:
                raise StructuralFailure(
                    f"{source}: phase {num}: entry numbering broken at "
                    f"{m.group(2)!r} (found {declared_no}, expected {order})"
                )
            name = m.group(2)
            if not re.fullmatch(r"[A-Za-z0-9]+(?:[ -][A-Za-z0-9]+)*", name):
                # Canonical ASCII names only: tabs, NBSP, zero-width characters,
                # and leading/trailing/double separators all silently defeat
                # mention matching, which reports clean while a dependency
                # exists. Adapt this policy deliberately for your artifact.
                raise StructuralFailure(
                    f"{source}: phase {num}: non-canonical component name {name!r} "
                    "(expected ASCII words separated by single spaces or hyphens)"
                )
            body_first = f"**{name}.** {m.group(3)}".rstrip()
            body = "\n".join([body_first] + raw_block[1:])
            body_raw = "\n".join(
                [re.sub(r"^\d+\.", "", raw_block[0], count=1)] + raw_block[1:]
            )
            components.append(
                Component(
                    name=name,
                    slug=_slug(name),
                    phase=num,
                    raw_block=list(raw_block),
                    body=body,
                    body_raw=body_raw,
                )
            )
    if not components:
        raise StructuralFailure(f"{source}: zero components declared in section 3")
    slugs = {}
    for c in components:
        if c.slug in slugs:
            raise StructuralFailure(
                f"{source}: duplicate component after slugging: {c.slug!r} "
                f"({slugs[c.slug]!r} vs {c.name!r})"
            )
        slugs[c.slug] = c.name
    return phases, layout, components


def _extract_deps(components):
    """Dependency = another declared component's name mentioned inside this
    component's own body (scoped — never a whole-file search). All matches are
    collected against the ORIGINAL text; a match fully contained inside a
    longer match is dropped (mentioning "tenant registry" is not a mention of
    a component named "registry"), but crossed overlaps keep BOTH edges —
    conservative in the findings direction. Self-mentions are ignored."""
    for c in components:
        spans = []  # (start, end, slug)
        for other in components:
            if other.slug == c.slug:
                continue
            # Spaces in a name match any run of whitespace, so a mention
            # wrapped across a continuation line ("Later\n   service") still
            # produces its edge instead of silently reporting clean.
            tokens = [re.escape(t) for t in other.name.split(" ")]
            pat = re.compile(
                r"(?<![\w-])" + r"\s+".join(tokens) + r"(?![\w-])", re.IGNORECASE
            )
            for m in pat.finditer(c.body):
                spans.append((m.start(), m.end(), other.slug))
        kept = []
        for s in spans:
            contained = any(
                o is not s and o[0] <= s[0] and s[1] <= o[1] and (o[1] - o[0]) > (s[1] - s[0])
                for o in spans
            )
            if not contained:
                kept.append(s)
        kept.sort()
        seen = set()
        c.deps = [slug for _s, _e, slug in kept if not (slug in seen or seen.add(slug))]


def _parse_criteria(blocks, source):
    criteria = {}
    for num, _idx, block in blocks:
        tests = []
        for ln in block:
            if ln.strip() == "":
                continue
            m = CRITERION_RE.match(ln)
            if not m:
                raise StructuralFailure(
                    f"{source}: criteria phase {num}: malformed criterion line: {ln!r}"
                )
            tests.append(m.group(2))
        criteria[num] = tests
    return criteria


def parse_spec(text, source="<input>") -> Spec:
    """Documented API — the fixture generator imports and reuses this parser
    (one parser, no drift). Raises StructuralFailure on any malformation."""
    if not text.strip():
        raise StructuralFailure(f"{source}: input is empty")
    lines = text.splitlines()
    spans = _find_sections(lines, source)
    intro3, blocks3 = _parse_phase_blocks(lines, spans[3], source, "section 3")
    phases, layout, components = _parse_components(blocks3, source)
    _extract_deps(components)
    _intro4, blocks4 = _parse_phase_blocks(lines, spans[4], source, "section 4")
    criteria = _parse_criteria(blocks4, source)
    return Spec(
        source=source,
        lines=lines,
        phases=phases,
        phase_layout=layout,
        components=components,
        criteria_phases=criteria,
        section3_span=spans[3],
        section3_intro=intro3,
    )


def rule_phase_closure(spec: Spec):
    """R1: a component may only depend on a component in the same phase or in
    a phase guaranteed to be complete first (see PHASES_GUARANTEED_FIRST).
    Cross-phase dependencies between unordered phases are violations in both
    directions. Per-edge, no recursion — any transitive violation contains a
    direct violating edge."""
    findings = []
    by_slug = spec.by_slug()
    for c in spec.components:
        for dep in c.deps:
            d = by_slug[dep]
            if d.phase != c.phase and not phase_precedes(d.phase, c.phase):
                findings.append(
                    Finding(
                        rule="R1",
                        location=f"{spec.source} §3 phase {c.phase}",
                        message=(
                            f"{c.slug} (phase {c.phase}) depends on {d.slug} "
                            f"(phase {d.phase}) — not guaranteed built"
                        ),
                    )
                )
    return findings


def rule_criteria_coverage(spec: Spec):
    """R2: every declared phase has at least one acceptance criterion, and
    every criteria phase heading names a declared phase. (An earlier draft
    searched the criteria for declared component names — a rule that can never
    find an undeclared name, i.e. catalogue row 3. This form is decidable.)"""
    findings = []
    for num in sorted(spec.phases):
        if not spec.criteria_phases.get(num):
            findings.append(
                Finding(
                    rule="R2",
                    location=f"{spec.source} §4",
                    message=f"phase {num} is declared but has no acceptance criteria",
                )
            )
    for num in sorted(spec.criteria_phases):
        if num not in spec.phases:
            findings.append(
                Finding(
                    rule="R2",
                    location=f"{spec.source} §4 phase {num}",
                    message=f"acceptance criteria given for undeclared phase {num}",
                )
            )
    return findings


# Registry: unknown ids are rejected in resolve_rule_ids() — `--rules R9` must
# exit 2, not match nothing and exit 0. An EMPTY registry is also fatal.
RULES = {
    "R1": (rule_phase_closure, "no dependency on a phase not guaranteed built"),
    "R2": (rule_criteria_coverage, "every phase has criteria; criteria name real phases"),
}


if __name__ == "__main__":
    sys.exit(run_wrapped(main))
