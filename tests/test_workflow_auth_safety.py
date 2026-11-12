from pathlib import Path
import re

import pytest


ROOT = Path(__file__).parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
SCHEDULE = ROOT / ".github" / "workflows" / "schedule.yml"
FLIGHT_PREP = ROOT / ".github" / "workflows" / "flight-prep-free-v5-20260616.yml"
CODE_TESTS = ROOT / ".github" / "workflows" / "auth-session-check.yml"
RUNNER_SETUP = ROOT / "scripts" / "setup_self_hosted_runner.ps1"
MAINTENANCE_AGENT = ROOT / "crew_agents" / "maintenance_agent.py"


def _assert_training_cleanup_safety(helper: str) -> None:
    # These guards moved out of YAML; they must still protect every deletion.
    for required in (
        "function Get-TrainingCleanupPlan", "[IO.Path]::GetFullPath($TempBase)",
        "[IO.Path]::GetFullPath($Root)", "(Split-Path -Parent $rootPath) -ne $tempPath",
        "[Regex]::Escape($Id)", "(Split-Path -Leaf $rootPath) -notmatch $namePattern",
        "CLEANUP_PATH_INVALID", "CLEANUP_ROOT_NAME_INVALID", "CLEANUP_REPARSE_POINT_REFUSED",
        "[IO.FileAttributes]::ReparsePoint", "$ancestor = $ancestor.Parent",
        "$pending.Pop()", "$pending.Push($item.FullName)",
        ".training-run-owner.json", "$owner.run_id -ne $Id", "$owner.root_name",
        "CLEANUP_OWNER_MISSING", "CLEANUP_OWNER_INVALID",
        "$plan = Get-TrainingCleanupPlan -Root $Root -TempBase $TempBase -Id $Id",
        "if ($Inspect)", "[switch]$InspectOnly", "FAILED_REQUIRES_LOCAL_REVIEW",
        "$attempt -le 3", "Remove-Item -LiteralPath",
    ):
        assert required in helper
    assert helper.index("$plan = Get-TrainingCleanupPlan") < helper.index("Remove-Item -LiteralPath")


def _assert_training_cleanup_workflow_safety(workflow: str, cleanup_helper: str | None) -> None:
    if "'training_downloader/cleanup_training.ps1'" in workflow:
        assert cleanup_helper is not None
        for required in (
            "& $helper", "CLEANUP_PATH_INVALID", "CLEANUP_HELPER_MISSING",
            "CLEANUP_HELPER_START_FAILED", "(Split-Path -Parent $runRoot) -ne $tempBase",
            "(Split-Path -Leaf $runRoot) -notmatch $namePattern",
            "& ./training_downloader/test_cleanup_training.ps1",
        ):
            assert required in workflow
        if "TRAINING_CLEANUP_HELPER" in workflow:
            for required in (
                "$expectedHelper = Join-Path $tempBase",
                "[IO.Path]::GetFullPath($env:TRAINING_CLEANUP_HELPER) -ne $expectedHelper",
                "CLEANUP_HELPER_PATH_INVALID", "$helper = $expectedHelper",
                "(Get-Item -LiteralPath $helper -Force).Attributes -band [IO.FileAttributes]::ReparsePoint",
            ):
                assert required in workflow
        else:
            assert "source/training_downloader/cleanup_training.ps1" in workflow
        _assert_training_cleanup_safety(cleanup_helper)
    else:
        assert "UNSAFE_CLEANUP_PATH" in workflow
        assert "CLEANUP_REPARSE_POINT_REFUSED" in workflow


