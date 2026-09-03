from pathlib import Path


ROOT = Path(__file__).parents[1]
SCHEDULE = ROOT / ".github" / "workflows" / "schedule.yml"
CODE_TESTS = ROOT / ".github" / "workflows" / "auth-session-check.yml"
RUNNER_SETUP = ROOT / "scripts" / "setup_self_hosted_runner.ps1"
MAINTENANCE_WORKFLOW = (
    ROOT
    / ".github"
    / "workflows"
    / "crew-maintenance-free-v3-20260616.yml"
)
MAINTENANCE_AGENT = ROOT / "crew_agents" / "maintenance_agent.py"


def test_schedule_keeps_three_times_and_uses_expected_secrets() -> None:
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
    for secret_name in (
        "CREW_PHONE",
        "IMAP_EMAIL",
        "IMAP_AUTH_CODE",
        "GMAIL_SMTP_USER",
        "GMAIL_SMTP_APP_PASSWORD",
        "CREW_NOTIFY_EMAIL",
    ):
        assert f"${{{{ secrets.{secret_name} }}}}" in workflow
    assert "GMAIL_NOTIFY_TO" not in workflow
    assert "imap.163.com" not in workflow
    assert "runs-on: [self-hosted, Windows, X64, crew-calendar]" in workflow
    assert "shell: pwsh" in workflow
    assert "shell: bash" not in workflow
    assert "cancel-in-progress: false" in workflow
    assert (
        "CREW_PERSISTENT_PROFILE_DIR: "
        r"C:\crew-calendar-data\browser-profile" in workflow
    )
    assert (
        "CREW_AUTH_CONTROL_PATH: "
        r"C:\crew-calendar-data\auth-control.json" in workflow
    )
    assert "CREW_BROWSER_CHANNEL: msedge" in workflow
    assert "playwright install" not in workflow
    assert "apt-get" not in workflow
    assert "actions/setup-python" not in workflow
    for forbidden in ("tesseract-ocr", "ddddocr"):
        assert forbidden not in workflow
    assert "actions/upload-artifact@v4" in workflow
    assert r"${{ runner.temp }}\crew-auth-diagnostic.json" in workflow
    assert "if-no-files-found: ignore" in workflow
    for forbidden_artifact in ("page.html", "playwright/.auth/"):
        assert forbidden_artifact not in workflow
    for removed_password_secret in (
        "CREW_USERNAME",
        "CREW_PASSWORD",
        "secrets.USERNAME",
        "secrets.PASSWORD",
    ):
        assert removed_password_secret not in workflow
    assert "crew-auth-password-captcha.png" not in workflow
    assert "debug_output/route_parse_failed_*.txt" in workflow
    assert "debug_output/route_parse_failed_*.png" in workflow
    assert workflow.count("debug_output/") == 2
    assert "path: debug_output" not in workflow
    assert "debug_output/**" not in workflow


def test_schedule_maps_auth_status_and_gates_clean_and_commit() -> None:
    workflow = SCHEDULE.read_text(encoding="utf-8")

    expected_mappings = (
        '0 { "AUTHENTICATED" }',
        '3 { "LOGIN_REQUIRED" }',
        '4 { "ADDITIONAL_VERIFICATION_REQUIRED" }',
        '5 { "PAGE_CHANGED_OR_UNKNOWN" }',
        '6 { "NETWORK_OR_SITE_ERROR" }',
        '7 { "AUTH_DEFERRED_OTP_COOLDOWN" }',
        '9 { "LOGIN_REQUIRED_DYNAMIC_OTP" }',
        'default { "SCRAPER_ERROR" }',
    )
    for mapping in expected_mappings:
        assert mapping in workflow
    assert '"auth_status=$authStatus"' in workflow
    assert "$env:GITHUB_OUTPUT" in workflow
    gate = (
        "steps.scraper.outcome == 'success' && "
        "steps.scraper.outputs.auth_status == 'AUTHENTICATED'"
    )
    assert workflow.count(gate) == 2
    assert 'if ($authStatus -eq "AUTH_DEFERRED_OTP_COOLDOWN")' in workflow
    assert "CALENDAR_UPDATE=SKIPPED_PRESERVE_LAST_GOOD" in workflow


def test_auth_notification_is_non_blocking_and_persists_only_safe_state() -> None:
    workflow = SCHEDULE.read_text(encoding="utf-8")

    assert "id: auth_notification" in workflow
    assert "python crew_auth_notification.py" in workflow
    assert workflow.count("continue-on-error: true") == 2
    assert (
        "always() && steps.auth_notification.outcome == 'success'"
        in workflow
    )
    assert (
        'git add -- $stateFile'
        in workflow
    )
    assert "git add -A" not in workflow
    assert workflow.index("Commit and push ICS files") < workflow.index(
        "Send authentication status notification"
    )


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
        "/browser-profile/",
        "/auth-backup/",
        "/crew-calendar-data/",
        "*.storage-state.json",
        "crew-auth-session*.json",
        ".env",
    ):
        assert pattern in content


def test_github_hosted_workflow_only_runs_code_tests() -> None:
    workflow = CODE_TESTS.read_text(encoding="utf-8")

    assert "runs-on: ubuntu-latest" in workflow
    assert "python -m pytest" in workflow
    assert "crew_calendar_main.py" not in workflow
    for forbidden in (
        "CREW_PHONE",
        "IMAP_EMAIL",
        "IMAP_AUTH_CODE",
        "CREW_STORAGE_STATE_B64",
        "playwright install",
        "workflow_dispatch inputs",
    ):
        assert forbidden not in workflow


def test_self_hosted_setup_script_registers_dedicated_windows_runner() -> None:
    script = RUNNER_SETUP.read_text(encoding="utf-8")

    for required in (
        "actions-runner-win-x64-",
        '--labels "crew-calendar"',
        "browser-profile",
        "auth-backup",
        "svc.cmd install",
        "svc.cmd start",
        "channel='msedge'",
    ):
        assert required in script
    assert "Write-Host $RegistrationToken" not in script
    assert "CREW_PHONE" not in script
    assert "IMAP_AUTH_CODE" not in script
