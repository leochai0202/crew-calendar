"""Safely synchronize one validated airport manual PDF into the repository."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pypdf import PdfReader


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = REPO_ROOT / "config" / "airport_manual_sync.json"
SOURCE_ENV_PLACEHOLDER = re.compile(r"^\$\{([A-Z][A-Z0-9_]*)\}$")
MANUAL_KEYWORDS = (
    "机场特点汇总",
    "airport information",
    "典型不安全事件",
    "核心威胁",
    "运行特点",
)


class SyncError(RuntimeError):
    """A safe, user-facing synchronization failure."""


@dataclass(frozen=True)
class SyncConfig:
    source_folder: Path
    target_folder: Path


@dataclass(frozen=True)
class SyncResult:
    changed: bool
    status: str
    source_name: str
    sha256: str
    target_path: Path | None


def _resolve_config_value(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SyncError(f"配置项 {field_name} 不能为空")

    raw_value = value.strip()
    placeholder = SOURCE_ENV_PLACEHOLDER.fullmatch(raw_value)
    if placeholder:
        variable_name = placeholder.group(1)
        resolved = os.environ.get(variable_name, "").strip()
        if not resolved:
            raise SyncError(
                f"配置项 {field_name} 依赖的环境变量 {variable_name} 未设置"
            )
        return resolved

    return os.path.expandvars(raw_value)


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def load_config(
    config_path: Path = DEFAULT_CONFIG_PATH,
    *,
    repo_root: Path = REPO_ROOT,
) -> SyncConfig:
    try:
        raw_config = json.loads(config_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SyncError("机场手册同步配置文件不存在") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise SyncError(f"机场手册同步配置无法读取：{type(exc).__name__}") from exc

    if not isinstance(raw_config, dict):
        raise SyncError("机场手册同步配置必须是JSON对象")

    source_value = _resolve_config_value(
        raw_config.get("source_folder"), "source_folder"
    )
    target_value = _resolve_config_value(
        raw_config.get("target_folder"), "target_folder"
    )

    source_folder = Path(source_value).expanduser().resolve()
    target_candidate = Path(target_value).expanduser()
    if not target_candidate.is_absolute():
        target_candidate = repo_root / target_candidate
    target_folder = target_candidate.resolve()
    resolved_repo_root = repo_root.resolve()
    if not _is_within(target_folder, resolved_repo_root):
        raise SyncError("target_folder必须位于当前仓库内")

    return SyncConfig(
        source_folder=source_folder,
        target_folder=target_folder,
    )


def find_single_source_pdf(source_folder: Path) -> Path:
    if not source_folder.is_dir():
        raise SyncError("Flight Data源目录不存在或不是目录")

    try:
        pdf_files = sorted(
            (
                path
                for path in source_folder.iterdir()
                if path.is_file() and path.suffix.casefold() == ".pdf"
            ),
            key=lambda path: path.name.casefold(),
        )
    except OSError as exc:
        raise SyncError(f"无法读取Flight Data源目录：{type(exc).__name__}") from exc

    if len(pdf_files) != 1:
        raise SyncError(
            "Flight Data源目录必须且只能包含一个PDF，"
            f"当前检测到{len(pdf_files)}个"
        )
    return pdf_files[0]


def validate_airport_manual_pdf(pdf_path: Path) -> None:
    try:
        reader = PdfReader(str(pdf_path), strict=False)
        if reader.is_encrypted:
            raise SyncError("机场手册PDF已加密，无法安全读取")
        if not reader.pages:
            raise SyncError("机场手册PDF没有可读取页面")

        extracted_parts: list[str] = []
        matched_keyword = False
        for page in reader.pages:
            text = page.extract_text() or ""
            if text.strip():
                extracted_parts.append(text)
                searchable = "\n".join(extracted_parts).casefold()
                if any(keyword.casefold() in searchable for keyword in MANUAL_KEYWORDS):
                    matched_keyword = True
                    break
    except SyncError:
        raise
    except Exception as exc:
        raise SyncError(f"机场手册PDF无法打开或解析：{type(exc).__name__}") from exc

    if not extracted_parts:
        raise SyncError("机场手册PDF无法提取文本")
    if not matched_keyword:
        raise SyncError("PDF未包含可识别的机场手册关键词")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise SyncError(f"无法读取PDF进行SHA256校验：{type(exc).__name__}") from exc
    return digest.hexdigest()


def _target_pdfs(target_folder: Path) -> list[Path]:
    if not target_folder.exists():
        return []
    if not target_folder.is_dir():
        raise SyncError("target_folder存在但不是目录")
    try:
        pdf_files = sorted(
            (
                path
                for path in target_folder.iterdir()
                if path.is_file() and path.suffix.casefold() == ".pdf"
            ),
            key=lambda path: path.name.casefold(),
        )
    except OSError as exc:
        raise SyncError(f"无法读取目标PDF目录：{type(exc).__name__}") from exc
    if len(pdf_files) > 1:
        raise SyncError("目标目录存在多个PDF，无法安全确定应替换的正式手册")
    return pdf_files


def _install_pdf_atomically(
    source_pdf: Path,
    target_folder: Path,
    source_hash: str,
) -> Path:
    try:
        target_folder.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise SyncError(f"无法创建目标PDF目录：{type(exc).__name__}") from exc
    destination = target_folder / source_pdf.name
    existing_pdfs = _target_pdfs(target_folder)
    previous_pdf = existing_pdfs[0] if existing_pdfs else None
    staged_path: Path | None = None
    new_destination_created = False

    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=".airport-manual-",
            suffix=".tmp",
            dir=target_folder,
            delete=False,
        ) as staged_file:
            staged_path = Path(staged_file.name)
            with source_pdf.open("rb") as source_stream:
                shutil.copyfileobj(source_stream, staged_file)
            staged_file.flush()
            os.fsync(staged_file.fileno())

        if sha256_file(staged_path) != source_hash:
            raise SyncError("机场手册暂存文件SHA256校验失败")

        os.replace(staged_path, destination)
        staged_path = None
        new_destination_created = previous_pdf != destination
        if previous_pdf is not None and previous_pdf != destination:
            try:
                previous_pdf.unlink()
            except OSError:
                destination.unlink(missing_ok=True)
                raise
        return destination
    except SyncError:
        raise
    except Exception as exc:
        raise SyncError(f"机场手册原子替换失败：{type(exc).__name__}") from exc
    finally:
        if staged_path is not None:
            staged_path.unlink(missing_ok=True)
        if new_destination_created and previous_pdf is not None and previous_pdf.exists():
            destination.unlink(missing_ok=True)


def sync_airport_manual(
    config_path: Path = DEFAULT_CONFIG_PATH,
    *,
    repo_root: Path = REPO_ROOT,
) -> SyncResult:
    config = load_config(config_path, repo_root=repo_root)
    source_pdf = find_single_source_pdf(config.source_folder)
    validate_airport_manual_pdf(source_pdf)
    source_hash = sha256_file(source_pdf)

    for existing_pdf in _target_pdfs(config.target_folder):
        if sha256_file(existing_pdf) == source_hash:
            return SyncResult(
                changed=False,
                status="UNCHANGED",
                source_name=source_pdf.name,
                sha256=source_hash,
                target_path=existing_pdf,
            )

    destination = _install_pdf_atomically(
        source_pdf,
        config.target_folder,
        source_hash,
    )
    return SyncResult(
        changed=True,
        status="UPDATED",
        source_name=source_pdf.name,
        sha256=source_hash,
        target_path=destination,
    )


def _append_github_output(output_path: Path, result: SyncResult) -> None:
    with output_path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(f"changed={'true' if result.changed else 'false'}\n")
        stream.write(f"sync_result={result.status}\n")


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="同步配置JSON路径",
    )
    parser.add_argument(
        "--github-output",
        type=Path,
        help="可选的GitHub Actions输出文件路径",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_argument_parser().parse_args(argv)
    try:
        result = sync_airport_manual(args.config)
    except SyncError as exc:
        print("SYNC_RESULT=ERROR")
        print(f"SYNC_ERROR={exc}")
        return 1

    print(f"SYNC_RESULT={result.status}")
    print(f"SOURCE_PDF={result.source_name}")
    print(f"SHA256={result.sha256}")
    if args.github_output is not None:
        _append_github_output(args.github_output, result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
