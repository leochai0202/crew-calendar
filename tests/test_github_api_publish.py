from __future__ import annotations

import json
from pathlib import Path

import pytest

import github_api_publish as publisher


REPOSITORY = "leochai0202/crew-calendar"
BASE_SHA = "1" * 40
MOVED_SHA = "2" * 40
TREE_SHA = "3" * 40
NEW_TREE_SHA = "4" * 40
NEW_COMMIT_SHA = "5" * 40


class FakeGitHubClient:
    def __init__(
        self,
        remote_files: dict[str, bytes],
        *,
        final_ref_sha: str = BASE_SHA,
        patch_error: bool = False,
    ) -> None:
        self.remote_files = remote_files
        self.final_ref_sha = final_ref_sha
        self.patch_error = patch_error
        self.calls: list[tuple[str, str, dict | None]] = []
        self.ref_reads = 0
        self.blob_number = 0

    def request_json(
        self,
        method: str,
        path: str,
        payload: dict | None = None,
    ) -> dict:
        self.calls.append((method, path, payload))
        if method == "GET" and "/git/ref/heads/main" in path:
            self.ref_reads += 1
            sha = BASE_SHA if self.ref_reads == 1 else self.final_ref_sha
            return {"object": {"sha": sha}}
        if method == "GET" and f"/git/commits/{BASE_SHA}" in path:
            return {"tree": {"sha": TREE_SHA}}
        if method == "GET" and f"/git/trees/{TREE_SHA}?recursive=1" in path:
            return {
                "tree": [
                    {
                        "path": name,
                        "type": "blob",
                        "sha": publisher.git_blob_sha(content),
                    }
                    for name, content in self.remote_files.items()
                ]
            }
        if method == "POST" and path.endswith("/git/blobs"):
            self.blob_number += 1
            return {"sha": f"blob-{self.blob_number}"}
        if method == "POST" and path.endswith("/git/trees"):
            return {"sha": NEW_TREE_SHA}
        if method == "POST" and path.endswith("/git/commits"):
            return {"sha": NEW_COMMIT_SHA}
        if method == "PATCH" and path.endswith("/git/refs/heads/main"):
            if self.patch_error:
                raise publisher.GitHubApiError("non-fast-forward")
            return {"object": {"sha": NEW_COMMIT_SHA}}
        raise AssertionError(f"unexpected API call: {method} {path}")


def _publish(
    tmp_path: Path,
    client: FakeGitHubClient,
    files: dict[str, bytes],
) -> publisher.PublishResult:
    for name, content in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    return publisher.publish_files(
        client,
        repository=REPOSITORY,
        branch="main",
        message="Update crew calendar",
        root=tmp_path,
        candidate_files=files,
    )


def _calls(client: FakeGitHubClient, method: str, suffix: str):
    return [
        call
        for call in client.calls
        if call[0] == method and call[1].endswith(suffix)
    ]


def test_no_changes_does_not_create_or_update_anything(tmp_path: Path) -> None:
    content = b"BEGIN:VCALENDAR\r\nEND:VCALENDAR\r\n"
    client = FakeGitHubClient({"flight.ics": content})

    result = _publish(tmp_path, client, {"flight.ics": content})

    assert result.status == "NO_CHANGES"
    assert not any(method in {"POST", "PATCH"} for method, _, _ in client.calls)
    assert client.ref_reads == 1


def test_one_changed_ics_creates_only_one_blob_and_uses_raw_bytes(
    tmp_path: Path,
) -> None:
    client = FakeGitHubClient({"flight.ics": b"line one\r\n"})

    result = _publish(tmp_path, client, {"flight.ics": b"line one\n"})

    assert result.status == "PUBLISHED"
    assert result.changed_files == ("flight.ics",)
    blob_calls = _calls(client, "POST", "/git/blobs")
    assert len(blob_calls) == 1
    assert blob_calls[0][2] == {
        "content": "bGluZSBvbmUK",
        "encoding": "base64",
    }


