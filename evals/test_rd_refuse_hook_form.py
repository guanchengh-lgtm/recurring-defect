#!/usr/bin/env python3
"""Contract tests for refuse-hook form selection (rd-refuse-hook-form).

Public interfaces under test:
  - SKILL.md — agent-facing skill prompt (intentional emitted interface)
  - evals/evals.json — machine-consumed evaluation fixture catalog
  - data/rd-refuse-hook-form/measure.md — owned five-line measurement contract

These tests do not call a live model. They assert the skill interface and
evaluation fixtures encode the required form-selection policy for misses that
are only observable at a lifecycle event.
"""

from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "SKILL.md"
EVALS = ROOT / "evals" / "evals.json"
MEASURE = ROOT / "data" / "rd-refuse-hook-form" / "measure.md"


def _section(text: str, heading: str) -> str:
    """Return body text under an ATX heading until the next same-or-higher heading."""
    start = re.compile(
        rf"^(#{{1,6}})[ \t]+{re.escape(heading)}[ \t]*$",
        re.MULTILINE,
    )
    match = start.search(text)
    if not match:
        raise AssertionError(f"missing section heading: {heading!r}")
    level = len(match.group(1))
    body_start = match.end()
    # Only a heading at the same or higher level closes this section.
    closer = re.compile(rf"^#{{1,{level}}}[ \t]+\S", re.MULTILINE)
    end = closer.search(text, body_start)
    body = text[body_start : end.start() if end else len(text)]
    return body


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


class MeasureContract(unittest.TestCase):
    def test_exactly_five_lines_with_required_fields(self) -> None:
        raw = MEASURE.read_text(encoding="utf-8")
        # Trailing newline is fine; blank lines are not.
        lines = raw.splitlines()
        self.assertEqual(
            len(lines),
            5,
            f"measure.md must be exactly five lines, got {len(lines)}: {lines!r}",
        )
        self.assertTrue(raw.endswith("\n"), "measure.md should end with a newline")
        self.assertFalse(any(line.strip() == "" for line in lines), "no blank lines")

        fields: dict[str, str] = {}
        for line in lines:
            self.assertIn(": ", line, f"expected 'key: value' line, got {line!r}")
            key, value = line.split(": ", 1)
            fields[key] = value
            self.assertTrue(value.strip(), f"empty value for {key!r}")

        required = {
            "recurring miss",
            "baseline",
            "hook observation",
            "refusal metric",
            "residual metric",
        }
        self.assertEqual(set(fields), required)

        joined = " ".join(fields.values()).lower()
        self.assertIn("spawn", joined)
        self.assertIn("slice", fields["recurring miss"].lower())
        self.assertNotRegex(joined, r"100\s*%|guaranteed")
        # Residual must be distinct from what the hook refuses at spawn.
        self.assertNotEqual(
            fields["refusal metric"].strip().lower(),
            fields["residual metric"].strip().lower(),
        )


class EvalFixtureContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        catalog = json.loads(EVALS.read_text(encoding="utf-8"))
        cls.catalog = catalog
        matches = [
            e for e in catalog["evals"] if e.get("name") == "worker-spawn-wrong-slice"
        ]
        assert len(matches) == 1, matches
        cls.case = matches[0]

    def test_catalog_shape(self) -> None:
        self.assertEqual(self.catalog.get("skill_name"), "recurring-defect")
        self.assertIsInstance(self.case.get("id"), int)
        self.assertIsInstance(self.case.get("prompt"), str)
        self.assertIsInstance(self.case.get("expected_output"), str)
        self.assertIsInstance(self.case.get("assertions"), list)
        self.assertEqual(self.case.get("files"), [])

    def test_prompt_is_non_artifact_lifecycle_miss(self) -> None:
        prompt = self.case["prompt"].lower()
        # Scenario: live coordinator state only, user wrongly asks for lint/CI + skip flag.
        self.assertIn("not written into code", prompt)
        self.assertRegex(prompt, r"\bspec\b")
        self.assertIn("ci-visible", prompt)
        self.assertRegex(prompt, r"\blint\b")
        self.assertRegex(prompt, r"\bci\b")
        self.assertIn("skip-slice-check", prompt)
        self.assertIn("twice", prompt)

    def test_expected_policy(self) -> None:
        expected = self.case["expected_output"].lower()
        self.assertIn("reject lint and ci", expected)
        self.assertIn("not artifact-observable", expected)
        self.assertIn("spawn", expected)
        self.assertIn("refuse-hook", expected)
        self.assertIn("residual", expected)
        self.assertRegex(expected, r"optional|skippable|bypass")

    def test_assertions_cover_intent(self) -> None:
        assertions = [a.lower() for a in self.case["assertions"]]
        blob = "\n".join(assertions)

        def require(pred: bool, msg: str) -> None:
            self.assertTrue(pred, msg + f"\nassertions:\n{blob}")

        require(
            any(
                "not observable" in a and ("code" in a or "spec" in a or "ci" in a)
                for a in assertions
            ),
            "must require stating non-artifact observability",
        )
        require(
            any("does not select lint or ci" in a for a in assertions),
            "must forbid lint/CI selection",
        )
        require(
            any("refuse-hook" in a and "spawn" in a for a in assertions),
            "must require spawn refuse-hook",
        )
        require(
            any("skip" in a or "bypass" in a or "optional" in a for a in assertions),
            "must reject optional/skippable bypass",
        )
        require(
            any("routine" in a and "refuse-hook" in a for a in assertions),
            "routine only alongside refuse-hook",
        )
        require(
            any("residual" in a for a in assertions),
            "must name/measure residual",
        )
        require(
            any(
                "100%" in a or "guaranteed-coverage" in a or "guaranteed" in a
                for a in assertions
            ),
            "must forbid 100%/guaranteed coverage claims",
        )


