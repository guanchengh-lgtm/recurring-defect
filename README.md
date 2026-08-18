# Recurring Defect

Recurring Defect turns a bug, review finding, or mistake that keeps returning into a mechanical check that catches the whole defect class. It helps choose an appropriately sized response, build fail-closed checks, prove them against derived historical fixtures, and attack them for false-clean failure modes.

## Clone

```sh
git clone https://github.com/guanchengh-lgtm/recurring-defect.git
```

## Install

Point your agent's skill directory at the cloned repository, or copy the repository there:

- Claude Code: `~/.claude/skills/recurring-defect`
- Pi: `~/.pi/agent/skills/recurring-defect`
- Codex: `$CODEX_HOME/skills/recurring-defect` (usually `~/.codex/skills/recurring-defect`)

See [`SKILL.md`](SKILL.md) for the method and [`evals/`](evals/) for evaluation fixtures.

## License

MIT. See [`LICENSE`](LICENSE).