def _assert_training_login_workflow_safety(workflow: str, cleanup_helper: str | None = None) -> None:
    assert workflow.splitlines()[0] == "name: 一点知识独立登录检查"
    triggers = workflow.split("\non:\n", 1)[1].split("\npermissions:", 1)[0]
    assert re.findall(r"^  ([\w-]+):", triggers, re.M) == ["workflow_dispatch"]
    encrypted_delivery = "confirm_platform_allows_capture:" in triggers
    description = ("确认仅执行一次登录并尝试授权下载目标 PDF，最多申请一次邮箱验证码"
                   if encrypted_delivery else "确认仅执行一次独立登录，最多申请一次邮箱验证码")
    assert (
        "      confirm_single_email:\n"
        f"        description: '{description}'\n"
        "        type: boolean\n"
        "        required: true\n"
        "        default: false" in triggers
    )
    assert "permissions:\n  contents: read\n  actions: read\n" in workflow
    assert "  group: crew-calendar\n  cancel-in-progress: false\n  queue: max" in workflow
    jobs = workflow.split("\njobs:\n", 1)[1]
    assert re.findall(r"^  ([\w-]+):", jobs, re.M) == ["login-check"]
    condition = jobs.split("    if: >-\n", 1)[1].split("    runs-on:", 1)[0]
    assert " ".join(condition.split()) == (
        "${{ github.event_name == 'workflow_dispatch' && "
        "github.repository == 'leochai0202/crew-calendar' && "
        "github.ref == 'refs/heads/main' && inputs.confirm_single_email"
        + (" && inputs.confirm_platform_allows_capture" if encrypted_delivery else "") + " }}"
    )
    for required in (
        "runs-on: [self-hosted, Windows, X64, crew-calendar]",
        "timeout-minutes: 40" if encrypted_delivery else "timeout-minutes: 12",
        "if ($env:GITHUB_RUN_ATTEMPT -ne '1') { throw 'RERUN_DISABLED' }",
        "[IO.Path]::GetFullPath($env:RUNNER_TEMP)",
        "[Guid]::NewGuid().ToString('N')",
        "throw 'DIRECTORY_ALREADY_EXISTS'",
        "python -B -m unittest discover -s training_downloader -p 'test_*.py'",
        "TRAINING_REQUIRE_GUARD: '1'",
        "if: ${{ always() && env.TRAINING_RUN_ROOT != '' }}",
    ):
        assert required in workflow
    _assert_training_cleanup_workflow_safety(workflow, cleanup_helper)
    assert workflow.count("python -B training_downloader/workflow_guard.py") == 1
    assert workflow.count("python -B training_downloader/login_probe.py --run") == 1
    assert workflow.index("python -B -m unittest") < workflow.index(
        "python -B training_downloader/workflow_guard.py"
    ) < workflow.index("python -B training_downloader/login_probe.py --run")
    assert sorted(re.findall(r"secrets\.([A-Z_]+)", workflow)) == [
        "CREW_PASSWORD", "CREW_USERNAME", "IMAP_AUTH_CODE", "IMAP_EMAIL"
    ]
    for forbidden in (
        "contents: write", "actions: write", "CREW_PHONE", "CREW_LOGIN_PHONE",
        "CREW_STORAGE_STATE_B64", "CREW_PERSISTENT_PROFILE_DIR", "CREW_AUTH_BACKUP_PATH",
        "CREW_AUTH_CONTROL_PATH", "python crew_calendar", "clean_ics_people.py",
        "github_api_publish.py", "git push",
    ):
        assert forbidden not in workflow
    if encrypted_delivery:
        _assert_training_encrypted_delivery_safety(workflow)
    else:
        assert "uses:" not in workflow


TRAINING_DELIVERY_GUARDS = (
        "confirm_platform_allows_capture:\n"
        "        description: '已确认平台允许将本课件截图保存；仅有查看权限不能勾选'\n"
        "        type: boolean\n        required: true\n        default: false",
        "preflight_only:\n"
        "        description: '只验证隔离环境和会话目录，不登录、不读取登录 Secrets、不申请验证码'\n"
        "        type: boolean\n        required: false\n        default: false",
        "if: ${{ !inputs.preflight_only }}",
        "TRAINING_CAPTURE_ALLOWED: ${{ inputs.confirm_platform_allows_capture && '1' || '0' }}",
        "if: ${{ success() && steps.pdf_attempt.outputs.encrypted_package != '' }}",
        "path: ${{ steps.pdf_attempt.outputs.encrypted_package }}",
        "if-no-files-found: error", "ENCRYPTED_ARTIFACT_AVAILABLE; LOCAL_DECRYPTION_REQUIRED",
)