def test_multiple_files_create_one_tree_with_only_changed_candidates(
    tmp_path: Path,
) -> None:
    files = {
        "flight.ics": b"new flight",
        "crew_schedule.ics": b"unchanged crew",
        "airport_aliases.json": b'{"PVG":"Shanghai"}',
    }
    client = FakeGitHubClient(
        {
            "flight.ics": b"old flight",
            "crew_schedule.ics": b"unchanged crew",
            "airport_aliases.json": b"{}",
            "README.md": b"must remain untouched",
        }
    )

    result = _publish(tmp_path, client, files)

    assert result.changed_files == ("airport_aliases.json", "flight.ics")
    assert len(_calls(client, "POST", "/git/blobs")) == 2
    tree_payload = _calls(client, "POST", "/git/trees")[0][2]
    assert tree_payload["base_tree"] == TREE_SHA
    assert [item["path"] for item in tree_payload["tree"]] == [
        "airport_aliases.json",
        "flight.ics",
    ]
    assert "README.md" not in json.dumps(tree_payload)


@pytest.mark.parametrize(
    "name",
    ["airport_aliases.json", "state/auth_notification_state.json"],
)
def test_approved_non_ics_file_can_be_published(
    tmp_path: Path,
    name: str,
) -> None:
    client = FakeGitHubClient({name: b"old"})

    result = _publish(tmp_path, client, {name: b"new"})

    assert result.status == "PUBLISHED"
    assert result.changed_files == (name,)


def test_main_moved_creates_no_ref_patch(tmp_path: Path) -> None:
    client = FakeGitHubClient(
        {"flight.ics": b"old"},
        final_ref_sha=MOVED_SHA,
    )

    result = _publish(tmp_path, client, {"flight.ics": b"new"})

    assert result.status == "MAIN_MOVED"
    assert result.base_sha == BASE_SHA
    assert result.commit_sha == NEW_COMMIT_SHA
    assert not _calls(client, "PATCH", "/git/refs/heads/main")


def test_ref_update_is_non_force_and_non_fast_forward_fails_safely(
    tmp_path: Path,
) -> None:
    client = FakeGitHubClient(
        {"flight.ics": b"old"},
        patch_error=True,
    )

    with pytest.raises(publisher.GitHubApiError, match="non-fast-forward"):
        _publish(tmp_path, client, {"flight.ics": b"new"})

    patch_call = _calls(client, "PATCH", "/git/refs/heads/main")[0]
    assert patch_call[2] == {"sha": NEW_COMMIT_SHA, "force": False}


def test_unapproved_or_outside_candidate_is_rejected(tmp_path: Path) -> None:
    debug = tmp_path / "debug_output" / "route.txt"
    debug.parent.mkdir()
    debug.write_bytes(b"diagnostic")

    with pytest.raises(publisher.GitHubApiError, match="not publishable"):
        publisher.publish_files(
            FakeGitHubClient({}),
            repository=REPOSITORY,
            branch="main",
            message="unsafe",
            root=tmp_path,
            candidate_files=[debug],
        )


def test_cli_error_output_never_includes_token(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    token = "secret-token-must-not-appear"
    (tmp_path / "flight.ics").write_bytes(b"new")

    class FailingClient:
        def __init__(self, supplied_token: str) -> None:
            assert supplied_token == token

        def request_json(self, method, path, payload=None):
            raise publisher.GitHubApiError("safe failure")

    monkeypatch.setenv("GITHUB_TOKEN", token)
    monkeypatch.setattr(publisher, "GitHubApiClient", FailingClient)
    exit_code = publisher.main(
        [
            "--repository",
            REPOSITORY,
            "--message",
            "test",
            "--root",
            str(tmp_path),
            "--files",
            "flight.ics",
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 1
    assert token not in output
    assert output.strip() == "GITHUB_API_PUBLISH=ERROR ERROR_TYPE=GitHubApiError"
