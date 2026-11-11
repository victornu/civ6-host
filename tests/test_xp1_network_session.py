"""XP1 parent preparation and real pipe-protocol validation, without a process.

Native preparation and process creation are explicit fixture boundaries. These
tests do not qualify the fixture response as a native gameplay observation.
"""
from contextlib import ExitStack
from copy import deepcopy
import ctypes
import hashlib
import importlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch
from uuid import uuid4

from civ6_host.contracts import network_turn
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256
from civ6_host.runtime.native.network_session import NativeNetworkSession, xp1_loaded_close_evidence
from civ6_host.runtime.native.native_action_session import NativeActionSession
from civ6_host.runtime.native.native_saved_session import ROOT, MEMORY_LIMIT
from civ6_host.runtime.native.native_saved_session_protocol import outcome
from civ6_host.runtime.native.native_victory_episode import POLICY_ID
from civ6_host.runtime.network_protocol import SCHEMA, validate_network_response
from civ6_host.runtime.xp1_saved_load import REFERENCE
from civ6_host.runtime.xp1_session_result import result_provenance
from civ6_host.runtime import xp1_session_inputs as inputs
from test_player_view import public_observation


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reset_reply(session):
    """Synthetic wire fixture validated by the unmodified shared protocol."""
    episode = str(uuid4())
    identity = dict(episode_id=episode, game_generation='native-'+episode)
    controls = dict(schema=network_turn.TURN_CONTROLS_SCHEMA, player_id=0, turn=1,
                    active=True, active_complete=True, can_unready=False, timer_elapsed=False)
    decisions = dict(schema=network_turn.CAPABILITY_SCHEMA, **identity, sequence=0,
        player_id=0, turn=1, turn_controls=controls, candidates=[],
        families=dict(found_city=dict(status='queried_complete', candidate_ids=[]),
            other_human_actions=dict(status='unqualified', reason='fixture_not_full_inventory')),
        family_inventory_complete=False, complete_action_space=False)
    decisions['decision_id'] = network_turn.digest(decisions)
    native = dict(schema='civ6rl.native_victory_episode.observation.v1', **identity,
        policy_id=POLICY_ID, player_id=0, current_game_turn=1,
        observation_only=True, eligible_for_training=False, exposed_to_learner=False,
        global_engine_terminal=None, engine_halted=None,
        episode_terminated=False, winner_present=False,
        **result_provenance(XP1_CORE_SHA256))
    return dict(stage='official_session_response', schema=SCHEMA, nonce=session.nonce,
        **identity, sequence=0, operation='reset', observation=public_observation(0, 1),
        rounds=0, outcome=outcome(native, 0, session.round_limit,
                                 maximum=session.protocol_class.max_round_limit),
        decisions=decisions, command_result=dict(status='none', reason=None, requested_action=None),
        applied_action=None, automatic_choices_applied=False, action_interface_complete=False,
        strategic_training_ready=False, session=dict(game_mode='LAN',
            turn_phase='TURNPHASE_SIMULTANEOUS', turn=1, local_player_id=0,
            human_player_ids=[0], active_human_player_ids=[0]))


