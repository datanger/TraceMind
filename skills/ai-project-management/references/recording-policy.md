# Execution Log, Research Topics, Solutions, and Experiments

This policy guides the Agent while it solves project work. The Agent should make these curation decisions automatically from repository evidence; it does not need to ask the user before recording ordinary, well-supported progress. Durable records must stay concise, useful, non-duplicative, and auditable.

## Recording flow

```text
Start or continue an L2 Work Package
  → append factual Execution Log events at meaningful boundaries
  → identify an unresolved, consequential technical question
  → search existing topics and solutions for a match
  → add a topic or distinct solution only if it passes the gates below
  → run an actual experiment and record its evidence and conclusion
  → update the package evidence and current research synthesis
```

The Execution Log is the chronological record of project activity. Research topics preserve important questions. Solutions preserve distinct approaches to a question. Experiments preserve what was actually tried and learned. Do not use one record type as a substitute for another.

## Execution Log: record as work happens

`project-management/execution-log.jsonl` is append-only. Add an event when a meaningful boundary occurs:

- Work Package starts or changes state.
- Implementation reaches a reviewable checkpoint.
- Verification produces a result, including a failure.
- A blocker, root cause, or decision changes the next action.
- A stable checkpoint is reached.

Do not log every model thought, prompt, tool invocation, file read, minor edit, or unchanged poll. Combine a burst of routine edits into one concise implementation event. Prefer one event for one meaningful outcome, and append it close to when that outcome becomes known.

Each row requires an ID, ISO-8601 timestamp, kind, summary, and one or more real evidence links. Add feature/work-package IDs and `from`/`to`/`status_category` when relevant. Summaries state what happened, not what the Agent intends to do or assumes happened. Link to code, tests, reports, commits, issue records, decisions, or other inspectable evidence. Never rewrite older lines to make history look smoother. Malformed lines are reported and prevent the dashboard update until repaired.

Good examples:

- `WP-12 entered VERIFYING; contract suite passed 18/18` → link the test report.
- `Redis invalidation hypothesis failed: old token remained valid on worker B` → link the reproducible test and output.
- `Selected token-family revocation after comparing cache invalidation and family tracking` → link the decision or experiment summary.

Do not write vague entries such as `made progress`, `fixed the issue`, or `tests look good` without a result and evidence. A low-value investigation may be omitted as a research experiment while its material blocker or verification outcome still belongs in this log.

Typical event kinds include `start`, `status`, `implementation`, `verification`, `issue`, `decision`, and `checkpoint`.

## Research topic admission and deduplication

The current project-state contract gives each L2 Work Package one primary research-topic slot. During project planning, define that topic as the central technical question relevant to the package. During execution, do not treat every issue or subtask as a new topic: continue the primary topic for related investigation, and add another topic only when a separate question is independently consequential and cannot be answered as part of the existing one. A package that needs no research can keep its planned topic without creating solutions or experiments.

Before creating a topic:

1. Search all existing topic titles, questions, and descriptions, including topics on neighboring Work Packages.
2. Compare the underlying question, not only its wording. If an existing topic covers the same uncertainty, continue it and link the experiment to that topic. Do not create a duplicate because the component, symptom, or phrasing differs.
3. Check that the question is directly relevant to the current L2 package and is supported by repository evidence or an observed problem.
4. Create the topic only if resolving it can change an implementation, architecture, reliability, safety, or verification decision, or can prevent meaningful rework through reusable learning.

Create a topic for questions such as whether a distributed token-revocation mechanism provides the required consistency, or which parser strategy safely handles the repository's actual grammar. Do not create one for routine wiring, straightforward known fixes, cosmetic changes, ordinary dependency updates, unverified speculation, or a question already answered by project documentation and tests.

If the gate fails for a newly discovered question, do not create an additional topic, placeholder, solution, or empty experiment. Record any material implementation/verification outcome in the Execution Log, and keep moving. Do not fabricate a research question merely to fill the package's required primary topic slot. If an existing topic becomes redundant, consolidate future work into the best matching topic. Preserve its historical experiment records and references; summarize the consolidation in evidence rather than deleting append-only history.

## Solution admission and deduplication

A solution is a named, testable approach to answering its parent topic's question. It must state the method and concise data source. A topic can have several solutions when the approaches are materially different; a new label, configuration tweak, or repeated run does not by itself make a new solution.

Before registering a solution:

- Search solutions under the topic for the same core mechanism or hypothesis. If it is the same approach, reuse its `solution_id` and add a new experiment only when the new run can teach something.
- Register a new solution only for a distinct mechanism, algorithm, architecture, or test strategy that could lead to a different decision.
- Do not create solution placeholders such as `TBD`, `default`, or `attempt 2` without a defined method and data source.
- Keep the solution conclusion as a concise synthesis of its experiments. Use `pending`/empty wording when evidence is insufficient; do not infer success from implementation alone.

