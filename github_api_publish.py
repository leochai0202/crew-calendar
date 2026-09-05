from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Protocol


API_BASE = "https://api.github.com"
API_VERSION = "2022-11-28"
ALLOWED_EXACT_PATHS = {
    "airport_aliases.json",
    "state/auth_notification_state.json",
}


class GitHubApiError(RuntimeError):
    """A sanitized GitHub API failure that never includes credentials."""


class JsonClient(Protocol):
    def request_json(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]: ...


class GitHubApiClient:
    def __init__(self, token: str, *, timeout: float = 30.0) -> None:
        if not token:
            raise GitHubApiError("GITHUB_TOKEN is required")
        self._token = token
        self._timeout = timeout
        # An empty ProxyHandler is an explicit direct connection. This avoids
        # inheriting HTTP_PROXY/HTTPS_PROXY from the self-hosted runner.
        self._opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}),
            urllib.request.HTTPSHandler(),
        )

    def request_json(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not path.startswith("/"):
            raise GitHubApiError("GitHub API path must be absolute")
        data = None
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            API_BASE + path,
            data=data,
            method=method,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json",
                "User-Agent": "crew-calendar-github-api-publisher",
                "X-GitHub-Api-Version": API_VERSION,
            },
        )
        try:
            with self._opener.open(request, timeout=self._timeout) as response:
                body = response.read()
        except urllib.error.HTTPError as exc:
            raise GitHubApiError(
                f"GitHub API {method} {path} failed with HTTP {exc.code}"
            ) from None
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise GitHubApiError(
                f"GitHub API {method} {path} network failure: "
                f"{type(exc).__name__}"
            ) from None
        try:
            parsed = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise GitHubApiError(
                f"GitHub API {method} {path} returned invalid JSON"
            ) from None
        if not isinstance(parsed, dict):
            raise GitHubApiError(
                f"GitHub API {method} {path} returned an unexpected payload"
            )
        return parsed


@dataclass(frozen=True)
class PublishResult:
    status: str
    changed_files: tuple[str, ...] = ()
    commit_sha: str = ""
    base_sha: str = ""


def git_blob_sha(content: bytes) -> str:
    header = f"blob {len(content)}\0".encode("ascii")
    return hashlib.sha1(header + content).hexdigest()


def _validate_repository(repository: str) -> None:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise GitHubApiError("Invalid repository name")


def _normalize_candidate(root: Path, candidate: str | Path) -> tuple[str, Path]:
    root = root.resolve()
    path = Path(candidate)
    if not path.is_absolute():
        path = root / path
    resolved = path.resolve(strict=True)
    try:
        relative = resolved.relative_to(root)
    except ValueError:
        raise GitHubApiError("Candidate file is outside the repository") from None
    repo_path = PurePosixPath(relative.as_posix()).as_posix()
    if not resolved.is_file():
        raise GitHubApiError(f"Candidate is not a file: {repo_path}")
    if not (
        ("/" not in repo_path and repo_path.lower().endswith(".ics"))
        or repo_path in ALLOWED_EXACT_PATHS
    ):
        raise GitHubApiError(f"Candidate path is not publishable: {repo_path}")
    return repo_path, resolved


def _api_path(repository: str, suffix: str) -> str:
    return f"/repos/{repository}{suffix}"


def _nested_string(payload: dict[str, Any], *keys: str) -> str:
    current: Any = payload
    for key in keys:
        if not isinstance(current, dict):
            return ""
        current = current.get(key)
    return current if isinstance(current, str) else ""