class Fixture:
    def __init__(self):
        self.stack = ExitStack()
        self.folder = Path(self.stack.enter_context(tempfile.TemporaryDirectory(
            prefix='xp1-session-fixtures-', dir=ROOT/'work')))
        self.package_path = self.folder/'prepared.json'
        self.package_path.write_text('{}', encoding='utf-8')
        self.package = dict(path=str(self.package_path), sha256=digest(self.package_path))
        # The OS launch is replaced; source/build selection still sees the real
        # pinned binary instead of a fake hash that no stdout profile admits.
        from civ6_host.runtime.paths import resource_root
        self.executable = resource_root()/inputs.SAVED_UI_HOST[0]
        self.proof = self.folder/'source-proof.json'
        self.proof.write_text('{"fixture":true}', encoding='utf-8')
        self.captured = NS(reference=REFERENCE, initial_turn=1)
        self.copies, self.spawns, self.resources, self.sessions = [], [], [], []
        self.win = NS(job=Mock(return_value=object()))

    def __enter__(self):
        from civ6_host.runtime.native import native_probe
        from civ6_host.runtime import session_launch, provenance, capture_admission, capture_candidates
        self.stack.enter_context(patch.object(native_probe, 'Windows', return_value=self.win))
        self.stack.enter_context(patch.object(provenance, 'verify_installation'))
        self.consume = self.stack.enter_context(patch.object(capture_candidates,
            'consume_input_handoff', return_value=self.captured))
        self.sources = self.stack.enter_context(patch.object(inputs, 'prepare_sources', side_effect=
            lambda *args, **kwargs: ({str(self.package_path):self.package['sha256'],
                                     str(self.executable):digest(self.executable)}, self.executable)))
        self.stack.enter_context(patch.object(inputs, 'prepare_private_fixture', side_effect=self.prepare))
        self.stack.enter_context(patch.object(capture_admission, 'configure_prepared_closure',
            side_effect=lambda closure, captured: captured is self.captured))
        for name in ('xp1_session_view', 'xp1_session_result', 'xp1_status_profiles', 'xp1_session_admission'):
            module = importlib.import_module('civ6_host.runtime.'+name)
            self.stack.enter_context(patch.object(module, 'source_dependencies',
                return_value={str(self.proof):digest(self.proof)}))
        self.stack.enter_context(patch.object(NativeNetworkSession, '_check_reset_resources',
            lambda session, phase: self.resources.append(phase)))
        self.stack.enter_context(patch.object(session_launch.subprocess, 'Popen', side_effect=self.spawn))
        self.stack.enter_context(patch.object(session_launch.threading, 'Thread'))
        self.stack.enter_context(patch.object(NativeNetworkSession, '_send'))
        self.stack.enter_context(patch.object(NativeNetworkSession, '_receive', reset_reply))
        self.stack.enter_context(patch.object(NativeNetworkSession, '_fail',
            lambda s, reason, error=None: setattr(s, 'fixture_failure', (reason, error))))
        self.stack.enter_context(patch.object(NativeNetworkSession, '_finish',
            lambda s: setattr(s, 'finished', True)))
        for name in ('CDLL', 'WinDLL'):
            self.stack.enter_context(patch.object(ctypes, name, side_effect=AssertionError('DLL forbidden')))
        return self

    def __exit__(self, *args):
        for session in self.sessions:
            stream = getattr(session, 'command_log', None)
            if stream is not None and not stream.closed:
                stream.close()
        return self.stack.__exit__(*args)

    def session(self, **kwargs):
        values = dict(input_profile='xp1-lan', official_bundle=dict(zip(('path','sha256'), REFERENCE)),
                      prepared_capture=self.package, lifetime_seconds=120)
        values.update(kwargs)
        session = NativeNetworkSession(self.folder, **values)
        self.sessions.append(session)
        return session

    def prepare(self, run, captured, pins):
        if captured is not self.captured:
            raise AssertionError('Foreign prepared bundle')
        fixture = run/'private'/'manifest.json'
        fixture.parent.mkdir()
        fixture.write_text('{}', encoding='utf-8')
        database = fixture.parent/'gameplay.sqlite'
        database.write_bytes(b'private fixture')
        pins[str(fixture)] = digest(fixture)
        pins[str(database)] = digest(database)
        self.copies.append(database)
        return fixture, dict(workers=[dict(manifest_path=str(fixture))], timings_seconds={})

    def spawn(self, args, **kwargs):
        self.spawns.append((args, kwargs))
        return NS(stdin=object(), stdout=object(), stderr=object())


