from pathlib import Path


ROOT = Path(__file__).parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
SCHEDULE = ROOT / ".github" / "workflows" / "schedule.yml"
FLIGHT_PREP = ROOT / ".github" / "workflows" / "flight-prep-free-v5-20260616.yml"
CODE_TESTS = ROOT / ".github" / "workflows" / "auth-session-check.yml"
RUNNER_SETUP = ROOT / "scripts" / "setup_self_hosted_runner.ps1"
MAINTENANCE_AGENT = ROOT / "crew_agents" / "maintenance_agent.py"


def test_actions_has_only_four_named_workflows() -> None:
    expected = {
        "auth-session-check.yml": "代码测试",
        "flight-prep-free-v5-20260616.yml": "生成航前准备",
        "schedule.yml": "更新机组日历",
        "sync-airport-manual.yml": "同步机场手册",
    }
    assert {path.name for path in WORKFLOWS.glob("*.yml")} == set(expected)
    for filename, display_name in expected.items():
        workflow = (WORKFLOWS / filename).read_text(encoding="utf-8")
        assert workflow.splitlines()[0] == f"name: {display_name}"
        assert "workflow_run:" not in workflow


def test_schedule_uses_three_calendar_updates_and_three_prep_checks() -> None:
    workflow = SCHEDULE.read_text(encoding="utf-8")

    for cron in (
        "cron: '7 1 * * *'",
        "cron: '17 7 * * *'",
        "cron: '27 13 * * *'",
        "cron: '37 22 * * *'",
        "cron: '37 10 * * *'",
        "cron: '43 1 * * *'",
    ):
        assert cron in workflow
    for retired in (
        "cron: '0 1 * * *'",
        "cron: '0 7 * * *'",
        "cron: '0 13 * * *'",
        "cron: '30 1 * * *'",
        "cron: '0 14 * * *'",
        "cron: '30 9 * * *'",
        "cron: '30 10 * * *'",
        "cron: '30 11 * * *'",
    ):
        assert retired not in workflow
    assert '"7 1 * * *"' in workflow
    assert '"17 7 * * *"' in workflow
    assert '"27 13 * * *"' in workflow
    assert '$scheduledCron -eq "43 1 * * *"' in workflow
    assert '$scheduledCron -in @("37 22 * * *", "37 10 * * *")' in workflow
    assert '$runScraper = "false"' in workflow
    assert "if: ${{ steps.schedule_mode.outputs.run_scraper == 'false' }}" in workflow
    assert workflow.count("--existing-only") == 2
    assert 'id: calendar_d1_prep_check' in workflow
    assert 'id: calendar_d2_prep_check' in workflow
    assert "actions: write" in workflow
    assert (
        "CREW_STORAGE_STATE_B64: "
        "${{ secrets.CREW_STORAGE_STATE_B64 }}" in workflow
    )
    for secret_name in (
        "CREW_USERNAME",
        "CREW_PASSWORD",
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
    assert r"${{ runner.temp }}\crew-auth-diagnostic.json" in workflow
    for forbidden_artifact in (
        "actions/upload-artifact",
        "if-no-files-found",
        "page.html",
        "playwright/.auth/",
    ):
        assert forbidden_artifact not in workflow
    for removed_password_secret in (
        "secrets.USERNAME",
        "secrets.PASSWORD",
    ):
        assert removed_password_secret not in workflow
    assert "crew-auth-password-captcha.png" not in workflow
    assert "debug_output/" not in workflow
    assert "python crew_calendar_email_entry.py" in workflow
    assert "python crew_calendar_main.py" not in workflow


def test_flight_prep_is_dispatch_only_and_run_name_uses_target_date() -> None:
    workflow = FLIGHT_PREP.read_text(encoding="utf-8")

    assert "run-name: ${{ inputs.target_date }} 航前准备" in workflow
    assert "workflow_dispatch:" in workflow
    assert "required: true" in workflow
    assert "schedule:" not in workflow
    for old_cron in ("17 10 * * *", "37 16 * * *", "7 1 * * *"):
        assert old_cron not in workflow


def test_schedule_dispatches_flight_prep_with_explicit_date() -> None:
    workflow = SCHEDULE.read_text(encoding="utf-8")

    assert "scripts/check_flight_prep_schedule.py" in workflow
    assert '--days-ahead "${{ steps.schedule_mode.outputs.days_ahead }}"' in workflow
    assert '--scheduled-cron "${{ github.event.schedule }}"' in workflow
    assert '--actual-start-utc "${{ steps.schedule_mode.outputs.actual_start_utc }}"' in workflow
    assert "--dispatch" in workflow
    assert "GITHUB_TOKEN: ${{ github.token }}" in workflow
    assert "GITHUB_REPOSITORY: ${{ github.repository }}" in workflow
    assert "Publish invalidated flight preparation state" in workflow
    assert "steps.flight_prep_check.outputs.state_changed == 'true'" in workflow
    assert "steps.calendar_d1_prep_check.outputs.state_changed == 'true'" in workflow
    assert "steps.calendar_d2_prep_check.outputs.state_changed == 'true'" in workflow
    assert "FLIGHT_PREP_STATE_API" in workflow


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


def test_schedule_has_no_remote_actions_or_diagnostic_uploads() -> None:
    workflow = SCHEDULE.read_text(encoding="utf-8")

    assert "uses:" not in workflow
    assert "actions/checkout" not in workflow
    assert "actions/upload-artifact" not in workflow
    assert "Upload safe authentication diagnostic" not in workflow
    assert "Upload safe route parsing diagnostic" not in workflow


def test_auth_notification_is_non_blocking_and_persists_only_safe_state() -> None:
    workflow = SCHEDULE.read_text(encoding="utf-8")

    assert "id: auth_notification" in workflow
    assert "python crew_auth_notification.py" in workflow
    assert workflow.count("continue-on-error: true") == 3
    assert "steps.schedule_mode.outputs.run_scraper == 'true'" in workflow
    assert "steps.auth_notification.outcome == 'success'" in workflow
    state_step = workflow.split(
        "- name: Publish authentication notification state through GitHub API", 1
    )[1]
    assert "github_api_publish.py" in state_step
    assert "state/auth_notification_state.json" in state_step
    assert "--message \"Update authentication notification state\"" in state_step
    assert "--status-prefix AUTH_STATE_API" in state_step
    assert workflow.index("Publish ICS files through GitHub API") < workflow.index(
        "Send authentication status notification"
    )


def test_schedule_uses_only_api_and_codeload_transport_for_repository_io() -> None:
    workflow = SCHEDULE.read_text(encoding="utf-8")

    for forbidden in (
        "git fetch",
        "git pull",
        "git push",
        "git add",
        "git diff",
        "git commit",
        "git config",
        "https://github.com",
    ):
        assert forbidden not in workflow
    assert "https://api.github.com" in workflow
    assert "github_api_publish.py" in workflow
    assert '"--status-prefix", "ICS_API"' in workflow
    assert "*.ics" in workflow
    assert "airport_aliases.json" in workflow


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
