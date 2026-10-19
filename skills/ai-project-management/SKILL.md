---
name: ai-project-management
description: Manage AI-assisted software projects as durable, evidence-backed state. Use when a coding task should update its Execution Log or high-value research experiments, or when a user asks to generate or refresh project OKRs, WBS/Work Packages, weekly/monthly milestones, progress, or the project HTML dashboard.
---

# AI Project Management

Treat project management as a versioned state contract. The project JSON and append-only JSONL records are the source data; the HTML dashboard is a deterministic view of those records. Let the host coding Agent interpret repository evidence and propose structured changes. Let Python validate, calculate, and render. Do not ask a model to calculate progress or write dashboard markup by hand.

## Choose the operating mode

### Automatic execution recording

Use this mode while implementing, debugging, testing, or reviewing code in a managed project. Do not wait for the user to request a log entry.

1. Find the project root and read its `AGENTS.md` files, project state, latest Execution Log events, unresolved blockers, and recent decisions before changing code.
2. Append a timestamped Execution Log event at meaningful work boundaries: task start, Work Package state transition, implementation checkpoint, verification result, blocker/decision that changes the path, or stable checkpoint. Do not log every thought, prompt, tool call, or small code edit. Include relevant L1/L2 IDs, state category, a concise factual summary, and real evidence links. Follow the examples and cadence in [references/recording-policy.md](references/recording-policy.md).
3. During problem solving, first search existing research topics and solutions before creating anything. Create a topic only for a consequential, non-obvious question that is directly tied to its L2 Work Package and can change a technical decision or produce reusable learning. Merge equivalent questions into the existing topic; do not turn routine implementation, ordinary bug fixing, cosmetic changes, or unrelated observations into topics. Under a topic, reuse a solution for the same core approach; create a solution only for a meaningfully distinct, testable approach. Apply the admission and deduplication gates in [references/recording-policy.md](references/recording-policy.md).
4. Record an experiment only after a real test or investigation produced observable evidence. Capture the hypothesis, method and conditions, concise data-source pointer, PASS/FAIL/INCONCLUSIVE result, observation, conclusion, and evidence links. Preserve high-value failures and inconclusive findings when they eliminate uncertainty; do not record proposed-but-unrun experiments or repeated trials that add no information. Apply the recording threshold in [references/recording-policy.md](references/recording-policy.md).
5. Update the Work Package's evidence and status using the gates in [references/data-model.md](references/data-model.md). Keep unrelated packages unchanged when a failure is local.
6. Never claim a test passed, a file exists, or an acceptance metric was met without checking it. If evidence is missing, leave the criterion `NOT_RUN` and explain what remains.

Automatic recording means the Agent summarizes verified work into these durable records as the work happens; it does not mean recording every intermediate action. Keep topic and solution lists curated: deduplicate first, prefer adding a meaningful experiment to an existing solution, and leave low-value details in the ordinary Execution Log only when they are relevant to project progress.

Append a real-time event:

```bash
python skills/ai-project-management/scripts/execution_log.py \
  project-management/execution-log.jsonl \
  --project-state project-management/project-state.json \
  --kind status \
  --summary "WP-003 entered VERIFYING after integration tests" \
  --feature-id F-01 --work-package-id WP-003 \
  --from-status IMPLEMENTED --to-status VERIFYING --status VERIFYING \
  --evidence reports/WP-003-verification.json
```

Record a qualifying experiment by writing a JSON object with the required fields, then run:

```bash
python skills/ai-project-management/scripts/execution_log.py \
  project-management/experiments.jsonl --experiment-json /tmp/experiment.json \
  --project-state project-management/project-state.json
```

Add `--solution-json /tmp/new-solution.json` only when registering a new solution ID.

The `--solution-json` argument is needed only when `solution_id` has not already been registered under that research topic. The recorder checks topic ownership, solution linkage, duplicate experiment IDs, and the value threshold before writing. For a new solution it validates and registers the solution in project state before appending the experiment; if the append fails, it restores the previous state file. The experiment JSONL remains append-only. Experiments carry their `topic_id`, `solution_id`, concise `data_source` reference, hypothesis, method, observed result, conclusion, value scores, and evidence links. Link large datasets at their source instead of copying raw data into the project state. A solution groups repeated experiments, and its conclusion must follow from recorded evidence. For the full decision rules and examples, read [references/recording-policy.md](references/recording-policy.md) before creating or updating a topic, solution, or experiment.

### User-triggered project/dashboard update

Use this mode when the user asks to refresh the plan, reconcile project status with the repository, update OKRs/WBS/milestones, or regenerate the project HTML. This is the Looma workflow described in [references/looma-workflow.md](references/looma-workflow.md).

