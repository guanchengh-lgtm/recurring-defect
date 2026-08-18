#!/usr/bin/env bash
# Selftest for checker-skeleton.py + fixture-generator-skeleton.py.
#
# This is the skill's "CI step" deliverable in the only form available to a
# non-repo skill directory: a re-runnable assertion that the historical-shape
# fixture still fires by EXACT rule, count, AND edge identity, plus the full
# fail-closed contract. Run it after any edit to either skeleton:
#
#   bash references/skeleton-selftest.sh
#
# Exit 0: all cases pass. Exit 1: at least one case failed (this script is a
# test harness, not a checker — it does not use the 0/1/2 contract itself).
# The eval fixture directory is read-only to this script; a checksum asserts it.
set -u

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHECKER="$HERE/checker-skeleton.py"
GEN="$HERE/fixture-generator-skeleton.py"
SPEC="$HERE/../evals/fixtures/platform-spec/docs/spec.md"
ROUND1="$HERE/../evals/fixtures/platform-spec/docs/reviews/round-1.md"
SCRATCH="$(mktemp -d)"
trap 'rm -rf "$SCRATCH"' EXIT

PASS=0; FAIL=0
SPEC_SUM_BEFORE=$(cksum < "$SPEC")

# expect <case-name> <expected-exit> <cmd...>
expect() {
  local name="$1" want="$2"; shift 2
  local out; out="$("$@" 2>&1)"; local got=$?
  if [ "$got" -eq "$want" ]; then
    PASS=$((PASS+1)); printf 'PASS %-46s (exit %s)\n' "$name" "$got"
  else
    FAIL=$((FAIL+1)); printf 'FAIL %-46s (exit %s, wanted %s)\n' "$name" "$got" "$want"
    printf '%s\n' "$out" | sed 's/^/     | /'
  fi
}

# expect_grep <case-name> <expected-exit> <expected-count> <pattern> <cmd...>
# Asserts exit status AND line count together: a command that crashes after
# printing the right lines must not pass.
expect_grep() {
  local name="$1" wantexit="$2" want="$3" pat="$4"; shift 4
  local out; out="$("$@" 2>&1)"; local gotexit=$?
  local got; got=$(printf '%s\n' "$out" | grep -c -- "$pat")
  if [ "$got" -eq "$want" ] && [ "$gotexit" -eq "$wantexit" ]; then
    PASS=$((PASS+1)); printf 'PASS %-46s (%s x%s, exit %s)\n' "$name" "$pat" "$got" "$gotexit"
  else
    FAIL=$((FAIL+1)); printf 'FAIL %-46s (%s x%s wanted %s, exit %s wanted %s)\n' \
      "$name" "$pat" "$got" "$want" "$gotexit" "$wantexit"
    printf '%s\n' "$out" | sed 's/^/     | /'
  fi
}

# ---- crafted inputs --------------------------------------------------------
mk() { printf '%s\n' "$@" > "$SCRATCH/$CRAFT"; }

CRAFT=malformed-entry.md mk \
  '## 3. Delivery phases' '### Phase 1' '1. **A.** Standalone.' '2. Broken entry with no bold name.' \
  '## 4. Acceptance criteria, by phase' '### Phase 1' '- A works. — `a_works`'
CRAFT=duplicate-component.md mk \
  '## 3. Delivery phases' '### Phase 1' '1. **A.** Standalone.' '2. **A.** Again.' \
  '## 4. Acceptance criteria, by phase' '### Phase 1' '- A works. — `a_works`'
CRAFT=malformed-phase.md mk \
  '## 3. Delivery phases' '### Phase Three' '1. **A.** Standalone.' \
  '## 4. Acceptance criteria, by phase' '### Phase 1' '- A works. — `a_works`'
CRAFT=duplicate-phase.md mk \
  '## 3. Delivery phases' '### Phase 1' '1. **A.** Standalone.' '### Phase 1' '1. **B.** Standalone.' \
  '## 4. Acceptance criteria, by phase' '### Phase 1' '- A works. — `a_works`'
CRAFT=zero-components.md mk \
  '## 3. Delivery phases' '### Phase 1' \
  '## 4. Acceptance criteria, by phase' '### Phase 1' '- A works. — `a_works`'