def _assert_training_encrypted_delivery_safety(workflow: str) -> None:
    for required in TRAINING_DELIVERY_GUARDS:
        assert required in workflow
    assert re.findall(r"uses:\s*(\S+)", workflow) == [
        "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02"]
    # Credentials belong only to the explicit, non-preflight login step.
    secret_block = workflow.split("if: ${{ !inputs.preflight_only }}", 1)[1].split("\n      - name:", 1)[0]
    assert sorted(re.findall(r"secrets\.([A-Z_]+)", secret_block)) == [
        "CREW_PASSWORD", "CREW_USERNAME", "IMAP_AUTH_CODE", "IMAP_EMAIL"]
    assert "python -B training_downloader/login_probe.py --run" in secret_block


@pytest.mark.parametrize("missing", [
    "required: true", "default: false", "if: ${{ !inputs.preflight_only }}",
    "TRAINING_CAPTURE_ALLOWED: ${{ inputs.confirm_platform_allows_capture && '1' || '0' }}",
    "if: ${{ success() && steps.pdf_attempt.outputs.encrypted_package != '' }}",
    "path: ${{ steps.pdf_attempt.outputs.encrypted_package }}",
    "if-no-files-found: error", "LOCAL_DECRYPTION_REQUIRED",
])
def test_encrypted_training_delivery_rejects_removed_guard(missing: str) -> None:
    # Build the complete asserted contract without copying a production workflow.
    workflow = "\n".join(TRAINING_DELIVERY_GUARDS) + "\nuses: actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02\n"
    workflow += "python -B training_downloader/login_probe.py --run\n" + "\n".join(
        "secrets." + name for name in ("CREW_PASSWORD", "CREW_USERNAME", "IMAP_AUTH_CODE", "IMAP_EMAIL"))
    _assert_training_encrypted_delivery_safety(workflow)
    with pytest.raises(AssertionError):
        _assert_training_encrypted_delivery_safety(workflow.replace(missing, "REMOVED"))


def _assert_workflow_inventory(workflows: Path) -> None:
    expected = {
        "auth-session-check.yml": "代码测试",
        "flight-prep-free-v5-20260616.yml": "生成航前准备",
        "schedule.yml": "更新机组日历",
        "sync-airport-manual.yml": "同步机场手册",
    }
    optional = "training-login-check.yml"
    actual = {path.name for pattern in ("*.yml", "*.yaml") for path in workflows.glob(pattern)}
    assert set(expected) <= actual <= set(expected) | {optional}
    for filename, display_name in expected.items():
        workflow = (workflows / filename).read_text(encoding="utf-8")
        assert workflow.splitlines()[0] == f"name: {display_name}"
        assert "workflow_run:" not in workflow
    if optional in actual:
        workflow = (workflows / optional).read_text(encoding="utf-8")
        helper_path = ROOT / "training_downloader" / "cleanup_training.ps1"
        helper = helper_path.read_text(encoding="utf-8") if helper_path.is_file() else None
        _assert_training_login_workflow_safety(workflow, helper)


def test_actions_has_only_required_and_approved_named_workflows() -> None:
    _assert_workflow_inventory(WORKFLOWS)