Require a feature inventory before planning. First search local project documentation, existing structured state, and implementation for an explicit list. If none exists but repository evidence clearly identifies the product capabilities, generate a source-linked inventory and use it as the L1 basis. If the evidence cannot establish the scope reliably, ask the user to provide a list or authorize repository-based derivation; stop before generating OKRs, requirements, technical solutions, WBS, milestones, or schedules. Keep per-feature provenance in `source_evidence`.

Use `assets/dashboard-shell.html` as the independent dashboard structure. If the repository contains a separate, relevant HTML design sample, it may be supplied through optional `--reference-html`; use it only to learn module hierarchy and interactions. Never require, migrate, or reuse a visual sample as project content or as the output shell.

Use the current local repository when the task is about the project open in the workspace; infer its identity and scope from repository code and documents without asking for a path. The Skill, scripts, schemas, plans, and specifications are product evidence when this repository is itself developing the project-management capability. Exclude generated `project-management/` state/log/output files and the visual reference HTML from product evidence. Cite existing files for identity and feature scope.

Resolve the project display name automatically from repository metadata, then README title, then root directory name. Keep this project name separate from the Skill or feature names and use it for the dashboard title and heading.

Only migrate a separate, existing legacy HTML when the Agent confirms from repository evidence that it contains the identified project's actual content and no structured state exists. Never recreate or depend on the removed root-level prototype, and never migrate a visual reference:

```bash
python skills/ai-project-management/scripts/migrate_legacy_html.py \
  "$LEGACY_PROJECT_HTML" project-management/project-state.json
```

The migration is a draft. Review its OKRs and acceptance targets. It deliberately resets historical manual progress to `TODO` because the old page does not provide per-Work-Package acceptance evidence. Do not migrate content from an HTML reference for a different project.

Run the deterministic Looma workflow:

```bash
python skills/ai-project-management/scripts/update_workflow.py \
  --project-root . \
  --state project-management/project-state.json \
  --output "project-management/项目管理.html"
```

Pass `--reference-html` only when an additional, relevant design sample exists; the normal workflow needs no HTML reference path.

The workflow asks the current host Agent to inspect the active repository, establish the feature inventory first, and return a complete structured proposal only if the inventory gate passes. Python verifies the inventory matches the proposed L1 list and that cited files exist before accepting downstream planning. An insufficient-evidence result returns a user question and publishes nothing. The workflow checks that the installed framework is exactly Looma Runtime 1.0.0 before starting. If Looma pauses with exit code `75`, follow the exact `script2agent` request and resume protocol in [references/looma-workflow.md](references/looma-workflow.md), including the same `LOOMA_RUN_KEY` when one was set. Do not execute an unvalidated resume command. Deterministic steps reject invalid state, recompute progress, render from the independent shell, and publish the HTML and state only after verification.

This update path is implemented with Looma's `@workflow`, `agent()`, and `step()` APIs. Looma controls suspension, persisted results, and replay; Python controls validation, calculations, rendering, and publication. Do not replace this with a free-form sequence of manual edits or direct model-written HTML.

From the project root, install the bundled Looma 1.0.0 wheel with:

```bash
python -m pip install -r skills/ai-project-management/requirements.txt
```

## Required Work Package contract

Each L2 Work Package must include its inputs, outputs, scope, measurable acceptance criteria, progress checkpoints, estimate weight, research topic, and one of the defined lifecycle statuses. Do not publish an incomplete contract. The exact field definitions, formulas, duplicate/transition gates, and examples are in [references/data-model.md](references/data-model.md).

## Dashboard behavior

Generate the single-file HTML from the independent shell through `render_dashboard.py`/the Looma workflow; never hand-edit generated app markup. The project view provides independent OKR, WBS, and milestone Gantt pages, weekly/monthly task plans, project progress, and linked daily/weekly/monthly evidence. Selecting an L1 feature opens an overview of its L2 Work Packages. Selecting an L2 Work Package opens its own detail page with its own time-by-status Execution Log timeline, research-topic dashboard card, expandable input/output/content/acceptance contract, and deadline. Selecting the topic card opens its experiment record. Unlinked project log entries must not be attributed to an L2 timeline. See [references/dashboard.md](references/dashboard.md).

## Validation

Run the test suite after changes to this skill:

```bash
python -m unittest discover -s skills/ai-project-management/tests -v
```

For Looma Runtime 1.0.0 integration coverage, run the same suite with the 1.0.0 package on `PYTHONPATH`. Validate a sample project state before publishing. The dashboard must embed one valid state snapshot, expose weekly and monthly views, and preserve clickable evidence links.
