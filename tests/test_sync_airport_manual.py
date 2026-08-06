import json
import shutil
from pathlib import Path

import pytest

from tools.sync_airport_manual import (
    SyncError,
    load_config,
    sha256_file,
    sync_airport_manual,
)


ROOT = Path(__file__).parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "sync-airport-manual.yml"


def _write_text_pdf(path: Path, text: str) -> None:
    escaped_text = (
        text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    )
    stream = f"BT /F1 12 Tf 72 720 Td ({escaped_text}) Tj ET".encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"
        ),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length "
        + str(len(stream)).encode("ascii")
        + b" >>\nstream\n"
        + stream
        + b"\nendstream",
    ]

    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for index, body in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{index} 0 obj\n".encode("ascii"))
        output.extend(body)
        output.extend(b"\nendobj\n")

    xref_offset = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode("ascii")
    )
    path.write_bytes(output)


def _write_config(path: Path, source: Path, target: str = "knowledge/pdf") -> None:
    path.write_text(
        json.dumps(
            {
                "source_folder": str(source),
                "target_folder": target,
            }
        ),
        encoding="utf-8",
    )


def _repo_layout(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    repo_root = tmp_path / "repo"
    source = tmp_path / "Flight Data"
    target = repo_root / "knowledge" / "pdf"
    config = repo_root / "config" / "airport_manual_sync.json"
    source.mkdir(parents=True)
    config.parent.mkdir(parents=True)
    _write_config(config, source)
    return repo_root, source, target, config


def test_single_valid_pdf_is_synchronized(tmp_path: Path) -> None:
    repo_root, source, target, config = _repo_layout(tmp_path)
    source_pdf = source / "Airport-Information-20260801.pdf"
    _write_text_pdf(source_pdf, "Airport Information Manual Revision 20260801")

    result = sync_airport_manual(config, repo_root=repo_root)

    assert result.changed is True
    assert result.status == "UPDATED"
    assert (target / source_pdf.name).is_file()
    assert sha256_file(target / source_pdf.name) == sha256_file(source_pdf)


def test_multiple_source_pdfs_fail_without_changing_target(tmp_path: Path) -> None:
    repo_root, source, target, config = _repo_layout(tmp_path)
    target.mkdir(parents=True)
    old_pdf = target / "current.pdf"
    _write_text_pdf(old_pdf, "Airport Information Current Manual")
    old_hash = sha256_file(old_pdf)
    _write_text_pdf(source / "one.pdf", "Airport Information Manual One")
    _write_text_pdf(source / "two.PDF", "Airport Information Manual Two")

    with pytest.raises(SyncError, match="必须且只能包含一个PDF"):
        sync_airport_manual(config, repo_root=repo_root)

    assert sha256_file(old_pdf) == old_hash
    assert [path.name for path in target.glob("*.pdf")] == ["current.pdf"]


def test_missing_source_pdf_fails_without_creating_target(tmp_path: Path) -> None:
    repo_root, _source, target, config = _repo_layout(tmp_path)

    with pytest.raises(SyncError, match="当前检测到0个"):
        sync_airport_manual(config, repo_root=repo_root)

    assert not target.exists()


def test_corrupt_pdf_fails_without_replacing_old_manual(tmp_path: Path) -> None:
    repo_root, source, target, config = _repo_layout(tmp_path)
    target.mkdir(parents=True)
    old_pdf = target / "current.pdf"
    _write_text_pdf(old_pdf, "Airport Information Current Manual")
    old_hash = sha256_file(old_pdf)
    (source / "broken.pdf").write_bytes(b"not a pdf")

    with pytest.raises(SyncError, match="无法打开或解析"):
        sync_airport_manual(config, repo_root=repo_root)

    assert sha256_file(old_pdf) == old_hash
    assert [path.name for path in target.glob("*.pdf")] == ["current.pdf"]


def test_matching_sha256_does_not_copy_or_rename(tmp_path: Path) -> None:
    repo_root, source, target, config = _repo_layout(tmp_path)
    target.mkdir(parents=True)
    source_pdf = source / "new-name.pdf"
    _write_text_pdf(source_pdf, "Airport Information Same Manual")
    old_pdf = target / "existing-name.pdf"
    shutil.copyfile(source_pdf, old_pdf)

    result = sync_airport_manual(config, repo_root=repo_root)

    assert result.changed is False
    assert result.status == "UNCHANGED"
    assert old_pdf.exists()
    assert not (target / source_pdf.name).exists()


def test_changed_sha256_replaces_formal_pdf(tmp_path: Path) -> None:
    repo_root, source, target, config = _repo_layout(tmp_path)
    target.mkdir(parents=True)
    old_pdf = target / "Airport-Information-20260720.pdf"
    _write_text_pdf(old_pdf, "Airport Information Manual Revision 20260720")
    source_pdf = source / "Airport-Information-20260801.pdf"
    _write_text_pdf(source_pdf, "Airport Information Manual Revision 20260801")

    result = sync_airport_manual(config, repo_root=repo_root)

    assert result.changed is True
    assert not old_pdf.exists()
    assert (target / source_pdf.name).exists()
    assert sha256_file(target / source_pdf.name) == sha256_file(source_pdf)


def test_source_folder_can_come_from_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = tmp_path / "repo"
    source = tmp_path / "Flight Data"
    source.mkdir()
    config = repo_root / "config.json"
    repo_root.mkdir()
    config.write_text(
        json.dumps(
            {
                "source_folder": "${AIRPORT_MANUAL_SOURCE_FOLDER}",
                "target_folder": "knowledge/pdf",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("AIRPORT_MANUAL_SOURCE_FOLDER", str(source))

    loaded = load_config(config, repo_root=repo_root)

    assert loaded.source_folder == source.resolve()
    assert loaded.target_folder == (repo_root / "knowledge" / "pdf").resolve()


def test_target_folder_cannot_escape_repository(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    source = tmp_path / "Flight Data"
    source.mkdir()
    repo_root.mkdir()
    config = repo_root / "config.json"
    _write_config(config, source, "../private")

    with pytest.raises(SyncError, match="必须位于当前仓库内"):
        load_config(config, repo_root=repo_root)


def test_workflow_is_self_hosted_and_only_commits_validated_target() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    for required in (
        "name: Sync Airport Manual",
        "workflow_dispatch:",
        "runs-on: [self-hosted, Windows, X64, crew-calendar]",
        "AIRPORT_MANUAL_SOURCE_FOLDER: "
        "${{ vars.AIRPORT_MANUAL_SOURCE_FOLDER }}",
        "python tools/sync_airport_manual.py",
        "steps.sync_manual.outputs.changed == 'true'",
        "git add --all -- knowledge/pdf",
        'git commit -m "Update airport manual"',
        "git push origin HEAD:main",
    ):
        assert required in workflow
    for forbidden in (
        "actions/upload-artifact",
        "flight_preparation",
        "flight.ics",
        "crew_schedule.ics",
        "git add -A",
        "force",
    ):
        assert forbidden not in workflow
