# Report Scheduling And Archive Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add safe scheduled generation, archive rotation, and stable latest outputs for the Sunday Report and Daily Premarket Report without changing report content generation.

**Architecture:** Keep content assembly inside the existing report modules, but move file lifecycle concerns into a shared `reports` helper that renders to temp files, archives the previous live artifact only after successful generation, and atomically promotes the new artifact into the stable live path. Add thin run wrappers for manual orchestration plus small scheduling/date helpers that are deterministic and easy to inspect.

**Tech Stack:** Python 3.11+, `pathlib`, `tempfile`, `shutil`, `zoneinfo`, `unittest`, existing `jinja2`/`weasyprint` report stack

---

### Task 1: Shared Rotation Helper

**Files:**
- Create: `reports/report_lifecycle.py`
- Test: `tests/test_report_lifecycle.py`

- [ ] Define Vancouver timezone helpers, archive naming, collision suffixing, temp artifact paths, and safe archive/promote helpers.
- [ ] Cover archive-date resolution, same-day rerun suffixing, promotion behavior, and failure preservation with focused unit tests.

### Task 2: Refactor Report Modules

**Files:**
- Modify: `reports/morning_edge.py`
- Modify: `reports/sunday_report.py`
- Test: `tests/test_morning_edge.py`

- [ ] Split rendering from promotion so each module can render HTML/PDF into caller-provided paths without directly mutating the live output location.
- [ ] Keep `python3 -m reports.morning_edge` and `python3 -m reports.sunday_report` working by routing them through thin orchestration that uses the shared helper.
- [ ] Move daily stable outputs to `reports/output/premarket.html` and `reports/output/premarket.pdf`, while leaving content-generation behavior intact.

### Task 3: Thin Wrappers And Scheduling

**Files:**
- Create: `reports/schedule.py`
- Create: `reports/run_premarket.py`
- Create: `reports/run_sunday.py`
- Test: `tests/test_report_schedule.py`

- [ ] Add pure helpers for “is this a scheduled Sunday run time?” and “is this a scheduled premarket trading-day run time?” using `America/Vancouver`.
- [ ] Use Monday-Friday as the explicit v1 trading-day fallback and keep the runtime wrappers thin and inspectable.

### Task 4: Downstream Compatibility

**Files:**
- Modify: `reports/build_all.py`
- Modify: `tests/test_build_all.py`
- Modify: `docs/DEV_LOG.md`

- [ ] Update static-site build assumptions to consume the new stable daily output/archive locations cleanly.
- [ ] Note the scheduling/archive change in the dev log.

### Task 5: Validation

**Files:**
- Modify: `tests/test_report_lifecycle.py`
- Modify: `tests/test_report_schedule.py`
- Modify: `tests/test_build_all.py`

- [ ] Run focused test coverage for report lifecycle, report scheduling, morning edge compatibility, and site build behavior.
- [ ] Verify temp files do not linger after success and failed generation preserves prior live outputs.
