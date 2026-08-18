#!/usr/bin/env python3
"""Starter fixture generator for the recurring-defect skill.

Derives a "before the fix" regression fixture MECHANICALLY from the current
artifact by reversing a documented change — here, moving components between
phases (the shape of the platform-spec fixture's ADR-0003/0007). Never
hand-write a fixture: a hand-written one is tuned, consciously or not, in the
rule's favour, and it drifts as the artifact evolves (SKILL.md step 4).

Usage:
  fixture-generator-skeleton.py --input docs/spec.md --output /tmp/derived.md \
      --move audit-log-store:3:1 --move capacity-planner:3:1

  --move SLUG:FROM:TO   move component SLUG from phase FROM to phase TO.
                        Repeatable; applied sequentially in CLI order.
                        Colon-separated on purpose: an arrow syntax like 3->1
                        contains a shell redirect and truncates a file named
                        "1" when unquoted.

The generator asserts its own expectations, each fatal (exit 2, no file
written) — without these, a parser regression shrinks the fixture through the
same bug it is meant to catch, and the regression quietly passes:
  - every --move component exists, and sits in its stated FROM phase at apply
    time (covers duplicate and conflicting moves);
  - FROM != TO (a no-op move is a mistake, not a fixture);
  - the TO phase exists in the document;
  - the output re-parses with the SAME parser the checker uses (imported from
    checker-skeleton.py — one parser, no drift);
  - fidelity: component count unchanged, every component's raw entry text
    byte-identical apart from the leading list number, every phase membership
    exactly as requested, and all text outside the components section
    byte-identical;
  - POSTCONDITION (required): the caller must declare what the output is FOR.
    Either `--expect-rule R1 --expect-count 3` (the output must fire that rule
    exactly that many times — a "regression fixture" that carries no defect is
    the quietest possible fail-open) or `--expect-clean` (every registry rule
    must produce zero findings). The postcondition is evaluated in memory
    BEFORE the file is written; on mismatch nothing is written.

Output safety: refuses --output equal to --input, refuses to overwrite an
existing file without --force, validates fully in memory, then writes
atomically (temp file + rename). The eval fixture directory is never modified.

Exit contract: 0 fixture written; 2 structural failure (any assertion, CLI, or
unexpected error). There is no exit-1 path — this tool has no findings.

LIMITS:
  - The derived fixture is a synthetic counterfactual: it reverses the
    documented location moves only, not contemporaneous wording changes. It is
    not a claim of byte-equivalence with the historical artifact.
  - Moved entries are appended at the end of the target phase, so a
    move-out-and-back round trip preserves parse-level content but not
    necessarily entry order or bytes.
  - Fidelity is LINE-CONTENT fidelity: the output is written with LF line
    endings and a trailing newline, so CRLF input or a missing final newline
    is normalized rather than preserved byte-for-byte.
  - Format-bound to the platform-spec adapter in checker-skeleton.py, which
    must sit in the same directory as this file.
"""

import argparse
import importlib.util
import os
import re
import sys
import tempfile
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_CHECKER = _HERE / "checker-skeleton.py"


def _load_checker():
    """One parser, no drift: reuse the checker's parse_spec. importlib is
    needed because the hyphenated filename cannot be a plain import. Fails
    closed when the sibling is missing — the two files travel together."""
    if not _CHECKER.is_file():
        print(
            f"STRUCTURAL FAILURE: {_CHECKER} not found — checker-skeleton.py "
            "must sit beside this file (it provides the shared parser)",
            file=sys.stderr,
        )
        sys.exit(2)
    try:
        spec = importlib.util.spec_from_file_location("checker_skeleton", _CHECKER)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        # API surface check INSIDE the boundary, against the module dict:
        # hasattr() would run a hostile module-level __getattr__, which could
        # sys.exit(0) its way past a check placed outside this try block.
        missing = [
            required
            for required in ("parse_spec", "run_rules", "run_wrapped",
                             "resolve_rule_ids", "StructuralFailure", "RULES")
            if required not in vars(mod)
        ]
    except BaseException as e:  # noqa: BLE001 — import runs before any wrapper
        # exists; a sibling that raises — or calls sys.exit(0) at import time —
        # must exit 2, never impersonate a successful generator run.
        print(
            f"STRUCTURAL FAILURE: could not import {_CHECKER}: {e!r}",
            file=sys.stderr,
        )
        sys.exit(2)
    if missing:
        print(
            f"STRUCTURAL FAILURE: {_CHECKER} lacks {missing!r} — wrong or "
            "stale sibling",
            file=sys.stderr,
        )
        sys.exit(2)
    return mod


checker = _load_checker()
StructuralFailure = checker.StructuralFailure