If two solutions are later found to be equivalent, stop adding trials to the duplicate and continue under the canonical solution. Keep old experiment references intact and explain the consolidation in the topic/solution synthesis.

## Experiment threshold: record only consequential learning

An experiment is a completed test or investigation that produces observable evidence. A proposed approach, code change without a relevant check, or intention to investigate is not an experiment record.

Score four dimensions from 1 to 5:

| Dimension | 1 | 3 | 5 |
|---|---|---|---|
| Impact | Local cosmetic behavior | Changes a package decision | Affects architecture, safety, reliability, or project direction |
| Novelty | Routine known operation | Some uncertainty in this repository | New or poorly understood mechanism |
| Learning | Little reusable conclusion | Clarifies one constraint | Eliminates a major uncertainty or changes the approach |
| Reuse | One-off and narrow | Useful to nearby packages | Likely reusable across the project or future projects |

Record only when the arithmetic mean is at least **3.5/5**. This is a triage threshold, not a scientific significance claim. Score based on what the result actually taught, not on how much effort was spent. Reassess borderline questions after learning more; do not inflate scores to preserve routine work.

Avoid experiment records when they merely repeat an unchanged test, confirm routine behavior, or produce no decision-relevant information. A repeated experiment is warranted when conditions changed, the earlier result was inconclusive, or the new run addresses a plausible alternative explanation. Keep high-value `FAIL` and `INCONCLUSIVE` outcomes: they can eliminate a path or narrow uncertainty. Never rewrite a failed result as success.

## Required experiment content and writing style

Every experiment requires:

- A specific question and falsifiable hypothesis.
- A `topic_id` and `solution_id` linking it to the exact question and approach.
- The method and important conditions used.
- A concise `data_source` pointer (dataset, fixture, report, system, or repository path).
- Result `PASS`, `FAIL`, or `INCONCLUSIVE`.
- A factual observation and the conclusion that follows from it.
- Evidence links and 1–5 scores for impact, novelty, learning, and reuse.

Write enough to reproduce or interpret the experiment, but do not copy detailed/raw datasets into project state. Identify where the data came from and link the source. The result should cite the actual test output, report, graph, commit, or artifact. When a chart helps compare results, derive it from the recorded experiment evidence; never invent counts or measurements to make a chart look complete. Explain the result and conclusion in text so the finding remains understandable without the visualization.

Example of a concise record:

```json
{
  "id": "EXP-WP12-03",
  "topic_id": "TOPIC-WP12-01",
  "solution_id": "SOL-WP12-01-A",
  "hypothesis": "Revoking the token family invalidates prior access tokens across workers.",
  "method": "Run the refresh integration scenario against two API workers and shared Redis.",
  "data_source": "tests/auth/token_refresh_multi_worker.py and reports/EXP-WP12-03.json",
  "result": "FAIL",
  "observation": "Worker B accepted the old token after worker A completed refresh.",
  "conclusion": "Family revocation is not propagated to access-token validation; add a shared revocation check before adopting this approach.",
  "evidence_links": ["reports/EXP-WP12-03.json", "tests/auth/token_refresh_multi_worker.py"],
  "value": {"impact": 5, "novelty": 4, "learning": 5, "reuse": 4}
}
```

Before appending, confirm that the topic maps to exactly one Work Package and the solution is registered under that topic. Reuse the registered solution ID for the same approach. For a genuinely new approach, register its ID, name, method, and data source together with the experiment so validation can reject orphan references. The recorder checks topic ownership, solution linkage, duplicate experiment IDs, and the value threshold. Experiment JSONL is append-only.

## Closing and summarizing research

At a meaningful package checkpoint, update the topic/solution synthesis from recorded evidence:

- What question was answered (or remains open).
- Which approaches were tested and their outcomes.
- What decision follows and what evidence supports it.
- Which uncertainty or next experiment remains, if any.

Do not create a fresh topic merely because the answer is incomplete; continue the same question unless the remaining question is independently consequential. Keep completed topics concise and discoverable, and do not keep adding low-value topics just to document all work. Historical experiment records remain available even when the current synthesis is consolidated or superseded.

## Period summaries

Daily, weekly (Monday–Sunday), and monthly views group Execution Log entries and qualifying experiments by timestamp. They retain evidence links and topic/package identifiers so each summary opens the source artifact. These are views over event history, not independent status claims. Summarize only evidence-backed work; do not generate a completion claim from the amount of logged activity.
