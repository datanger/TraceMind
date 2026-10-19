import importlib
import json
import sys
import tempfile
import unittest
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))


def api(test_case, name):
    try:
        module = importlib.import_module("render_dashboard")
    except ModuleNotFoundError as error:
        test_case.fail(f"render_dashboard module is not implemented: {error}")
    if not hasattr(module, name):
        test_case.fail(f"render_dashboard.{name} is not implemented")
    return getattr(module, name)


class DashboardTests(unittest.TestCase):
    def test_static_fragment_links_resolve_and_html_ids_are_unique(self):
        class FragmentAudit(HTMLParser):
            def __init__(self):
                super().__init__()
                self.ids = []
                self.fragments = []

            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                if attrs.get("id"):
                    self.ids.append(attrs["id"])
                href = attrs.get("href", "")
                if tag == "a" and href.startswith("#"):
                    self.fragments.append(href)

        parser = FragmentAudit()
        parser.feed((ROOT / "skills/ai-project-management/assets/dashboard-shell.html").read_text(encoding="utf-8"))
        duplicates = [identifier for identifier, count in Counter(parser.ids).items() if count > 1]
        routes = ("#project/", "#feature/", "#work-package/", "#research/")
        missing = [href for href in parser.fragments if not href.startswith(routes) and href[1:] not in set(parser.ids)]

        self.assertEqual(duplicates, [])
        self.assertEqual(missing, [])

    def test_embedded_state_is_safe_and_contains_feature_workspace_contract(self):
        render = api(self, "render_dashboard")
        state = {"schema_version": 1, "project": {"id": "p", "name": "</script><script>alert(1)</script>"}, "objectives": [{"id": "O1", "title": "Goal", "key_results": [{"id": "KR1", "metric": "pass", "target": "100%", "measurement_method": "test"}]}], "milestones": [{"id": "M1", "title": "M1", "date": "2026-10-30", "acceptance": "done"}], "weeks": [{"id": "W1", "start": "2026-10-12", "end": "2026-10-18", "objective": "Ship feature", "deliverables": ["demo"]}], "features": [{"id": "F-1", "title": "Feature", "work_packages": [{"id": "WP-1", "title": "WP", "status": "TODO", "description": "Scope", "inputs": ["req"], "outputs": ["artifact"], "scope": ["scope"], "acceptance_criteria": [{"id": "AC-1", "method": "test", "metric": "pass", "target": "100%"}], "progress_items": [{"id": "P-1", "weight": 1, "done": False}], "research_topic": {"id": "R-1", "title": "Research"}}]}], "execution_log": [{"id": "E-1", "timestamp": "2026-10-16T09:00:00+08:00", "status_category": "IN_PROGRESS", "summary": "Started"}], "work_logs": {"daily": [], "weekly": [], "monthly": []}}
        html = render("<html><body><!-- AI_PM_STATE_SLOT --></body></html>", state)
        self.assertNotIn("</script><script>alert(1)</script>", html)
        for marker in ("feature-workspace", "执行记录时间线，横轴为时间，纵轴为 Work Package 状态", "research-topic-link", "data-schedule-view=\"weekly\"", "data-schedule-view=\"monthly\"", "application/json"):
            self.assertIn(marker, html)

    def test_project_switcher_has_complete_okr_wbs_tables_and_milestone_gantt(self):
        render = api(self, "render_dashboard")
        state = json.loads((ROOT / "project-management/project-state.json").read_text(encoding="utf-8"))
        template = (ROOT / "skills/ai-project-management/assets/dashboard-shell.html").read_text(encoding="utf-8")
        html = render(template, state)

        for marker in (
            'data-project-page-view="okr"',
            'data-project-page-view="wbs"',
            'data-project-page-view="milestones"',
            'id="okr-table"',
            'id="wbs-table"',
            'id="milestone-gantt"',
            'data-schedule-view="weekly"',
            'data-schedule-view="monthly"',
        ):
            self.assertIn(marker, html)
        self.assertIn("measurement_method", html)
        self.assertIn("acceptance_criteria", html)
        self.assertIn("project.objectives||[]", html)
        self.assertIn("project.features||[]", html)
        for column in ("Objective ID", "目标值", "衡量方法", "输入", "输出", "范围", "验收方法 / 指标 / 目标", "估算权重", "状态 / 进度"):
            self.assertIn(column, html)
        self.assertIn("#aipm-state-plan{left:50%;right:auto;transform:translateX(-50%);width:min(100%,1500px)", html)

    def test_work_package_detail_owns_its_execution_log_and_research_dashboard(self):
        render = api(self, "render_dashboard")
        state = json.loads((ROOT / "project-management/project-state.json").read_text(encoding="utf-8"))
        template = (ROOT / "skills/ai-project-management/assets/dashboard-shell.html").read_text(encoding="utf-8")
        state["experiments"] = [
            {"id": "X-1", "topic_id": "R-K01", "result": "PASS", "timestamp": "2026-10-16T10:00:00+08:00"},
            {"id": "X-2", "topic_id": "R-K01", "result": "FAIL", "timestamp": "2026-10-16T11:00:00+08:00"},
            {"id": "X-3", "topic_id": "R-K02", "result": "INCONCLUSIVE", "timestamp": "2026-10-16T12:00:00+08:00"},
        ]
        html = render(template, state)

        for marker in (
            'function renderWorkPackage(featureId,workPackageId)',
            'href="#work-package/${encodeURIComponent(feature.id)}/${encodeURIComponent(workPackage.id)}"',
            'data-view="work-package-detail"',
            'aria-label="二级功能详情导航"',
            'id="execution-log"',
            'id="research-topic"',
            'event.work_package_id===workPackage.id',
            'data-research-topic="${safe(topic.id||\'\')}"',
            'data-latest-experiment=',
            "实验总数",
            "PASS",
            "FAIL",
            "INCONCLUSIVE",
            "item.topic_id===topic.id",
        ):
            self.assertIn(marker, html)
        self.assertNotIn('id="research-dashboard"', html)
        self.assertNotIn('id="research-topics"', html)

    def test_l1_overview_does_not_aggregate_work_package_logs_or_topics(self):
        source = (ROOT / "skills/ai-project-management/scripts/render_dashboard.py").read_text(encoding="utf-8")
        start = source.index("function renderFeature(id)")
        end = source.index("function renderWorkPackage(featureId,workPackageId)", start)
        l1_view = source[start:end]

        self.assertIn("href=\"#work-package/${encodeURIComponent(feature.id)}/${encodeURIComponent(workPackage.id)}\"", l1_view)
        self.assertIn("data-jump-to=\"work-packages\"", l1_view)
        self.assertNotIn("Execution Log 状态时间线", l1_view)
        self.assertNotIn("研究课题仪表盘", l1_view)

    def test_wbs_research_entry_routes_through_its_work_package(self):
        render = api(self, "render_dashboard")
        state = json.loads((ROOT / "project-management/project-state.json").read_text(encoding="utf-8"))
        template = (ROOT / "skills/ai-project-management/assets/dashboard-shell.html").read_text(encoding="utf-8")
        html = render(template, state)

        self.assertIn('href="#work-package/${encodeURIComponent(feature.id)}/${encodeURIComponent(wp.id)}" aria-label="先查看', html)
        self.assertIn("const workPackageMatch=routeHash.match(/^#work-package\\/([^/]+)\\/(.+)$/)", html)
        self.assertIn("else if(onWorkPackagePage)renderWorkPackage(workPackageFeatureId,workPackageId)", html)

    def test_research_topic_filter_reports_visible_count_and_empty_results(self):
        render = api(self, "render_dashboard")
        state = json.loads((ROOT / "project-management/project-state.json").read_text(encoding="utf-8"))
        template = (ROOT / "skills/ai-project-management/assets/dashboard-shell.html").read_text(encoding="utf-8")
        html = render(template, state)

        self.assertIn('data-experiment-count aria-live="polite"', html)
        self.assertIn('data-experiment-empty hidden', html)
        self.assertIn("count.textContent=`显示 ${visible} / ${experiments.length} 条`", html)
        self.assertIn("empty.hidden=visible>0", html)
        self.assertIn('id="aipm-back">← 返回</button>', html)
        self.assertIn("previousRouteHash&&previousRouteHash!==location.hash?previousRouteHash", html)

    def test_milestone_gantt_positions_align_with_equal_width_month_axis(self):
        render = api(self, "render_dashboard")
        state = json.loads((ROOT / "project-management/project-state.json").read_text(encoding="utf-8"))
        template = (ROOT / "skills/ai-project-management/assets/dashboard-shell.html").read_text(encoding="utf-8")
        html = render(template, state)

        self.assertIn("monthIndex=months.indexOf(month)", html)
        self.assertIn("dayFraction=(date.getDate()-1)/new Date(date.getFullYear(),date.getMonth()+1,0).getDate()", html)
        self.assertIn("(monthIndex+dayFraction)/months.length*100", html)

    def test_mobile_navigation_and_controls_keep_large_touch_targets(self):
        render = api(self, "render_dashboard")
        state = json.loads((ROOT / "project-management/project-state.json").read_text(encoding="utf-8"))
        template = (ROOT / "skills/ai-project-management/assets/dashboard-shell.html").read_text(encoding="utf-8")
        html = render(template, state)
        styles = html[html.index('<style id="ai-pm-styles">'):html.index('</style>', html.index('<style id="ai-pm-styles">'))]
        mobile = styles[styles.rfind('@media(max-width:720px)'):]

        self.assertIn(".aipm-back,.aipm-project-home,.aipm-section-nav button,.aipm-project-views :is(a,button),.aipm-schedule-switch button,.aipm-research-filter button,.aipm-clear-filters,.aipm-sort-button,.aipm-table-tools input,.aipm-table-tools select{min-height:44px", mobile)
        self.assertIn("@media(max-width:800px){#feature-workspace .aipm-section-nav,#feature-workspace .aipm-detail-toolbar>.aipm-project-views{align-self:stretch;width:100%;margin-left:0;justify-content:flex-end}", styles)

    def test_home_feature_research_project_and_schedule_views_have_navigation(self):
        render = api(self, "render_dashboard")
        state = json.loads((ROOT / "project-management/project-state.json").read_text(encoding="utf-8"))
        template = (ROOT / "skills/ai-project-management/assets/dashboard-shell.html").read_text(encoding="utf-8")
        html = render(template, state)

        for marker in (
            'id="aipm-project-view-nav"',
            'aria-label="一级功能内容导航"',
            'aria-label="项目视图导航"',
            'aria-label="项目视图"',
            'id="aipm-project-home"',
            'data-schedule-view="weekly"',
            'data-schedule-view="monthly"',
        ):
            self.assertIn(marker, html)

    def test_back_controls_return_to_previous_route_with_home_fallback(self):
        render = api(self, "render_dashboard")
        state = json.loads((ROOT / "project-management/project-state.json").read_text(encoding="utf-8"))
        template = (ROOT / "skills/ai-project-management/assets/dashboard-shell.html").read_text(encoding="utf-8")
        html = render(template, state)

        self.assertIn("function navigateBack(fallback='')", html)
        self.assertIn("location.hash=previousRouteHash&&previousRouteHash!==location.hash?previousRouteHash:fallback", html)
        self.assertIn('class="aipm-back" id="aipm-back">← 返回</button>', html)
        self.assertNotIn("返回项目总览", html)
        self.assertIn("navigateBack('')", html)

    def test_return_navigation_restores_focus_to_originating_topic_or_wbs_row(self):
        render = api(self, "render_dashboard")
        state = json.loads((ROOT / "project-management/project-state.json").read_text(encoding="utf-8"))
        template = (ROOT / "skills/ai-project-management/assets/dashboard-shell.html").read_text(encoding="utf-8")
        html = render(template, state)

        self.assertIn("else if(onWorkPackagePage&&previousResearch)", html)
        self.assertIn("workspace.querySelector(`[data-research-topic=\"${CSS.escape(previousTopic)}\"]`)", html)
        self.assertIn("else if(onProjectPage&&previousFeature)", html)
        self.assertIn("#wbs-table tbody tr[data-feature=\"${CSS.escape(previousId)}\"]", html)

    def test_route_back_restores_the_previous_page_scroll_position(self):
        render = api(self, "render_dashboard")
        state = json.loads((ROOT / "project-management/project-state.json").read_text(encoding="utf-8"))
        template = (ROOT / "skills/ai-project-management/assets/dashboard-shell.html").read_text(encoding="utf-8")
        html = render(template, state)

        self.assertIn("const routeScrollPositions=new Map()", html)
        self.assertIn("function routeScroller(hash)", html)
        self.assertIn("routeScrollPositions.set(previousHash,previousScroller?.scrollTop??window.scrollY)", html)
        self.assertIn("const savedScrollTop=routeScrollPositions.get(routeHash)", html)
        self.assertIn("routeScrollPositions.get(routeHash)", html)
        self.assertIn("window.scrollTo(0,savedScrollTop)", html)

    def test_invalid_feature_and_work_package_routes_render_navigable_not_found_state(self):
        render = api(self, "render_dashboard")
        state = json.loads((ROOT / "project-management/project-state.json").read_text(encoding="utf-8"))
        template = (ROOT / "skills/ai-project-management/assets/dashboard-shell.html").read_text(encoding="utf-8")
        html = render(template, state)

        self.assertIn("function renderNotFound(message)", html)
        self.assertIn("if(!feature)return renderNotFound('未找到该一级功能。')", html)
        self.assertIn("if(!feature||!workPackage)return renderNotFound('未找到该二级功能。')", html)
        self.assertIn("if(!entry&&!workPackage)return renderNotFound('未找到该研究课题。')", html)
        self.assertIn('aria-label="项目视图导航"', html)

    def test_monthly_schedule_has_columns_for_task_bar_and_deliverables(self):
        render = api(self, "render_dashboard")
        state = json.loads((ROOT / "project-management/project-state.json").read_text(encoding="utf-8"))
        template = (ROOT / "skills/ai-project-management/assets/dashboard-shell.html").read_text(encoding="utf-8")
        html = render(template, state)

        self.assertIn(".aipm-month-week{display:grid;grid-template-columns:220px minmax(520px,1fr) minmax(180px,.7fr)", html)
        self.assertIn('class="aipm-week-bar" tabindex="0" role="img" aria-label=', html)
        self.assertIn('button type="button" data-schedule-view="weekly"', html)
        self.assertIn('button type="button" data-schedule-view="monthly"', html)

    def test_schedule_view_and_month_changes_preserve_content_scroll_position(self):
        render = api(self, "render_dashboard")
        state = json.loads((ROOT / "project-management/project-state.json").read_text(encoding="utf-8"))
        template = (ROOT / "skills/ai-project-management/assets/dashboard-shell.html").read_text(encoding="utf-8")
        html = render(template, state)

        self.assertIn("function renderProjectPlan(projectView=currentProjectView,scheduleView=currentScheduleView,selectedMonth='',preservedScrollTop=null)", html)
        self.assertIn("if(preservedScrollTop!==null&&content)content.scrollTop=preservedScrollTop", html)
        self.assertIn("const scrollTop=panel.querySelector('.aipm-plan-content')?.scrollTop||0", html)
        self.assertIn("renderProjectPlan(currentProjectView,currentScheduleView,month,scrollTop)", html)
        self.assertIn("renderProjectPlan(currentProjectView,currentScheduleView,selected,scrollTop)", html)
        self.assertIn(".aipm-month-week{grid-template-columns:160px minmax(500px,1fr) minmax(180px,.7fr)", html)

    def test_weekly_schedule_has_an_explanatory_empty_state(self):
        render = api(self, "render_dashboard")
        state = json.loads((ROOT / "project-management/project-state.json").read_text(encoding="utf-8"))
        template = (ROOT / "skills/ai-project-management/assets/dashboard-shell.html").read_text(encoding="utf-8")
        html = render(template, state)

        self.assertIn("view==='monthly'?", html)
        self.assertIn("weeks.length?", html)
        self.assertIn("尚未安排周计划。", html)

    def test_feature_section_navigation_tracks_current_section(self):
        render = api(self, "render_dashboard")
        state = json.loads((ROOT / "project-management/project-state.json").read_text(encoding="utf-8"))
        template = (ROOT / "skills/ai-project-management/assets/dashboard-shell.html").read_text(encoding="utf-8")
        html = render(template, state)

        self.assertIn("scroller.addEventListener('scroll'", html)
        self.assertIn("function bindSectionNavigation(root)", html)
        self.assertIn("button.setAttribute('aria-current','location')", html)
        self.assertIn(".aipm-section-nav button[aria-current=location]", html)

    def test_execution_timeline_keeps_labels_readable_on_narrow_screens(self):
        render = api(self, "render_dashboard")
        state = json.loads((ROOT / "project-management/project-state.json").read_text(encoding="utf-8"))
        template = (ROOT / "skills/ai-project-management/assets/dashboard-shell.html").read_text(encoding="utf-8")
        html = render(template, state)

        self.assertIn(".aipm-timeline-wrap{max-width:100%;overflow-x:auto", html)
        self.assertIn(".aipm-timeline{display:block;width:100%;min-width:720px;max-width:900px", html)
        self.assertIn('class="aipm-timeline-wrap" tabindex="0" role="region"', html)
        self.assertIn('id="execution-log" data-nav-section="execution-log"', html)

    def test_progress_formula_disclosure_has_visible_keyboard_focus(self):
        render = api(self, "render_dashboard")
        state = json.loads((ROOT / "project-management/project-state.json").read_text(encoding="utf-8"))
        template = (ROOT / "skills/ai-project-management/assets/dashboard-shell.html").read_text(encoding="utf-8")
        html = render(template, state)

        self.assertIn(".progress-rubric summary:focus-visible", html)

    def test_home_removes_daily_results_card_and_keeps_full_width_progress_layout(self):
        render = api(self, "render_dashboard")
        state = json.loads((ROOT / "project-management/project-state.json").read_text(encoding="utf-8"))
        template = (ROOT / "skills/ai-project-management/assets/dashboard-shell.html").read_text(encoding="utf-8")
        html = render(template, state)

        self.assertNotIn('class="today-card"', html)
        self.assertNotIn('id="todaySummary"', html)
        self.assertIn(".management-top { display: grid; grid-template-columns:1fr;", html)
        self.assertIn("homePage.insertBefore(viewNav,homeContent)", html)

    def test_execution_log_without_state_does_not_infer_in_progress(self):
        render = api(self, "render_dashboard")
        state = json.loads((ROOT / "project-management/project-state.json").read_text(encoding="utf-8"))
        state["execution_log"] = [{
            "id": "E-UNKNOWN-STATE",
            "feature_id": "F-01",
            "work_package_id": "K01",
            "kind": "implementation",
            "timestamp": "2026-10-16T10:00:00+08:00",
            "summary": "记录了一次实现活动，但没有状态流转字段",
        }]
        template = (ROOT / "skills/ai-project-management/assets/dashboard-shell.html").read_text(encoding="utf-8")
        html = render(template, state)
        start = html.index("function renderExecutionTimeline(feature,workPackage)")
        end = html.index("function bindSectionNavigation(root)", start)
        timeline = html[start:end]

        self.assertIn("const stateOf=event=>", timeline)
        self.assertIn("未标注状态", timeline)
        self.assertIn("event.work_package_id===workPackage.id", timeline)
        self.assertIn("暂无关联的 Execution Log 记录", timeline)
        self.assertNotIn("||'IN_PROGRESS'", timeline)

    def test_render_to_file_requires_valid_project_state_and_publishes_output(self):
        render_file = api(self, "render_to_file")
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "template.html"
            target = Path(directory) / "dashboard.html"
            state_path = Path(directory) / "state.json"
            source.write_text("<html><body><!-- AI_PM_STATE_SLOT --></body></html>", encoding="utf-8")
            state = {"schema_version": 1, "project": {"id": "p", "name": "Project"}, "features": [], "execution_log": [], "work_logs": {"daily": [], "weekly": [], "monthly": []}}
            state_path.write_text(json.dumps(state), encoding="utf-8")
            with self.assertRaises(ValueError):
                render_file(source, state_path, target)
            self.assertFalse(target.exists())

    def test_managed_html_can_be_updated_repeatedly_without_duplicate_app_shells(self):
        render = api(self, "render_dashboard")
        state = json.loads((ROOT / "project-management/project-state.json").read_text(encoding="utf-8"))
        template = (ROOT / "skills/ai-project-management/assets/dashboard-shell.html").read_text(encoding="utf-8")
        first = render(template, state)
        state["project"]["name"] = "Updated Project"
        second = render(first, state)
        self.assertEqual(second.count('id="ai-pm-state"'), 1)
        self.assertIn("Updated Project", second)


if __name__ == "__main__":
    unittest.main()
