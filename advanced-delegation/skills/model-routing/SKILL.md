---
name: model-routing
description: Before a big job: hand parts to subagents on cheaper models
version: 0.1.0
author: Ziad Osama El-Boshy (ziadelboshy)
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [delegation, model-routing, subagents, cost, ledger]
---

# Model Routing Skill

Split big work into subagent tasks and send each one to the cheapest of your advanced-delegation
model routes that reliably passes it, escalating only when the model itself was the problem. A
stdlib helper script keeps a local ledger of outcomes, so route suggestions learn from real test
results. The skill adds no tools; it uses `delegate_task` with the routes set up for you in Model
routes mode (`delegation.backend: model_map`).

## When to Use

- Work with 3+ independent parts, several files or areas, bulk repetitive edits, parallel
  research, or an implement -> test -> fix loop with mechanical parts.
- 3+ documents or sources that each need reading and judging (contracts, tenders, reports):
  hand each reading to a subagent, so the documents stay out of your own chat, and keep the
  comparison and the answer yourself.
- Any `delegate_task` call while Model routes mode is active, and any failed subagent task.
- After the model routes change (re-sync the ladder).

Don't use for: work one program does in a pass (write the program yourself), small work
(roughly under 15 minutes or 1-2 files, unless it is the reading above), tightly coupled changes,
work that needs the user's back-and-forth, or a split whose handoff costs more than the cheaper
route saves. Subagents start blank and re-read files.

## Prerequisites

- The advanced-delegation plugin enabled, in Model routes mode, with routes **ordered cheapest
  -> strongest**, each with a one-line description. The order is the ladder this skill climbs.
  The routes are the ones nadicode chose for the company's Agents, already in that order; you
  cannot add, edit or reorder them.
- Python 3.8+ for `scripts/route_ledger.py` (stdlib only). `sync-routes` also needs ruamel.yaml or
  PyYAML to read your settings file; the `python` in your terminal has it.
- The ledger follows the active Agent (`HERMES_HOME`).

## How to Run

Run every command through the `terminal` tool, in the Agent that delegates:

```
terminal(command='python "${HERMES_SKILL_DIR}/scripts/route_ledger.py" sync-routes', timeout=240)
```

Nadia fills in `${HERMES_SKILL_DIR}` (this skill's folder inside the plugin) when it loads this
file; if `skills.template_vars` is off, use the `skill_dir` that `skill_view` reports.

`sync-routes` reads your routes in config order from your own settings file
(`<HERMES_HOME>/config.yaml`), and stores names, descriptions and
`provider:model@effort[+tier][+daybreak]` (never keys or URL credentials) in `routes.json` beside
the ledger. Use `--from FILE` to read saved routes instead (UTF-8, or UTF-16 with a BOM).
Malformed routes are skipped with a warning.

## Quick Reference

```
python "${HERMES_SKILL_DIR}/scripts/route_ledger.py" sync-routes [--from FILE|-]
python "${HERMES_SKILL_DIR}/scripts/route_ledger.py" ladder
python "${HERMES_SKILL_DIR}/scripts/route_ledger.py" classes
python "${HERMES_SKILL_DIR}/scripts/route_ledger.py" suggest --class <class> --difficulty <1-5> [--risk high]
python "${HERMES_SKILL_DIR}/scripts/route_ledger.py" add --class <class> --difficulty <n> [--risk high] --route <route> --outcome pass|fail --attempt <n> [--cause <cause>] --task "<what>" --evidence "<test command + result>" [--project <name>]
python "${HERMES_SKILL_DIR}/scripts/route_ledger.py" stats [--class <class>]
```

Causes (required for a failure): `model`, `spec`, `context`, `env`, `flaky`.
Files: ledger `<HERMES_HOME>/plugin-data/advanced-delegation/routing-ledger.jsonl`,
ladder `routes.json` in the same folder.

## Procedure

1. **Sync the ladder.** Run `sync-routes`, then `ladder`. Done when the printed order runs cheapest
   -> strongest; if not, tell the person the order looks wrong and do not try to change it.
2. **Decide whether to split** (When to Use above). Done when you either do the work in the main
   session or have a list of independent tasks.
3. **Plan so nothing is left to guess**: files, data shapes, edge cases, acceptance tests. For
   multi-module work write a contract doc first (see `references/workflow.md`). Done when every
   task has an acceptance check you can run.
4. **Build the task table**: task, class (`classes`), difficulty 1-5, risk low/high, owned files
   (no overlap between parallel tasks), acceptance check. Route each with `suggest`. Done when
   every row has a suggested route.
5. **Dispatch** independent tasks in parallel with `delegate_task`, each task's `option` set to
   its route and a self-contained brief: owned files, the contract, "do not commit", "do not edit
   skills; put proposed skill text in your final reply". Dependent tasks wait for their inputs.
   Done when every task is running or queued behind a named dependency.
6. **Verify yourself** with real tests (`terminal`, `read_file`, `search_files`); a subagent's
   "done" is not a pass. Check its chosen defaults and limits against the spec. Done when each
   task has a test result you ran.
7. **Record every result**, passes included, with `add` and the real test evidence. Done when the
   ledger has one row per attempt.
8. **Handle failures by cause**: `model` -> rerun on `escalate_on_model_failure_to`;
   `spec`/`context` -> fix the brief, same route; `env`/`flaky` -> fix or retry, same route.
   Done when every failed task has passed or is reported as blocked.
9. **Final review** of the combined change on the strongest route before reporting done.
   Done when its findings are fixed or listed for the user.

## Pitfalls

- Cost per successful task decides, never price per token: retries and corrections dominate.
- Escalating on `spec`/`context` failures burns money and hides plan gaps.
- Parallel tasks must never edit the same file; the parent commits, children never do.
- Route order is config order. A strong route listed first becomes the cheap route here; if the
  order looks wrong, say so to the person instead of trying to change it.
- A route renamed or removed in config drops out of the ladder; its old ledger rows no longer
  count. Re-pointing a route to another model or effort keeps its passes but voids its old
  model-caused failures.
- Without Model routes mode, `delegate_task` has no `option` parameter; `sync-routes` warns.
- Route changes apply to new sessions; sync again after the routes change.
- Details, the rubric and the learning rules: `references/workflow.md`.

## Verification

- `ladder` prints your routes in the intended order with the difficulty mapping.
- `suggest` returns a route from that ladder with `reasons`.
- After a run, `stats` shows one row per class/difficulty/route you dispatched, and every task's
  evidence names a test you ran yourself.