CRAFT=no-section4.md mk \
  '## 3. Delivery phases' '### Phase 1' '1. **A.** Standalone.'
CRAFT=broken-numbering.md mk \
  '## 3. Delivery phases' '### Phase 1' '1. **A.** Standalone.' '3. **B.** Standalone.' \
  '## 4. Acceptance criteria, by phase' '### Phase 1' '- A works. — `a_works`'
CRAFT=indented-entry.md mk \
  '## 3. Delivery phases' '### Phase 1' '  1. **A.** Indented, would be swallowed as prose.' \
  '## 4. Acceptance criteria, by phase' '### Phase 1' '- A works. — `a_works`'
# Adversary round 1: an indented entry AFTER a valid entry must not become a
# continuation line of the previous component.
CRAFT=indented-after-entry.md mk \
  '## 3. Delivery phases' '### Phase 1' '1. **A.** Standalone.' '  2. **B.** Hidden dependency host.' \
  '## 4. Acceptance criteria, by phase' '### Phase 1' '- A works. — `a_works`'
# Adversary round 1: an indented phase heading must not attach its components
# to the previous phase.
CRAFT=indented-heading.md mk \
  '## 3. Delivery phases' '### Phase 1' '1. **A.** Standalone.' '  ### Phase 3' '1. **B.** Standalone.' \
  '## 4. Acceptance criteria, by phase' '### Phase 1' '- A works. — `a_works`'
# Adversary round 1: a component-like line with a broken separator must not be
# absorbed as phase-prefix prose.
CRAFT=prefix-candidate.md mk \
  '## 3. Delivery phases' '### Phase 1' '1 **Dropped.** Missing dot separator.' '1. **A.** Standalone.' \
  '## 4. Acceptance criteria, by phase' '### Phase 1' '- A works. — `a_works`'
# Adversary round 1: a name with trailing whitespace defeats mention matching.
CRAFT=noncanonical-name.md mk \
  '## 3. Delivery phases' '### Phase 1' '1. **Later .** Trailing space in name.' \
  '## 4. Acceptance criteria, by phase' '### Phase 1' '- A works. — `a_works`'
# Adversary round 1: crossed overlap "foo bar baz" vs names "Foo bar"/"Bar baz"
# must record BOTH edges (conservative), not let match order drop one.
CRAFT=crossed-overlap.md mk \
  '## 3. Delivery phases' '### Phase 1' '1. **C.** Uses foo bar baz here.' \
  '### Phase 2' '1. **Foo bar.** Standalone.' '2. **Bar baz.** Standalone.' \
  '## 4. Acceptance criteria, by phase' '### Phase 1' '- C works. — `c_works`' \
  '### Phase 2' '- ok. — `ok_works`'
# Adversary round 2: an entry-like line in the section intro (before the first
# phase heading) must not be absorbed as prose.
CRAFT=intro-entry.md mk \
  '## 3. Delivery phases' '  1. **B.** Hidden in the intro.' '### Phase 1' '1. **A.** Standalone.' \
  '## 4. Acceptance criteria, by phase' '### Phase 1' '- A works. — `a_works`'
# Adversary round 2: prose before the first phase heading of section 4.
CRAFT=section4-intro.md mk \
  '## 3. Delivery phases' '### Phase 1' '1. **A.** Standalone.' \
  '## 4. Acceptance criteria, by phase' 'Unexpected prose here.' '### Phase 1' '- A works. — `a_works`'
# Adversary round 2: malformed numbered continuation must not attach to the
# previous entry.
CRAFT=malformed-continuation.md mk \
  '## 3. Delivery phases' '### Phase 1' '1. **A.** Standalone.' '  2.. **Hidden.** Broken separator.' \
  '## 4. Acceptance criteria, by phase' '### Phase 1' '- A works. — `a_works`'
# Adversary round 2: a mention wrapped across a continuation line must still
# produce its edge (phases 2 and 3 are unordered, so this is a violation).
CRAFT=wrapped-mention.md mk \
  '## 3. Delivery phases' '### Phase 2' '1. **Consumer.** Uses the Later' '   service here.' \
  '### Phase 3' '1. **Later service.** Standalone.' \
  '## 4. Acceptance criteria, by phase' '### Phase 2' '- ok. — `ok_works`' \
  '### Phase 3' '- later. — `later_works`'
