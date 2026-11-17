"""Content identity for preparation inputs, independent of Git/ICS refreshes."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def generation_inputs(repo: Path, *, code_root: Path | None = None) -> dict:
    # Import lazily so both the scheduler and the running generator use the
    # exact same manual resolver (including same-version fallback sources).
    from crew_agents.flight_prep_agent import airport_manual_candidate_chain

    code_root = code_root or Path(__file__).resolve().parents[1]
    files: dict[str, str] = {}

    def include(label: str, path: Path) -> None:
        if path.is_file():
            digest = hashlib.sha256()
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
            files[label] = digest.hexdigest()
        else:
            files[label] = "MISSING"

    for path in sorted((code_root / "crew_agents").glob("flight_prep*.py")):
        include(path.relative_to(code_root).as_posix(), path)
    for name in ("crew_agents/common.py", "crew_agents/ics_utils.py", "requirements-agent.txt"):
        include(name, code_root / name)
    for name in (
        "prep_settings.json", "pilot_profile.json", "operational_focus.json",
        "airport_english_names.json", "airport_iata.json", "airport_supplements.json",
        "user_confirmed_airport_facts.json", "flight_prep_english_overrides.json",
        "flight_prep_chinese_translations.json",
    ):
        include("config/" + name, repo / "config" / name)
    include("airport_aliases.json", repo / "airport_aliases.json")
    for path in airport_manual_candidate_chain(repo / "knowledge"):
        include(path.relative_to(repo.resolve()).as_posix(), path)
    # airport_experience is regenerated from calendar history; ICS content and
    # Git HEAD are deliberately not part of the generator/template identity.
    payload = {"schema": 1, "files": files}
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    return {"sha256": digest, **payload}
