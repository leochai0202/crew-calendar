from __future__ import annotations

import base64
import errno
import hashlib
import http.client
import json
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pytest

import github_api_publish as publisher


PREFIX = "/repos/owner/repo"
BASE = "1" * 40
TARGET = "2" * 40
MOVED = "3" * 40
TOKEN = "test-secret-not-for-logs"


class Response:
    def __init__(self, result: dict | BaseException) -> None:
        self.result = result

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def read(self):
        if isinstance(self.result, BaseException):
            raise self.result
        return json.dumps(self.result).encode()


class Opener:
    def __init__(self, results):
        self.results = iter(results)
        self.requests = []

    def open(self, request, *, timeout):
        self.requests.append(request)
        result = next(self.results)
        if isinstance(result, BaseException):
            raise result
        return Response(result)


def client_with_results(monkeypatch, results):
    client = publisher.GitHubApiClient(TOKEN)
    opener = Opener(results)
    delays = []
    client._opener = opener
    monkeypatch.setattr(publisher.time, "sleep", delays.append)
    return client, opener, delays


@pytest.mark.parametrize("error", [
    http.client.IncompleteRead(b"partial secret body"),
    urllib.error.URLError("private URL or proxy credential"),
    TimeoutError("private request"),
    ConnectionResetError("private request"),
    OSError(errno.ENETUNREACH, "private request"),
])
def test_transient_get_error_retries_then_succeeds(monkeypatch, error):
    # IncompleteRead occurs while reading a successful response, not just open().
    results = [Response(error), {"object": {"sha": BASE}}]
    client, opener, delays = client_with_results(monkeypatch, [])
    iterator = iter(results)

    def open_response(request, *, timeout):
        opener.requests.append(request)
        result = next(iterator)
        return result if isinstance(result, Response) else Response(result)

    opener.open = open_response
    assert client.request_json("GET", PREFIX + "/git/ref/heads/main")["object"]["sha"] == BASE
    assert len(opener.requests) == 2
    assert delays == [5]


def test_transport_exhaustion_is_bounded_and_sanitized(monkeypatch, capsys):
    client, opener, delays = client_with_results(monkeypatch, [
        http.client.IncompleteRead(TOKEN.encode()) for _ in range(3)
    ])
    with pytest.raises(publisher.GitHubApiError) as captured:
        client.request_json("GET", PREFIX + "/git/ref/heads/main")
    assert len(opener.requests) == 3
    assert delays == [5, 15]
    safe_output = str(captured.value) + capsys.readouterr().out
    assert TOKEN not in safe_output
    assert "IncompleteRead" in safe_output
    assert "after 3 attempts" in safe_output
    assert "Authorization" not in safe_output


@pytest.mark.parametrize("status", [401, 403, 404, 422, 500, 503])
@pytest.mark.parametrize("method,suffix", [("GET", "/git/ref/heads/main"), ("POST", "/git/blobs")])
def test_explicit_http_errors_are_not_transport_retries(monkeypatch, status, method, suffix):
    error = urllib.error.HTTPError("https://private.invalid/?secret=" + TOKEN, status, TOKEN, {}, None)
    client, opener, delays = client_with_results(monkeypatch, [error])
    with pytest.raises(publisher.GitHubApiError, match=f"HTTP {status}") as captured:
        client.request_json(method, PREFIX + suffix, {"content": TOKEN} if method == "POST" else None)
    assert len(opener.requests) == 1
    assert delays == []
    assert TOKEN not in str(captured.value)


def test_local_permission_error_is_not_transient(monkeypatch):
    client, opener, delays = client_with_results(monkeypatch, [PermissionError("private")])
    with pytest.raises(publisher.GitHubApiError):
        client.request_json("GET", PREFIX + "/git/ref/heads/main")
    assert len(opener.requests) == 1
    assert not delays


def test_default_proxy_handler_inherits_environment(monkeypatch):
    monkeypatch.setenv("HTTP_PROXY", "http://proxy.invalid:8123")
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.invalid:8123")
    client = publisher.GitHubApiClient(TOKEN)
    handlers = [handler for handler in client._opener.handlers if isinstance(handler, urllib.request.ProxyHandler)]
    assert len(handlers) == 1
    assert handlers[0].proxies["https"] == "http://proxy.invalid:8123"


@pytest.mark.parametrize("suffix,payload", [
    ("/git/blobs", {"encoding": "base64", "content": base64.b64encode(b"binary\x00\xff").decode()}),
    ("/git/trees", {"base_tree": BASE, "tree": [{"path": "flight.ics", "sha": TARGET}]}),
    ("/git/commits", {"message": "Update crew calendar", "tree": TARGET, "parents": [BASE]}),
])
def test_immutable_git_object_retry_reuses_identical_bytes(monkeypatch, suffix, payload, capsys):
    original = json.dumps(payload)
    client, opener, delays = client_with_results(monkeypatch, [
        http.client.IncompleteRead(TOKEN.encode()), {"sha": TARGET},
    ])
    assert client.request_json("POST", PREFIX + suffix, payload)["sha"] == TARGET
    assert len(opener.requests) == 2
    assert opener.requests[0].data == opener.requests[1].data
    assert delays == [5]
    assert json.dumps(payload) == original  # Never mutate the caller's payload.
    if suffix == "/git/commits":
        posted = json.loads(opener.requests[0].data)
        for identity in (posted["author"], posted["committer"]):
            assert identity["name"] and identity["email"]
            assert identity["date"].endswith("Z")
        assert posted["author"] == posted["committer"]
    output = capsys.readouterr().out
    assert TOKEN not in output
    assert "content" not in output and "Authorization" not in output