# Adversary round 3: a decimal in continuation prose is legitimate, but a
# decimal-numbered bold token is still a hidden-component candidate.
CRAFT=decimal-continuation.md mk \
  '## 3. Delivery phases' '### Phase 1' '1. **A.** Sustains a rate of' '   2.0 requests per second.' \
  '## 4. Acceptance criteria, by phase' '### Phase 1' '- A works. — `a_works`'
CRAFT=decimal-bold-entry.md mk \
  '## 3. Delivery phases' '### Phase 1' '1. **A.** Standalone.' '  2.5 **Hidden.** Decimal number.' \
  '## 4. Acceptance criteria, by phase' '### Phase 1' '- A works. — `a_works`'
# Adversary round 2: tab / NBSP inside a name defeats mention matching and
# must be structurally rejected (canonical ASCII name policy).
printf '## 3. Delivery phases\n### Phase 1\n1. **Later\tservice.** Tab name.\n## 4. Acceptance criteria, by phase\n### Phase 1\n- A works. — `a_works`\n' > "$SCRATCH/tab-name.md"
printf '## 3. Delivery phases\n### Phase 1\n1. **Later\xc2\xa0service.** NBSP name.\n## 4. Acceptance criteria, by phase\n### Phase 1\n- A works. — `a_works`\n' > "$SCRATCH/nbsp-name.md"
# R2 positives: phase 2 declared without criteria; criteria for undeclared phase 5.
CRAFT=r2-fires.md mk \
  '## 3. Delivery phases' '### Phase 1' '1. **A.** Standalone.' '### Phase 2' '1. **B.** Standalone.' \
  '## 4. Acceptance criteria, by phase' '### Phase 1' '- A works. — `a_works`' \
  '### Phase 5' '- ghost. — `ghost_works`'

# ---- checker: findings, edge identity, regression -------------------------
expect      "R1 fires on current spec"                1 python3 "$CHECKER" --input "$SPEC"
expect_grep "R1 fires exactly 3 times"                1 3 'FINDING\[R1\]' python3 "$CHECKER" --input "$SPEC"
expect_grep "R1 edge: ledger->audit-log"              1 1 'billing-ledger (phase 1) depends on audit-log-store (phase 3)' python3 "$CHECKER" --input "$SPEC"
expect_grep "R1 edge: provisioning->capacity"         1 1 'tenant-provisioning-api (phase 1) depends on capacity-planner (phase 3)' python3 "$CHECKER" --input "$SPEC"
expect_grep "R1 edge: metrics->audit-log"             1 1 'metrics-pipeline (phase 2) depends on audit-log-store (phase 3)' python3 "$CHECKER" --input "$SPEC"
expect      "regression exact count passes"           0 python3 "$CHECKER" --input "$SPEC" --expect-rule R1 --expect-count 3
expect      "regression wrong count fails"            1 python3 "$CHECKER" --input "$SPEC" --expect-rule R1 --expect-count 2
expect      "regression unknown rule is fatal"        2 python3 "$CHECKER" --input "$SPEC" --expect-rule R9 --expect-count 3
expect      "expect-count 0 is rejected"              2 python3 "$CHECKER" --input "$SPEC" --expect-rule R1 --expect-count 0
expect      "expect-rule without count is fatal"      2 python3 "$CHECKER" --input "$SPEC" --expect-rule R1
expect      "unknown --rules id is fatal"             2 python3 "$CHECKER" --input "$SPEC" --rules R9
expect      "empty --rules is fatal"                  2 python3 "$CHECKER" --input "$SPEC" --rules ""
expect      "duplicate --rules ids are fatal"         2 python3 "$CHECKER" --input "$SPEC" --rules R1,R1
expect      "R2 alone is clean on current spec"       0 python3 "$CHECKER" --input "$SPEC" --rules R2
expect      "expect-rule outside --rules is fatal"    2 python3 "$CHECKER" --input "$SPEC" --rules R2 --expect-rule R1 --expect-count 3
expect      "--help exits 0 (documented exception)"   0 python3 "$CHECKER" --help