class SkillFormSelectionInterface(unittest.TestCase):
    """SKILL.md is the emitted agent interface for form selection."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.skill = SKILL.read_text(encoding="utf-8")
        cls.sizing = _section(cls.skill, "Observability fork, then size and form")
        cls.forms = _section(cls.skill, "Three output forms")
        cls.method = _section(cls.skill, "The method")

    def test_observability_fork_before_size_and_form(self) -> None:
        sizing = _norm(self.sizing)
        # Observability is decided first; Full/Light only apply on the artifact path.
        self.assertIn(
            "first decide whether the miss is observable in an artifact", sizing
        )
        self.assertIn("code", sizing)
        self.assertIn("specification", sizing)
        self.assertIn("ci-visible", sizing)
        self.assertIn("size and form come only after that fork", sizing)
        self.assertIn(
            "if the miss is not observable there, **never select lint or ci as the check**",
            sizing,
        )
        self.assertIn("do **not** pick full or light", sizing)
        # Lifecycle path sizes refuse-hook work, not CI machinery.
        self.assertIn("lifecycle-only miss", sizing)
        self.assertIn("refuse-hook", sizing)
        self.assertIn("not full/light ci", sizing)
        self.assertIn("not ci wiring", sizing)
        # Artifact path keeps Full/Light/Neither after the fork.
        self.assertIn("only after the miss is artifact-observable", sizing)
        self.assertIn("full method", sizing)
        self.assertIn("light", sizing)
        self.assertIn("neither", sizing)

    def test_observability_gate_before_form_choice(self) -> None:
        forms = _norm(self.forms)
        self.assertIn("observability fork", forms)
        self.assertIn(
            "if the miss is not observable there, **never select lint or ci as the check**",
            forms,
        )

    def test_routine_requires_refuse_hook_at_lifecycle(self) -> None:
        forms = _norm(self.forms)
        self.assertIn("a routine with a refuse-hook", forms)
        for event in ("cleanup", "spawn", "done"):
            self.assertIn(event, forms)
        self.assertIn("refuse the illegal state itself", forms)
        self.assertIn("optional/skippable flag", forms)
        self.assertIn("insufficient", forms)
        self.assertIn(
            "documented routine is allowed only alongside the refuse-hook",
            forms,
        )
        self.assertIn("residual", forms)
        self.assertIn("do not claim 100% coverage", forms)
        self.assertIn(
            "refuse-hooks are not a form for artifact-observable misses", forms
        )

    def test_unfinished_step1_requires_event_and_residual(self) -> None:
        forms = _norm(self.forms)
        self.assertIn("lifecycle event", forms)
        self.assertIn("residual is measured", forms)
        self.assertIn("you have not finished step 1", forms)

    def test_method_redirect_keeps_refuse_hook(self) -> None:
        # Step 3 redirect must not re-open unhooked routines or noisy gates.
        step3 = _norm(_section(self.skill, "3. Write the rule"))
        self.assertIn("routine with a refuse-hook", step3)
        self.assertIn("refusal at the observable lifecycle event", step3)


class FormSelectionDecisionTable(unittest.TestCase):
    """Executable decision table for the eval scenario.

    Encodes the skill's public policy as pure functions and checks the
    worker-spawn-wrong-slice inputs select refuse-hook, never lint/CI/unhooked
    routine/skippable flag, and never Full/Light CI sizing on lifecycle-only misses.
    """

    @staticmethod
    def select_size(*, observable_in_artifact: bool, proposed_size: str) -> dict:
        """Return size verdict after the observability fork."""
        size = proposed_size.lower().strip()
        if not observable_in_artifact:
            if size in {"full", "light"}:
                return {
                    "accept": False,
                    "size": None,
                    "reason": "lifecycle-only miss must not select Full/Light CI machinery",
                }
            if size == "refuse-hook":
                return {
                    "accept": True,
                    "size": "refuse-hook",
                    "reason": "lifecycle-only miss sizes refuse-hook work, not CI",
                }
            return {
                "accept": False,
                "size": None,
                "reason": "lifecycle-only miss requires refuse-hook sizing",
            }
        if size in {"full", "light", "neither"}:
            return {
                "accept": True,
                "size": size,
                "reason": "artifact-observable miss may size Full/Light/Neither",
            }
        return {
            "accept": False,
            "size": None,
            "reason": "artifact-observable miss uses Full/Light/Neither, not refuse-hook size",
        }

    @staticmethod
    def select_form(
        *,
        observable_in_artifact: bool,
        lifecycle_event: str | None,
        proposed: str,
        skippable_bypass: bool,
        residual_named: bool,
    ) -> dict:
        """Return selection verdict for a proposed check form."""
        proposed = proposed.lower().strip()
        event = (lifecycle_event or "").lower().strip() or None
        allowed_events = {"cleanup", "spawn", "done"}

        if observable_in_artifact:
            if proposed in {"lint", "ci", "rule", "advisory"}:
                return {
                    "accept": True,
                    "form": proposed,
                    "reason": "artifact-observable miss may use rule/advisory/lint/CI",
                }
            # No fallthrough into lifecycle forms.
            return {
                "accept": False,
                "form": None,
                "reason": (
                    "artifact-observable miss accepts only rule/advisory/lint/CI; "
                    "refuse-hook/routine forms are for lifecycle-only misses"
                ),
            }

        # Non-artifact miss path.
        if proposed in {"lint", "ci", "rule", "advisory"}:
            return {
                "accept": False,
                "form": None,
                "reason": "non-artifact miss must not select lint/CI/rule/advisory",
            }
        if skippable_bypass:
            return {
                "accept": False,
                "form": None,
                "reason": "optional/skippable bypass is not a refuse-hook",
            }
        if proposed in {"reminder", "checklist", "unhooked-routine", "routine"}:
            return {
                "accept": False,
                "form": None,
                "reason": "unhooked routine/reminder/checklist is insufficient",
            }
        if event not in allowed_events:
            return {
                "accept": False,
                "form": None,
                "reason": "non-artifact miss requires refuse-hook at cleanup|spawn|done",
            }
        if proposed not in {"refuse-hook", "routine-with-refuse-hook"}:
            return {
                "accept": False,
                "form": None,
                "reason": "must refuse illegal state at the lifecycle event",
            }
        if not residual_named:
            return {
                "accept": False,
                "form": None,
                "reason": "must name and measure residual; never claim 100% coverage",
            }
        return {
            "accept": True,
            "form": "routine-with-refuse-hook"
            if proposed == "routine-with-refuse-hook"
            else "refuse-hook",
            "event": event,
            "reason": "lifecycle refuse-hook with named residual",
        }

    def test_lifecycle_size_rejects_full_and_light(self) -> None:
        for bad in ("full", "light", "neither"):
            got = self.select_size(observable_in_artifact=False, proposed_size=bad)
            self.assertFalse(got["accept"], bad)
            self.assertIsNone(got["size"])
        got = self.select_size(
            observable_in_artifact=False, proposed_size="refuse-hook"
        )
        self.assertTrue(got["accept"])
        self.assertEqual(got["size"], "refuse-hook")

    def test_artifact_size_allows_full_light_neither(self) -> None:
        for size in ("full", "light", "neither"):
            got = self.select_size(observable_in_artifact=True, proposed_size=size)
            self.assertTrue(got["accept"], size)
            self.assertEqual(got["size"], size)
        refuse_size = self.select_size(
            observable_in_artifact=True, proposed_size="refuse-hook"
        )
        self.assertFalse(refuse_size["accept"])

    def test_eval_scenario_rejects_lint_ci_skip_unhooked(self) -> None:
        base = dict(
            observable_in_artifact=False,
            lifecycle_event="spawn",
            skippable_bypass=False,
            residual_named=True,
        )
        for bad in (
            "lint",
            "ci",
            "rule",
            "advisory",
            "reminder",
            "checklist",
            "unhooked-routine",
            "routine",
        ):
            got = self.select_form(proposed=bad, **base)
            self.assertFalse(got["accept"], bad)
            self.assertIsNone(got["form"])

        skip = self.select_form(
            observable_in_artifact=False,
            lifecycle_event="spawn",
            proposed="refuse-hook",
            skippable_bypass=True,
            residual_named=True,
        )
        self.assertFalse(skip["accept"])

        no_residual = self.select_form(
            observable_in_artifact=False,
            lifecycle_event="spawn",
            proposed="refuse-hook",
            skippable_bypass=False,
            residual_named=False,
        )
        self.assertFalse(no_residual["accept"])

    def test_eval_scenario_accepts_spawn_refuse_hook_with_residual(self) -> None:
        got = self.select_form(
            observable_in_artifact=False,
            lifecycle_event="spawn",
            proposed="refuse-hook",
            skippable_bypass=False,
            residual_named=True,
        )
        self.assertTrue(got["accept"])
        self.assertEqual(got["form"], "refuse-hook")
        self.assertEqual(got["event"], "spawn")

        paired = self.select_form(
            observable_in_artifact=False,
            lifecycle_event="spawn",
            proposed="routine-with-refuse-hook",
            skippable_bypass=False,
            residual_named=True,
        )
        self.assertTrue(paired["accept"])
        self.assertEqual(paired["form"], "routine-with-refuse-hook")

    def test_artifact_miss_still_allows_lint(self) -> None:
        got = self.select_form(
            observable_in_artifact=True,
            lifecycle_event=None,
            proposed="lint",
            skippable_bypass=False,
            residual_named=False,
        )
        self.assertTrue(got["accept"])
        self.assertEqual(got["form"], "lint")

    def test_artifact_miss_rejects_refuse_hook_without_fallthrough(self) -> None:
        for bad in ("refuse-hook", "routine-with-refuse-hook", "routine", "reminder"):
            got = self.select_form(
                observable_in_artifact=True,
                lifecycle_event="spawn",
                proposed=bad,
                skippable_bypass=False,
                residual_named=True,
            )
            self.assertFalse(got["accept"], bad)
            self.assertIsNone(got["form"])
            self.assertIn("artifact-observable", got["reason"])

    def test_eval_scenario_sizes_refuse_hook_not_ci(self) -> None:
        # Concrete path: user asks for lint/CI on live coordinator state.
        size = self.select_size(observable_in_artifact=False, proposed_size="full")
        self.assertFalse(size["accept"])
        size = self.select_size(
            observable_in_artifact=False, proposed_size="refuse-hook"
        )
        form = self.select_form(
            observable_in_artifact=False,
            lifecycle_event="spawn",
            proposed="refuse-hook",
            skippable_bypass=False,
            residual_named=True,
        )
        self.assertTrue(size["accept"])
        self.assertTrue(form["accept"])
        self.assertEqual(form["event"], "spawn")

    def test_measure_residual_matches_accepted_form(self) -> None:
        """End-to-end: measure.md residual is what spawn hook cannot observe."""
        lines = MEASURE.read_text(encoding="utf-8").splitlines()
        fields = dict(line.split(": ", 1) for line in lines)
        self.assertIn("spawn", fields["hook observation"].lower())
        # Hook sees declared vs live at spawn; residual is post-accept duplicates.
        self.assertIn(
            "spawn",
            fields["refusal metric"].lower() + fields["hook observation"].lower(),
        )
        residual = fields["residual metric"].lower()
        self.assertTrue(
            "after accepted" in residual or "duplicate" in residual,
            residual,
        )
        verdict = self.select_form(
            observable_in_artifact=False,
            lifecycle_event="spawn",
            proposed="routine-with-refuse-hook",
            skippable_bypass=False,
            residual_named=True,
        )
        self.assertTrue(verdict["accept"])


def main() -> int:
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
