# Report Scheduling Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add US holiday-aware premarket scheduling, durable latest-pointer outputs, and clearer external-scheduler guidance without changing report content.

**Architecture:** Extend the existing report lifecycle helper so successful live promotion can also refresh portable `latest_*` copies, and add a small deterministic US market-calendar helper for premarket schedule checks. Keep report generators separate from orchestration, and keep production scheduling documented as cron/systemd driven one-shot runs.

**Tech Stack:** Python 3.11+, `datetime`, `pathlib`, `shutil`, `zoneinfo`, `unittest`

---

### Task 1: Trading Calendar Helper

**Files:**
- Create: `reports/trading_calendar.py`
- Modify: `reports/schedule.py`
- Test: `tests/test_report_schedule.py`

- [ ] Add deterministic US full-holiday logic plus `is_us_trading_day(...)`.
- [ ] Update premarket schedule helpers to skip US market holidays.

### Task 2: Latest Pointer Promotion

**Files:**
- Modify: `reports/report_lifecycle.py`
- Modify: `reports/morning_edge.py`
- Modify: `reports/sunday_report.py`
- Test: `tests/test_report_lifecycle.py`
- Test: `tests/test_report_runners.py`

- [ ] Extend safe promotion to refresh `latest_*` pointer files only after successful live promotion.
- [ ] Preserve live outputs and latest pointers on failures.

### Task 3: Thin Runner Clarification

**Files:**
- Modify: `reports/run_premarket.py`
- Modify: `reports/run_sunday.py`
- Test: `tests/test_report_runners.py`

- [ ] Keep one-shot runners thin.
- [ ] Add holiday skip behavior to premarket wrapper.
- [ ] Preserve optional `--schedule` mode without expanding daemon complexity.

### Task 4: Docs And Validation

**Files:**
- Modify: `README.md`
- Modify: `docs/DEV_LOG.md`
- Modify: `tests/test_report_schedule.py`
- Modify: `tests/test_report_runners.py`

- [ ] Document cron/systemd as the preferred production scheduling path.
- [ ] Document holiday-aware premarket behavior and `latest_*` files as preferred stable references.
