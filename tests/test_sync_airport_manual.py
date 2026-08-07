import json
import shutil
from pathlib import Path

import pytest

from tools.sync_airport_manual import (
    SyncError,
    is_airport_manual_candidate,
    load_config,
    main,
    sha256_file,
    sync_airport_manual,
)


ROOT = Path(__file__).parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "sync-airport-manual.yml"


def _manual_name(version: str) -> str:
    return (
        "AirDropManual-机场特点汇总"
        f"(Airport Information){version}-Manual.pdf"
    )


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
    source = tmp_path / "Flight_Data"
    target = repo_root / "knowledge" / "pdf"
    config = repo_root / "config" / "airport_manual_sync.json"
    source.mkdir(parents=True)
    config.parent.mkdir(parents=True)
    _write_config(config, source)
    return repo_root, source, target, config


def _write_other_flight_data_files(source: Path) -> None:
    other_pdf_names = (
        "FCOM-Vol-1.pdf",
        "FCOM-Vol-2.PDF",
        "FCTM.pdf",
        "SOP.pdf",
        "标准操作程序.pdf",
        "操作指导手册.pdf",
        "飞行操作信息技术通告-1.pdf",
        "飞行操作信息技术通告-2.pdf",
        "QRH.pdf",
        "MEL.pdf",
    )
    for name in other_pdf_names:
        (source / name).write_bytes(b"not an airport manual")
    (source / "notes.yaml").write_text("private: ignored", encoding="utf-8")
    (source / "draft.docx").write_bytes(b"ignored")


def test_one_manual_is_selected_among_ten_other_pdfs(tmp_path: Path) -> None:
    repo_root, source, target, config = _repo_layout(tmp_path)
    _write_other_flight_data_files(source)
    source_pdf = source / _manual_name("20260801")
    _write_text_pdf(source_pdf, "Airport Information Manual Revision 20260801")

    result = sync_airport_manual(config, repo_root=repo_root)

    assert result.changed is True
    assert result.status == "UPDATED"
    assert result.top_level_pdf_count == 11
    assert result.ignored_pdf_count == 10
    assert [path.name for path in target.iterdir()] == [source_pdf.name]
    assert sha256_file(target / source_pdf.name) == sha256_file(source_pdf)


def test_fcom_fctm_and_sop_are_not_candidates(tmp_path: Path) -> None:
    repo_root, source, target, config = _repo_layout(tmp_path)
    _write_other_flight_data_files(source)

    with pytest.raises(SyncError, match="未找到文件名同时包含"):
        sync_airport_manual(config, repo_root=repo_root)

    assert not target.exists()


def test_two_manual_candidates_fail_and_report_every_name(tmp_path: Path) -> None:
    repo_root, source, target, config = _repo_layout(tmp_path)
    target.mkdir(parents=True)
    old_pdf = target / _manual_name("20260720")
    _write_text_pdf(old_pdf, "Airport Information Current Manual")
    old_hash = sha256_file(old_pdf)
    first_name = _manual_name("20260801")
    second_name = _manual_name("20260901")
    _write_text_pdf(source / first_name, "Airport Information Manual One")
    _write_text_pdf(source / second_name, "Airport Information Manual Two")

    with pytest.raises(SyncError, match="检测到多个机场特点汇总候选文件") as exc:
        sync_airport_manual(config, repo_root=repo_root)

    assert first_name in str(exc.value)
    assert second_name in str(exc.value)
    assert sha256_file(old_pdf) == old_hash
    assert [path.name for path in target.glob("*.pdf")] == [old_pdf.name]


def test_nested_manual_candidate_is_not_scanned(tmp_path: Path) -> None:
    repo_root, source, target, config = _repo_layout(tmp_path)
    nested = source / "flight-prep-update"
    nested.mkdir()
    _write_text_pdf(
        nested / _manual_name("20991231"),
        "Airport Information Nested Manual",
    )
    top_level_pdf = source / _manual_name("20260801")
    _write_text_pdf(top_level_pdf, "Airport Information Top Level Manual")

    result = sync_airport_manual(config, repo_root=repo_root)

    assert result.source_name == top_level_pdf.name
    assert result.top_level_pdf_count == 1
    assert [path.name for path in target.glob("*.pdf")] == [top_level_pdf.name]


@pytest.mark.parametrize(
    ("version", "extension"),
    (("20260720", ".pdf"), ("20270115", ".PDF"), ("Rev-A", ".pdf")),
)
def test_filename_version_changes_remain_candidates(
    tmp_path: Path, version: str, extension: str
) -> None:
    filename = _manual_name(version)
    candidate = tmp_path / f"{filename[:-4]}{extension}"
    candidate.write_bytes(b"candidate name only")

    assert is_airport_manual_candidate(candidate) is True


def test_corrupt_manual_does_not_replace_old_manual(tmp_path: Path) -> None:
    repo_root, source, target, config = _repo_layout(tmp_path)
    target.mkdir(parents=True)
    old_pdf = target / _manual_name("20260720")
    _write_text_pdf(old_pdf, "Airport Information Current Manual")
    old_hash = sha256_file(old_pdf)
    (source / _manual_name("20260801")).write_bytes(b"not a pdf")

    with pytest.raises(SyncError, match="无法打开或解析"):
        sync_airport_manual(config, repo_root=repo_root)

    assert sha256_file(old_pdf) == old_hash
    assert [path.name for path in target.glob("*.pdf")] == [old_pdf.name]


def test_matching_sha256_is_unchanged_without_rename(tmp_path: Path) -> None:
    repo_root, source, target, config = _repo_layout(tmp_path)
    target.mkdir(parents=True)
    source_pdf = source / _manual_name("20260801")
    _write_text_pdf(source_pdf, "Airport Information Same Manual")
    old_pdf = target / _manual_name("20260720")
    shutil.copyfile(source_pdf, old_pdf)

    result = sync_airport_manual(config, repo_root=repo_root)

    assert result.changed is False
    assert result.status == "UNCHANGED"
    assert old_pdf.exists()
    assert not (target / source_pdf.name).exists()


def test_changed_sha256_replaces_only_formal_manual(tmp_path: Path) -> None:
    repo_root, source, target, config = _repo_layout(tmp_path)
    target.mkdir(parents=True)
    old_pdf = target / _manual_name("20260720")
    _write_text_pdf(old_pdf, "Airport Information Manual Revision 20260720")
    source_pdf = source / _manual_name("20260801")
    _write_text_pdf(source_pdf, "Airport Information Manual Revision 20260801")
    _write_other_flight_data_files(source)

    result = sync_airport_manual(config, repo_root=repo_root)

    assert result.changed is True
    assert result.ignored_pdf_count == 10
    assert not old_pdf.exists()
    assert [path.name for path in target.iterdir()] == [source_pdf.name]
    assert sha256_file(target / source_pdf.name) == sha256_file(source_pdf)


def test_source_folder_can_come_from_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = tmp_path / "repo"
    source = tmp_path / "Flight_Data"
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
    source = tmp_path / "Flight_Data"
    source.mkdir()
    repo_root.mkdir()
    config = repo_root / "config.json"
    _write_config(config, source, "../private")

    with pytest.raises(SyncError, match="必须位于当前仓库内"):
        load_config(config, repo_root=repo_root)


def test_cli_reports_failed_safe_without_candidate(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _repo_root, _source, _target, config = _repo_layout(tmp_path)

    exit_code = main(["--config", str(config)])

    assert exit_code == 1
    assert "SYNC_RESULT=FAILED_SAFE" in capsys.readouterr().out


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
        "Flight_Data",
        "git add -A",
        "force",
    ):
        assert forbidden not in workflow
