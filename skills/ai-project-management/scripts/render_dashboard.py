"""Deterministically embed a validated project contract into the HTML prototype."""

from __future__ import annotations

import json
import html as html_lib
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from project_state import validate_project_state

SLOT = "<!-- AI_PM_STATE_SLOT -->"
APP_START = "<!-- AI_PM_APP_START -->"
APP_END = "<!-- AI_PM_APP_END -->"

APP_HTML = r'''
<style id="ai-pm-styles">
  .aipm-evidence-unavailable{display:inline-block;margin-top:8px;color:#8a9992;font-size:12px}.aipm-project-note{margin:0 0 10px;color:#71847a;font-size:12px}.aipm-inline-link{color:#347760;text-decoration:none;font-size:12px}.aipm-inline-link:hover{text-decoration:underline}
  .aipm-solution-list{display:grid;gap:14px}.aipm-solution{padding:16px;border:1px solid #e0e9e3;border-radius:14px;background:linear-gradient(145deg,#fff,#f8faf8)}.aipm-solution>h2{margin:0 0 8px;font-size:18px}.aipm-solution-meta{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin:10px 0}.aipm-solution-meta>div{padding:10px 12px;border-radius:10px;background:#f0f5f1}.aipm-solution-meta b{display:block;margin-bottom:3px;color:#557064;font-size:12px}.aipm-outcome-chart{display:block;width:100%;max-width:660px;height:auto;margin:10px 0}.aipm-outcome-chart text{font:12px system-ui,sans-serif;fill:#49695a}.aipm-experiment-list{display:grid;gap:10px;margin-top:12px}.aipm-experiment-card{padding:14px;border:1px solid #e5ece7;border-radius:11px;background:#fff}.aipm-experiment-card h3{margin:6px 0}.aipm-experiment-card p{margin:5px 0}.aipm-research-controls{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;margin:12px 0}.aipm-research-filter{display:flex;gap:6px;flex-wrap:wrap}.aipm-research-filter button{border:1px solid #dce8e0;border-radius:8px;padding:6px 10px;background:white;cursor:pointer}.aipm-research-filter button[aria-pressed=true]{background:#eaf5ee;color:#28684e;border-color:#bfd9c8}.aipm-outcome-note{color:#71847a;font-size:12px}
  #feature-workspace{position:fixed;inset:0;z-index:1000;overflow:hidden;padding:clamp(16px,4vw,52px);background:#f5f8f5;color:#243c32;font:15px/1.55 system-ui,sans-serif;box-sizing:border-box}
  .aipm-feature-summary{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:18px;align-items:center;margin:20px 0 14px;padding:22px 24px;border:1px solid #dce8e0;border-radius:18px;background:linear-gradient(115deg,#fff 0%,#f7faf7 100%);box-shadow:0 12px 28px rgba(36,73,54,.045)}.aipm-feature-summary h1{margin:7px 0 8px;font-size:clamp(25px,3vw,36px);letter-spacing:-.035em;line-height:1.2}.aipm-feature-summary p{max-width:780px;margin:0;color:#5f7569}.aipm-feature-summary-meta{display:flex;align-items:center;gap:9px;flex-wrap:wrap;margin-top:14px}.aipm-feature-progress{min-width:116px;padding:12px 16px;border-left:1px solid #e0e9e3;text-align:center}.aipm-feature-progress strong{display:block;color:#28704f;font-size:28px;line-height:1.2}.aipm-feature-progress span{color:#708278;font-size:12px}.aipm-feature-contract{margin:0 0 20px;border:1px solid #dce8e0;border-radius:14px;background:#fff;overflow:hidden}.aipm-feature-contract summary{display:flex;align-items:center;justify-content:space-between;gap:14px;padding:13px 17px;color:#28684e;font-weight:700;cursor:pointer;list-style:none}.aipm-feature-contract summary::-webkit-details-marker{display:none}.aipm-feature-contract summary::after{content:'＋';color:#347760;font-size:18px}.aipm-feature-contract[open] summary::after{content:'−'}.aipm-feature-contract summary:focus-visible{outline:2px solid #6da987;outline-offset:-3px}.aipm-feature-contract-body{display:grid;gap:12px;padding:0 16px 16px}.aipm-feature-contract-item{padding:15px;border:1px solid #e6eee8;border-radius:12px;background:#fbfdfb}.aipm-feature-contract-item h3{margin:0 0 11px;font-size:15px}.aipm-feature-contract-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.aipm-feature-contract-grid section{min-width:0;padding:11px 12px;border-radius:9px;background:#f1f6f2}.aipm-feature-contract-grid h4{margin:0 0 5px;color:#61786c;font-size:12px}.aipm-feature-contract-grid p,.aipm-feature-contract-grid ul{margin:0}.aipm-feature-contract-grid ul{padding-left:18px}.aipm-feature-contract-grid li+li{margin-top:5px}.aipm-feature-acceptance li{margin-bottom:8px}.aipm-feature-acceptance b{color:#355c49}
  #feature-workspace[hidden]{display:none!important}.aipm-detail{max-width:1200px;height:100%;margin:auto;display:flex;flex-direction:column;min-height:0}.aipm-detail-toolbar{display:flex;align-items:center;justify-content:space-between;gap:12px;flex:none;padding:10px 0;background:#f5f8f5;border-bottom:1px solid #dce8e0}.aipm-back{border:0;background:none;color:#347760;font:inherit;cursor:pointer}.aipm-section-nav{display:flex;justify-content:flex-end;gap:8px;flex-wrap:wrap;margin-left:auto;padding:0;background:transparent}.aipm-section-nav button{border:1px solid #dce8e0;border-radius:9px;padding:7px 12px;background:#fff;color:#347760;cursor:pointer;font:inherit}.aipm-detail-scroll{flex:1;min-height:0;overflow:auto;overscroll-behavior:contain;padding-bottom:24px}.aipm-detail-grid>.aipm-box{scroll-margin-top:16px}.aipm-detail-head{display:flex;justify-content:space-between;gap:20px;align-items:start;margin:20px 0}.aipm-detail-head h1{margin:4px 0;font-size:clamp(24px,3vw,34px);letter-spacing:-.035em;line-height:1.2}.aipm-detail-head h1:focus-visible,.aipm-plan-head h1:focus-visible{outline:2px solid #6da987;outline-offset:4px;border-radius:3px}.aipm-detail-grid{display:grid;grid-template-columns:1fr;gap:16px}.aipm-box,.aipm-wp{padding:18px;border:1px solid #e0e9e3;border-radius:14px;background:#fff}.aipm-wps{display:grid;gap:10px}.aipm-wp h3{margin:0}.aipm-wp h4{margin:12px 0 2px;font-size:13px;color:#62796d}.aipm-chips{display:flex;gap:6px;flex-wrap:wrap}.aipm-chip{border-radius:99px;padding:3px 9px;background:#eff5f0;font-size:12px}.aipm-topic{display:inline-block;margin-top:8px;color:#347760}.aipm-timeline{width:100%;overflow:visible}.aipm-timeline text{font:11px system-ui,sans-serif;fill:#697e73}.aipm-metrics{display:flex;gap:10px;flex-wrap:wrap}.aipm-metric{flex:1;min-width:120px;padding:10px;border-radius:10px;background:#f3f7f4}.aipm-metric b{display:block;font-size:20px}.aipm-periods{display:flex;gap:5px;margin-bottom:10px}.aipm-periods button{border:1px solid #dce8e0;border-radius:8px;padding:6px 10px;background:white;cursor:pointer}.aipm-periods button[aria-pressed=true]{background:#eaf5ee;color:#347760}.aipm-log-list{padding-left:20px}.aipm-log-list a{color:#347760}.aipm-empty{color:#8a9992}@media(max-width:800px){.aipm-detail-grid{grid-template-columns:1fr}.aipm-detail-toolbar{align-items:flex-start;flex-direction:column}.aipm-section-nav,.aipm-detail-toolbar>.aipm-project-views{align-self:flex-end;margin-left:0;justify-content:flex-end}.aipm-feature-summary{grid-template-columns:1fr;padding:18px}.aipm-feature-progress{padding:9px 0 0;border-left:0;border-top:1px solid #e0e9e3;text-align:left}.aipm-feature-contract-grid{grid-template-columns:1fr}}
  .aipm-plan{position:fixed;inset:0;z-index:1000;box-sizing:border-box;width:100%;height:100dvh;max-width:none;margin:0;padding:20px clamp(18px,4vw,58px) 24px;border:0;background:#f5f8f5;display:flex;flex-direction:column;overflow:hidden}.aipm-plan[hidden]{display:none!important}.aipm-plan-content{flex:1;min-height:0;overflow:auto;margin-top:12px;padding:20px;border:1px solid #e0e9e3;border-radius:22px;background:rgba(255,255,255,.96);box-shadow:0 18px 48px rgba(34,73,63,.055)}.aipm-project-page-top{display:flex;align-items:center;justify-content:space-between;gap:12px;flex:none;flex-wrap:wrap;padding:8px 0 12px;background:#f5f8f5;border-bottom:1px solid #dce8e0}.aipm-project-home{border:0;background:none;color:#347760;cursor:pointer;font:inherit}.aipm-plan-head{display:flex;justify-content:space-between;gap:14px;align-items:center;flex-wrap:wrap}.aipm-plan-head h1{margin:3px 0;font-size:21px;letter-spacing:-.025em;line-height:1.3;font-weight:750}.aipm-project-views{display:flex;gap:5px;flex-wrap:wrap;justify-content:flex-end;margin-left:auto}.aipm-project-views :is(a,button),.aipm-schedule-switch button,.aipm-plan select{display:inline-flex;align-items:center;min-height:36px;border:1px solid #dce8e0;border-radius:8px;padding:6px 10px;background:#fff;color:#49695a;text-decoration:none;cursor:pointer;font:inherit}.aipm-project-views a[aria-current=page],.aipm-project-views button[aria-pressed=true],.aipm-schedule-switch button[aria-pressed=true]{background:#eaf5ee;color:#28684e;border-color:#bfd9c8;font-weight:650}.aipm-schedule{margin-top:22px;padding-top:16px;border-top:1px solid #e7eee9}.aipm-schedule-head{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}.aipm-schedule-head h3{margin:0}.aipm-schedule-switch{display:flex;gap:5px;align-items:center}.aipm-table-wrap{overflow:auto;border:1px solid #e1eae4;border-radius:10px}.aipm-table{width:100%;border-collapse:collapse;min-width:760px;font-size:13px}.aipm-table th,.aipm-table td{padding:10px 12px;border-bottom:1px solid #e9efeb;text-align:left;vertical-align:top}.aipm-table th{position:sticky;top:0;background:#f3f7f4;color:#557064;white-space:nowrap}.aipm-table tr:last-child td{border-bottom:0}.aipm-table td ul{padding-left:17px;margin:0}.aipm-table .aipm-wbs-cell{min-width:190px}.aipm-table .aipm-long-cell{min-width:220px}.aipm-week-list{display:grid;gap:8px;margin-top:12px}.aipm-week-row{display:grid;grid-template-columns:170px 1fr;gap:10px;padding:12px;border:1px solid #e7eee9;border-radius:10px}.aipm-week-row h3{margin:0;font-size:14px}.aipm-week-row p{margin:3px 0}.aipm-month-grid{overflow:auto;border:1px solid #e6eee8;border-radius:10px;margin-top:12px}.aipm-month-title{padding:12px;font-weight:700}.aipm-month-week{display:grid;grid-template-columns:220px minmax(520px,1fr) minmax(180px,.7fr);gap:10px;padding:10px;border-top:1px solid #edf2ee}.aipm-week-bar{position:relative;height:25px;border-radius:8px;background:linear-gradient(90deg,#6da987,#9ac3a7);color:#fff;font-size:11px;line-height:25px;padding:0 8px;white-space:nowrap;overflow:hidden}.aipm-gantt{display:grid;gap:10px}.aipm-gantt-axis{display:grid;grid-template-columns:minmax(170px,260px) 1fr;gap:12px;align-items:end}.aipm-gantt-months{display:grid;grid-template-columns:repeat(var(--month-count),1fr);font-size:12px;color:#596d65;text-align:center}.aipm-gantt-row{display:grid;grid-template-columns:minmax(170px,260px) 1fr;gap:12px;align-items:stretch;padding:12px;border:1px solid #e7eee9;border-radius:10px}.aipm-gantt-label p{margin:5px 0 0;color:#596d65;font-size:12px}.aipm-gantt-track{position:relative;min-height:58px;display:grid;grid-template-columns:repeat(var(--month-count),1fr);align-items:center;background:repeating-linear-gradient(90deg,#f8faf8 0,#f8faf8 calc(100% / var(--month-count) - 1px),#e4ece6 calc(100% / var(--month-count) - 1px),#e4ece6 calc(100% / var(--month-count)))}.aipm-gantt-marker{position:absolute;top:50%;width:14px;height:14px;transform:translate(-50%,-50%) rotate(45deg);border:2px solid #fff;border-radius:3px;background:#438165;box-shadow:0 0 0 2px #438165}.aipm-research-dashboard{display:grid;grid-template-columns:1fr;gap:12px}.aipm-research-card{display:block;width:100%;padding:16px;text-align:left;text-decoration:none;color:inherit;border:1px solid #e0e9e3;border-radius:13px;background:linear-gradient(145deg,#fff,#f7faf7);transition:transform .16s ease,border-color .16s ease,box-shadow .16s ease}.aipm-research-card:hover{transform:translateY(-2px);border-color:#9fcab0;box-shadow:0 10px 26px rgba(34,73,63,.08)}.aipm-research-card h3{margin:9px 0 4px;font-size:15px}.aipm-research-card p{margin:0;color:#596d65;font-size:12px}.aipm-research-stats{display:flex;gap:6px;flex-wrap:wrap;margin-top:12px}.aipm-research-stats span{padding:3px 7px;border-radius:99px;background:#eff5f0;font-size:11px}.aipm-research-status{color:#347760;font-weight:700}.aipm-milestone-acceptance{margin:0;color:#647a6f;font-size:12px}@media(max-width:720px){.aipm-week-row{grid-template-columns:1fr}.aipm-month-week{grid-template-columns:160px minmax(500px,1fr) minmax(180px,.7fr)}.aipm-gantt-axis,.aipm-gantt-row{grid-template-columns:1fr}.aipm-gantt-axis>span{display:none}}
  .aipm-home-view-nav{position:sticky;top:0;z-index:10;align-self:stretch;padding:8px 0;background:#f5f8f5;border-bottom:1px solid #dce8e0;box-shadow:0 5px 12px rgba(34,73,63,.05)}
  :is(#feature-workspace,#aipm-state-plan,#aipm-project-view-nav) :is(button,a,select,input,[tabindex="0"]){transition:color .14s ease,background-color .14s ease,border-color .14s ease,box-shadow .14s ease}
  :is(#feature-workspace,#aipm-state-plan,#aipm-project-view-nav) :is(button,a):hover{border-color:#9fcab0;background:#f2f8f4;color:#245f48}
  :is(#feature-workspace,#aipm-state-plan,#aipm-project-view-nav) :is(button,a,select,input,[tabindex="0"]):focus-visible{outline:3px solid #6da987;outline-offset:2px;z-index:2}
  .aipm-back,.aipm-project-home{min-height:36px;padding:6px 10px;border-radius:8px;touch-action:manipulation;-webkit-tap-highlight-color:rgba(56,128,91,.14)}
  .aipm-section-nav button,.aipm-project-views :is(a,button),.aipm-schedule-switch button,.aipm-research-filter button,.aipm-clear-filters,.aipm-sort-button{min-height:36px;padding:6px 10px;border-radius:8px;touch-action:manipulation;-webkit-tap-highlight-color:rgba(56,128,91,.14)}
  .aipm-detail-toolbar,.aipm-project-page-top{box-shadow:0 4px 10px rgba(30,65,50,.035)}.aipm-detail-toolbar,.aipm-project-page-top{position:relative;z-index:3}
  #feature-workspace .aipm-section-nav button[aria-current=location]{background:#eaf5ee;color:#28684e;border-color:#bfd9c8;font-weight:650}
  #aipm-state-plan{left:50%;right:auto;transform:translateX(-50%);width:min(100%,1500px)}
  @media(max-width:800px){#feature-workspace .aipm-section-nav,#feature-workspace .aipm-detail-toolbar>.aipm-project-views{align-self:stretch;width:100%;margin-left:0;justify-content:flex-end}}
  .aipm-wp-link{display:block;color:inherit;text-decoration:none;transition:border-color .14s ease,background-color .14s ease,box-shadow .14s ease}.aipm-wp-link:hover{border-color:#9fcab0;background:#f7fbf8;box-shadow:0 4px 14px rgba(34,73,63,.07)}.aipm-wp-link:focus-visible{outline:3px solid #6da987;outline-offset:2px}.aipm-wp-open{display:block;margin-top:10px;color:#347760;font-size:12px;font-weight:650}
  .aipm-timeline-wrap{max-width:100%;overflow-x:auto;overscroll-behavior-x:contain;-webkit-overflow-scrolling:touch}.aipm-timeline{display:block;width:100%;min-width:720px;max-width:900px;overflow:visible}
  .aipm-plan-content{padding:16px;border-radius:14px;box-shadow:0 8px 24px rgba(34,73,63,.045)}
  .aipm-box,.aipm-wp{padding:14px;border-radius:11px}
  .aipm-detail-grid{gap:12px}
  .aipm-research-dashboard{grid-template-columns:repeat(auto-fit,minmax(min(100%,320px),1fr));gap:8px}
  .aipm-research-card{padding:12px;border-radius:10px;transition:background-color .14s ease,border-color .14s ease,box-shadow .14s ease}
  .aipm-research-card:hover{transform:none;border-color:#83b99a;background:#f7fbf8;box-shadow:0 3px 12px rgba(34,73,63,.07)}
  .aipm-research-card:focus-visible{outline:3px solid #6da987;outline-offset:2px}
  .aipm-table-tools{display:flex;align-items:end;gap:8px;flex-wrap:wrap;margin:0 0 10px;padding:10px;border:1px solid #e1eae4;border-radius:10px;background:#f8faf8}
  .aipm-table-tools label{display:grid;gap:3px;color:#647a6f;font-size:11px;font-weight:650}
  .aipm-table-tools input,.aipm-table-tools select{min-width:150px;min-height:34px;padding:6px 9px;border:1px solid #d5e2d9;border-radius:7px;background:white;color:#243c32;font:inherit;font-size:12px}
  .aipm-table-tools input[type=search]{min-width:min(260px,70vw)}
  .aipm-table-count{margin-left:auto;color:#647a6f;font-size:12px}
  .aipm-clear-filters{min-height:34px;padding:6px 10px;border:1px solid #d5e2d9;border-radius:7px;background:#fff;color:#347760;cursor:pointer;font:inherit;font-size:12px}
  .aipm-sort-button{padding:3px 4px;border:0;background:transparent;color:inherit;font:inherit;font-weight:700;cursor:pointer;white-space:nowrap}
  .aipm-table th[aria-sort=ascending] .aipm-sort-button::after{content:' ↑';color:#347760}.aipm-table th[aria-sort=descending] .aipm-sort-button::after{content:' ↓';color:#347760}
  .aipm-table tbody tr:hover{background:#f7faf7}.aipm-table tbody tr[hidden]{display:none}
  .aipm-table-wrap{scrollbar-color:#b7cec0 #f3f7f4;scrollbar-width:thin}
  .aipm-table th{z-index:1}
  .aipm-empty-row td{text-align:center;padding:24px;color:#596d65}
  .aipm-timeline circle{cursor:help}.aipm-timeline circle:focus{stroke:#204f3a;stroke-width:3px;outline:none}.aipm-timeline-tooltip{display:block;min-height:1.4em;margin-top:8px;padding:8px 10px;border-left:3px solid #6da987;border-radius:0 7px 7px 0;background:#f7faf7;color:#40594d;font-size:12px}
  .page :is(button,a,select,input,[tabindex="0"]){transition:color .14s ease,background-color .14s ease,border-color .14s ease,box-shadow .14s ease}
  .page :is(button,a,select,input,[tabindex="0"]):focus-visible{outline:3px solid #6da987;outline-offset:2px}
  #main-content .progress-rubric summary:focus-visible{outline:3px solid #6da987;outline-offset:3px;border-radius:4px}
  .page button:active,.aipm-project-views :is(a,button):active,.aipm-section-nav button:active,.aipm-schedule-switch button:active{transform:translateY(1px)}
  .feature-trigger{transition:background-color .14s ease,border-color .14s ease,box-shadow .14s ease}
  .feature-trigger:focus-visible{position:relative;z-index:2;outline:3px solid #6da987;outline-offset:2px}
  .today-summary a,.research-topic-link,.aipm-feature-link{color:#347760;text-decoration-thickness:1px;text-underline-offset:2px}
  .today-summary a:hover,.research-topic-link:hover,.aipm-feature-link:hover{color:#245f48;text-decoration-thickness:2px}
  .aipm-research-controls{display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:10px}.aipm-experiment-list{display:grid;gap:10px}.aipm-research-filter{display:flex;gap:6px;align-items:center;flex-wrap:wrap;margin:0}
  .aipm-research-filter button{min-height:32px;padding:5px 9px;border:1px solid #dce8e0;border-radius:7px;background:white;color:#49695a;cursor:pointer;font:inherit;font-size:12px}
  .aipm-research-filter button[aria-pressed=true]{background:#eaf5ee;color:#28684e;border-color:#bfd9c8}.aipm-research-filter button:hover,.aipm-clear-filters:hover,.aipm-sort-button:hover{border-color:#9fcab0;background:#f2f8f4;color:#245f48}.aipm-project-home:hover,.aipm-back:hover{background:#edf5ef;color:#245f48}
  .aipm-hidden{display:none!important}
  @media(prefers-reduced-motion:reduce){#feature-workspace *,#aipm-state-plan *,#aipm-project-view-nav *{scroll-behavior:auto!important;transition:none!important;animation:none!important}}
  @media(max-width:720px){.aipm-plan-content{padding:10px}.aipm-table-tools{align-items:stretch}.aipm-table-tools label,.aipm-table-tools input,.aipm-table-tools select{width:100%;box-sizing:border-box}.aipm-table-count{width:100%;margin:0}.aipm-detail-toolbar{gap:6px}.aipm-section-nav{gap:5px}.aipm-back,.aipm-project-home,.aipm-section-nav button,.aipm-project-views :is(a,button),.aipm-schedule-switch button,.aipm-research-filter button,.aipm-clear-filters,.aipm-sort-button,.aipm-table-tools input,.aipm-table-tools select{min-height:44px}.aipm-section-nav button{padding:6px 8px;font-size:12px}}
</style>
<nav id="aipm-project-view-nav" class="aipm-project-views" aria-label="项目视图"><a href="#project/okr">OKR</a><a href="#project/wbs">WBS</a><a href="#project/milestones">里程碑甘特图</a></nav>
<section id="feature-workspace" class="aipm-feature-workspace" hidden></section>
<section id="aipm-state-plan" class="aipm-plan" aria-label="项目管理视图" hidden></section>
<script type="application/json" id="ai-pm-state">__STATE_JSON__</script>
<script>
(() => {
  const stateNode=document.getElementById('ai-pm-state');
  let project=JSON.parse(stateNode.textContent);
  let currentProjectView='okr';
  let currentScheduleView='weekly';
  let currentRouteHash=location.hash;
  let routeHistory=[location.hash];
  let routeHistoryIndex=0;
  let historyTraversalPending=false;
  let fallbackRoutePending=false;
  const workspace=document.getElementById('feature-workspace');
  const routeScrollPositions=new Map();
  function routeScroller(hash){
    if(/^#project\/(okr|wbs|milestones)$/.test(hash))return document.getElementById('aipm-state-plan')?.querySelector('.aipm-plan-content')||null;
    if(/^#(feature\/|work-package\/|research\/)/.test(hash))return workspace.querySelector('.aipm-detail-scroll');
    return null;
  }
  function navigateBack(fallback=''){
    if(routeHistoryIndex>0){window.history.back();return}
    const target=fallback?(fallback.startsWith('#')?fallback:`#${fallback}`):'';
    if(target===location.hash)return;
    routeHistory=[target];routeHistoryIndex=0;fallbackRoutePending=true;
    window.history.replaceState(window.history.state,'',`${location.pathname}${location.search}${target}`);
    setRoute();
  }
  const labels=['TODO','READY','IN_PROGRESS','IMPLEMENTED','VERIFYING','DONE','BLOCKED','FAILED','FIXING'];
  const safe=(value)=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const evidencePrefix=__EVIDENCE_PREFIX__;
  const safeHref=(value)=>{const link=String(value||'').trim();if(!link)return null;if(/^(https?:\/\/|mailto:)/i.test(link))return safe(link);if(/^[a-z][a-z0-9+.-]*:/i.test(link)||link.startsWith('//'))return null;return safe(link.startsWith('/')||link.startsWith('#')?link:`${evidencePrefix}${link}`)};
  const renderEvidenceLink=(value)=>{const href=safeHref(value);return href?`<a class="aipm-topic" href="${href}" rel="noopener noreferrer">证据 ↗</a>`:'<span class="aipm-evidence-unavailable" aria-label="证据链接不可用">证据链接不可用</span>'};
  const pct=(n)=>`${Math.round(Number(n)||0)}%`;
  function allEvents(){return Array.isArray(project.execution_log)?project.execution_log:[]}
  function featureByTitle(title,id){return project.features.find(f=>f.title===title)||(id?project.features.find(f=>f.id===id):null)}
  function renderResearchCard(feature,workPackage){
    const topic=workPackage.research_topic||{};
    const experiments=(project.experiments||[]).filter(item=>item.topic_id===topic.id);
    const solutions=topic.solutions||[];
    const latest=[...experiments].sort((a,b)=>String(a.timestamp||'').localeCompare(String(b.timestamp||''))).at(-1);
    const counts=Object.fromEntries(['PASS','FAIL','INCONCLUSIVE'].map(result=>[result,experiments.filter(item=>item.result===result).length]));
    const labels={PASS:'最近通过',FAIL:'最近失败',INCONCLUSIVE:'最近未定'};
    const status=latest?(labels[latest.result]||`最近 ${latest.result}`):'未开始';
    return `<a class="aipm-research-card" data-feature-id="${safe(feature.id)}" data-research-topic="${safe(topic.id||'')}" data-work-package-id="${safe(workPackage.id)}" data-latest-experiment="${safe(latest?.result||'NONE')}" href="#research/${encodeURIComponent(topic.id||'')}"><span class="aipm-chip">${safe(workPackage.id)}</span><span class="aipm-chip aipm-research-status">${safe(status)}</span><h3>${safe(topic.title||'待定义课题')}</h3><div class="aipm-research-stats"><span>方案 ${solutions.length}</span><span>实验总数 ${experiments.length}</span><span>PASS ${counts.PASS}</span><span>FAIL ${counts.FAIL}</span><span>INCONCLUSIVE ${counts.INCONCLUSIVE}</span><span>最近结果 ${safe(latest?.result||'无')}</span></div></a>`;
  }
  function renderExecutionTimeline(feature,workPackage){
    const recorded=(workPackage.status_history||[]).map((event,index)=>({...event,id:event.id||`${workPackage.id}-history-${index}`,work_package_id:workPackage.id,summary:event.summary||`${event.from||'状态'} → ${event.to||'状态'}`}));
    const events=allEvents().filter(event=>event.work_package_id===workPackage.id&&(!event.feature_id||event.feature_id===feature.id));
    const seen=new Set();
    const history=[...recorded,...events].filter(event=>Number.isFinite(Date.parse(event.timestamp||''))).filter(event=>{if(!event.id)return true;if(seen.has(event.id))return false;seen.add(event.id);return true}).sort((a,b)=>a.timestamp.localeCompare(b.timestamp));
    if(!history.length)return {history,points:[],html:'<p class="aipm-empty">该二级功能暂无关联的 Execution Log 记录。后续记录需绑定此 Work Package，时间线才会显示状态变化。</p>'};
    const stateOf=event=>{const raw=event.status_category||event.to||event.status;const state=raw==='VERIFICATION_FAILED'?'FAILED':raw;return labels.includes(state)?state:null};
    const categories=[...labels,'未标注状态'];
    const chartTop=30,rowHeight=36,chartBottom=chartTop+categories.length*rowHeight,chartHeight=chartBottom+36;
    const yFor=Object.fromEntries(categories.map((category,index)=>[category,chartTop+index*rowHeight]));
    const dates=history.map(event=>Date.parse(event.timestamp));
    const lo=Math.min(...dates),hi=Math.max(...dates);
    const xFor=event=>80+((Date.parse(event.timestamp)-lo)/(hi-lo||1))*680;
    const groupSize=new Map();
    for(const event of history){const key=JSON.stringify([event.timestamp,stateOf(event)||'未标注状态']);groupSize.set(key,(groupSize.get(key)||0)+1)}
    const groupIndex=new Map();
    const points=history.map(event=>{const state=stateOf(event),category=state||'未标注状态',key=JSON.stringify([event.timestamp,category]),index=groupIndex.get(key)||0,total=groupSize.get(key)||1;groupIndex.set(key,index+1);const step=total>1?Math.min(8,24/(total-1)):0;const displayY=yFor[category]+step*(index-(total-1)/2);const time=new Intl.DateTimeFormat('zh-CN',{year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false}).format(new Date(event.timestamp));const detail=`${time} · ${state?`状态 ${state}`:`未标注状态${event.kind?` · 事件类型 ${event.kind}`:''}`} · ${event.summary||event.message||event.reason||'状态变更'} · ${workPackage.id}`;return {x:xFor(event),y:yFor[category],displayY,state,detail}});
    const statusPoints=points.filter(point=>point.state);
    const lines=statusPoints.map((point,index)=>index?`<line x1="${statusPoints[index-1].x}" y1="${statusPoints[index-1].y}" x2="${point.x}" y2="${point.y}" stroke="#89aa96" stroke-width="2"/>`:"").join('');
    const dots=points.map((point,index)=>`<circle data-log-event="${index}" cx="${point.x}" cy="${point.displayY}" r="5" tabindex="0" role="img" aria-label="${safe(point.detail)}" fill="${point.state==='FAILED'||point.state==='BLOCKED'?'#c56d5f':point.state?'#438165':'#84928b'}"><title>${safe(point.detail)}</title></circle>`).join('');
    const axis=categories.map((category,index)=>`<text x="4" y="${chartTop+4+index*rowHeight}">${safe(category)}</text><line x1="75" y1="${chartTop+index*rowHeight}" x2="765" y2="${chartTop+index*rowHeight}" stroke="#edf2ee"/>`).join('');
    const first=new Intl.DateTimeFormat('zh-CN',{year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false}).format(new Date(lo));
    const last=new Intl.DateTimeFormat('zh-CN',{year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false}).format(new Date(hi));
    const statusEvents=history.filter(event=>stateOf(event));
    const latest=statusEvents.at(-1);
    const failures=statusEvents.filter(event=>stateOf(event)==='FAILED').length;
    const returns=history.filter(event=>event.from==='VERIFYING'&&['FAILED','BLOCKED'].includes(event.to||stateOf(event))).length;
    const recent=event=>Date.now()-Date.parse(event.timestamp)<=7*86400000;
    const recentFailures=history.filter(event=>recent(event)&&stateOf(event)==='FAILED').length;
    const recentReturns=history.filter(event=>recent(event)&&event.from==='VERIFYING'&&['FAILED','BLOCKED'].includes(event.to||stateOf(event))).length;
    const convergence=recentReturns>=2||recentFailures>=3?'可能反复验证':'未达到观察阈值';
    const metrics=`<div class="aipm-metrics"><div class="aipm-metric"><b>${returns}</b>验证回退</div><div class="aipm-metric"><b>${failures}</b>验证失败</div><div class="aipm-metric"><b>${latest?`${Math.floor(Math.max(0,Date.now()-Date.parse(latest.timestamp))/3600000)} h`:'—'}</b>${latest?`${safe(stateOf(latest))} 停留时间`:'状态停留时间'}</div><div class="aipm-metric"><b>${convergence}</b>7 日观察规则：≥2 次验证回退或 ≥3 次失败</div></div>`;
    const html=`<div class="aipm-timeline-wrap" tabindex="0" role="region" aria-label="Execution Log 时间线，可横向滚动查看"><svg class="aipm-timeline" viewBox="0 0 780 ${chartHeight}" role="img" aria-label="执行记录时间线，横轴为时间，纵轴为 Work Package 状态">${axis}${lines}${dots}<line x1="80" y1="${chartBottom}" x2="765" y2="${chartBottom}" stroke="#9baca2"/><text x="80" y="${chartBottom+18}">${safe(first)}</text><text x="620" y="${chartBottom+18}">${hi>lo?safe(last):''}</text></svg></div><output class="aipm-timeline-tooltip" aria-live="polite">将焦点或指针移到时间点上查看详情。</output>${metrics}`;
    return {history,points,html};
  }
  function bindSectionNavigation(root){
    const buttons=[...root.querySelectorAll('[data-jump-to]')];
    const scroller=root.querySelector('.aipm-detail-scroll');
    const sections=scroller?[...scroller.querySelectorAll('[data-nav-section]')]:[];
    const mark=id=>buttons.forEach(button=>{if(button.dataset.jumpTo===id)button.setAttribute('aria-current','location');else button.removeAttribute('aria-current')});
    const reduceMotion=window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    buttons.forEach(button=>button.onclick=()=>{mark(button.dataset.jumpTo);const section=scroller?.querySelector(`[data-nav-section="${CSS.escape(button.dataset.jumpTo)}"]`);const disclosure=section?.closest('details');if(disclosure)disclosure.open=true;section?.scrollIntoView({behavior:reduceMotion?'auto':'smooth',block:'start'})});
    if(sections.length){mark(sections[0].dataset.navSection);let pending=false;scroller.addEventListener('scroll',()=>{if(pending)return;pending=true;requestAnimationFrame(()=>{pending=false;const anchor=scroller.getBoundingClientRect().top+48;const current=sections.filter(section=>section.getBoundingClientRect().top<=anchor).at(-1)||sections[0];mark(current.dataset.navSection)})},{passive:true})}
  }
  function renderNotFound(message){
    workspace.innerHTML=`<div class="aipm-detail"><div class="aipm-detail-toolbar"><button class="aipm-back" id="aipm-back">← 返回</button><nav class="aipm-project-views" aria-label="项目视图导航"><a href="#project/okr">OKR</a><a href="#project/wbs">WBS</a><a href="#project/milestones">里程碑甘特图</a></nav></div><div class="aipm-detail-scroll"><section class="aipm-box" role="status"><h1 id="aipm-active-heading" tabindex="-1">${safe(message)}</h1><p>此链接可能已过期，或对应的项目功能已调整。</p></section></div></div>`;
    document.getElementById('aipm-back').onclick=()=>navigateBack('');
  }
  function renderFeature(id){
    const feature=project.features.find(item=>item.id===id);if(!feature)return renderNotFound('未找到该一级功能。');
    const packages=feature.work_packages||[];
    const cards=packages.map(workPackage=>`<a class="aipm-wp aipm-wp-link" data-work-package="${safe(workPackage.id)}" href="#work-package/${encodeURIComponent(feature.id)}/${encodeURIComponent(workPackage.id)}"><div class="aipm-chips"><span class="aipm-chip">${safe(workPackage.id)}</span><span class="aipm-chip">${safe(workPackage.status||'TODO')}</span><span class="aipm-chip">进度 ${pct(workPackage.progress??0)}</span></div><h3>${safe(workPackage.title)}</h3><p>${safe(workPackage.description)}</p><div class="aipm-research-stats"><span>输入 ${workPackage.inputs?.length||0}</span><span>输出 ${workPackage.outputs?.length||0}</span><span>验收项 ${workPackage.acceptance_criteria?.length||0}</span></div><span class="aipm-wp-open">查看二级功能详情 →</span></a>`).join('');
    const packageIds=new Set(packages.map(workPackage=>workPackage.id));
    const relatedWeeks=(project.weeks||[]).filter(week=>(week.work_package_ids||[]).some(workPackageId=>packageIds.has(workPackageId))&&week.end);
    const deadline=relatedWeeks.map(week=>week.end).sort().at(-1)||'暂无关联计划';
    const acceptanceMarkup=items=>items.length?`<ul class="aipm-feature-acceptance">${items.map(item=>`<li><b>${safe(item.metric)}</b>：${safe(item.target)}<br><span>验收方法：${safe(item.method)}</span></li>`).join('')}</ul>`:'<p class="aipm-empty">尚未定义验收指标与方法。</p>';
    const contract=packages.map(workPackage=>`<article class="aipm-feature-contract-item"><h3>${safe(workPackage.id)} · ${safe(workPackage.title)}</h3><div class="aipm-feature-contract-grid"><section><h4>输入</h4><ul>${(workPackage.inputs||[]).map(item=>`<li>${safe(item)}</li>`).join('')||'<li class="aipm-empty">待补充</li>'}</ul></section><section><h4>输出</h4><ul>${(workPackage.outputs||[]).map(item=>`<li>${safe(item)}</li>`).join('')||'<li class="aipm-empty">待补充</li>'}</ul></section><section><h4>内容</h4><p>${safe(workPackage.description||'待补充')}</p><ul>${(workPackage.scope||[]).map(item=>`<li>${safe(item)}</li>`).join('')}</ul></section><section><h4>验收指标与方法</h4>${acceptanceMarkup(workPackage.acceptance_criteria||[])}</section></div></article>`).join('');
    const done=packages.filter(workPackage=>workPackage.status==='DONE').length;
    workspace.innerHTML=`<div class="aipm-detail"><div class="aipm-detail-toolbar"><button class="aipm-back" id="aipm-back">← 返回</button><nav class="aipm-section-nav" aria-label="一级功能内容导航"><button type="button" data-jump-to="work-packages">二级功能</button></nav></div><div class="aipm-detail-scroll"><header class="aipm-feature-summary"><div><div class="aipm-chip">一级功能 · ${safe(feature.id)}</div><h1 id="aipm-active-heading" tabindex="-1">${safe(feature.title)}</h1><p>${safe(feature.description||'暂无功能简介。')}</p><div class="aipm-feature-summary-meta"><span class="aipm-chip">截止时间 · ${safe(deadline)}</span><span class="aipm-chip">${done} / ${packages.length} 个二级功能已完成</span></div></div><div class="aipm-feature-progress"><strong>${pct(feature.progress??0)}</strong><span>一级功能进度</span></div></header><details class="aipm-feature-contract"><summary>展开功能详情：输入、输出、内容与验收指标/方法</summary><div class="aipm-feature-contract-body">${contract||'<p class="aipm-empty">当前一级功能尚无二级功能详情。</p>'}</div></details><section class="aipm-box" id="work-packages" data-nav-section="work-packages"><h2>二级功能</h2><div class="aipm-wps">${cards||'<p class="aipm-empty">当前一级功能尚无二级功能。</p>'}</div></section></div></div>`;
    bindSectionNavigation(workspace);
    document.getElementById('aipm-back').onclick=()=>navigateBack('');
  }
  function renderWorkPackage(featureId,workPackageId){
    const feature=project.features.find(item=>item.id===featureId);
    const workPackage=feature?.work_packages?.find(item=>item.id===workPackageId);
    if(!feature||!workPackage)return renderNotFound('未找到该二级功能。');
    const timeline=renderExecutionTimeline(feature,workPackage);
    const topic=workPackage.research_topic||{};
    const topicCard=topic.id?renderResearchCard(feature,workPackage):'<p class="aipm-empty">该二级功能尚未关联研究课题。</p>';
    const acceptance=(workPackage.acceptance_criteria||[]).map(item=>`<li><b>${safe(item.method)}</b>：${safe(item.metric)} · ${safe(item.target)} · ${safe(item.status||'NOT_RUN')}</li>`).join('');
    const relatedWeeks=(project.weeks||[]).filter(week=>(week.work_package_ids||[]).includes(workPackage.id)&&week.end);
    const deadline=relatedWeeks.map(week=>week.end).sort().at(-1)||'暂无关联计划';
    const contract=`<article class="aipm-feature-contract-item"><div class="aipm-feature-contract-grid"><section><h4>输入</h4><ul>${(workPackage.inputs||[]).map(item=>`<li>${safe(item)}</li>`).join('')||'<li class="aipm-empty">待补充</li>'}</ul></section><section><h4>输出</h4><ul>${(workPackage.outputs||[]).map(item=>`<li>${safe(item)}</li>`).join('')||'<li class="aipm-empty">待补充</li>'}</ul></section><section><h4>内容</h4><p>${safe(workPackage.description||'待补充')}</p><ul>${(workPackage.scope||[]).map(item=>`<li>${safe(item)}</li>`).join('')}</ul></section><section><h4>验收指标与方法</h4>${acceptance?`<ul class="aipm-feature-acceptance">${acceptance}</ul>`:'<p class="aipm-empty">尚未定义验收指标与方法。</p>'}</section></div></article>`;
    workspace.innerHTML=`<div class="aipm-detail" data-view="work-package-detail" data-work-package-id="${safe(workPackage.id)}"><div class="aipm-detail-toolbar"><button class="aipm-back" id="aipm-back">← 返回</button><nav class="aipm-section-nav" aria-label="二级功能详情导航"><button type="button" data-jump-to="execution-log">Execution Log</button><button type="button" data-jump-to="research-topic">研究课题</button><button type="button" data-jump-to="work-package-contract">功能详情</button></nav></div><div class="aipm-detail-scroll"><header class="aipm-feature-summary"><div><div class="aipm-chips"><a class="aipm-chip aipm-feature-link" href="#feature/${encodeURIComponent(feature.id)}">${safe(feature.title)}</a><span class="aipm-chip">二级功能 · ${safe(workPackage.id)}</span><span class="aipm-chip">${safe(workPackage.status||'TODO')}</span></div><h1 id="aipm-active-heading" tabindex="-1">${safe(workPackage.title)}</h1><p>${safe(workPackage.description||'暂无功能简介。')}</p><div class="aipm-feature-summary-meta"><span class="aipm-chip">截止时间 · ${safe(deadline)}</span><span class="aipm-chip">验收项 · ${(workPackage.acceptance_criteria||[]).length}</span></div></div><div class="aipm-feature-progress"><strong>${pct(workPackage.progress??0)}</strong><span>二级功能进度</span></div></header><details class="aipm-feature-contract" id="work-package-contract" data-nav-section="work-package-contract"><summary>展开功能详情：输入、输出、内容与验收指标/方法</summary><div class="aipm-feature-contract-body">${contract}</div></details><div class="aipm-detail-grid"><section class="aipm-box" id="execution-log" data-nav-section="execution-log"><h2>Execution Log 状态时间线</h2><p class="aipm-empty">纵轴展示该二级功能已记录的状态；未绑定 Work Package 的项目级日志不会计入。</p>${timeline.html}</section><section class="aipm-box" id="research-topic" data-nav-section="research-topic"><h2>研究课题仪表盘</h2><div class="aipm-research-dashboard">${topicCard}</div></section></div></div></div>`;
    const tooltip=workspace.querySelector('.aipm-timeline-tooltip');
    workspace.querySelectorAll('[data-log-event]').forEach(dot=>{const show=()=>{const point=timeline.points[Number(dot.dataset.logEvent)];if(tooltip&&point)tooltip.textContent=point.detail};dot.addEventListener('pointerenter',show);dot.addEventListener('focus',show);dot.addEventListener('pointerleave',()=>{if(document.activeElement!==dot&&tooltip)tooltip.textContent='将焦点或指针移到时间点上查看详情。'});dot.addEventListener('blur',()=>{if(tooltip)tooltip.textContent='将焦点或指针移到时间点上查看详情。'})});
    bindSectionNavigation(workspace);
    document.getElementById('aipm-back').onclick=()=>navigateBack(`feature/${encodeURIComponent(feature.id)}`);
  }
  function renderResearch(id){
    const feature=project.features.find(item=>item.work_packages?.some(workPackage=>workPackage.research_topic?.id===id));
    const workPackage=feature?.work_packages?.find(item=>item.research_topic?.id===id);
    if(!feature||!workPackage)return renderNotFound('该研究课题未关联二级功能，无法打开。');
    const topic=workPackage.research_topic;
    const experiments=(project.experiments||[]).filter(item=>item.topic_id===id);
    const solutions=Array.isArray(topic.solutions)?topic.solutions:[];
    const resultNames={PASS:'PASS',FAIL:'FAIL',INCONCLUSIVE:'INCONCLUSIVE'};
    const outcomeChart=(rows,label)=>{
      if(!rows.length)return '<p class="aipm-empty">尚无实验结果可视化。</p>';
      const counts=Object.fromEntries(Object.keys(resultNames).map(result=>[result,rows.filter(item=>item.result===result).length]));
      const max=Math.max(1,...Object.values(counts));
      const colors={PASS:'#4f9470',FAIL:'#d47768',INCONCLUSIVE:'#c4a35b'};
      const bars=Object.entries(resultNames).map(([key,name],index)=>{const y=20+index*32,width=Math.round(counts[key]/max*360);return `<g><text x="0" y="${y+13}">${name} · ${counts[key]}</text><rect x="142" y="${y}" width="360" height="19" rx="7" fill="#eff4f0"/><rect x="142" y="${y}" width="${width}" height="19" rx="7" fill="${colors[key]}"/><title>${name}：${counts[key]} 次</title></g>`}).join('');
      return `<svg class="aipm-outcome-chart" viewBox="0 0 520 112" role="img" aria-label="${safe(label)}实验结果统计：PASS ${counts.PASS}，FAIL ${counts.FAIL}，INCONCLUSIVE ${counts.INCONCLUSIVE}">${bars}</svg><p class="aipm-outcome-note">按实验结论计数；该统计不代表验收通过率。</p>`;
    };
    const renderExperiment=(item,solution)=>`<article class="aipm-experiment-card" data-experiment-result="${safe(item.result)}"><div class="aipm-chips"><span class="aipm-chip">${safe(resultNames[item.result]||item.result)}</span><span class="aipm-chip">${safe(item.timestamp)}</span><span class="aipm-chip">价值分 ${safe(item.value_score??'—')}</span></div><h3>${safe(item.hypothesis)}</h3><p><b>使用的方法：</b>${safe(item.method||solution?.method||'尚未记录')}</p><p><b>数据来源：</b>${safe(item.data_source||solution?.data_source||'尚未记录')}</p><p><b>实验结果：</b>${safe(item.observation||item.summary||'尚未记录')}</p><p><b>结论：</b>${safe(item.conclusion||'尚未记录')}</p><div>${(item.evidence_links||[]).map(renderEvidenceLink).join(' ')}</div></article>`;
    const renderedSolutions=solutions.map(solution=>{
      const trials=experiments.filter(item=>item.solution_id===solution.id);
      return `<section class="aipm-solution" data-solution-id="${safe(solution.id)}"><h2>${safe(solution.name)} <span class="aipm-chip">${trials.length} 次实验</span></h2><div class="aipm-solution-meta"><div><b>使用的方法</b>${safe(solution.method)}</div><div><b>数据来源</b>${safe(solution.data_source)}</div></div><h3>实验结果</h3>${outcomeChart(trials,solution.name)}<div class="aipm-experiment-list">${trials.map(item=>renderExperiment(item,solution)).join('')||'<p class="aipm-empty">该方案尚无实验记录。</p>'}</div><h3>方案结论</h3><p>${safe(solution.conclusion||'尚未形成结论；请基于已记录实验结果归纳，不从未验证假设推断。')}</p></section>`;
    }).join('');
    const unassigned=experiments.filter(item=>!item.solution_id||!solutions.some(solution=>solution.id===item.solution_id));
    const legacySection=unassigned.length?`<section class="aipm-solution"><h2>未归入方案的历史实验</h2><div class="aipm-solution-meta"><div><b>使用的方法</b>按单次实验记录展示</div><div><b>数据来源</b>读取每次实验记录</div></div><h3>实验结果</h3>${outcomeChart(unassigned,'历史实验')}<div class="aipm-experiment-list">${unassigned.map(item=>renderExperiment(item,null)).join('')}</div></section>`:'';
    const filterControls=experiments.length?`<div class="aipm-research-controls"><div class="aipm-research-filter" role="group" aria-label="筛选实验结果"><button type="button" data-experiment-filter="all" aria-pressed="true">全部 ${experiments.length}</button>${['PASS','FAIL','INCONCLUSIVE'].map(result=>`<button type="button" data-experiment-filter="${result}" aria-pressed="false">${result} ${experiments.filter(item=>item.result===result).length}</button>`).join('')}</div><output class="aipm-table-count" data-experiment-count aria-live="polite">显示 ${experiments.length} / ${experiments.length} 条</output></div>`:'';
    const records=experiments.length?`${filterControls}<div class="aipm-solution-list">${renderedSolutions}${legacySection}<p class="aipm-empty" data-experiment-empty hidden>没有匹配的实验记录。请选择其他结果类型或切换到“全部”。</p></div>`:solutions.length?`<div class="aipm-solution-list">${renderedSolutions}</div>`:'<p class="aipm-empty">此课题尚未登记方案或达到记录阈值的实验。补充方案名称、使用方法和数据来源后，再记录 PASS、FAIL 或 INCONCLUSIVE 实验；不补造实验数据。</p>';
    workspace.innerHTML=`<div class="aipm-detail" data-view="research-detail" data-work-package-id="${safe(workPackage.id)}"><div class="aipm-detail-toolbar"><button class="aipm-back" id="aipm-back">← 返回</button><nav class="aipm-project-views" aria-label="项目视图导航"><a href="#project/okr">OKR</a><a href="#project/wbs">WBS</a><a href="#project/milestones">里程碑甘特图</a></nav></div><div class="aipm-detail-scroll"><div class="aipm-detail-head"><div><a class="aipm-chip aipm-feature-link" href="#work-package/${encodeURIComponent(feature.id)}/${encodeURIComponent(workPackage.id)}">所属二级功能 · ${safe(workPackage.id)} · ${safe(workPackage.title)}</a><div class="aipm-chip">研究课题 · ${safe(topic.id)}</div><h1 id="aipm-active-heading" tabindex="-1">${safe(topic.title)}</h1><p>${safe(topic.question||topic.description||'记录解决二级功能开发过程中的关键技术问题。')}</p></div></div><div class="aipm-box"><h2>课题方案与实验</h2><p class="aipm-project-note">每个方案说明方法和数据来源，实验结果按状态统计，具体观察与结论保留在实验记录中。</p>${records}</div></div></div>`;
    document.getElementById('aipm-back').onclick=()=>navigateBack(workPackage?`work-package/${encodeURIComponent(feature.id)}/${encodeURIComponent(workPackage.id)}`:`feature/${encodeURIComponent(feature?.id||'')}`);
    const cards=[...workspace.querySelectorAll('[data-experiment-result]')];
    const count=workspace.querySelector('[data-experiment-count]');
    const empty=workspace.querySelector('[data-experiment-empty]');
    workspace.querySelectorAll('[data-experiment-filter]').forEach(button=>button.onclick=()=>{const value=button.dataset.experimentFilter;workspace.querySelectorAll('[data-experiment-filter]').forEach(item=>item.setAttribute('aria-pressed',String(item===button)));let visible=0;cards.forEach(card=>{const matches=value==='all'||card.dataset.experimentResult===value;card.classList.toggle('aipm-hidden',!matches);if(matches)visible++});if(count)count.textContent=`显示 ${visible} / ${experiments.length} 条`;if(empty)empty.hidden=visible>0});
  }
  function renderOkrTable(){
    const objectives=project.objectives||[];
    const objectiveOptions=objectives.map(item=>`<option value="${safe(item.id)}">${safe(item.id)} · ${safe(item.title)}</option>`).join('');
    const krOptions=objectives.flatMap(item=>(item.key_results||[]).map(result=>`<option value="${safe(result.id)}">${safe(result.id)}</option>`)).join('');
    const rows=objectives.flatMap(objective=>{
      const results=objective.key_results||[];
      return results.length?results.map(result=>`<tr data-objective="${safe(objective.id)}" data-kr="${safe(result.id)}"><td>${safe(objective.id)}</td><td class="aipm-long-cell"><b>${safe(objective.title)}</b></td><td>${safe(result.id)}</td><td>${safe(result.metric)}</td><td>${safe(result.target)}</td><td class="aipm-long-cell">${safe(result.measurement_method)}</td></tr>`):[`<tr data-objective="${safe(objective.id)}" data-kr=""><td>${safe(objective.id)}</td><td>${safe(objective.title)}</td><td colspan="4">尚未定义 Key Result</td></tr>`];
    }).join('');
    return `<div class="aipm-table-tools" data-table-controls="okr"><label>关键词<input type="search" data-filter="query" placeholder="搜索目标、指标、方法…" aria-label="搜索 OKR"></label><label>Objective<select data-filter="objective" aria-label="按 Objective 筛选"><option value="">全部目标</option>${objectiveOptions}</select></label><label>KR<select data-filter="kr" aria-label="按 KR 筛选"><option value="">全部关键结果</option>${krOptions}</select></label><button type="button" class="aipm-clear-filters" data-clear-filters>清除筛选</button><output class="aipm-table-count" aria-live="polite"></output></div><div class="aipm-table-wrap"><table class="aipm-table" id="okr-table"><thead><tr>${['Objective ID','目标 Objective','KR ID','关键结果指标','目标值','衡量方法'].map((label,index)=>`<th scope="col" aria-sort="none"><button type="button" class="aipm-sort-button" data-sort-column="${index}" aria-label="按${label}排序">${label}</button></th>`).join('')}</tr></thead><tbody>${rows||'<tr><td colspan="6" class="aipm-empty">尚未定义 OKR。</td></tr>'}<tr class="aipm-empty-row" data-no-matches hidden><td colspan="6">没有匹配的 OKR。请调整或清除筛选条件。</td></tr></tbody></table></div>`;
  }
  function renderWbsTable(){
    const features=project.features||[];
    const featureOptions=features.map(feature=>`<option value="${safe(feature.id)}">${safe(feature.id)} · ${safe(feature.title)}</option>`).join('');
    const statuses=[...new Set(features.flatMap(feature=>(feature.work_packages||[]).map(wp=>wp.status||'TODO')))];
    const rows=features.flatMap(feature=>(feature.work_packages||[]).map(wp=>{
      const acceptance=(wp.acceptance_criteria||[]).map(item=>`<li><b>${safe(item.method)}</b><br>${safe(item.metric)} · ${safe(item.target)} · ${safe(item.status||'NOT_RUN')}</li>`).join('');
      const topic=wp.research_topic||{};
      const hasAcceptance=(wp.acceptance_criteria||[]).length>0,hasTopic=!!topic.id;
      const completeness=[!hasAcceptance?'missing-acceptance':'',!hasTopic?'missing-topic':''].filter(Boolean).join(' ')||'complete';
      return `<tr data-feature="${safe(feature.id)}" data-wp-status="${safe(wp.status||'TODO')}" data-completeness="${completeness}"><td>${safe(feature.id)}</td><td><a class="aipm-feature-link" href="#feature/${encodeURIComponent(feature.id)}">${safe(feature.title)}</a></td><td><a class="aipm-feature-link" href="#work-package/${encodeURIComponent(feature.id)}/${encodeURIComponent(wp.id)}" aria-label="查看 ${safe(wp.id)} 二级功能详情">${safe(wp.id)}</a></td><td class="aipm-wbs-cell"><b>${safe(wp.title)}</b><br>${safe(wp.description)}</td><td class="aipm-long-cell"><ul>${(wp.inputs||[]).map(item=>`<li>${safe(item)}</li>`).join('')}</ul></td><td class="aipm-long-cell"><ul>${(wp.outputs||[]).map(item=>`<li>${safe(item)}</li>`).join('')}</ul></td><td class="aipm-long-cell"><ul>${(wp.scope||[]).map(item=>`<li>${safe(item)}</li>`).join('')}</ul></td><td class="aipm-long-cell"><ul>${acceptance}</ul></td><td>${safe(wp.estimate_points??1)}</td><td><span class="aipm-chip">${safe(wp.status||'TODO')}</span><br>${pct(wp.progress??0)}</td><td>${hasTopic?`<a class="research-topic-link" href="#work-package/${encodeURIComponent(feature.id)}/${encodeURIComponent(wp.id)}" aria-label="先查看 ${safe(wp.id)} 二级功能，再进入研究课题">${safe(topic.title)}</a>`:'<span class="aipm-empty">待定义</span>'}</td></tr>`;
    })).join('');
    return `<div class="aipm-table-tools" data-table-controls="wbs"><label>关键词<input type="search" data-filter="query" placeholder="搜索功能、输入、验收…" aria-label="搜索 WBS"></label><label>一级功能<select data-filter="feature" aria-label="按一级功能筛选"><option value="">全部一级功能</option>${featureOptions}</select></label><label>状态<select data-filter="status" aria-label="按二级功能状态筛选"><option value="">全部状态</option>${statuses.map(value=>`<option value="${safe(value)}">${safe(value)}</option>`).join('')}</select></label><label>信息完整度<select data-filter="completeness" aria-label="按验收和研究课题完整度筛选"><option value="">全部条目</option><option value="missing-acceptance">缺少验收标准</option><option value="missing-topic">缺少研究课题</option><option value="complete">信息齐全</option></select></label><button type="button" class="aipm-clear-filters" data-clear-filters>清除筛选</button><output class="aipm-table-count" aria-live="polite"></output></div><div class="aipm-table-wrap"><table class="aipm-table" id="wbs-table"><thead><tr>${['L1 ID','一级功能','L2 ID','二级功能 / 内容','输入','输出','范围','验收方法 / 指标 / 目标','估算权重','状态 / 进度','研究课题'].map((label,index)=>`<th scope="col" aria-sort="none"><button type="button" class="aipm-sort-button" data-sort-column="${index}" aria-label="按${label}排序">${label}</button></th>`).join('')}</tr></thead><tbody>${rows||'<tr><td colspan="11" class="aipm-empty">尚未定义 WBS。</td></tr>'}<tr class="aipm-empty-row" data-no-matches hidden><td colspan="11">没有匹配的 WBS。请调整或清除筛选条件。</td></tr></tbody></table></div>`;
  }
  function bindTableControls(panel,tableId){
    const table=panel.querySelector(`#${tableId}`),tools=panel.querySelector(`[data-table-controls="${tableId==='okr-table'?'okr':'wbs'}"]`);if(!table||!tools)return;
    const body=table.tBodies[0],allRows=[...body.rows].filter(row=>!row.dataset.noMatches),empty=body.querySelector('[data-no-matches]'),count=tools.querySelector('.aipm-table-count');
    const selected=key=>tools.querySelector(`[data-filter="${key}"]`)?.value||'';
    const update=()=>{const query=selected('query').trim().toLocaleLowerCase();let visible=0;allRows.forEach(row=>{const matchQuery=!query||row.textContent.toLocaleLowerCase().includes(query);const matchObjective=!selected('objective')||row.dataset.objective===selected('objective');const matchKr=!selected('kr')||row.dataset.kr===selected('kr');const matchFeature=!selected('feature')||row.dataset.feature===selected('feature');const matchStatus=!selected('status')||row.dataset.wpStatus===selected('status');const matchComplete=!selected('completeness')||row.dataset.completeness.split(' ').includes(selected('completeness'));const show=matchQuery&&matchObjective&&matchKr&&matchFeature&&matchStatus&&matchComplete;row.hidden=!show;if(show)visible++});if(empty)empty.hidden=visible>0||allRows.length===0;if(count)count.textContent=`显示 ${visible} / ${allRows.length} 条`;};
    tools.querySelectorAll('input,select').forEach(control=>control.addEventListener(control.tagName==='INPUT'?'input':'change',update));
    tools.querySelector('[data-clear-filters]')?.addEventListener('click',()=>{tools.querySelectorAll('input,select').forEach(control=>control.value='');update();tools.querySelector('input')?.focus()});
    let sortColumn=-1,sortDirection=1;table.querySelectorAll('[data-sort-column]').forEach(button=>button.addEventListener('click',()=>{const index=Number(button.dataset.sortColumn);sortDirection=sortColumn===index?-sortDirection:1;sortColumn=index;table.querySelectorAll('[data-sort-column]').forEach(item=>item.closest('th')?.setAttribute('aria-sort',item===button?(sortDirection===1?'ascending':'descending'):'none'));const indexed=allRows.map((row,order)=>({row,order,value:row.cells[index]?.textContent.trim().toLocaleLowerCase()||''}));indexed.sort((a,b)=>{if(!a.value&&!b.value)return a.order-b.order;if(!a.value)return 1;if(!b.value)return -1;return a.value.localeCompare(b.value,'zh-CN',{numeric:true})*sortDirection||a.order-b.order});indexed.forEach(item=>body.append(item.row));if(empty)body.append(empty);update()}));
    update();
  }
  function renderMilestoneGantt(){
    const milestones=project.milestones||[];
    const dates=milestones.map(item=>({item,time:Date.parse(`${item.date}T00:00:00`)})).filter(entry=>Number.isFinite(entry.time));
    if(!dates.length)return '<p class="aipm-empty">尚未定义带日期的里程碑。</p>';
    const first=new Date(Math.min(...dates.map(entry=>entry.time)));
    const last=new Date(Math.max(...dates.map(entry=>entry.time)));
    const months=[];const cursor=new Date(first.getFullYear(),first.getMonth(),1);const end=new Date(last.getFullYear(),last.getMonth(),1);
    while(cursor<=end){months.push(`${cursor.getFullYear()}-${String(cursor.getMonth()+1).padStart(2,'0')}`);cursor.setMonth(cursor.getMonth()+1)}
    const axis=`<div class="aipm-gantt-axis"><span>里程碑与验收条件</span><div class="aipm-gantt-months" style="--month-count:${months.length}">${months.map(month=>`<span>${safe(month)}</span>`).join('')}</div></div>`;
    const rows=dates.map(({item,time})=>{const date=new Date(time);const month=`${date.getFullYear()}-${String(date.getMonth()+1).padStart(2,'0')}`;const monthIndex=months.indexOf(month);const dayFraction=(date.getDate()-1)/new Date(date.getFullYear(),date.getMonth()+1,0).getDate();const offset=Math.max(0,Math.min(100,(monthIndex+dayFraction)/months.length*100));return `<div class="aipm-gantt-row"><div class="aipm-gantt-label"><b>${safe(item.id)} · ${safe(item.title)}</b><p>${safe(item.date)} · ${safe(item.status||'TODO')}</p><p class="aipm-milestone-acceptance">${safe(item.acceptance)}</p></div><div class="aipm-gantt-track" style="--month-count:${months.length}"><span class="aipm-gantt-marker" tabindex="0" role="img" aria-label="${safe(item.date)} 里程碑：${safe(item.title)}，状态 ${safe(item.status||'TODO')}" style="left:${offset}%" title="${safe(item.date)} · ${safe(item.title)}"></span></div></div>`}).join('');
    return `<div class="aipm-gantt" id="milestone-gantt">${axis}${rows}</div>`;
  }
  function renderTaskSchedule(view,month,months){
    const weeks=project.weeks||[];
    const body=view==='monthly'?(()=>{
      if(!month)return '<p class="aipm-empty">没有排期数据。</p>';
      const year=Number(month.slice(0,4)),mon=Number(month.slice(5,7)),days=new Date(year,mon,0).getDate(),start=`${month}-01`,end=`${month}-${String(days).padStart(2,'0')}`;
      const rows=weeks.filter(week=>week.end>=start&&week.start<=end).map(week=>{
        const left=Math.max(new Date(week.start+'T00:00:00').getTime(),new Date(start+'T00:00:00').getTime());
        const right=Math.min(new Date(week.end+'T00:00:00').getTime(),new Date(end+'T00:00:00').getTime());
        const first=new Date(year,mon-1,1).getTime(),offset=Math.max(0,(left-first)/86400000),span=Math.max(1,(right-left)/86400000+1);
        return `<div class="aipm-month-week"><div><b>${safe(week.id)}</b><br>${safe(week.objective)}</div><div class="aipm-week-bar" tabindex="0" role="img" aria-label="${safe(week.id)}，${safe(week.objective)}，${safe(week.start)} 至 ${safe(week.end)}；交付物：${safe((week.deliverables||[]).join('、'))}" style="margin-left:${offset/days*100}%;width:${Math.max(4,span/days*100)}%" title="${safe(week.start)} — ${safe(week.end)}">${safe(week.start)} — ${safe(week.end)}</div><div>${(week.deliverables||[]).map(safe).join(' · ')}</div></div>`;
      }).join('');
      return `<div class="aipm-month-grid"><div class="aipm-month-title">${safe(month)} · ${days} 天</div>${rows||'<p class="aipm-empty">本月没有计划周。</p>'}</div>`;
    })():weeks.length?`<div class="aipm-week-list">${weeks.map(week=>`<article class="aipm-week-row"><div><span class="aipm-chip">${safe(week.id)}</span><p>${safe(week.start)} — ${safe(week.end)}</p></div><div><h3>${safe(week.objective)}</h3><ul>${(week.deliverables||[]).map(item=>`<li>${safe(item)}</li>`).join('')}</ul>${week.work_package_ids?.length?`<p>关联 WBS：${week.work_package_ids.map(safe).join(' · ')}</p>`:''}</div></article>`).join('')}</div>`:'<p class="aipm-empty">尚未安排周计划。</p>';
    return `<section class="aipm-schedule" aria-label="周月任务计划"><div class="aipm-schedule-head"><h3>任务计划</h3><div class="aipm-schedule-switch"><button type="button" data-schedule-view="weekly" aria-pressed="${view==='weekly'}">按周</button><button type="button" data-schedule-view="monthly" aria-pressed="${view==='monthly'}">按月甘特图</button>${view==='monthly'?`<select id="aipm-plan-month" aria-label="选择月份">${months.map(value=>`<option value="${value}" ${value===month?'selected':''}>${value}</option>`).join('')}</select>`:''}</div></div>${body}</section>`;
  }
  function renderProjectPlan(projectView=currentProjectView,scheduleView=currentScheduleView,selectedMonth='',preservedScrollTop=null){
    const panel=document.getElementById('aipm-state-plan');if(!panel)return;
    currentProjectView=projectView;
    const weeks=project.weeks||[];
    const months=[...new Set(weeks.flatMap(week=>{const first=week.start.slice(0,7),last=week.end.slice(0,7),values=[];let cursor=new Date(`${first}-01T00:00:00`),end=new Date(`${last}-01T00:00:00`);while(cursor<=end){values.push(`${cursor.getFullYear()}-${String(cursor.getMonth()+1).padStart(2,'0')}`);cursor.setMonth(cursor.getMonth()+1)}return values}))].sort();
    const currentMonth=`${new Date().getFullYear()}-${String(new Date().getMonth()+1).padStart(2,'0')}`;
    const month=months.includes(selectedMonth)?selectedMonth:(months.includes(currentMonth)?currentMonth:months[0]||'');
    const title=projectView==='okr'?'OKR 目标与关键结果':projectView==='wbs'?'WBS 功能分解与任务计划':'里程碑甘特图';
    const viewBody=projectView==='okr'?renderOkrTable():projectView==='wbs'?renderWbsTable():renderMilestoneGantt();
    const body=projectView==='wbs'?`${viewBody}${renderTaskSchedule(scheduleView,month,months)}`:viewBody;
    panel.innerHTML=`<div class="aipm-project-page-top"><button type="button" id="aipm-project-home" class="aipm-project-home">← 返回</button><nav class="aipm-project-views" aria-label="项目视图"><a href="#project/okr" data-project-page-view="okr">OKR</a><a href="#project/wbs" data-project-page-view="wbs">WBS</a><a href="#project/milestones" data-project-page-view="milestones">里程碑甘特图</a></nav></div><div class="aipm-plan-content"><div class="aipm-plan-head"><div><div class="section-kicker">PROJECT CONTROL</div><h1 id="aipm-active-heading" tabindex="-1">${title}</h1></div></div>${body}</div>`;
    const content=panel.querySelector('.aipm-plan-content');if(preservedScrollTop!==null&&content)content.scrollTop=preservedScrollTop;
    if(projectView==='okr')bindTableControls(panel,'okr-table');if(projectView==='wbs')bindTableControls(panel,'wbs-table');
    panel.querySelectorAll('[data-project-page-view]').forEach(link=>{if(link.dataset.projectPageView===projectView)link.setAttribute('aria-current','page');else link.removeAttribute('aria-current')});panel.querySelector('#aipm-project-home').onclick=()=>navigateBack('');
    panel.querySelectorAll('[data-schedule-view]').forEach(button=>button.onclick=()=>{const scrollTop=panel.querySelector('.aipm-plan-content')?.scrollTop||0;currentScheduleView=button.dataset.scheduleView;renderProjectPlan(currentProjectView,currentScheduleView,month,scrollTop);panel.querySelector(`[data-schedule-view="${currentScheduleView}"]`)?.focus({preventScroll:true})});
    panel.querySelector('#aipm-plan-month')?.addEventListener('change',event=>{const scrollTop=panel.querySelector('.aipm-plan-content')?.scrollTop||0;const selected=event.target.value;renderProjectPlan(currentProjectView,currentScheduleView,selected,scrollTop);panel.querySelector('#aipm-plan-month')?.focus({preventScroll:true})});
  }
  function setRoute(){
    const previousHash=currentRouteHash;
    const routeHash=location.hash;
    if(routeHash!==previousHash){
      const previousScroller=routeScroller(previousHash);routeScrollPositions.set(previousHash,previousScroller?.scrollTop??window.scrollY);
      if(fallbackRoutePending)fallbackRoutePending=false;
      else if(historyTraversalPending){
        if(routeHistoryIndex>0&&routeHistory[routeHistoryIndex-1]===routeHash)routeHistoryIndex--;
        else if(routeHistoryIndex<routeHistory.length-1&&routeHistory[routeHistoryIndex+1]===routeHash)routeHistoryIndex++;
        else{const existing=routeHistory.lastIndexOf(routeHash);if(existing>=0)routeHistoryIndex=existing;else{routeHistory=routeHistory.slice(0,routeHistoryIndex+1);routeHistory.push(routeHash);routeHistoryIndex++}}
        historyTraversalPending=false;
      }else{routeHistory=routeHistory.slice(0,routeHistoryIndex+1);routeHistory.push(routeHash);routeHistoryIndex++}
    }
    currentRouteHash=routeHash;
    const projectMatch=routeHash.match(/^#project\/(okr|wbs|milestones)$/);
    const workPackageMatch=routeHash.match(/^#work-package\/([^/]+)\/(.+)$/);
    const featureMatch=routeHash.match(/^#feature\/(.+)$/);
    const researchMatch=routeHash.match(/^#research\/(.+)$/);
    const projectView=projectMatch?.[1];
    const workPackageFeatureId=workPackageMatch?decodeURIComponent(workPackageMatch[1]):null;
    const workPackageId=workPackageMatch?decodeURIComponent(workPackageMatch[2]):null;
    const id=featureMatch?decodeURIComponent(featureMatch[1]):null;
    const topicId=researchMatch?decodeURIComponent(researchMatch[1]):null;
    const onProjectPage=!!projectView;
    const onWorkPackagePage=!!workPackageFeatureId&&!!workPackageId;
    const activeWorkPackage=onWorkPackagePage?project.features.find(feature=>feature.id===workPackageFeatureId)?.work_packages?.find(workPackage=>workPackage.id===workPackageId):null;
    document.title=activeWorkPackage?`${activeWorkPackage.title} · ${project.project?.name||'项目管理'}`:'项目管理控制台 · '+(project.project?.name||'项目管理');
    workspace.hidden=!id&&!topicId&&!onWorkPackagePage;
    const plan=document.getElementById('aipm-state-plan');
    if(plan)plan.hidden=!onProjectPage;
    document.querySelector('.page').hidden=!!(id||topicId||onWorkPackagePage||onProjectPage);
    if(onProjectPage)renderProjectPlan(projectView,currentScheduleView);
    else if(onWorkPackagePage)renderWorkPackage(workPackageFeatureId,workPackageId);
    else if(id)renderFeature(id);
    else if(topicId)renderResearch(topicId);
    const skip=document.querySelector('.aipm-skip-link');
    if(skip)skip.href=id||topicId||onWorkPackagePage||onProjectPage?'#aipm-active-heading':'#main-content';

    if(routeHash!==previousHash){
      let target=document.getElementById(id||topicId||onProjectPage?'aipm-active-heading':'main-content');
      const previousFeature=previousHash.match(/^#feature\/(.+)$/);
      const previousWorkPackage=previousHash.match(/^#work-package\/([^/]+)\/(.+)$/);
      const previousResearch=previousHash.match(/^#research\/(.+)$/);
      if(!id&&!topicId&&!onProjectPage&&previousFeature){
        const previousId=decodeURIComponent(previousFeature[1]);
        target=document.querySelector(`.feature[data-feature-id="${CSS.escape(previousId)}"] .feature-trigger`)||target;
      }else if(id&&previousWorkPackage){
        const previousWp=decodeURIComponent(previousWorkPackage[2]);
        target=workspace.querySelector(`[data-work-package="${CSS.escape(previousWp)}"]`)||target;
      }else if(id&&previousResearch){
        const previousTopic=decodeURIComponent(previousResearch[1]);
        target=workspace.querySelector(`[data-research-topic="${CSS.escape(previousTopic)}"]`)||target;
      }else if(onWorkPackagePage&&previousResearch){
        const previousTopic=decodeURIComponent(previousResearch[1]);
        target=workspace.querySelector(`[data-research-topic="${CSS.escape(previousTopic)}"]`)||target;
      }else if(onProjectPage&&previousFeature){
        const previousId=decodeURIComponent(previousFeature[1]);
        target=plan?.querySelector(`#wbs-table tbody tr[data-feature="${CSS.escape(previousId)}"] .aipm-feature-link`)||target;
      }
      const savedScrollTop=routeScrollPositions.get(routeHash);
      requestAnimationFrame(()=>{const scroller=routeScroller(routeHash);if(savedScrollTop!==undefined){if(scroller)scroller.scrollTop=savedScrollTop;else window.scrollTo(0,savedScrollTop)}target?.focus({preventScroll:true})});
    }
  }
  document.getElementById('featureFlow')?.addEventListener('click',event=>{const trigger=event.target.closest('.feature-trigger:not(.dependency-trigger)');if(!trigger)return;const card=trigger.closest('.feature');const feature=featureByTitle(card?.querySelector('h3')?.textContent?.trim(),card?.dataset.featureId);if(feature){event.preventDefault();event.stopImmediatePropagation();location.hash=`feature/${encodeURIComponent(feature.id)}`}},true);
  const viewNav=document.getElementById('aipm-project-view-nav');const homePage=document.querySelector('.page');const homeContent=homePage?.querySelector('.management-top');if(viewNav&&homePage&&homeContent){viewNav.classList.add('aipm-home-view-nav');homePage.insertBefore(viewNav,homeContent)}
  
  function updateTodaySummary(){const target=document.getElementById('todaySummary');if(!target)return;const date=document.getElementById('todayDate');if(date)date.textContent=new Intl.DateTimeFormat('zh-CN',{year:'numeric',month:'2-digit',day:'2-digit',weekday:'short'}).format(new Date());const rows=project.work_logs?.daily||[];target.innerHTML=rows.length?rows.map(row=>`<div>${safe(row.summary||row.title||'')} ${(row.evidence_links||[]).map(renderEvidenceLink).join(' ')}</div>`).join(''):'<span class="aipm-empty">暂无带证据链接的当日执行记录。</span>'}
  function applyFeatureFilter(){const selected=document.querySelector('.filter[aria-pressed="true"]')?.dataset.filter||'all';for(const feature of project.features){const node=document.querySelector(`#featureFlow [data-feature-id="${CSS.escape(feature.id)}"]`);if(!node)continue;const packages=feature.work_packages||[];const completed=packages.length>0&&packages.every(item=>item.status==='DONE');const active=packages.some(item=>['READY','IN_PROGRESS','IMPLEMENTED','VERIFYING','BLOCKED','FAILED','FIXING'].includes(item.status));node.dataset.status=completed?'done':active?'active':'todo';node.hidden=selected!=='all'&&node.dataset.status!==selected}}
  document.querySelectorAll('.filter[data-filter]').forEach(button=>button.addEventListener('click',()=>{document.querySelectorAll('.filter[data-filter]').forEach(item=>{const selected=item===button;item.classList.toggle('active',selected);item.setAttribute('aria-pressed',String(selected))});applyFeatureFilter()}));
  function updateOverview(){const flow=document.getElementById('featureFlow');for(const feature of project.features){let node=flow?.querySelector(`[data-feature-id="${CSS.escape(feature.id)}"]`);if(!node&&flow){node=document.createElement('article');node.className='feature status-build';node.dataset.status='build';node.dataset.featureId=feature.id;const button=document.createElement('button');button.className='feature-trigger';button.type='button';const heading=document.createElement('h3');const description=document.createElement('p');const status=document.createElement('span');status.className='feature-state';status.innerHTML='状态 <b></b>';const progress=document.createElement('span');progress.className='feature-progress';progress.innerHTML='<span class="progress-track"><span class="progress-fill"></span></span><span class="feature-progress-label"><span>一级功能进度</span><span class="feature-percent">0%</span></span>';button.append(heading,description,status,progress);node.append(button);flow.append(node)}if(!node)continue;const heading=node.querySelector('h3');if(heading)heading.textContent=feature.title;const description=node.querySelector('.feature-trigger p');if(description)description.textContent=feature.description||'';const value=Math.round(feature.progress||0);const fill=node.querySelector('.feature-progress .progress-fill');if(fill)fill.style.width=pct(value);const label=node.querySelector('.feature-percent');if(label)label.textContent=pct(value);const stateNode=node.querySelector('.feature-state b');if(stateNode)stateNode.textContent=`${(feature.work_packages||[]).filter(w=>w.status==='DONE').length}/${(feature.work_packages||[]).length} 二级功能验收通过`}const total=project.features.reduce((sum,f)=>sum+(f.work_packages||[]).length,0);const done=project.features.flatMap(f=>f.work_packages||[]).filter(w=>w.status==='DONE').length;const overall=Math.round(project.project.progress||0);const percent=document.getElementById('overallPercent');if(percent)percent.textContent=pct(overall);const fill=document.getElementById('overallFill');if(fill)fill.style.width=pct(overall);const progress=document.getElementById('overallProgress');if(progress)progress.setAttribute('aria-valuenow',String(overall));const counts=document.getElementById('overallCounts');if(counts)counts.textContent=`${done} / ${total} 个二级功能通过验收`;const method=document.getElementById('overallMethod');if(method)method.textContent='由项目 JSON 中的验收证据自动汇总';const lastUpdated=document.getElementById('lastUpdated');const timestamps=allEvents().map(event=>Date.parse(event.timestamp||'')).filter(Number.isFinite);if(lastUpdated&&timestamps.length){const latest=new Date(Math.max(...timestamps));const dateParts=Object.fromEntries(new Intl.DateTimeFormat('en',{timeZone:project.project?.timezone||'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(latest).map(part=>[part.type,part.value]));const stamp=`${dateParts.year}-${dateParts.month}-${dateParts.day}`;lastUpdated.dateTime=stamp;lastUpdated.textContent=stamp}updateTodaySummary()}
  document.addEventListener('DOMContentLoaded',()=>{document.querySelector('.roadmap')?.setAttribute('hidden','');updateOverview();applyFeatureFilter();renderProjectPlan();setRoute()},{once:true});
  window.addEventListener('popstate',()=>{historyTraversalPending=true});window.addEventListener('hashchange',setRoute);setRoute();
})();
</script>
'''