@pytest.fixture
def external_training_cleanup_wrapper() -> str:
    # The helper is staged outside the source tree in newer main revisions.
    return "\n".join((
        "'training_downloader/cleanup_training.ps1'", "& $helper",
        "CLEANUP_PATH_INVALID", "CLEANUP_HELPER_MISSING", "CLEANUP_HELPER_START_FAILED",
        "(Split-Path -Parent $runRoot) -ne $tempBase",
        "(Split-Path -Leaf $runRoot) -notmatch $namePattern",
        "& ./training_downloader/test_cleanup_training.ps1",
        "$expectedHelper = Join-Path $tempBase",
        "[IO.Path]::GetFullPath($env:TRAINING_CLEANUP_HELPER) -ne $expectedHelper",
        "CLEANUP_HELPER_PATH_INVALID", "$helper = $expectedHelper",
        "(Get-Item -LiteralPath $helper -Force).Attributes -band [IO.FileAttributes]::ReparsePoint",
    ))


def test_external_training_cleanup_delegates_to_helper_validation(
    monkeypatch: pytest.MonkeyPatch, external_training_cleanup_wrapper: str,
) -> None:
    checked = []
    monkeypatch.setitem(globals(), "_assert_training_cleanup_safety", checked.append)
    _assert_training_cleanup_workflow_safety(external_training_cleanup_wrapper, "helper source")
    assert checked == ["helper source"]


@pytest.mark.parametrize("missing", [
    "& $helper", "CLEANUP_PATH_INVALID", "CLEANUP_HELPER_MISSING", "CLEANUP_HELPER_START_FAILED",
    "(Split-Path -Parent $runRoot) -ne $tempBase",
    "(Split-Path -Leaf $runRoot) -notmatch $namePattern",
    "& ./training_downloader/test_cleanup_training.ps1",
    "$expectedHelper = Join-Path $tempBase",
    "[IO.Path]::GetFullPath($env:TRAINING_CLEANUP_HELPER) -ne $expectedHelper",
    "CLEANUP_HELPER_PATH_INVALID", "$helper = $expectedHelper",
    "(Get-Item -LiteralPath $helper -Force).Attributes -band [IO.FileAttributes]::ReparsePoint",
])
def test_external_training_cleanup_rejects_removed_wrapper_guard(
    monkeypatch: pytest.MonkeyPatch, external_training_cleanup_wrapper: str, missing: str,
) -> None:
    monkeypatch.setitem(globals(), "_assert_training_cleanup_safety", lambda helper: None)
    with pytest.raises(AssertionError):
        _assert_training_cleanup_workflow_safety(
            external_training_cleanup_wrapper.replace(missing, "REMOVED"), "invalid helper",
        )


@pytest.mark.parametrize("helper", [None, "invalid helper"])
def test_external_training_cleanup_requires_valid_helper(
    external_training_cleanup_wrapper: str, helper: str | None,
) -> None:
    with pytest.raises(AssertionError):
        _assert_training_cleanup_workflow_safety(external_training_cleanup_wrapper, helper)


@pytest.mark.parametrize("unexpected", ["unreviewed.yml", "unreviewed.yaml"])
def test_workflow_inventory_rejects_unreviewed_workflows(tmp_path: Path, unexpected: str) -> None:
    for path in WORKFLOWS.glob("*.yml"):
        (tmp_path / path.name).write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    (tmp_path / unexpected).write_text("name: Unreviewed\n", encoding="utf-8")
    with pytest.raises(AssertionError):
        _assert_workflow_inventory(tmp_path)


@pytest.mark.parametrize("missing", [
    "auth-session-check.yml", "flight-prep-free-v5-20260616.yml",
    "schedule.yml", "sync-airport-manual.yml",
])
def test_workflow_inventory_still_requires_each_original_workflow(tmp_path: Path, missing: str) -> None:
    for path in WORKFLOWS.glob("*.yml"):
        if path.name != missing:
            (tmp_path / path.name).write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    with pytest.raises(AssertionError):
        _assert_workflow_inventory(tmp_path)


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
    assert workflow.count("continue-on-error: true") == 4
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
