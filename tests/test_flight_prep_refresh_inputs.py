from datetime import date
import json
from pathlib import Path

from crew_agents.flight_prep_inputs import generation_inputs
from scripts import check_flight_prep_schedule as checker
from tests.test_flight_prep_schedule import _repo_with_event, _write_success_state, _write_ics, _event, TARGET


def test_input_identity_tracks_code_template_and_selected_manual_not_ics_or_git(tmp_path):
    repo = tmp_path
    (repo / "crew_agents").mkdir()
    (repo / "config").mkdir()
    (repo / "knowledge/pdf").mkdir(parents=True)
    code = repo / "crew_agents/flight_prep_agent.py"
    code.write_text("original")
    template = repo / "config/prep_settings.json"
    template.write_text('{}')
    manual = repo / "knowledge/pdf/AirDropManual-机场特点20261019.pdf"
    manual.write_bytes(b"source-one")
    original = generation_inputs(repo, code_root=repo)
    for name in ("flight.ics", "crew_schedule.ics", "config/airport_experience.json"):
        (repo / name).write_text("ordinary calendar refresh")
    assert generation_inputs(repo, code_root=repo) == original
    for path in (code, template, manual):
        before = path.read_bytes()
        path.write_bytes(before + b"change")
        assert generation_inputs(repo, code_root=repo)["sha256"] != original["sha256"]
        path.write_bytes(before)
    old = repo / "knowledge/pdf/AirDropManual-机场特点20260720.pdf"
    old.write_bytes(b"not selected")
    assert generation_inputs(repo, code_root=repo) == original


def test_legacy_partial_refresh_receipt_prevents_repeat_without_changing_release(tmp_path):
    repo = _repo_with_event(tmp_path)
    _write_success_state(repo)
    path = repo / f"flight_preparation/{TARGET}_meta.json"
    state = json.loads(path.read_text(encoding="utf-8"))
    state.pop("generation_inputs")
    state.update(status="PARTIAL_RELEASE", prep_groups=[dict(status="SUCCESS", release_eligible=True, output="released.txt")])
    path.write_text(json.dumps(state), encoding="utf-8")
    (path.parent / "released.txt").write_text("LAST_GOOD")
    first = checker.evaluate_preparation(repo, TARGET)
    assert first.should_dispatch and first.reason == "generation_inputs_changed"
    receipt = checker.record_dispatched_generation(repo, TARGET, first)
    assert receipt.state_changed and receipt.state_files == (f"flight_preparation/{TARGET}_meta.json",)
    assert not checker.evaluate_preparation(repo, TARGET).should_dispatch
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved['status'] == 'PARTIAL_RELEASE'
    assert 'generation_inputs' not in saved  # a receipt is NOT a generated draft
    assert (path.parent / "released.txt").read_text() == "LAST_GOOD"
    assert not (path.parent / '.success').exists()
    (repo / 'config').mkdir()
    (repo / 'config/prep_settings.json').write_text('{"updated": true}')
    assert checker.evaluate_preparation(repo, TARGET).should_dispatch


def test_same_failed_safe_inputs_are_not_retried_but_new_inputs_are(tmp_path):
    repo = _repo_with_event(tmp_path)
    _write_success_state(repo)
    path = repo / f"flight_preparation/{TARGET}_meta.json"
    state = json.loads(path.read_text(encoding="utf-8"))
    state['status'] = 'FAILED_SAFE'
    path.write_text(json.dumps(state), encoding="utf-8")
    assert not checker.evaluate_preparation(repo, TARGET).should_dispatch
    (repo / 'config').mkdir()
    (repo / 'config/prep_settings.json').write_text('{"updated": true}')
    assert checker.evaluate_preparation(repo, TARGET).should_dispatch


def test_new_successful_inputs_settle_without_repeat(tmp_path):
    repo = _repo_with_event(tmp_path)
    _write_success_state(repo)
    assert not checker.evaluate_preparation(repo, TARGET).should_dispatch
    (repo / 'irrelevant.txt').write_text('ordinary unrelated commit')
    assert not checker.evaluate_preparation(repo, TARGET).should_dispatch


def test_cancellation_clears_prior_attempt_so_restored_same_flight_regenerates(tmp_path):
    repo = _repo_with_event(tmp_path)
    _write_success_state(repo)
    result = checker.evaluate_preparation(repo, TARGET)
    checker.record_dispatched_generation(repo, TARGET, result)
    _write_ics(repo / 'flight.ics', [])
    assert checker.evaluate_preparation(repo, TARGET).status == 'INVALIDATED_NO_TASK'
    _write_ics(repo / 'flight.ics', [_event()])
    assert checker.evaluate_preparation(repo, TARGET).should_dispatch


def test_failed_dispatch_does_not_record_a_successful_attempt(tmp_path, monkeypatch):
    from argparse import Namespace
    repo = _repo_with_event(tmp_path)
    _write_success_state(repo)
    path = repo / f'flight_preparation/{TARGET}_meta.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    data.pop('generation_inputs')
    path.write_text(json.dumps(data), encoding='utf-8')
    before = path.read_bytes()
    args = Namespace(repo=str(repo), target_date=str(TARGET), days_ahead=1,
        actual_start_utc='', scheduled_cron='', existing_only=False,
        github_output=str(tmp_path / 'output'), dispatch=True)
    monkeypatch.setattr(checker, 'parse_args', lambda: args)
    def fail(*args):
        raise RuntimeError('HTTP 403')
    monkeypatch.setattr(checker, 'dispatch_flight_preparation', fail)
    import pytest
    with pytest.raises(RuntimeError, match='403'):
        checker.main()
    assert path.read_bytes() == before
    assert checker.evaluate_preparation(repo, TARGET).should_dispatch


def test_existing_state_publisher_guards_the_snapshot_against_concurrent_generation():
    workflow = (Path(__file__).parents[1] / '.github/workflows/schedule.yml').read_text(encoding='utf-8')
    state_step = workflow.split('- name: Publish invalidated flight preparation state', 1)[1].split('- name:', 1)[0]
    assert '"--expected-main-sha", "${{ steps.ics_publish.outputs.commit_sha || steps.ics_publish.outputs.base_sha || steps.bootstrap.outputs.bootstrap_main_sha }}"' in state_step
    assert '"--status-prefix", "FLIGHT_PREP_STATE_API"' in state_step
    assert '"github_api_publish.py"' in state_step