class XP1NetworkSessionTests(unittest.TestCase):
    def test_v5_cancel_offer_and_waiting_null_orders_cross_actual_parent_admission(self):
        from test_capability_world_contract import value as world_value
        from test_capability_unit_orders import extend
        from test_session_capabilities import observation
        for waiting in (False,True):
            with self.subTest(waiting=waiting),Fixture() as f:
                session=f.session()
                def reply(s):
                    response=reset_reply(s);obs=observation()
                    identity=NS(episode_id=response['episode_id'],game_generation=response['game_generation'])
                    response['observation']=obs
                    response['decisions']=extend(world_value(identity,obs,waiting=waiting),obs,unavailable=waiting)
                    if waiting:response['session']['active_human_player_ids']=[]
                    return response
                with patch.object(NativeNetworkSession,'_receive',reply):
                    response=session.reset()
                self.assertFalse(session.unit_order_cancel_diagnostic)
                self.assertTrue(session._cancel_offer_admitted())
                self.assertEqual(session.protocol.catalogues[0],response['decisions'])
                if waiting:
                    self.assertIsNone(response['decisions']['unit_orders'])
                else:
                    self.assertTrue(any(r['action']['item_type']=='UNITCOMMAND_CANCEL'
                        for r in response['decisions']['unit_orders']['offers']))

    def test_xp1_cancel_admission_rejects_foreign_or_absent_source_receipt(self):
        with Fixture() as f:
            session=f.session();response=session.reset()
            original=deepcopy(session._xp1_unit_order_source_admission)
            for receipt in (None,dict(original,source_sha256=('f'*64,)*3),
                            dict(original,official_bundle=('foreign','0'*64))):
                session._xp1_unit_order_source_admission=receipt
                with self.subTest(receipt=receipt),self.assertRaisesRegex(ValueError,'exact bundle and sources'):
                    session._accepted_response(response)
            session._xp1_unit_order_source_admission=original
            self.assertTrue(session._cancel_offer_admitted())

    def test_explicit_constructor_scope_and_base_reset_are_preserved(self):
        with Fixture() as f:
            session = f.session()
            self.assertIs(session.protocol_class, NativeNetworkSession.protocol_class)
            for change in (dict(input_profile='xp2'), dict(prepared_capture=None),
                           dict(lifetime_seconds=1501), dict(checkpoint_on_close=1),
                           dict(city_management_diagnostic=True), dict(world_input_diagnostic=True),
                           dict(_admitted_bundle=object()), dict(privileged_critic_diagnostic=True)):
                with self.subTest(change=change), self.assertRaises(ValueError):
                    f.session(**change)
            with self.assertRaises(ValueError):
                f.session(input_profile='lan')
            base = f.session(input_profile='lan', prepared_capture=None)
            with patch.object(NativeActionSession, 'reset', return_value='base-original') as reset:
                self.assertEqual(base.reset(), 'base-original')
                reset.assert_called_once_with()
            self.assertFalse(f.spawns)

    def test_checkpoint_option_pins_selected_save_sources_in_actual_parent_closure(self):
        with Fixture() as f:
            session = f.session(checkpoint_on_close=True)
            from civ6_host.runtime import xp1_checkpoint_profile
            with patch.object(xp1_checkpoint_profile, 'source_dependencies',
                              return_value={str(f.proof):digest(f.proof)}):
                session.reset()
            closure = json.loads((session.run/'closure.json').read_bytes())
            self.assertIs(closure['checkpoint_on_close'], True)
            self.assertEqual(closure['input_profile'], 'xp1-lan')
            self.assertEqual(closure['pins'][str(f.proof)], digest(f.proof))

    def test_checkpoint_head_rejects_foreign_engine_and_ancestry_refuses_before_spawn(self):
        from civ6_host.runtime import network_checkpoint, xp1_checkpoint_profile

        reference = ('work/retained/checkpoint.json', 'a' * 64)
        checkpoint = dict(zip(('path', 'sha256'), reference))
        source = dict(zip(('path', 'sha256'), REFERENCE))
        with Fixture() as f, patch.object(network_checkpoint, 'normalize', return_value=reference), \
                patch.object(network_checkpoint, '_read', return_value={
                    'schema': network_checkpoint.SCHEMA,
                    'core_sha256': '0' * 64, 'source_official_bundle': source}) as read, \
                patch.object(network_checkpoint, '_validate_lineage',
                             side_effect=ValueError('Checkpoint ancestor changed')) as walk, \
                patch.object(xp1_checkpoint_profile, 'source_dependencies', return_value={}):
            with self.assertRaisesRegex(ValueError, 'another engine or official capture'):
                f.session(checkpoint=checkpoint)
            read.return_value['core_sha256'] = XP1_CORE_SHA256
            session = f.session(checkpoint=checkpoint)
            walk.assert_not_called()
            with self.assertRaisesRegex(ValueError, 'ancestor changed'):
                session.reset()
            walk.assert_called_once()
            self.assertEqual(walk.call_args.args, (reference,))
            self.assertFalse(f.spawns)

    def test_reset_reuses_preparers_launch_and_real_protocol_without_base_catalogues(self):
        with Fixture() as f:
            session = f.session()
            with patch.object(NativeActionSession, '_configure_closure',
                              side_effect=AssertionError('Base admission forbidden')):
                response = session.reset()
            self.assertEqual(f.resources, ['before_preflight', 'after_preflight'])
            f.sources.assert_called_once_with(f.captured, f.package, postload160=True,
                publish_cache=True, close_loaded=True, observe_player=True, unit_commands=True,
                core_sha256=XP1_CORE_SHA256)
            self.assertEqual(session.protocol.core_sha256, XP1_CORE_SHA256)
            self.assertEqual(session.protocol.session, response['session'])
            self.assertEqual(session.protocol.catalogues[0], response['decisions'])
            self.assertIs(session.response_validator, validate_network_response)
            closure = json.loads((session.run/'closure.json').read_bytes())
            self.assertEqual(closure['prepared_capture'], f.package)
            self.assertEqual(closure['official_bundle'], dict(zip(('path','sha256'), REFERENCE)))
            self.assertEqual(closure['nonce'], session.nonce)
            self.assertEqual(closure['input_profile'], 'xp1-lan')
            self.assertEqual(closure['lifetime_seconds'], 120)
            self.assertNotIn('unit_command', closure)
            self.assertNotIn(str(session.run/'closure.json'), closure['pins'])
            self.assertEqual(session.pins[str(session.run/'closure.json')], digest(session.run/'closure.json'))
            for filename in ('network_session.py', 'network_worker.py', 'xp1_session_view.py',
                             'xp1_session_result.py', 'xp1_status_profiles.py', 'xp1_session_admission.py'):
                self.assertTrue(any(Path(name).name == filename for name in closure['pins']), filename)
            self.assertIn(str(f.proof), closure['pins'])
            args, options = f.spawns[0]
            self.assertEqual(args[0], str(f.executable))
            self.assertEqual(Path(args[2]).name, 'network_worker.py')
            self.assertNotIn('PYTHONPATH', options['env'])
            self.assertEqual(options['env'][inputs.SAVED_LOAD_CLOSURE_ENV], digest(session.run/'closure.json'))
            self.assertEqual(json.loads(options['env']['CIV6_HOST_PREPARED_CAPTURE']), f.package)
            self.assertEqual(f.win.job.call_args.args[1], MEMORY_LIMIT)
            session._send.assert_called_once_with(b'go\n')
            self.assertEqual(session.last, response)

    def test_second_reset_requires_reap_and_gets_new_private_inputs_nonce_and_episode(self):
        with Fixture() as f:
            session = f.session()
            first = session.reset()
            prior_run, prior_nonce = session.run, session.nonce
            session.command_log.close()
            session.finished = True
            session.report = dict(reaped=False)
            with self.assertRaisesRegex(RuntimeError, 'not reaped'):
                session.reset()
            self.assertEqual(len(f.spawns), 1)
            session.report = dict(reaped=True, episode_id=first['episode_id'], pid=123)
            (prior_run/'supervisor.json').write_text(json.dumps(session.report), encoding='utf-8')
            second = session.reset()
            self.assertNotEqual(session.run, prior_run)
            self.assertNotEqual(session.nonce, prior_nonce)
            self.assertNotEqual(second['episode_id'], first['episode_id'])
            self.assertEqual(len(set(f.copies)), 2)
            closure = json.loads((session.run/'closure.json').read_bytes())
            self.assertTrue(closure['replaces']['previous_reaped'])
            self.assertEqual(closure['replaces']['episode_id'], first['episode_id'])

    def test_common_reset_validation_rejects_base_outcome_and_foreign_nonce(self):
        from civ6_host.runtime.xp1_session_result import BASE_CORE_SHA256
        for mutation in ('base', 'nonce'):
            with self.subTest(mutation=mutation), Fixture() as f:
                session = f.session()
                def bad(s):
                    value = reset_reply(s)
                    if mutation == 'nonce':
                        value['nonce'] = '0'*32
                    else:
                        value['outcome']['native_victory'].update(result_provenance(BASE_CORE_SHA256))
                    return value
                with patch.object(NativeNetworkSession, '_receive', bad), self.assertRaises(ValueError):
                    session.reset()
                self.assertEqual(session.fixture_failure[0], 'reset_failed')
                self.assertIsNone(session.last)

    def test_prelaunch_failure_keeps_failed_inputs_but_restores_supervised_ancestry(self):
        for failed_phase in ('private_fixture', 'closure'):
            with self.subTest(phase=failed_phase), Fixture() as f:
                session = f.session()
                initial = session.reset()
                session.command_log.close()
                session.finished = True
                session.report = dict(reaped=True, episode_id=initial['episode_id'], pid=123)
                (session.run/'supervisor.json').write_text(json.dumps(session.report), encoding='utf-8')
                prior_run, prior_pins, prior_nonce = session.run, session.pins, session.nonce
                prior_report, prior_last = session.report, session.last
                if failed_phase == 'private_fixture':
                    def fail_copy(*args):
                        f.prepare(*args)
                        raise OSError('fixture copy interrupted')
                    injection = patch.object(inputs, 'prepare_private_fixture', side_effect=fail_copy)
                else:
                    original = session._write_private_closure
                    def fail_closure(*args, **kwargs):
                        original(*args, **kwargs)
                        raise OSError('closure preparation interrupted')
                    injection = patch.object(session, '_write_private_closure', side_effect=fail_closure)
                with injection, self.assertRaisesRegex(OSError, 'interrupted'):
                    session.reset()
                self.assertEqual(len(f.spawns), 1)
                self.assertEqual(session.run, prior_run)
                self.assertEqual(session.runs, [prior_run])
                self.assertIs(session.pins, prior_pins)
                self.assertEqual(session.nonce, prior_nonce)
                self.assertIs(session.report, prior_report)
                self.assertIs(session.last, prior_last)
                failure = session.last_preparation_failure
                failed_run = Path(failure['run_directory'])
                record = json.loads((failed_run/'parent-preparation-failure.json').read_bytes())
                self.assertEqual(record['phase'], failed_phase)
                self.assertEqual(record['previous_supervised_run'], str(prior_run))
                self.assertIs(record['native_process_started'], False)
                self.assertIs(record['supervisor_report_created'], False)
                self.assertTrue((failed_run/'private'/'gameplay.sqlite').is_file())
                self.assertFalse((failed_run/'supervisor.json').exists())
                resumed = session.reset()
                closure = json.loads((session.run/'closure.json').read_bytes())
                self.assertEqual(closure['replaces']['episode_id'], initial['episode_id'])
                self.assertEqual(closure['replaces']['run'], prior_run.relative_to(ROOT).as_posix())
                self.assertNotEqual(resumed['episode_id'], initial['episode_id'])
                self.assertNotEqual(session.run, failed_run)
                self.assertEqual(len(f.spawns), 2)


