from __future__ import annotations

import io
import os
import subprocess
import threading
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "bootstrap_repository.ps1"
WORKFLOW = ROOT / ".github" / "workflows" / "schedule.yml"
TARGET_SHA = "a" * 40


def _zip_bytes(entries: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    return buffer.getvalue()


class ArchiveServer:
    def __init__(self, body: bytes, *, failures_before_success: int = 0) -> None:
        self.body = body
        self.failures_before_success = failures_before_success
        self.api_requests = 0
        self.archive_requests = 0
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                if self.path == f"/repos/owner/repo/zipball/{TARGET_SHA}":
                    owner.api_requests += 1
                    if owner.api_requests <= owner.failures_before_success:
                        self.send_response(503)
                        self.end_headers()
                        return
                    self.send_response(302)
                    self.send_header(
                        "Location",
                        f"http://127.0.0.1:{owner.port}/archive.zip",
                    )
                    self.end_headers()
                    return
                if self.path == "/archive.zip":
                    owner.archive_requests += 1
                    self.send_response(200)
                    self.send_header("Content-Type", "application/zip")
                    self.send_header("Content-Length", str(len(owner.body)))
                    self.end_headers()
                    self.wfile.write(owner.body)
                    return
                self.send_response(404)
                self.end_headers()

            def log_message(self, format, *args):
                return

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


def _quote_pwsh(value: str | Path) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _run_bootstrap(
    tmp_path: Path,
    server: ArchiveServer,
    *,
    workspace: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    workspace = workspace or tmp_path / "workspace"
    runner_temp = tmp_path / "runner-temp"
    workspace.mkdir(parents=True, exist_ok=True)
    runner_temp.mkdir(parents=True, exist_ok=True)
    command = " ".join(
        (
            f"& {_quote_pwsh(SCRIPT)}",
            "-Repository 'owner/repo'",
            f"-TargetSha '{TARGET_SHA}'",
            f"-Workspace {_quote_pwsh(workspace)}",
            f"-RunnerTemp {_quote_pwsh(runner_temp)}",
            f"-ApiBase 'http://127.0.0.1:{server.port}'",
            "-AllowedArchiveHost '127.0.0.1'",
            "-MaxAttempts 3",
            "-RetryDelaysSeconds @(0,0,0)",
        )
    )
    env = os.environ.copy()
    env["GITHUB_TOKEN"] = "test-token-not-logged"
    return subprocess.run(
        ["pwsh", "-NoLogo", "-NoProfile", "-Command", command],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=False,
    )


def test_bootstrap_downloads_fixed_sha_and_cleans_then_copies_workspace(
    tmp_path: Path,
) -> None:
    body = _zip_bytes(
        {
            "owner-repo-sha/crew_calendar_main.py": b"print('safe')\n",
            "owner-repo-sha/.github/workflows/schedule.yml": b"name: test\n",
        }
    )
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "stale.txt").write_text("remove me", encoding="utf-8")

    with ArchiveServer(body) as server:
        result = _run_bootstrap(tmp_path, server, workspace=workspace)

    assert result.returncode == 0, result.stderr
    assert f"BOOTSTRAP_MAIN_SHA={TARGET_SHA}" in result.stdout
    assert "ARCHIVE_DOWNLOAD=SUCCESS" in result.stdout
    assert server.api_requests == 1
    assert server.archive_requests == 1
    assert not (workspace / "stale.txt").exists()
    assert (workspace / "crew_calendar_main.py").read_bytes() == b"print('safe')\n"
    assert (workspace / ".github" / "workflows" / "schedule.yml").is_file()
    assert not (workspace / ".git").exists()


@pytest.mark.parametrize(
    "body",
    [
        b"not a zip",
        _zip_bytes({"repo-one/file.txt": b"one", "repo-two/file.txt": b"two"}),
    ],
)
def test_invalid_archive_fails_before_cleaning_workspace(
    tmp_path: Path,
    body: bytes,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    sentinel = workspace / "last-good.txt"
    sentinel.write_text("preserve", encoding="utf-8")

    with ArchiveServer(body) as server:
        result = _run_bootstrap(tmp_path, server, workspace=workspace)

    assert result.returncode != 0
    assert sentinel.read_text(encoding="utf-8") == "preserve"


def test_archive_network_action_retries_at_most_three_times(
    tmp_path: Path,
) -> None:
    body = _zip_bytes({"owner-repo-sha/file.txt": b"ok"})
    with ArchiveServer(body, failures_before_success=2) as server:
        result = _run_bootstrap(tmp_path, server)

    assert result.returncode == 0, result.stderr
    assert server.api_requests == 3
    assert server.archive_requests == 1
    assert "attempt 1/3 failed" in result.stdout
    assert "attempt 2/3 failed" in result.stdout


def test_archive_network_action_stops_after_third_failure(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    sentinel = workspace / "last-good.txt"
    sentinel.write_text("preserve", encoding="utf-8")
    body = _zip_bytes({"owner-repo-sha/file.txt": b"not reached"})

    with ArchiveServer(body, failures_before_success=3) as server:
        result = _run_bootstrap(tmp_path, server, workspace=workspace)

    assert result.returncode != 0
    assert server.api_requests == 3
    assert server.archive_requests == 0
    assert sentinel.read_text(encoding="utf-8") == "preserve"


def test_bootstrap_uses_explicit_direct_clients_and_safe_temporary_storage() -> None:
    script = SCRIPT.read_text(encoding="utf-8")

    assert "$handler.UseProxy = $false" in script
    assert "$handler.AllowAutoRedirect = $false" in script
    assert '"/zipball/" + $TargetSha' in script
    assert "127.0.0.1:7890" not in script
    assert "MaxAttempts must be between 1 and 3" in script
    assert "Archive file is empty" in script
    assert "Archive must contain exactly one top-level repository directory" in script
    assert "Archive top-level directory did not match the repository" in script
    assert "Get-ChildItem -LiteralPath $workspaceFull -Force" in script
    assert "Remove-Item -LiteralPath $_.FullName -Recurse -Force" in script


def test_workflow_resolves_main_once_and_bootstraps_before_scraper() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "/git/ref/heads/main" in workflow
    assert "BOOTSTRAP_MAIN_SHA=$bootstrapSha" in workflow
    assert "scripts/bootstrap_repository.ps1?ref=$bootstrapSha" in workflow
    assert "-TargetSha $bootstrapSha" in workflow
    assert workflow.index("Bootstrap repository from GitHub API") < workflow.index(
        "Run scraper"
    )
    bootstrap_step = workflow.split("- name: Bootstrap repository", 1)[1].split(
        "- name: Verify self-hosted runtime", 1
    )[0]
    assert "if: ${{ always() }}" not in bootstrap_step
    assert "$handler.UseProxy = $false" in bootstrap_step