# ---- checker: structural failures -----------------------------------------
expect "non-spec input (no sections) is fatal"        2 python3 "$CHECKER" --input "$ROUND1"
expect "missing input file is fatal"                  2 python3 "$CHECKER" --input "$SCRATCH/does-not-exist.md"
expect "malformed component entry is fatal"           2 python3 "$CHECKER" --input "$SCRATCH/malformed-entry.md"
expect "duplicate component is fatal"                 2 python3 "$CHECKER" --input "$SCRATCH/duplicate-component.md"
expect "malformed phase heading is fatal"             2 python3 "$CHECKER" --input "$SCRATCH/malformed-phase.md"
expect "duplicate phase is fatal"                     2 python3 "$CHECKER" --input "$SCRATCH/duplicate-phase.md"
expect "zero components is fatal"                     2 python3 "$CHECKER" --input "$SCRATCH/zero-components.md"
expect "missing section 4 is fatal"                   2 python3 "$CHECKER" --input "$SCRATCH/no-section4.md"
expect "broken entry numbering is fatal"              2 python3 "$CHECKER" --input "$SCRATCH/broken-numbering.md"
expect "indented (swallowed) entry is fatal"          2 python3 "$CHECKER" --input "$SCRATCH/indented-entry.md"
expect "indented entry after valid entry is fatal"    2 python3 "$CHECKER" --input "$SCRATCH/indented-after-entry.md"
expect "indented phase heading is fatal"              2 python3 "$CHECKER" --input "$SCRATCH/indented-heading.md"
expect "component-like prefix line is fatal"          2 python3 "$CHECKER" --input "$SCRATCH/prefix-candidate.md"
expect "non-canonical component name is fatal"        2 python3 "$CHECKER" --input "$SCRATCH/noncanonical-name.md"
expect "entry-like line in section intro is fatal"    2 python3 "$CHECKER" --input "$SCRATCH/intro-entry.md"
expect "prose intro in section 4 is fatal"            2 python3 "$CHECKER" --input "$SCRATCH/section4-intro.md"
expect "malformed numbered continuation is fatal"     2 python3 "$CHECKER" --input "$SCRATCH/malformed-continuation.md"
expect "decimal in continuation prose is allowed"     0 python3 "$CHECKER" --input "$SCRATCH/decimal-continuation.md"
expect "decimal-numbered bold entry is fatal"         2 python3 "$CHECKER" --input "$SCRATCH/decimal-bold-entry.md"
expect "tab inside component name is fatal"           2 python3 "$CHECKER" --input "$SCRATCH/tab-name.md"
expect "NBSP inside component name is fatal"          2 python3 "$CHECKER" --input "$SCRATCH/nbsp-name.md"

# ---- checker: dependency extraction ----------------------------------------
expect_grep "crossed overlap records both edges"      1 2 'FINDING\[R1\]' python3 "$CHECKER" --input "$SCRATCH/crossed-overlap.md" --rules R1
expect_grep "wrapped mention still produces its edge" 1 1 'FINDING\[R1\]' python3 "$CHECKER" --input "$SCRATCH/wrapped-mention.md" --rules R1

# ---- checker: R2 positive --------------------------------------------------
expect      "R2 fires on uncovered/undeclared"        0 python3 "$CHECKER" --input "$SCRATCH/r2-fires.md" --expect-rule R2 --expect-count 2
expect_grep "R2 fires exactly 2 times"                1 2 'FINDING\[R2\]' python3 "$CHECKER" --input "$SCRATCH/r2-fires.md" --rules R2

