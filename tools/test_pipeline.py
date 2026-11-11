"""Run the native Rise and Fall persistence smoke test on a prepared capture."""

import argparse
import json
import os
from pathlib import Path


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def request_action(client, view, kind):
    catalogue = view['decisions']
    matches = [row for row in catalogue['candidates'] if row['action']['kind'] == kind]
    require(len(matches) == 1, f'Expected one offered {kind} command')
    chosen = matches[0]
    reply = client.act(0, catalogue['decision_id'], chosen['candidate_id'])
    command = client.last_command_receipt(0)['command_result']
    require(command['requested_action'] == chosen['action'], f'GameCore receipt differs for {kind}')
    return reply, command


def select_action(client, view, kind):
    reply, command = request_action(client, view, kind)
    require(command['status'] == 'completed' and reply['applied_action'] == command['requested_action'],
            f'GameCore did not confirm {kind}: {command}')
    return reply, command['requested_action']


def step_to_next_active_turn(client, view):
    turn = view['observation']['turn']
    for _ in range(3):
        previous_decision = view['decisions']['decision_id']
        view, command = request_action(client, view, 'force_end_turn')
        if command['status'] == 'completed':
            require(view['applied_action'] == command['requested_action'],
                    'GameCore completed a different action')
            break
        controls = view['decisions']['turn_controls']
        # The engine may interrupt end-turn processing and return a fresh
        # decision on the same turn. Only the new catalogue can authorize retry.
        require(command['status'] == 'submitted'
                and command['reason'] == 'native_turn_reactivated_same_turn'
                and controls['turn'] == turn and controls['active'] is True
                and view['applied_action'] is None
                and view['decisions']['decision_id'] != previous_decision,
                f'GameCore did not confirm force_end_turn: {command}')
    else:
        raise RuntimeError('GameCore reactivated the same turn three times')
    for polls in range(21):
        controls = view['decisions']['turn_controls']
        if controls['turn'] == turn + 1 and controls['active'] and controls['active_complete']:
            return view
        if controls['turn'] > turn + 1 or polls == 20:
            break
        view = client.poll(0)
    raise RuntimeError('GameCore did not reach the next active local turn in the poll budget')


def supervised_close(backend):
    report = backend.report or {}
    require(report.get('reaped') is True and report.get('normal_destroy_called') is True
            and report.get('exit_code') == 90 and report.get('error') is None,
            f'Native shutdown was not verified: {backend.run}')
    return report['sampled_memory_peaks']['private_bytes']


def produce(backend_type, client_type, options):
    backend = backend_type(**options, checkpoint_on_close=True)
    with client_type(backend) as client:
        initial = client.reset()
        print(f'Official capture loaded: {backend.run}', flush=True)
        require(not initial['observation']['cities'], 'Smoke fixture must start before settlement')
        founded, action = select_action(client, initial, 'found_city')
        cities = founded['observation']['cities']
        require(len(cities) == 1 and (cities[0]['x'], cities[0]['y']) == (action['x'], action['y'])
                and all(unit['id'] != action['unit_id'] for unit in founded['observation']['units']),
                'The native city and consumed founder were not observed')
        saved = step_to_next_active_turn(client, founded)
        require(cities[0]['id'] in {city['id'] for city in saved['observation']['cities']},
                'Founded city is missing at the save boundary')
        print(f'Native turn reached: {saved["observation"]["turn"]}', flush=True)
        client.close(0)
    peak = supervised_close(backend)
    reference = backend.checkpoint
    require(reference is not None, 'Native checkpoint was not published')
    print(f'Native checkpoint: {json.dumps(reference)}', flush=True)
    return reference, saved, backend.run, peak


def resume(backend_type, client_type, options, reference, expected):
    backend = backend_type(**options, checkpoint=reference)
    with client_type(backend) as client:
        view = client.reset()
        require(view['observation'] == expected['observation'],
                'The restored player observation differs from the saved observation')
        saved_candidates = {row['candidate_id']: row['action']
                            for row in expected['decisions']['candidates']}
        candidates = {row['candidate_id']: row['action'] for row in view['decisions']['candidates']}
        require(candidates == saved_candidates, 'The restored choices differ from the saved choices')
        require(view['sequence'] == 0 and client.last_command_receipt(0) is None,
                'A command receipt carried over into the new native session')
        require(view['episode_id'] != expected['decisions']['episode_id']
                and view['game_generation'] != expected['decisions']['game_generation'],
                'The native session identity was reused')
        client.close(0)
    return view, backend.run, supervised_close(backend)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--resources', type=Path, required=True, help='Private civ6-rl-lab root')
    parser.add_argument('--resume', nargs=2, metavar=('CHECKPOINT', 'SHA256'),
                        help='Qualify reload of an existing, hash-pinned checkpoint')
    args = parser.parse_args()
    root = args.resources.resolve(strict=True)
    os.environ['CIV6_HOST_RESOURCE_ROOT'] = str(root)

    from civ6_host.runtime.backend import NetworkBackend
    from civ6_host.runtime.execution_images import _XP1_PROFILE
    from civ6_host.runtime.network_checkpoint import manifest
    from civ6_host.runtime.xp1_prepared_reader_transition import PACKAGE_RELATIVE, PACKAGE_SHA256
    from civ6_host.runtime.xp1_saved_load import REFERENCE
    from civ6_host.session_client import SessionClient

    options = dict(resources=root, official_bundle=dict(zip(('path', 'sha256'), REFERENCE)),
                   prepared_capture=dict(path=str(root / PACKAGE_RELATIVE), sha256=PACKAGE_SHA256),
                   input_profile='xp1-lan', execution_image_profile=_XP1_PROFILE.id,
                   run_root=root / 'work/x1sm', lifetime_seconds=420, round_limit=2)
    producer_run = None
    peaks = []
    if args.resume:
        reference = dict(path=args.resume[0], sha256=args.resume[1])
        expected = manifest(reference, official_bundle=REFERENCE, execution_image=_XP1_PROFILE)
        require(len(expected['observation']['cities']) == 1,
                'The retained smoke checkpoint must contain the founded city')
    else:
        reference, expected, producer_run, peak = produce(NetworkBackend, SessionClient, options)
        peaks.append(peak)
    view, restored_run, peak = resume(NetworkBackend, SessionClient, options, reference, expected)
    peaks.append(peak)
    print(json.dumps(dict(verified=True, checkpoint=reference, restored_turn=view['observation']['turn'],
                          cities=len(view['observation']['cities']),
                          producer_run=str(producer_run) if producer_run is not None else None,
                          restored_run=str(restored_run), peak_private_bytes=max(peaks))), flush=True)


if __name__ == '__main__':
    main()
