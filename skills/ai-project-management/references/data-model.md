# Project State and Work Package Contract

The canonical contract is [project-state.schema.json](../schemas/project-state.schema.json); [project-state.json](../examples/project-state.json) is a small complete example. The migrated project seed is maintained separately in `project-management/project-state.json`.

## Hierarchy

```text
Project
├── Objective (OKR)
│   └── Key Result (metric, target, measurement method)
├── Feature (L1)
│   └── Work Package (L2)
│       └── Research Topic
│           └── Solution (method, data source, conclusion)
│               └── Experiment (result, observation, evidence)
├── Milestone
└── Week (date range, objective, deliverables, linked Work Packages)
```

Each L1 feature carries `source_evidence` linking the feature inventory to repository or user-provided sources. This preserves why the feature exists and lets later updates re-check the inventory against local project evidence. Each Work Package describes the task's **inputs**, **outputs**, **scope**, estimated effort, weighted evidence checkpoints, and acceptance criteria. Every criterion names a verification method, a measurable metric and a target. Each Work Package links to a research topic. L2 is the minimum decomposition level; do not add vague “miscellaneous” packages in place of identifiable functions.

A research topic may group repeated trials under a solution. Each solution requires an ID, name, method, and data source; its conclusion is a synthesis and may remain pending until evidence exists. Each newly recorded experiment links by `topic_id` and `solution_id`, names its data source and method, and records its result, observation, conclusion, and evidence. Historical records without solution IDs remain readable and render under an unassigned-history group.

## Progress formulas

For Work Package (w), a checkpoint contributes only when it is marked done and has a non-empty evidence link:

```text
WP_progress = 100 × Σ(checkpoint_weight × evidence_backed_done) / Σ(checkpoint_weight)
```

For an L1 feature, use each Work Package's `estimate_points`; an individual missing estimate defaults to 1, and if all are absent the result is an equal-weight average:

```text
L1_progress = Σ(WP_progress × WP_estimate_points) / Σ(WP_estimate_points)
```

For the project, use each feature's `weight`; an individual missing weight defaults to 1, and if all are absent the result is an equal-weight average:

```text
Project_progress = Σ(L1_progress × feature_weight) / Σ(feature_weight)
```

The runtime stores calculated values to two decimal places. There is no manual override and no five-percent band rounding. Missing evidence contributes zero.

## Status lifecycle

Normal delivery:

```text
TODO → READY → IN_PROGRESS → IMPLEMENTED → VERIFYING → DONE
```

Failure and recovery:

```text
VERIFYING → BLOCKED or FAILED → FIXING → VERIFYING
```

`apply_status_transition()` rejects skipped or illegal transitions. `READY` requires a complete contract and completed dependencies. `IN_PROGRESS` requires a start/execution record; `IMPLEMENTED` requires implementation evidence; `VERIFYING` requires verification evidence; `DONE` requires all acceptance criteria to be `PASS` with evidence. `BLOCKED`, `FAILED`, and `FIXING` require their corresponding blocker, failed verification, and fix-plan evidence.

Status derivation advances at most one legal state at a time from the current status and its evidence. A failing criterion during verification does not become `DONE`; keep it in the failure/fix/retest loop. Preserve timestamped status history.

## Acceptance evidence

- `NOT_RUN`: no result yet.
- `PASS`: the recorded method met the target; evidence link is mandatory.
- `FAIL`: the method ran and did not meet target; preserve failure evidence and create a linked issue/fix path.
- `BLOCKED`: unable to run; record why and the missing dependency.

Evidence links can be repository paths, report paths, commit references, or URLs. Link to the concrete output wherever possible. The Agent may propose changes, but Python validation and observed test results decide whether a criterion can be marked passed.