def test_unknown_write_is_not_blindly_retried(monkeypatch):
    client, opener, delays = client_with_results(monkeypatch, [ConnectionResetError()])
    with pytest.raises(publisher.GitHubApiError, match="Uncertain write"):
        client.request_json("POST", PREFIX + "/unknown", {})
    assert len(opener.requests) == 1 and not delays


def test_lost_patch_response_checks_ref_without_second_patch(monkeypatch):
    client, opener, delays = client_with_results(monkeypatch, [
        http.client.IncompleteRead(b"partial"), {"object": {"sha": TARGET}},
    ])
    result = client.request_json("PATCH", PREFIX + "/git/refs/heads/main", {"sha": TARGET, "force": False})
    assert result["object"]["sha"] == TARGET
    assert [request.method for request in opener.requests] == ["PATCH", "GET"]
    assert not delays


def test_unapplied_patch_is_retried_only_after_ref_and_parent_confirmation(monkeypatch):
    client, opener, delays = client_with_results(monkeypatch, [
        ConnectionResetError(), {"object": {"sha": BASE}},
        {"parents": [{"sha": BASE}]}, {"object": {"sha": TARGET}},
    ])
    client.request_json("PATCH", PREFIX + "/git/refs/heads/main", {"sha": TARGET, "force": False})
    assert [request.method for request in opener.requests] == ["PATCH", "GET", "GET", "PATCH"]
    assert opener.requests[0].data == opener.requests[-1].data
    assert json.loads(opener.requests[-1].data)["force"] is False
    assert delays == [5]


def test_uncertain_patch_main_moved_does_not_patch_again(monkeypatch):
    client, opener, delays = client_with_results(monkeypatch, [
        ConnectionResetError(), {"object": {"sha": MOVED}}, {"parents": [{"sha": BASE}]},
    ])
    with pytest.raises(publisher.GitHubMainMovedError, match="MAIN_MOVED"):
        client.request_json("PATCH", PREFIX + "/git/refs/heads/main", {"sha": TARGET, "force": False})
    assert [request.method for request in opener.requests] == ["PATCH", "GET", "GET"]
    assert not delays


def test_uncertain_ref_probe_failure_does_not_retry_patch(monkeypatch):
    client, opener, delays = client_with_results(monkeypatch, [
        ConnectionResetError(), TimeoutError(), TimeoutError(), TimeoutError(),
    ])
    with pytest.raises(publisher.GitHubApiError):
        client.request_json("PATCH", PREFIX + "/git/refs/heads/main", {"sha": TARGET, "force": False})
    assert [request.method for request in opener.requests].count("PATCH") == 1


def test_atomic_publish_survives_lost_object_and_ref_responses(monkeypatch, tmp_path: Path):
    client = publisher.GitHubApiClient(TOKEN)
    monkeypatch.setattr(publisher.time, "sleep", lambda _: None)
    files = {"flight.ics": b"new flight\r\n", "crew_schedule.ics": b"new crew\r\n"}
    for name, content in files.items():
        (tmp_path / name).write_bytes(content)
    state = {"ref": BASE, "updates": 0, "commit_payloads": [], "commits": {}}
    calls = []

    class AtomicOpener:
        def open(self, request, *, timeout):
            path = urllib.parse.urlsplit(request.full_url).path
            payload = json.loads(request.data) if request.data else None
            calls.append((request.method, path, payload))
            if request.method == "GET" and path.endswith("/git/ref/heads/main"):
                return Response({"object": {"sha": state["ref"]}})
            if request.method == "GET" and path.endswith("/git/commits/" + BASE):
                return Response({"tree": {"sha": MOVED}})
            if request.method == "GET" and "/git/trees/" in path:
                return Response({"tree": []})
            if request.method == "POST" and path.endswith("/git/blobs"):
                return Response({"sha": publisher.git_blob_sha(base64.b64decode(payload["content"]))})
            if request.method == "POST" and path.endswith("/git/trees"):
                return Response({"sha": TARGET})
            if request.method == "POST" and path.endswith("/git/commits"):
                state["commit_payloads"].append(request.data)
                sha = hashlib.sha1(request.data).hexdigest()
                state["commits"][sha] = payload
                return Response(http.client.IncompleteRead(b"lost") if len(state["commit_payloads"]) == 1 else {"sha": sha})
            if request.method == "PATCH":
                assert payload["force"] is False
                state["ref"] = payload["sha"]
                state["updates"] += 1
                return Response(http.client.IncompleteRead(b"lost ref response"))
            raise AssertionError("Unexpected API operation")

    client._opener = AtomicOpener()
    result = publisher.publish_files(
        client, repository="owner/repo", branch="main", message="Update crew calendar",
        root=tmp_path, candidate_files=files,
    )
    assert result.status == "PUBLISHED"
    assert result.changed_files == tuple(sorted(files))
    assert len(state["commits"]) == 1
    assert len(set(state["commit_payloads"])) == 1
    assert state["updates"] == 1
    assert sum(method == "PATCH" for method, _, _ in calls) == 1
    assert sum(method == "POST" and path.endswith("/git/trees") for method, path, _ in calls) == 1