# ---- checker: crash wrapper (white-box) ------------------------------------
# These import the module and drive run_wrapped directly, proving the wrapper
# maps every unexpected outcome to exit 2 — never 0 (clean) and never 1
# (findings).
wb() { python3 - "$CHECKER" "$@" <<'PY'
import importlib.util, sys
spec = importlib.util.spec_from_file_location("cs", sys.argv[1])
cs = importlib.util.module_from_spec(spec); spec.loader.exec_module(cs)
case = sys.argv[2]
if case == "empty-registry":
    cs.RULES.clear()
    sys.exit(cs.run_wrapped(cs.main, ["--input", sys.argv[3]]))
if case == "forged-label":
    cs.RULES["R1"] = (lambda s: [cs.Finding("R2", "x", "forged")], "forged")
    sys.exit(cs.run_wrapped(cs.main, ["--input", sys.argv[3], "--expect-rule", "R1", "--expect-count", "1"]))
if case == "entry-returns-none":
    sys.exit(cs.run_wrapped(lambda argv: None, []))
if case == "entry-returns-true":
    sys.exit(cs.run_wrapped(lambda argv: True, []))
if case == "entry-returns-float":
    sys.exit(cs.run_wrapped(lambda argv: 0.0, []))
if case == "library-sysexit-zero":
    cs.RULES["R1"] = (lambda s: sys.exit(0), "hostile")
    sys.exit(cs.run_wrapped(cs.main, ["--input", sys.argv[3], "--rules", "R1"]))
if case == "generator-rule":
    real = cs.RULES["R1"][0]
    cs.RULES["R1"] = ((lambda s: (f for f in real(s))), "generator-returning rule")
    sys.exit(cs.run_wrapped(cs.main, ["--input", sys.argv[3], "--rules", "R1"]))
sys.exit(97)
PY
}
expect "empty rule registry is fatal"                 2 wb empty-registry "$SPEC"
expect "forged finding label is fatal"                2 wb forged-label "$SPEC"
expect "entry returning None is fatal"                2 wb entry-returns-none
expect "entry returning True is fatal"                2 wb entry-returns-true
expect "entry returning 0.0 is fatal"                 2 wb entry-returns-float
expect "sys.exit(0) from a rule is fatal"             2 wb library-sysexit-zero "$SPEC"
expect_grep "generator-returning rule keeps findings" 1 3 'FINDING\[R1\]' wb generator-rule "$SPEC"

# ---- generator: derive clean + round trip ----------------------------------
expect "generator reverses documented moves"          0 python3 "$GEN" --input "$SPEC" --output "$SCRATCH/clean.md" \
        --expect-clean --move audit-log-store:3:1 --move capacity-planner:3:1
expect "derived counterfactual is clean"              0 python3 "$CHECKER" --input "$SCRATCH/clean.md"
expect "generator re-derives broken state"            0 python3 "$GEN" --input "$SCRATCH/clean.md" --output "$SCRATCH/broken.md" \
        --expect-rule R1 --expect-count 3 --move audit-log-store:1:3 --move capacity-planner:1:3
expect "derived fixture re-fires R1 exactly 3x"       0 python3 "$CHECKER" --input "$SCRATCH/broken.md" --expect-rule R1 --expect-count 3

# ---- generator: structural failures ----------------------------------------
expect "missing postcondition is fatal"               2 python3 "$GEN" --input "$SPEC" --output "$SCRATCH/x.md" --move audit-log-store:3:1
expect "both postconditions is fatal"                 2 python3 "$GEN" --input "$SPEC" --output "$SCRATCH/x.md" --expect-clean \
        --expect-rule R1 --expect-count 1 --move audit-log-store:3:1
expect "unmet expect-clean is fatal, no write"        2 python3 "$GEN" --input "$SPEC" --output "$SCRATCH/x.md" --expect-clean \
        --move audit-log-store:3:1
expect "unmet expect-count is fatal, no write"        2 python3 "$GEN" --input "$SPEC" --output "$SCRATCH/x.md" \
        --expect-rule R1 --expect-count 9 --move audit-log-store:3:1
expect "unknown component is fatal"                   2 python3 "$GEN" --input "$SPEC" --output "$SCRATCH/x.md" --expect-clean --move no-such-thing:3:1
expect "wrong source phase is fatal"                  2 python3 "$GEN" --input "$SPEC" --output "$SCRATCH/x.md" --expect-clean --move audit-log-store:1:2
expect "missing target phase is fatal"                2 python3 "$GEN" --input "$SPEC" --output "$SCRATCH/x.md" --expect-clean --move audit-log-store:3:9
expect "no-op move is fatal"                          2 python3 "$GEN" --input "$SPEC" --output "$SCRATCH/x.md" --expect-clean --move audit-log-store:3:3
expect "conflicting duplicate move is fatal"          2 python3 "$GEN" --input "$SPEC" --output "$SCRATCH/x.md" --expect-clean \
        --move audit-log-store:3:1 --move audit-log-store:3:1