def _script_safe_json(state: Mapping[str, Any]) -> str:
    return json.dumps(state, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def _sync_last_updated(template: str, state: Mapping[str, Any]) -> str:
    timezone_name = str(state.get("project", {}).get("timezone") or "UTC")
    try:
        project_timezone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        project_timezone = timezone.utc
    timestamps = []
    for event in state.get("execution_log", []):
        try:
            timestamp = datetime.fromisoformat(str(event.get("timestamp", "")).replace("Z", "+00:00"))
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=project_timezone)
            timestamps.append(timestamp.astimezone(project_timezone))
        except (TypeError, ValueError, OverflowError):
            continue
    if not timestamps:
        return template
    stamp = max(timestamps).date().isoformat()
    pattern = re.compile(r'(<time id="lastUpdated" datetime=")[^"]*("[^>]*>)[^<]*(</time>)')
    return pattern.sub(lambda match: f"{match.group(1)}{stamp}{match.group(2)}{stamp}{match.group(3)}", template, count=1)


def render_dashboard(template: str, state: Mapping[str, Any], evidence_prefix: str = "") -> str:
    errors = validate_project_state(state)
    if errors:
        raise ValueError("invalid project state: " + "; ".join(errors))
    template = template.replace("__PROJECT_NAME__", html_lib.escape(str(state.get("project", {}).get("name", "项目管理控制台")), quote=True))
    template = _sync_last_updated(template, state)
    app = APP_HTML.replace("__STATE_JSON__", _script_safe_json(state)).replace(
        "__EVIDENCE_PREFIX__", json.dumps(evidence_prefix, ensure_ascii=False)
    )
    replacement = f"{APP_START}\n{app}\n{APP_END}"
    if template.count(APP_START) == 1 and template.count(APP_END) == 1:
        start = template.index(APP_START)
        end = template.index(APP_END) + len(APP_END)
        if end < start:
            raise ValueError("HTML dashboard app markers are out of order")
        return template[:start] + replacement + template[end:]
    if template.count(SLOT) == 1:
        return template.replace(SLOT, replacement)
    # Upgrade a dashboard generated by the earlier prototype of this renderer.
    legacy_start = template.find('<style id="ai-pm-styles">')
    legacy_end_marker = "window.addEventListener('hashchange',setRoute);setRoute();\n})();\n</script>"
    legacy_end = template.find(legacy_end_marker, legacy_start)
    if legacy_start >= 0 and legacy_end >= 0:
        legacy_end += len(legacy_end_marker)
        return template[:legacy_start] + replacement + template[legacy_end:]
    raise ValueError("HTML template must contain one AI_PM_STATE_SLOT or a valid managed-app marker pair")


def evidence_prefix_for_output(project_root: str | Path, output_path: str | Path) -> str:
    """Return the relative prefix from an output directory back to the project root."""
    root = Path(project_root).resolve()
    output_parent = Path(output_path).resolve().parent
    try:
        depth = len(output_parent.relative_to(root).parts)
    except ValueError:
        return ""
    return "../" * depth


def render_to_file(template_path: str | Path, state_path: str | Path, output_path: str | Path) -> Path:
    template_file, state_file, output_file = Path(template_path), Path(state_path), Path(output_path)
    state = json.loads(state_file.read_text(encoding="utf-8"))
    template = template_file.read_text(encoding="utf-8")
    project_root = state_file.parent.parent if state_file.parent.name == "project-management" else state_file.parent
    evidence_prefix = evidence_prefix_for_output(project_root, output_file)
    output = render_dashboard(template, state, evidence_prefix)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(output, encoding="utf-8")
    return output_file
