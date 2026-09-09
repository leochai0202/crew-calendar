from __future__ import annotations

import base64
import hashlib
from pathlib import Path

import pytest

import github_api_publish as publisher


REPOSITORY = "leochai0202/crew-calendar"
BASE_SHA = "1" * 40
MOVED_SHA = "2" * 40
TREE_SHA = "3" * 40
NEW_TREE_SHA = "4" * 40
NEW_COMMIT_SHA = "5" * 40


def _manual_name(version: str) -> str:
    return (
        "AirDropManual-机场特点汇总"
        f"(Airport Information){version}-Manual.pdf"
    )


class FakeGitHubClient:
    def __init__(
        self,
        remote_files: dict[str, bytes],
        *,
        ref_shas: list[str] | None = None,
        tree_error: str = "",
    ) -> None:
        self.remote_files = remote_files
        self.ref_shas = ref_shas or [BASE_SHA, BASE_SHA, BASE_SHA]
        self.tree_error = tree_error
        self.calls: list[tuple[str, str, dict | None]] = []
        self.ref_reads = 0

    def request_json(
        self,
        method: str,
        path: str,
        payload: dict | None = None,
    ) -> dict:
        self.calls.append((method, path, payload))
        if method == "GET" and "/git/ref/heads/main" in path:
            index = min(self.ref_reads, len(self.ref_shas) - 1)
            self.ref_reads += 1
            return {"object": {"sha": self.ref_shas[index]}}
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
            assert payload is not None
            content = base64.b64decode(payload["content"], validate=True)
            return {"sha": publisher.git_blob_sha(content)}
        if method == "POST" and path.endswith("/git/trees"):
            if self.tree_error:
                raise publisher.GitHubApiError(self.tree_error)
            return {"sha": NEW_TREE_SHA}
        if method == "POST" and path.endswith("/git/commits"):
            return {"sha": NEW_COMMIT_SHA}
        if method == "PATCH" and path.endswith("/git/refs/heads/main"):
            return {"object": {"sha": NEW_COMMIT_SHA}}
        raise AssertionError(f"unexpected API call: {method} {path}")


def _write_manual(root: Path, version: str, content: bytes) -> Path:
    path = root / "knowledge" / "pdf" / _manual_name(version)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def _publish(
    root: Path,
    client: FakeGitHubClient,
    manual: Path,
) -> publisher.PublishResult:
    return publisher.publish_airport_manual(
        client,
        repository=REPOSITORY,
        branch="main",
        message="Update airport manual",
        root=root,
        manual_file=manual,
        expected_main_sha=BASE_SHA,
    )


def _calls(client: FakeGitHubClient, method: str, suffix: str):
    return [
        call
        for call in client.calls
        if call[0] == method and call[1].endswith(suffix)
    ]


def test_airport_manual_scope_rejects_every_path_outside_exact_pdf_directory(
    tmp_path: Path,
) -> None:
    wrong_parent = tmp_path / "knowledge" / _manual_name("20260907")
    wrong_parent.parent.mkdir(parents=True)
    wrong_parent.write_bytes(b"pdf")
    wrong_name = tmp_path / "knowledge" / "pdf" / "other.pdf"
    wrong_name.parent.mkdir(parents=True)
    wrong_name.write_bytes(b"pdf")

    for candidate in (wrong_parent, wrong_name):
        with pytest.raises(publisher.GitHubApiError):
            publisher.publish_airport_manual(
                FakeGitHubClient({}),
                repository=REPOSITORY,
                branch="main",
                message="unsafe",
                root=tmp_path,
                manual_file=candidate,
                expected_main_sha=BASE_SHA,
            )


def test_airport_manual_directory_must_contain_exactly_one_pdf(
    tmp_path: Path,
) -> None:
    first = _write_manual(tmp_path, "20260824", b"old")
    _write_manual(tmp_path, "20260907", b"new")

    with pytest.raises(publisher.GitHubApiError, match="exactly one"):
        _publish(tmp_path, FakeGitHubClient({}), first)