def publish_files(
    client: JsonClient,
    *,
    repository: str,
    branch: str,
    message: str,
    root: Path,
    candidate_files: Iterable[str | Path],
) -> PublishResult:
    _validate_repository(repository)
    if not re.fullmatch(r"[A-Za-z0-9._/-]+", branch) or branch.startswith("/"):
        raise GitHubApiError("Invalid branch name")
    normalized = dict(
        sorted(_normalize_candidate(root, item) for item in candidate_files)
    )
    if not normalized:
        return PublishResult(status="NO_CHANGES")

    quoted_branch = urllib.parse.quote(branch, safe="")
    ref_path = _api_path(repository, f"/git/ref/heads/{quoted_branch}")
    ref = client.request_json("GET", ref_path)
    base_sha = _nested_string(ref, "object", "sha")
    if not base_sha:
        raise GitHubApiError("main ref response did not contain a commit SHA")
    commit = client.request_json(
        "GET", _api_path(repository, f"/git/commits/{base_sha}")
    )
    base_tree_sha = _nested_string(commit, "tree", "sha")
    if not base_tree_sha:
        raise GitHubApiError("commit response did not contain a tree SHA")
    tree = client.request_json(
        "GET",
        _api_path(repository, f"/git/trees/{base_tree_sha}?recursive=1"),
    )
    if tree.get("truncated") is True:
        raise GitHubApiError("repository tree response was truncated")
    tree_entries = tree.get("tree")
    if not isinstance(tree_entries, list):
        raise GitHubApiError("repository tree response had an invalid shape")
    remote_blobs = {
        str(entry.get("path")): str(entry.get("sha"))
        for entry in tree_entries
        if isinstance(entry, dict) and entry.get("type") == "blob"
    }

    changed: list[tuple[str, bytes]] = []
    for repo_path, local_path in normalized.items():
        content = local_path.read_bytes()
        if git_blob_sha(content) != remote_blobs.get(repo_path):
            changed.append((repo_path, content))
    if not changed:
        return PublishResult(status="NO_CHANGES", base_sha=base_sha)

    tree_entries: list[dict[str, str]] = []
    for repo_path, content in changed:
        blob = client.request_json(
            "POST",
            _api_path(repository, "/git/blobs"),
            {
                "content": base64.b64encode(content).decode("ascii"),
                "encoding": "base64",
            },
        )
        blob_sha = _nested_string(blob, "sha")
        if not blob_sha:
            raise GitHubApiError("create blob response did not contain a SHA")
        tree_entries.append(
            {
                "path": repo_path,
                "mode": "100644",
                "type": "blob",
                "sha": blob_sha,
            }
        )

    new_tree = client.request_json(
        "POST",
        _api_path(repository, "/git/trees"),
        {"base_tree": base_tree_sha, "tree": tree_entries},
    )
    new_tree_sha = _nested_string(new_tree, "sha")
    if not new_tree_sha:
        raise GitHubApiError("create tree response did not contain a SHA")
    new_commit = client.request_json(
        "POST",
        _api_path(repository, "/git/commits"),
        {"message": message, "tree": new_tree_sha, "parents": [base_sha]},
    )
    new_commit_sha = _nested_string(new_commit, "sha")
    if not new_commit_sha:
        raise GitHubApiError("create commit response did not contain a SHA")

    current_ref = client.request_json("GET", ref_path)
    current_sha = _nested_string(current_ref, "object", "sha")
    if current_sha != base_sha:
        return PublishResult(
            status="MAIN_MOVED",
            changed_files=tuple(path for path, _ in changed),
            commit_sha=new_commit_sha,
            base_sha=base_sha,
        )
    client.request_json(
        "PATCH",
        _api_path(repository, f"/git/refs/heads/{quoted_branch}"),
        {"sha": new_commit_sha, "force": False},
    )
    return PublishResult(
        status="PUBLISHED",
        changed_files=tuple(path for path, _ in changed),
        commit_sha=new_commit_sha,
        base_sha=base_sha,
    )


def _write_github_output(path: str | None, result: PublishResult) -> None:
    if not path:
        return
    with Path(path).open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(f"publish_status={result.status}\n")
        handle.write(f"changed_files={','.join(result.changed_files)}\n")
        handle.write(f"commit_sha={result.commit_sha}\n")
        handle.write(f"base_sha={result.base_sha}\n")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Publish selected crew-calendar files via GitHub Git Database API"
    )
    parser.add_argument("--repository", required=True)
    parser.add_argument("--branch", default="main")
    parser.add_argument("--message", required=True)
    parser.add_argument("--root", default=".")
    parser.add_argument("--github-output")
    parser.add_argument("--status-prefix", default="GITHUB_API")
    parser.add_argument("--files", nargs="+", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    token = os.environ.get("GITHUB_TOKEN", "")
    try:
        if not re.fullmatch(r"[A-Z][A-Z0-9_]*", args.status_prefix):
            raise GitHubApiError("Invalid status prefix")
        client = GitHubApiClient(token)
        result = publish_files(
            client,
            repository=args.repository,
            branch=args.branch,
            message=args.message,
            root=Path(args.root),
            candidate_files=args.files,
        )
        print(f"BASE_MAIN_SHA={result.base_sha}")
        print(f"GITHUB_API_PUBLISH={result.status}")
        print(f"GITHUB_API_CHANGED_FILES={','.join(result.changed_files)}")
        print(f"GITHUB_API_COMMIT_SHA={result.commit_sha}")
        if args.status_prefix != "GITHUB_API":
            print(f"{args.status_prefix}_PUBLISH={result.status}")
            print(
                f"{args.status_prefix}_CHANGED_FILES="
                f"{','.join(result.changed_files)}"
            )
            print(f"{args.status_prefix}_COMMIT_SHA={result.commit_sha}")
        _write_github_output(args.github_output, result)
        return 2 if result.status == "MAIN_MOVED" else 0
    except Exception as exc:
        print(f"GITHUB_API_PUBLISH=ERROR ERROR_TYPE={type(exc).__name__}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
