"""Publish validated outputs atop current main without rebasing generated JSON."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile


def git(repo, *args, data=None, env=None, check=True):
    result = subprocess.run(['git', '-C', str(repo), *args], input=data,
                            capture_output=True, env=env)
    if check and result.returncode:
        raise RuntimeError('GIT_' + args[0].upper() + '_FAILED')
    return result


def blob(repo, ref, name):
    result = git(repo, 'show', f'{ref}:{name}', check=False)
    return result.stdout if result.returncode == 0 else None


def receipt_only_change(old, current):
    try:
        left, right = json.loads(old or b'{}'), json.loads(current or b'{}')
        left.pop('generation_attempt', None)
        right.pop('generation_attempt', None)
        # A newly created receipt may add only the matching target date.
        if not old:
            right.pop('target_date', None)
        return left == right
    except (ValueError, TypeError):
        return False


def publish(repo, base, candidates, target, *, attempts=3):
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', target):
        raise ValueError('INVALID_TARGET')
    allowed = re.compile(rf'flight_preparation/(?:{target}_meta\.json|{target}_航前准备(?:_EN|_\d+_[A-Za-z0-9]+(?:_EN)?)?\.txt|latest(?:_en)?\.txt|latest_meta\.json)$')
    payload = {}
    for name, content in candidates.items():
        if not allowed.fullmatch(name):
            raise ValueError('UNAPPROVED_OUTPUT_PATH')
        if content != blob(repo, base, name):
            payload[name] = content
    for _ in range(attempts):
        git(repo, 'fetch', 'origin', 'main')
        current = git(repo, 'rev-parse', 'FETCH_HEAD').stdout.decode().strip()
        # No stale tasks/manual/code may be published after an intervening edit.
        changed = git(repo, 'diff', '--name-only', base, current).stdout.decode().splitlines()
        if any(p.startswith(('crew_agents/', 'config/', 'knowledge/')) or p in
               {'flight.ics', 'crew_schedule.ics', 'airport_aliases.json'} for p in changed):
            raise RuntimeError('GENERATION_INPUTS_MOVED')
        updates = {}
        for name, content in payload.items():
            remote, original = blob(repo, current, name), blob(repo, base, name)
            if remote == content:
                continue
            if remote != original:
                if name == 'flight_preparation/latest_meta.json':
                    # Dated state is authoritative; never replace another
                    # concurrently generated date's latest pointer.
                    continue
                if name == f'flight_preparation/{target}_meta.json' and receipt_only_change(original, remote):
                    pass
                else:
                    raise RuntimeError('OUTPUT_MOVED:' + name)
            updates[name] = content
        if not updates:
            return current
        with tempfile.TemporaryDirectory(prefix='prep-publish-') as temporary:
            env = dict(os.environ, GIT_INDEX_FILE=str(Path(temporary) / 'index'),
                       GIT_AUTHOR_NAME='github-actions[bot]', GIT_COMMITTER_NAME='github-actions[bot]',
                       GIT_AUTHOR_EMAIL='41898282+github-actions[bot]@users.noreply.github.com',
                       GIT_COMMITTER_EMAIL='41898282+github-actions[bot]@users.noreply.github.com')
            git(repo, 'read-tree', current, env=env)
            for name, content in updates.items():
                sha = git(repo, 'hash-object', '-w', '--stdin', data=content).stdout.decode().strip()
                git(repo, 'update-index', '--add', '--cacheinfo', f'100644,{sha},{name}', env=env)
            tree = git(repo, 'write-tree', env=env).stdout.decode().strip()
            commit = git(repo, 'commit-tree', tree, '-p', current, '-m',
                         f'Publish validated flight preparation for {target}', env=env).stdout.decode().strip()
            result = git(repo, 'push', 'origin', f'{commit}:refs/heads/main', check=False)
            if result.returncode == 0:
                return commit
            # Response loss is checked before another bounded publication.
            git(repo, 'fetch', 'origin', 'main')
            observed = git(repo, 'rev-parse', 'FETCH_HEAD').stdout.decode().strip()
            if git(repo, 'merge-base', '--is-ancestor', commit, observed, check=False).returncode == 0:
                return commit
    raise RuntimeError('PUBLICATION_RETRY_EXHAUSTED')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', type=Path, default=Path('.'))
    parser.add_argument('--target-date', required=True)
    args = parser.parse_args()
    root = args.repo
    delivery = root / 'agent_output/flight_prep/public_delivery_state.json'
    if delivery.is_file():
        from scripts.deliver_flight_prep_copy import safe_public_payload
        state = safe_public_payload(json.loads(delivery.read_text(encoding='utf-8')))
        if state.get('schema') != 2 or state.get('target_date') != args.target_date:
            raise RuntimeError('INVALID_DELIVERY_STATE')
        name = f'flight_preparation/{args.target_date}_meta.json'
        base = git(root, 'rev-parse', 'HEAD').stdout.decode().strip()
        sha = publish(root, base, {name: delivery.read_bytes()}, args.target_date)
        print('FLIGHT_PREP_STATE=PUBLISHED');print('FLIGHT_PREP_COMMIT_SHA='+sha)
        return
    if not (root / 'flight_preparation/.success').is_file():
        print('FLIGHT_PREP_PUBLISH=NO_RELEASE'); return
    base = git(root, 'rev-parse', 'HEAD').stdout.decode().strip()
    meta = json.loads((root / f'flight_preparation/{args.target_date}_meta.json').read_text(encoding='utf-8'))
    if meta['status'] not in {'SUCCESS', 'PARTIAL_RELEASE'}:
        raise RuntimeError('NO_VALIDATED_RELEASE')
    names = [f'flight_preparation/{args.target_date}_meta.json', 'flight_preparation/latest_meta.json']
    for group in meta.get('prep_groups', []):
        if group.get('release_eligible') and group.get('status') == 'SUCCESS':
            names += ['flight_preparation/' + group[key] for key in ('output', 'english_output') if group.get(key)]
    if meta['status'] == 'SUCCESS':
        names += ['flight_preparation/' + name for name in
                  (f'{args.target_date}_航前准备.txt', f'{args.target_date}_航前准备_EN.txt', 'latest.txt', 'latest_en.txt')
                  if (root / 'flight_preparation' / name).is_file()]
    sha = publish(root, base, {name: (root/name).read_bytes() for name in names}, args.target_date)
    print('FLIGHT_PREP_PUBLISH=PUBLISHED'); print('FLIGHT_PREP_COMMIT_SHA=' + sha)


if __name__ == '__main__':
    main()
