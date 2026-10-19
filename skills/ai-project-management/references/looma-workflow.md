# Looma Update Workflow

Use Looma Runtime 1.0.0 with `@workflow`, `step()`, and `agent()`. Python owns control flow, validation, calculation, rendering, and publication. The current host Agent identifies the project from the active task and accessible workspace/repository evidence; Looma does not call an LLM API or start another Agent.

## Deterministic sequence

```text
load state and append-only records
→ Agent searches for an existing feature inventory and reconciles it with repository evidence
→ if absent and evidence is sufficient, Agent first creates a sourced feature inventory
→ Python gates on a non-empty inventory that matches the proposed L1 feature list
→ if evidence is insufficient, return one user question and publish nothing
→ Agent proposes OKRs, requirements, technical solutions, WBS, milestones, and schedules
→ Python confirms project identity, evidence paths, state contract, and transitions
→ calculate Work Package / L1 / project progress and period reports
→ render from the independent dashboard shell
→ verify embedded state and required interactions
→ publish the project-management HTML and JSON together
```

The feature inventory is a required planning input, not an optional byproduct of WBS generation. Search repository docs, existing project artifacts, and structured state first. If no list exists but implementation and specifications clearly establish the capability boundaries, generate a repository-inferred inventory with per-feature source evidence, then use it as the L1 source for downstream planning in the same run. Persist that provenance as `feature.source_evidence`. If evidence is weak or scope is ambiguous, return `status="needs_user_input"` and ask one concise question; do not generate OKRs, requirements, technical designs, WBS, milestones, or schedules and do not publish a dashboard.

The user does not need to provide a source path up front. When the user selects the current local project, the Agent analyzes that repository only and does not search neighboring repositories. For this project, the AI project-management Skill, implementation scripts, schemas, plans, and specifications are product evidence. Generated `project-management/` state/log/output files and the reference HTML are not evidence for project identity or feature scope. It returns `project_identity` with `status`, `source_root`, `project_id`, `project_name`, `selection_reason`, and `evidence_files` (`path`, `kind`, `supports`). The project-state identity must match. Python confirms the source root is the active project and cited files exist.

Resolve the display name in Python from project metadata (`pyproject.toml`, `Cargo.toml`, `setup.cfg`, `package.json`, or `composer.json`), then a README title, then the repository root directory name. Pass this value to the Agent as `resolved_project_name`, persist its provenance as `project.name_source`, and render it in the page title and top-level heading. Do not derive the display name from a feature, Skill, or dashboard label.

An HTML reference is optional. When supplied, it is **read-only design input**: extract useful module hierarchy and interaction patterns, but do not copy its project name, feature names, plans, data, or full page shell. Normally use the repository's independent `assets/dashboard-shell.html` without requiring another HTML path. The reference path is never passed to the renderer or used as an output target. If the Agent cannot identify one project from real source evidence, it returns `project_identity.status="needs_clarification"` and one concise question. Python stops before rendering or publication.

After the inventory gate passes, the Agent proposes the semantic project-state snapshot, including OKRs, WBS, weekly plans, milestones, complete Work Package contracts, and research/technical solution groups where repository evidence supports them. It cannot modify authoritative JSONL history. New Execution Log and experiment entries carry `project_id`; the workflow only shows records owned by the selected project. Existing unscoped records stay in the append-only files. Python validates Work Package transitions and recalculates progress. If the current plan is explicitly identified as unrelated or inaccurate, it may be replaced without changing project identity by setting `plan_rebased_from` to the existing project ID and recording `plan_rebase_reason`. Identity changes use the separate `baseline_rebased_from` gate.

## First run and resume

Run the workflow as a Python file so Looma can replay the same entry point:

```bash
python skills/ai-project-management/scripts/update_workflow.py \
  --project-root . \
  --state project-management/project-state.json \
  --output "project-management/项目管理.html"
```

Add `--reference-html PATH` only when a separate design reference is available and relevant. The normal invocation does not require one.

When `--output` is omitted, publish to `project-management/项目管理.html`.

On the first pass Looma pauses at `agent()` with exit code `75` and writes a `script2agent` request. The host Agent must inspect its `agent_input` and `task`, write the structured result to `output.result_file`, and return only the exact `agent2script` from `expected_output`. Resume through Looma's strict handoff validator, using the same `LOOMA_RUN_KEY` when one was set. Never execute a different command or use the reference HTML as the output shell.

Durable `step()` calls protect proposal validation, progress calculation, rendering, and publication from replaying side effects. If identity or any validation gate fails, no dashboard or state file is published. JSONL remains the source of truth for Execution Log and experiments; the model cannot delete or rewrite it through its state proposal.
