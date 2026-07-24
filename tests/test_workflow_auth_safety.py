from pathlib import Path


ROOT = Path(__file__).parents[1]
SCHEDULE = ROOT / ".github" / "workflows" / "schedule.yml"
MAINTENANCE_WORKFLOW = (
    ROOT
    / ".github"
    / "workflows"
    / "crew-maintenance-free-v3-20260616.yml"
)
MAINTENANCE_AGENT = ROOT / "crew_agents" / "maintenance_agent.py"


def test_schedule_keeps_three_times_and_uses_only_session_secret() -> None:
    workflow = SCHEDULE.read_text(encoding="utf-8")

    for cron in (
        "cron: '30 9 * * *'",
        "cron: '30 10 * * *'",
        "cron: '30 11 * * *'",
    ):
        assert cron in workflow
    assert (
        "CREW_STORAGE_STATE_B64: "
        "${{ secrets.CREW_STORAGE_STATE_B64 }}" in workflow
    )
    assert "pip install -r requirements.txt" in workflow
    assert "playwright install --with-deps chromium" in workflow
    for forbidden in (
        "CREW_USERNAME",
        "CREW_PASSWORD",
        "tesseract-ocr",
        "ddddocr",
        "upload-artifact",
        "debug_output",
    ):
        assert forbidden not in workflow


def test_schedule_maps_auth_status_and_gates_clean_and_commit() -> None:
    workflow = SCHEDULE.read_text(encoding="utf-8")

    expected_mappings = (
        '0) auth_status="AUTHENTICATED"',
        '3) auth_status="LOGIN_REQUIRED"',
        '4) auth_status="ADDITIONAL_VERIFICATION_REQUIRED"',
        '5) auth_status="PAGE_CHANGED_OR_UNKNOWN"',
        '6) auth_status="NETWORK_OR_SITE_ERROR"',
        '*) auth_status="SCRAPER_ERROR"',
    )
    for mapping in expected_mappings:
        assert mapping in workflow
    assert 'echo "auth_status=$auth_status" >> "$GITHUB_OUTPUT"' in workflow
    gate = (
        "steps.scraper.outcome == 'success' && "
        "steps.scraper.outputs.auth_status == 'AUTHENTICATED'"
    )
    assert workflow.count(gate) == 2


def test_maintenance_workflow_has_no_scraper_or_raw_diagnostics_path() -> None:
    workflow = MAINTENANCE_WORKFLOW.read_text(encoding="utf-8")

    assert "workflow_dispatch:" in workflow
    assert 'workflows: ["Update Crew Calendar"]' in workflow
    assert "agent_output/maintenance/" in workflow
    for forbidden in (
        "run_scraper",
        "crew_calendar_main.py",
        "clean_ics_people.py",
        "CREW_USERNAME",
        "CREW_PASSWORD",
        "CREW_STORAGE_STATE_B64",
        "playwright",
        "tesseract",
        "ddddocr",
        "agent_run",
        "debug_output",
    ):
        assert forbidden not in workflow


def test_maintenance_agent_is_static_and_checks_session_auth_integration() -> None:
    source = MAINTENANCE_AGENT.read_text(encoding="utf-8")

    for required in (
        '"crew_auth_session.py"',
        "CREW_STORAGE_STATE_B64",
        "crew_auth_session",
        "decode_auth_bundle",
        "upstream_conclusion",
    ):
        assert required in source
    for forbidden in (
        "CREW_USERNAME",
        "CREW_PASSWORD",
        "debug_output",
        "scraper.log",
        "cleaner.log",
        "agent_run",
        "check_logs",
        "read_tail",
    ):
        assert forbidden not in source


def test_gitignore_excludes_debug_output_without_removing_auth_rules() -> None:
    content = (ROOT / ".gitignore").read_text(encoding="utf-8")

    for pattern in (
        "/debug_output/",
        "playwright/.auth/",
        "playwright/.auth-diagnostics/",
        "*.storage-state.json",
        "crew-auth-session*.json",
        ".env",
    ):
        assert pattern in content