MOVE_RE = re.compile(r"^([a-z0-9-]+):(\d+):(\d+)$")


def parse_moves(raw_moves):
    moves = []
    for raw in raw_moves:
        m = MOVE_RE.match(raw)
        if not m:
            raise StructuralFailure(
                f"bad --move {raw!r}: expected SLUG:FROM:TO (e.g. audit-log-store:3:1)"
            )
        slug, src, dst = m.group(1), int(m.group(2)), int(m.group(3))
        if src == dst:
            raise StructuralFailure(f"--move {raw!r} is a no-op (FROM == TO)")
        moves.append((slug, src, dst))
    return moves


def apply_moves(spec, moves):
    """Sequential, order-sensitive application over phase membership lists.
    Each precondition failure is fatal — a move that silently matched nothing
    would shrink the fixture through the exact bug class it must catch."""
    order = sorted(spec.phases, key=lambda n: spec.phases[n])
    membership = {n: [c for c in spec.components if c.phase == n] for n in order}
    for slug, src, dst in moves:
        if dst not in membership:
            raise StructuralFailure(f"--move {slug}: target phase {dst} does not exist")
        if src not in membership:
            raise StructuralFailure(f"--move {slug}: source phase {src} does not exist")
        matches = [c for c in membership[src] if c.slug == slug]
        if not matches:
            where = [n for n in membership for c in membership[n] if c.slug == slug]
            raise StructuralFailure(
                f"--move {slug}: not found in phase {src} at apply time "
                + (f"(currently in phase {where[0]})" if where else "(no such component)")
            )
        comp = matches[0]
        membership[src].remove(comp)
        membership[dst].append(comp)
    return order, membership


def rebuild(spec, order, membership):
    """Reassemble the document: only the components section is rebuilt; every
    other line is carried over verbatim."""
    start, end = spec.section3_span
    out = list(spec.lines[:start])
    out.append(spec.lines[start])  # the `## 3.` heading itself
    out.extend(spec.section3_intro)
    for num in order:
        out.append(spec.lines[spec.phases[num]])  # `### Phase N` heading, verbatim
        out.extend(spec.phase_layout[num]["prefix"])
        for i, comp in enumerate(membership[num], start=1):
            first = re.sub(r"^\d+\.", f"{i}.", comp.raw_block[0], count=1)
            out.append(first)
            out.extend(comp.raw_block[1:])
        out.extend(spec.phase_layout[num]["suffix"])
    out.extend(spec.lines[end:])
    return "\n".join(out) + "\n"


def assert_fidelity(spec, out_text, moves, source_label):
    """Re-parse the output with the shared parser and verify the transform did
    exactly what was asked — count and membership checks alone cannot detect a
    mangled description body, and the body is where the dependencies live."""
    reparsed = checker.parse_spec(out_text, source=source_label)

    before = {c.slug: c for c in spec.components}
    after = {c.slug: c for c in reparsed.components}
    _assert_sets_and_bodies(spec, before, after, reparsed, moves)

    in_lines, out_lines = spec.lines, out_text.splitlines()
    s, e = spec.section3_span
    tail_len = len(in_lines) - e
    if out_lines[:s] != in_lines[:s] or (
        tail_len and out_lines[-tail_len:] != in_lines[e:]
    ):
        raise StructuralFailure("fidelity: text outside the components section changed")
    return reparsed