expect "bad move syntax is fatal"                     2 python3 "$GEN" --input "$SPEC" --output "$SCRATCH/x.md" --expect-clean --move 'audit-log-store:3->1'
cp "$SPEC" "$SCRATCH/copy.md"
expect "output aliasing input is fatal"               2 python3 "$GEN" --input "$SCRATCH/copy.md" --output "$SCRATCH/copy.md" --expect-clean --move audit-log-store:3:1
expect "overwrite without --force is fatal"           2 python3 "$GEN" --input "$SPEC" --output "$SCRATCH/clean.md" --expect-clean --move audit-log-store:3:1
expect "overwrite with --force succeeds"              0 python3 "$GEN" --input "$SPEC" --output "$SCRATCH/clean.md" --force --expect-clean \
        --move audit-log-store:3:1 --move capacity-planner:3:1
test ! -e "$SCRATCH/x.md" && { PASS=$((PASS+1)); printf 'PASS %-46s\n' "failed generator runs wrote nothing"; } \
  || { FAIL=$((FAIL+1)); printf 'FAIL %-46s\n' "failed generator runs wrote nothing"; }
cp "$GEN" "$SCRATCH/orphan-generator.py"
expect "missing sibling checker is fatal"             2 python3 "$SCRATCH/orphan-generator.py" --input "$SPEC" --output "$SCRATCH/x.md" --expect-clean --move audit-log-store:3:1
# Adversary round 2: a hostile sibling that calls sys.exit(0) at import time
# must not let the generator exit clean.
mkdir -p "$SCRATCH/hostile"
cp "$GEN" "$SCRATCH/hostile/fixture-generator-skeleton.py"
printf 'import sys\nsys.exit(0)\n' > "$SCRATCH/hostile/checker-skeleton.py"
expect "hostile sibling sys.exit(0) is fatal"         2 python3 "$SCRATCH/hostile/fixture-generator-skeleton.py" --input "$SPEC" --output "$SCRATCH/x.md" --expect-clean --move audit-log-store:3:1
# Adversary round 3: a sibling with a module-level __getattr__ that exits 0
# must not escape through the API-surface validation.
mkdir -p "$SCRATCH/hostile2"
cp "$GEN" "$SCRATCH/hostile2/fixture-generator-skeleton.py"
printf 'import sys\ndef __getattr__(name):\n    sys.exit(0)\n' > "$SCRATCH/hostile2/checker-skeleton.py"
expect "hostile sibling __getattr__ is fatal"         2 python3 "$SCRATCH/hostile2/fixture-generator-skeleton.py" --input "$SPEC" --output "$SCRATCH/x.md" --expect-clean --move audit-log-store:3:1
# Adversary round 3: a dangling symlink at the output path counts as existing.
ln -s "$SCRATCH/nonexistent-target" "$SCRATCH/dangling.md"
expect "dangling symlink output is fatal sans force"  2 python3 "$GEN" --input "$SPEC" --output "$SCRATCH/dangling.md" --expect-clean \
        --move audit-log-store:3:1 --move capacity-planner:3:1
# Adversary round 2: an emptied rule registry must not make --expect-clean a
# vacuous pass (white-box through the generator's own import of the checker).
wbg() { python3 - "$GEN" "$@" <<'PY'
import importlib.util, sys
spec = importlib.util.spec_from_file_location("fg", sys.argv[1])
fg = importlib.util.module_from_spec(spec); spec.loader.exec_module(fg)
fg.checker.RULES.clear()
sys.exit(fg.checker.run_wrapped(fg.main, sys.argv[2:]))
PY
}
expect "empty registry in generator is fatal"         2 wbg --input "$SPEC" --output "$SCRATCH/x.md" --expect-clean --move audit-log-store:3:1

# ---- fixture directory untouched -------------------------------------------
SPEC_SUM_AFTER=$(cksum < "$SPEC")
if [ "$SPEC_SUM_BEFORE" = "$SPEC_SUM_AFTER" ]; then
  PASS=$((PASS+1)); printf 'PASS %-46s\n' "eval fixture unmodified"
else
  FAIL=$((FAIL+1)); printf 'FAIL %-46s\n' "eval fixture unmodified"
fi

echo
echo "selftest: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