def test_approximately_25mb_binary_uses_lossless_base64_blob_path(
    tmp_path: Path,
) -> None:
    size = int(24.7 * 1024 * 1024)
    pattern = b"\x00\xffPDF\r\n"
    content = (pattern * (size // len(pattern) + 1))[:size]
    manual = _write_manual(tmp_path, "20260907", content)
    client = FakeGitHubClient({})

    result = _publish(tmp_path, client, manual)

    assert result.status == "PUBLISHED"
    blob_payload = _calls(client, "POST", "/git/blobs")[0][2]
    assert blob_payload is not None
    assert blob_payload["encoding"] == "base64"
    assert base64.b64decode(blob_payload["content"], validate=True) == content


def test_git_blob_sha_is_byte_accurate() -> None:
    content = b"\x00\xffbinary\r\ncontent\n"
    expected = hashlib.sha1(
        f"blob {len(content)}\0".encode("ascii") + content
    ).hexdigest()

    assert publisher.git_blob_sha(content) == expected


def test_new_manual_is_added_and_old_manual_is_deleted_from_tree(
    tmp_path: Path,
) -> None:
    old_path = f"knowledge/pdf/{_manual_name('20260824')}"
    new_path = f"knowledge/pdf/{_manual_name('20260907')}"
    manual = _write_manual(tmp_path, "20260907", b"new validated pdf")
    client = FakeGitHubClient({old_path: b"old validated pdf"})

    result = _publish(tmp_path, client, manual)

    assert result.status == "PUBLISHED"
    assert result.changed_files == tuple(sorted((old_path, new_path)))
    tree = _calls(client, "POST", "/git/trees")[0][2]["tree"]
    assert tree[0] == {
        "path": new_path,
        "mode": "100644",
        "type": "blob",
        "sha": publisher.git_blob_sha(b"new validated pdf"),
    }
    assert tree[1] == {
        "path": old_path,
        "mode": "100644",
        "type": "blob",
        "sha": None,
    }


def test_no_change_performs_zero_write_requests(tmp_path: Path) -> None:
    content = b"same validated pdf"
    repo_path = f"knowledge/pdf/{_manual_name('20260907')}"
    manual = _write_manual(tmp_path, "20260907", content)
    client = FakeGitHubClient({repo_path: content})

    result = _publish(tmp_path, client, manual)

    assert result.status == "NO_CHANGES"
    assert not any(method in {"POST", "PATCH"} for method, _, _ in client.calls)


def test_main_moved_before_blob_creation_performs_no_write_or_patch(
    tmp_path: Path,
) -> None:
    old_path = f"knowledge/pdf/{_manual_name('20260824')}"
    manual = _write_manual(tmp_path, "20260907", b"new")
    client = FakeGitHubClient(
        {old_path: b"old"},
        ref_shas=[BASE_SHA, MOVED_SHA],
    )

    result = _publish(tmp_path, client, manual)

    assert result.status == "MAIN_MOVED"
    assert not any(method in {"POST", "PATCH"} for method, _, _ in client.calls)


def test_ref_patch_is_explicitly_non_force(tmp_path: Path) -> None:
    manual = _write_manual(tmp_path, "20260907", b"new")
    client = FakeGitHubClient({})

    result = _publish(tmp_path, client, manual)

    assert result.status == "PUBLISHED"
    patch = _calls(client, "PATCH", "/git/refs/heads/main")
    assert patch[0][2] == {"sha": NEW_COMMIT_SHA, "force": False}


def test_remote_unapproved_pdf_fails_before_any_write(tmp_path: Path) -> None:
    manual = _write_manual(tmp_path, "20260907", b"new")
    client = FakeGitHubClient({"knowledge/pdf/private.pdf": b"private"})

    with pytest.raises(publisher.GitHubApiError, match="unapproved PDF"):
        _publish(tmp_path, client, manual)

    assert not any(method in {"POST", "PATCH"} for method, _, _ in client.calls)


def test_cli_failure_never_logs_token_pdf_bytes_or_base64(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    token = "secret-token-must-not-appear"
    content = b"private-pdf-bytes-must-not-appear"
    encoded = base64.b64encode(content).decode("ascii")
    manual = _write_manual(tmp_path, "20260907", content)
    client = FakeGitHubClient(
        {},
        tree_error=f"unsafe {token} {content.decode()} {encoded}",
    )
    client_options: dict[str, object] = {}

    def make_client(supplied: str, **kwargs):
        assert supplied == token
        client_options.update(kwargs)
        return client

    monkeypatch.setenv("GITHUB_TOKEN", token)
    monkeypatch.setattr(publisher, "GitHubApiClient", make_client)

    exit_code = publisher.main(
        [
            "--repository",
            REPOSITORY,
            "--message",
            "Update airport manual",
            "--root",
            str(tmp_path),
            "--expected-main-sha",
            BASE_SHA,
            "--airport-manual",
            str(manual),
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 1
    assert token not in output
    assert content.decode() not in output
    assert encoded not in output
    assert client_options == {
        "timeout": publisher.AIRPORT_MANUAL_API_TIMEOUT_SECONDS,
    }
    assert output.strip() == "GITHUB_API_PUBLISH=ERROR ERROR_TYPE=GitHubApiError"
