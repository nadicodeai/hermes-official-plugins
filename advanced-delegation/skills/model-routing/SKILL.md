---
name: model-routing
description: Before a big job, hand parts to subagents on cheaper models.
version: 0.1.0
author: Ziad Osama El-Boshy (ziadelboshy)
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [delegation, model-routing, subagents, cost, ledger]
---

# Model Routing Skill

Your own model is the dear one. Give each part of a job to the cheapest of your model routes that
does it well, and keep what needs your judgment: the plan, the check and the answer. The skill adds
no tools; it uses `delegate_task` with the routes set up for you in Model routes mode
(`delegation.backend: model_map`).

## When to Use

- A lot of reading (ten long documents or more, or over fifty pages: contracts, tenders,
  reports, long threads), while the cheapest route reads for much less than your own model: the
  reading goes to subagents there, so the documents never enter your own chat, where you would
  pay for them at your own price on every later step.
- 3+ independent parts: several files or areas, bulk repetitive edits, parallel research, or an
  implement -> test -> fix loop with mechanical parts.
- Any `delegate_task` call while Model routes mode is active, and any failed subagent task.

Don't use for: a small job (a few short files, one lookup), exact work on numbers or tables that
a short program does (write the program yourself), tightly coupled changes, or work that needs
the person's back-and-forth. A subagent starts blank and you pay to brief it and to read its
answer, so a split pays only when the part is big enough.

## Prerequisites

- The advanced-delegation plugin enabled, in Model routes mode, with routes **ordered cheapest
  -> strongest**, each with a one-line description. The order is the ladder this skill climbs.
  The routes are the ones nadicode chose for the company's Agents, already in that order; you
  cannot add, edit or reorder them.
- For the ledger only: Python 3.8+ for `scripts/route_ledger.py` (stdlib only). Its `sync-routes`
  also needs ruamel.yaml or PyYAML to read your settings file; the `python` in your terminal has
  it. The ledger follows the active Agent (`HERMES_HOME`).

## How to Run

A single job needs no command: follow the Procedure with `delegate_task`. The ledger is for work
of a kind you do again and again, where it learns which route passes. Run it through the
`terminal` tool, in the Agent that delegates:

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

1. **Split.** List the parts that do not depend on each other. Reading and judging are two
   parts: a subagent reads and reports, you judge. Done when you either do the job yourself
   (Don't use for, above) or have that list.
2. **Give each part a route.** The routes are in the `option` of `delegate_task`, cheapest first.
   Take the first whose description fits the part: reading a document and reporting what it says
   needs no more than the cheapest route that takes reading. Done when every part has a route,
   and none sits higher than its description asks.
3. **Write each brief so the subagent needs nothing else**: the file paths (never the files'
   text, which you would pay for twice), the facts to report as a short list (a long report costs
   you to read), "quote the exact words of each fact and say where they are", and "report
   anything elsewhere in the file that changes, limits or contradicts it". For code add the owned files, the acceptance test and "do
   not commit" (see `references/workflow.md`). Done when a stranger could do the part from the
   brief alone.
4. **Dispatch** the independent parts in one `delegate_task` call, each task's `option` set to
   its route. With more documents than tasks allowed, put a few documents in each task. Parts
   that depend on another wait for it. Done when every part is running or queued behind a named
   dependency.
5. **Check what comes back, cheaply.** Look up each surprising finding, and one ordinary finding
   per subagent, by searching the file for the quoted words (`search_files`, or `read_file` on
   that passage); run the tests of code with `terminal`. Do not read the whole documents again:
   that pays for them a second time, at your price. A subagent's "done" is not a pass. Done when
   those findings are confirmed or corrected.
6. **Handle a failure by its cause.** While a task runs, do not do its work. The task was
   refused, failed or did not answer (a limit, an error) -> do that part yourself, and send it to
   no other route. The model returned work that misses a clearly briefed part -> the same task one
   route up. The brief was unclear or missed context -> fix the brief, same route. Done
   when every failed part has passed or you did it yourself.
7. **Answer yourself.** The comparison, the judgment and the reply are yours; say what you
   checked. Done when the person has the answer and knows what was checked.
8. **For repeated work, record the results** with `add`, passes included, and ask `suggest`
   before the next job of that kind. Done when the ledger has one row per attempt.

## Pitfalls

- Cost per finished part decides. A route higher than the part needs is money spent for nothing;
  a route too low costs a retry. Start low, check, and go up only when the model was the cause.
- Going up a route for an unclear brief burns money and hides the gap in the plan.
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

- Every dispatched task named a route, and the reading sat on the cheapest route that fits.
- Each surprising finding in your answer is one you looked up in the source yourself.
- With the ledger: `ladder` prints your routes in the intended order, `suggest` returns a route
  from it with `reasons`, and `stats` shows one row per class/difficulty/route you dispatched.
