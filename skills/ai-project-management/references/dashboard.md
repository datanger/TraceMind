# HTML Dashboard Contract

`render_dashboard.py` generates a fresh page from `assets/dashboard-shell.html` and a validated project JSON snapshot. A separate HTML design reference may be supplied optionally, but project content never comes from a visual sample. The published dashboard lives at `project-management/项目管理.html`. All data is embedded in one JSON script element so the page works without a backend.

## Overview

- Shows top-right project navigation for `OKR`, `WBS`, and `里程碑甘特图`. Each opens an independent routed page; none of these tables appears on the home overview.
- The OKR page is a full table of objectives and all Key Results, targets, and measurement methods.
- The WBS view is a full L1/L2 table containing inputs, outputs, scope, acceptance method/metric/target, estimate, status, progress, and research topic.
- The WBS page is a full table and retains the weekly task plan and monthly task Gantt controls below it.
- The milestone view plots each dated milestone on a month-scale Gantt timeline and shows its acceptance condition and status.
- Calculates project progress from the JSON; there is no manual progress override.
- Displays each L1 feature and its weighted L2 progress and accepted-package count.
- Project pages use the same 1500px content width and horizontal padding as the home overview.
- Every routed page keeps its toolbar outside the scrollable content. The generic `返回` action returns to the previous route when available and uses the page's parent route as a direct-entry fallback. When the prior control is identifiable, keyboard focus returns to it.
- Stale feature, Work Package, or topic routes render a navigable not-found view instead of blanking the workspace or retaining prior detail content.

## Feature detail screen

Clicking an L1 feature opens a routed overview with its short description, deadline derived from linked weekly plans, status/progress, and a collapsible L2 contract summary covering inputs, outputs, content, acceptance metrics, and methods. It lists its L2 Work Packages but does not aggregate research topics or Execution Log timelines from its children. Project-wide milestones remain on the dedicated milestone Gantt page.

Clicking an L2 Work Package opens its own detail screen with its short description, deadline derived from linked weekly plans, state/progress, and a collapsible contract with inputs, outputs, content, acceptance metrics, and methods. That screen also owns the Work Package's status timeline and research-topic dashboard card. The timeline only includes that package's `status_history` and Execution Log events whose `work_package_id` matches it. Project-level events without an L2 link remain unassigned and are never inferred into a package timeline. A topic card shows the linked package, latest experiment status, solution count, total experiment count, and PASS/FAIL/INCONCLUSIVE counts. Clicking it opens the topic detail grouped by solution. Each solution presents its method and data source, a PASS/FAIL/INCONCLUSIVE results chart, experiment observations and conclusions, and a solution-level conclusion. Each experiment links to its evidence. Historical experiments without a solution ID remain visible under a clearly labeled unassigned group. A research topic without a Work Package parent is not rendered as an independent topic page.

The per-Work-Package Execution Log chart plots timestamp on the horizontal axis and status category on the vertical axis. It shows verification failures, verification-to-failure/blocker returns, and how long the latest state has been open. The “possible repeated verification” flag is only a heuristic: at least two returns or three failures in seven days. It does not decide acceptance or automatically label a package as non-convergent.

The home overview shows the daily work summary with evidence links. A linked research topic opens its experiment history, including PASS, FAIL, and INCONCLUSIVE results.

## Safety and update rules

- The renderer escapes `<`, `>`, and `&` in the embedded JSON to prevent a project name or summary from terminating the script element.
- Dashboard text is inserted through text-safe rendering; evidence links with executable URL schemes are not made clickable.
- An invalid project snapshot is rejected before the generated HTML is written.
- For project updates, use `update_workflow.py`. It verifies the rendered document, stages both files, then replaces them; if either replacement fails, it restores the prior files.
- Before publish, the workflow verifier requires the project switcher, L1/L2/research navigation, OKR/WBS/milestone view routes, schedule controls, and route-return contract to be present in the generated application. It also enforces Work Package ownership for status timelines and research-topic detail pages.