_REVIEW = Path(__file__).resolve().parents[1]/'work/xp1-session-integration/native-session01/native-review.json'


@unittest.skipUnless(_REVIEW.is_file(), 'Retained private XP1 session evidence required')
class XP1LoadedCloseReportingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.review = json.loads(_REVIEW.read_bytes())

    def original(self, row):
        run = Path(row['run'])
        closure = json.loads((run/'closure.json').read_bytes())
        pins = dict(closure['pins'])
        pins[str(run/'closure.json')] = row['closure']['sha256']
        return run, json.loads((run/'supervisor.json').read_bytes()), pins

    def copy_fixture(self, destination):
        source, report, pins = self.original(self.review['runs'][0])
        (destination/'closure.json').write_bytes((source/'closure.json').read_bytes())
        pins[str(destination/'closure.json')] = pins.pop(str(source/'closure.json'))
        report['source_unchanged'] = {key:True for key in pins}
        result = json.loads((source/'loaded-lifetime-result.json').read_bytes())
        stages = {'before_xp1_saved_loaded_close', 'before_xp1_loaded_unload',
            'xp1_loaded_unload_returned', 'before_xp1_loaded_destroy',
            'xp1_loaded_destroy_returned', 'xp1_loaded_lifetime_closed',
            'xp1_saved_loaded_close_returned', 'official_session_response',
            'official_session_controlled_stop'}
        events = []
        with (source/'events.jsonl').open('rb') as stream:
            for line in stream:
                value = json.loads(line)
                if value['stage'] in stages and (value['stage'] != 'official_session_response'
                                                or value.get('operation') == 'close'):
                    events.append(value)
        self.write_fixture(destination, result, events)
        return report, pins, result, events

    def write_fixture(self, run, result, events, *, engine='xp1'):
        target = run/'loaded-lifetime-result.json'
        target.write_text(json.dumps(result), encoding='utf-8')
        for event in events:
            if event['stage'] == f'{engine}_loaded_lifetime_closed':
                event.clear(); event.update(stage=f'{engine}_loaded_lifetime_closed', **deepcopy(result))
            elif event['stage'] == 'xp1_saved_loaded_close_returned':
                event['receipt'] = dict(path=str(target), bytes=target.stat().st_size, sha256=digest(target))
        self.write_events(run, events)

    def write_events(self, run, events):
        (run/'events.jsonl').write_text(''.join(json.dumps(event)+'\n' for event in events), encoding='utf-8')

    def test_both_retained_native_closes_authenticate_without_rewriting_originals(self):
        for row in self.review['runs']:
            with self.subTest(run=row['run']):
                run, report, pins = self.original(row)
                paths = [run/name for name in ('closure.json', 'supervisor.json',
                                               'loaded-lifetime-result.json', 'events.jsonl')]
                before = [digest(path) for path in paths]
                evidence = xp1_loaded_close_evidence(run, report, pins)
                self.assertTrue(evidence['native_unload_and_destroy_returned'])
                self.assertFalse(evidence['native_calls_during_verification'])
                self.assertFalse(report['normal_destroy_called'])
                self.assertEqual(evidence['transcript_sha256'], row['transcript']['sha256'])
                self.assertEqual(before, [digest(path) for path in paths])

    def test_receipt_order_identity_source_and_steps_corruptions_refuse(self):
        for mutation in ('path', 'bytes', 'sha', 'order', 'steps', 'source', 'flag', 'episode', 'abort'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as folder:
                run = Path(folder).resolve()
                report, pins, result, events = self.copy_fixture(run)
                receipt = next(e for e in events if e['stage'] == 'xp1_saved_loaded_close_returned')['receipt']
                if mutation == 'path': receipt['path'] = str(run.parent/'foreign.json')
                elif mutation == 'bytes': receipt['bytes'] += 1
                elif mutation == 'sha': receipt['sha256'] = '0'*64
                elif mutation == 'order': events[2], events[3] = events[3], events[2]
                elif mutation == 'episode':
                    next(e for e in events if e['stage'] == 'official_session_response')['episode_id'] = str(uuid4())
                elif mutation == 'abort': events.append(dict(stage='official_session_refused', error='fixture refusal'))
                else:
                    if mutation == 'steps': result['steps'][1:3] = result['steps'][1:3][::-1]
                    elif mutation == 'source': result['source_sha256'] = '0'*64
                    else: result['native_destroy_called'] = False
                    self.write_fixture(run, result, events)
                self.write_events(run, events)
                with self.assertRaises(ValueError):
                    xp1_loaded_close_evidence(run, report, pins)

    def test_override_annotates_only_new_clean_xp1_reports_and_refuses_bad_receipt(self):
        for profile, failed, corrupt in (('lan',False,False), ('xp1-lan',True,False),
                                         ('xp1-lan',False,False), ('xp1-lan',False,True)):
            with self.subTest(profile=profile, failed=failed, corrupt=corrupt), tempfile.TemporaryDirectory() as folder:
                run = Path(folder).resolve()
                report, pins, _, _ = self.copy_fixture(run)
                if corrupt:
                    (run/'loaded-lifetime-result.json').write_bytes(b'changed')
                if failed:
                    report.update(exit_code=89, error='native refusal', stop_reason='command_failed')
                session = object.__new__(NativeNetworkSession)
                session.input_profile, session.finished, session.run, session.pins = profile, False, run, pins
                session.official_bundle = REFERENCE
                def finish_base(s):
                    s.report = deepcopy(report); s.finished = True
                with patch.object(NativeActionSession, '_finish', finish_base), patch(
                        'civ6_host.runtime.native.native_saved_session.write_json') as write:
                    session._finish()
                    if profile == 'lan' or failed:
                        write.assert_not_called()
                        self.assertFalse(session.report['normal_destroy_called'])
                    else:
                        write.assert_called_once_with(run/'supervisor.json', session.report)
                        self.assertEqual(session.report['normal_destroy_called'], not corrupt)
                        if corrupt:
                            self.assertEqual(session.report['stop_reason'], 'xp1_loaded_close_unverified')
                        else:
                            self.assertTrue(session.report['native_lifetime']['native_unload_and_destroy_returned'])


if __name__ == '__main__':
    unittest.main()