def _assert_sets_and_bodies(spec, before, after, reparsed, moves):
    if set(before) != set(after):
        raise StructuralFailure(
            f"fidelity: component sets differ: lost {sorted(set(before) - set(after))}, "
            f"gained {sorted(set(after) - set(before))}"
        )
    if len(reparsed.components) != len(spec.components):
        raise StructuralFailure("fidelity: component count changed")

    expected_phase = {slug: c.phase for slug, c in before.items()}
    for slug, _src, dst in moves:
        expected_phase[slug] = dst
    for slug, comp in after.items():
        if comp.phase != expected_phase[slug]:
            raise StructuralFailure(
                f"fidelity: {slug} is in phase {comp.phase}, expected {expected_phase[slug]}"
            )
        if comp.body_raw != before[slug].body_raw:
            raise StructuralFailure(
                f"fidelity: raw entry text of {slug} changed during the move — "
                "only the leading list number may differ"
            )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Derive a before-the-fix fixture by reversing documented phase moves.",
        epilog="Exit codes: 0 fixture written, 2 structural failure. No exit-1 path.",
    )
    parser.add_argument("--input", required=True, help="current artifact (read-only)")
    parser.add_argument("--output", required=True, help="derived fixture to write")
    parser.add_argument(
        "--move",
        action="append",
        required=True,
        metavar="SLUG:FROM:TO",
        help="component move to apply (repeatable, sequential)",
    )
    parser.add_argument(
        "--force", action="store_true", help="allow overwriting an existing output file"
    )
    parser.add_argument(
        "--expect-rule",
        default=None,
        help="postcondition: rule id the OUTPUT must fire (with --expect-count)",
    )
    parser.add_argument(
        "--expect-count",
        type=int,
        default=None,
        help="postcondition: exact firing count for --expect-rule on the output (> 0)",
    )
    parser.add_argument(
        "--expect-clean",
        action="store_true",
        help="postcondition: every registry rule must produce zero findings on the output",
    )
    args = parser.parse_args(argv)

    # A generator that does not know what its output is for cannot notice that
    # it produced a defect-free "regression fixture" — the quietest fail-open.
    has_expect = args.expect_rule is not None or args.expect_count is not None
    if (args.expect_rule is None) != (args.expect_count is None):
        raise StructuralFailure("--expect-rule and --expect-count must be given together")
    if has_expect == args.expect_clean:
        raise StructuralFailure(
            "exactly one postcondition is required: --expect-rule/--expect-count "
            "(output must carry the defect) or --expect-clean (output must be clean)"
        )
    if args.expect_count is not None and args.expect_count <= 0:
        raise StructuralFailure("--expect-count must be > 0 (0 passes while the rule is dead)")
    if args.expect_rule is not None and args.expect_rule not in checker.RULES:
        raise StructuralFailure(
            f"unknown --expect-rule {args.expect_rule!r}; known: {sorted(checker.RULES)}"
        )

    in_path = Path(args.input)
    out_path = Path(args.output)
    if not in_path.is_file():
        raise StructuralFailure(f"input not found or not a file: {in_path}")
    if out_path.exists() and out_path.resolve() == in_path.resolve():
        raise StructuralFailure("--output must not be the same file as --input")
    if os.path.lexists(out_path) and not args.force:
        # lexists: a dangling symlink is still an existing destination.
        raise StructuralFailure(f"output exists (use --force to overwrite): {out_path}")

    try:
        text = in_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        raise StructuralFailure(f"input unreadable: {in_path}: {e}")

    moves = parse_moves(args.move)
    spec = checker.parse_spec(text, source=str(in_path))
    order, membership = apply_moves(spec, moves)
    out_text = rebuild(spec, order, membership)
    reparsed = assert_fidelity(spec, out_text, moves, source_label=f"{out_path} (in memory)")

    # Postcondition: evaluate the output's findings in memory before writing.
    # resolve_rule_ids(None) re-validates the registry — an emptied registry
    # must not turn --expect-clean into a vacuous pass.
    all_rules = checker.resolve_rule_ids(None)
    if args.expect_clean:
        residue = checker.run_rules(reparsed, all_rules)
        if residue:
            for f in residue:
                print(f.render(), file=sys.stderr)
            raise StructuralFailure(
                f"postcondition --expect-clean failed: output has {len(residue)} finding(s)"
            )
    else:
        hits = checker.run_rules(reparsed, [args.expect_rule])
        if len(hits) != args.expect_count:
            raise StructuralFailure(
                f"postcondition failed: {args.expect_rule} fired {len(hits)} time(s) "
                f"on the output, expected exactly {args.expect_count} — refusing to "
                "write a fixture that does not carry its defect"
            )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    # tempfile.mkstemp: unpredictable name + O_CREAT|O_EXCL, so a pre-created
    # symlink at a guessable tmp path cannot redirect this write.
    fd, tmp_name = tempfile.mkstemp(
        dir=out_path.parent, prefix=f".{out_path.name}.", suffix=".tmp"
    )
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(out_text)
        if args.force:
            os.replace(tmp, out_path)  # atomic overwrite
        else:
            try:
                os.link(tmp, out_path)  # atomic AND exclusive — no exists/replace race
            except FileExistsError:
                raise StructuralFailure(
                    f"output appeared during the run (use --force to overwrite): {out_path}"
                )
    finally:
        tmp.unlink(missing_ok=True)

    print(f"derived fixture written: {out_path}")
    for slug, src, dst in moves:
        print(f"  moved {slug}: phase {src} -> phase {dst}")
    post = (
        "clean (0 findings, all rules)"
        if args.expect_clean
        else f"{args.expect_rule} x{args.expect_count}"
    )
    print(
        "self-assertions passed: found/no-op/target, re-parse, count, membership, "
        f"fidelity, postcondition [{post}]"
    )
    return 0


if __name__ == "__main__":
    sys.exit(checker.run_wrapped(main))
