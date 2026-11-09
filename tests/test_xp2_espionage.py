"""Saved-session spy composition with explicit native-call fixtures.

The actual SavedLoadOwner graph guards, catalogue seals, UI source builders,
wire parsers and adapter lifecycle run.  No Lua or GameCore code executes.
"""
from contextlib import ExitStack
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import threading
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from civ6_host.contracts import espionage
from civ6_host.runtime import xp2_espionage as adapter
from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
from civ6_host.runtime.execution_images import known_path, select
from civ6_host.runtime.native import native_player_observation, native_saved_espionage as native
from civ6_host.runtime.native.native_episode_identity import initialize_episode
from civ6_host.runtime.xp1_saved_load_owner import SavedLoadOwner


class SpySession:
    def __init__(self):
        self.calls, self.emitted, self.delivered = [], [], []
        self.request_result = b'submitted'
        self.archive_count = 1
        self.archive = b'fixture-native-spy-order-archive'
        self.effect_confirmed = True
        self.effect_override = None
        self.query_hook = None
        self.leave_deferred = False
        self.publication_increment = 1
        self.observation = dict(player_id=0, turn=17, width=4, height=3,
                                units=[dict(id=9, owner=0, x=2, y=1)], cities=[])
        self.action = dict(kind='spy_mission', unit_id=9,
            operation_type='UNITOPERATION_SPY_STEAL_TECH_BOOST', operation_hash=0xf0000011,
            mode='start', x=2, y=1, plot_id=6)
        self.before = dict(schema=espionage.SCHEMA, player_id=0, turn=17,
            width=4, height=3, capacity=1,
            spies=[dict(unit_id=9, name='Ada', level=1, x=2, y=1,
                        operation=-1, turns_remaining=-1)],
            captured=[], off_map=[], history=[], offers=[dict(action=deepcopy(self.action),
                turns=6, success_percent=80, failure_percent=10, captured_or_killed_percent=10)])
        self.after = deepcopy(self.before)
        self.after['spies'][0].update(operation=12, turns_remaining=6)
        self.after['offers'] = []
        image_id = 'xp2-gamecore-current-092abfbb'
        self.image = select(image_id, core_path=known_path(image_id))
        p = self.prefix = NS(runtime=NS(evaluate_text=self.evaluate), ui_child=object(),
                            quarantined=False)
        identity = initialize_episode(p)
        b = self.backend = NS(prefix=p, core=NS(_civ6_host_execution_image=self.image),
            host=object(), context=object(), inputs=object(), raw_load_result={},
            load_abi=NS(core_sha256=XP2_CORE_SHA256),
            _xp2_postload_requested=True, _saved_load_candidate=True,
            _xp1_commands_requested=True, poisoned=False, destroyed=False,
            stage='xp1-continuation-ready', busy=False,
            check_thread=self.check_thread, control=self.control)
        c = self.continuation = NS(owner=b, prefix=p, identity=identity,
            observation=deepcopy(self.observation), sequence=7, publication_count=0,
            check=self.check_continuation, flush_trade_feedback=self.flush,
            transport=NS(require_empty_native_queue=self.require_empty))
        p.actions = NS(pending=[], deliver_one=self.deliver)
        p.deferred_events = NS(pending=[], drain_empty_receivers=self.drain)
        p.view_publisher = NS(publish=self.publish)
        saved = self.saved = SavedLoadOwner._allocate(
            dict(post160_candidate=True, unit_commands_candidate=True), self.emit)
        saved.backend = saved._backend = b
        saved._engine_sha256 = XP2_CORE_SHA256
        saved.prefix, saved.core, saved.host = p, b.core, b.host
        saved.context, saved.inputs, saved.receipt = b.context, b.inputs, b.raw_load_result
        saved.continuation, saved.phase, saved._running = c, 'commands', True
        b._saved_stage_owner, b._xp1_continuation = saved, c
        self.owner_thread = threading.get_ident()
        self.stack = ExitStack()
        self.stack.enter_context(patch.object(native_player_observation, 'observe_player', self.observe))

    def close(self):
        self.stack.close()

    def check_thread(self):
        if threading.get_ident() != self.owner_thread:
            raise RuntimeError('Fixture native backend belongs to another thread')

    def check_continuation(self, *, active):
        expected = 'xp1-continuation-active' if active else 'xp1-continuation-ready'
        if self.backend.stage != expected or self.backend.busy is not active:
            raise ValueError('Fixture native continuation stage differs')

    def activate(self):
        self.backend.stage = 'xp1-continuation-active'
        self.backend.busy = True

    def control(self, *, empty):
        if empty is not True:
            raise AssertionError('Expected quiescent native control query')
        self.calls.append('control')
        return {}

    def require_empty(self):
        self.calls.append('queue_empty')
        if self.prefix.actions.pending:
            raise RuntimeError('Fixture native queue is not empty')

    def evaluate(self, child, source, label, **kwargs):
        if child is not self.prefix.ui_child or type(source) is not bytes:
            raise AssertionError('Foreign fixture Lua child or source')
        if label == b'@explicit_espionage_catalog':
            self.calls.append('catalogue')
            state = self.after if self.delivered else self.before
            if self.query_hook is not None:
                self.query_hook()
            return json.dumps(state).encode()
        if label == b'@xp2_espionage_request':
            self.calls.append('request')
            if self.request_result == b'submitted':
                self.prefix.actions.pending.extend([self.archive] * self.archive_count)
            return self.request_result
        if label == b'@explicit_espionage_effect':
            self.calls.append('effect')
            if self.effect_override is not None:
                return self.effect_override
            return json.dumps(dict(schema='civ6-host.espionage-effect.v1',
                player_id=0, turn=17, kind=self.action['kind'], unit_id=9,
                confirmed=self.effect_confirmed, expected_operation=12)).encode()
        raise AssertionError('Unexpected fixture Lua label: ' + repr(label))

    def deliver(self):
        self.calls.append('deliver')
        self.delivered.append(self.prefix.actions.pending.pop(0))
        self.prefix.deferred_events.pending.append('fixture-spy-event')

    def drain(self):
        self.calls.append('drain')
        if not self.leave_deferred:
            self.prefix.deferred_events.pending.clear()

    def flush(self):
        self.calls.append('flush')
        return [dict(kind='fixture-script-feedback')]

    def publish(self):
        self.calls.append('publish')
        self.continuation.publication_count += self.publication_increment

    def observe(self, runtime, child, player_id):
        if (runtime is not self.prefix.runtime or child is not self.prefix.ui_child
                or player_id != 0):
            raise AssertionError('Foreign fixture observation request')
        self.calls.append('observe')
        return deepcopy(self.observation)

    def emit(self, stage, **values):
        self.emitted.append((stage, deepcopy(values)))

    def query(self):
        return adapter.catalogue(self.saved, self.observation)

    def apply(self):
        self.activate()
        return adapter.apply(self.saved, self.action, self.observation)


class XP2EspionageAdapterTests(unittest.TestCase):
    def fixture(self):
        value = SpySession()
        self.addCleanup(value.close)
        return value

    def test_query_retains_exact_owner_revision_and_detaches_native_data(self):
        f = self.fixture()
        result = f.query()
        record = f.continuation._xp2_espionage_catalogue
        self.assertIs(record.saved, f.saved)
        self.assertIs(record.backend, f.backend)
        self.assertIs(record.continuation, f.continuation)
        self.assertIs(record.prefix, f.prefix)
        self.assertIs(record.identity, f.continuation.identity)
        self.assertEqual(record.sequence, 7)
        self.assertEqual(result, f.before)
        result['spies'][0]['name'] = 'Changed by caller'
        f.before['spies'][0]['name'] = 'Changed fixture source'
        self.assertEqual(record.espionage['spies'][0]['name'], 'Ada')
        self.assertEqual(f.continuation.explicit_espionage['spies'][0]['name'], 'Ada')
        self.assertNotIn('request', f.calls)

    def test_source_dependencies_reject_unknown_or_wrong_image_before_file_reads(self):
        f = self.fixture()
        for image in (None, object(), replace(f.image, image_sha256='0' * 64)):
            with self.subTest(image=type(image).__name__), patch.object(
                    Path, 'read_bytes', side_effect=AssertionError('Unexpected source read')):
                with self.assertRaisesRegex(ValueError, 'pinned current XP2'):
                    adapter.source_dependencies(execution_image=image)

    def test_changed_source_pin_refuses_before_native_query(self):
        f = self.fixture()
        with patch.object(Path, 'read_bytes', return_value=b'changed installed espionage source'):
            with self.assertRaisesRegex(RuntimeError, 'source changed'):
                f.query()
        self.assertEqual(f.calls, [])

    def test_query_detects_revision_crossing_and_foreign_observation(self):
        f = self.fixture()
        changed = deepcopy(f.observation)
        changed['turn'] += 1
        with self.assertRaisesRegex(ValueError, 'current observation'):
            adapter.catalogue(f.saved, changed)
        self.assertEqual(f.calls, [])
        f.query_hook = lambda: setattr(f.continuation, 'sequence', 8)
        with self.assertRaisesRegex(ValueError, 'observation revision'):
            f.query()
        self.assertIsNone(f.continuation._xp2_espionage_catalogue)
        self.assertIsNone(f.continuation.explicit_espionage)

    def test_stale_foreign_or_mutated_catalogues_refuse_before_request(self):
        def mutate_revision(f):
            f.continuation.sequence += 1

        def mutate_identity(f):
            del f.prefix._diagnostic_episode_identity
            f.continuation.identity = initialize_episode(f.prefix)

        def mutate_catalogue(f):
            f.continuation.explicit_espionage['capacity'] += 1

        def mutate_observation(f):
            f.continuation.observation['turn'] += 1

        def foreign_record(f):
            f.continuation._xp2_espionage_catalogue = replace(
                f.continuation._xp2_espionage_catalogue, saved=NS())

        for mutate in (mutate_revision, mutate_identity, mutate_catalogue,
                       mutate_observation, foreign_record):
            with self.subTest(mutation=mutate.__name__):
                f = self.fixture()
                f.query()
                mutate(f)
                with self.assertRaisesRegex(ValueError, 'stale or foreign'):
                    f.apply()
                self.assertNotIn('request', f.calls)
                self.assertEqual(f.delivered, [])

    def test_original_saved_owner_graph_checks_are_not_bypassed(self):
        f = self.fixture()
        f.query()
        f.backend._saved_stage_owner = NS()
        with self.assertRaisesRegex(ValueError, 'original live backend graph'):
            f.apply()
        self.assertNotIn('request', f.calls)

    def test_unoffered_action_and_foreign_before_state_refuse_without_native_request(self):
        for mutate in ('action', 'observation'):
            with self.subTest(mutation=mutate):
                f = self.fixture()
                f.query()
                f.activate()
                action, before = deepcopy(f.action), deepcopy(f.observation)
                if mutate == 'action':
                    action['unit_id'] = 10
                else:
                    before['turn'] += 1
                with self.assertRaisesRegex(ValueError, 'not offered'):
                    adapter.apply(f.saved, action, before)
                self.assertNotIn('request', f.calls)

    def test_refused_request_delivers_no_archive_and_invalidates_query(self):
        f = self.fixture()
        f.query()
        f.request_result = b'refused'
        result = f.apply()
        self.assertEqual(result['status'], 'refused')
        self.assertEqual(result['refusal_code'], 'native_spy_choice_unavailable')
        self.assertFalse(result['receipt']['native_archive_delivered'])
        self.assertFalse(result['receipt']['native_effect_readback'])
        self.assertEqual(f.delivered, [])
        self.assertEqual(f.prefix.actions.pending, [])
        self.assertNotIn('publish', f.calls)
        self.assertNotIn('flush', f.calls)
        self.assertEqual(f.continuation.publication_count, 0)
        self.assertIsNone(f.continuation._xp2_espionage_catalogue)

    def test_completed_order_requires_native_effect_and_flushes_before_publication(self):
        f = self.fixture()
        f.query()
        f.calls.clear()
        result = f.apply()
        receipt = result['receipt']
        self.assertEqual(result['status'], 'completed')
        self.assertTrue(receipt['native_archive_delivered'])
        self.assertTrue(receipt['native_effect_readback'])
        self.assertFalse(receipt['native_order_pending'])
        self.assertFalse(receipt['mission_completion_claimed'])
        self.assertFalse(receipt['automatic_choices_applied'])
        self.assertEqual(receipt['native_archive_sha256'], hashlib.sha256(f.archive).hexdigest())
        self.assertEqual(f.delivered, [f.archive])
        self.assertEqual(f.continuation.publication_count, 1)
        self.assertEqual([name for name in f.calls if name in
                          ('request', 'deliver', 'drain', 'flush', 'publish', 'observe', 'catalogue', 'effect')],
                         ['request', 'deliver', 'drain', 'flush', 'publish', 'observe', 'catalogue', 'effect'])
        self.assertEqual(len(f.emitted), 1)
        self.assertEqual(f.emitted[0][1]['receipt']['mission_completion_claimed'], False)
        self.assertIsNone(f.continuation._xp2_espionage_catalogue)
        self.assertIsNone(f.continuation.explicit_espionage)

    def test_delivery_without_native_effect_remains_pending(self):
        f = self.fixture()
        f.query()
        f.effect_confirmed = False
        f.after = deepcopy(f.before)
        result = f.apply()
        self.assertEqual(result['status'], 'pending')
        self.assertTrue(result['receipt']['native_archive_delivered'])
        self.assertFalse(result['receipt']['native_effect_readback'])
        self.assertTrue(result['receipt']['native_order_pending'])
        self.assertFalse(result['receipt']['mission_completion_claimed'])
        self.assertEqual(f.delivered, [f.archive])

    def test_request_status_and_archive_count_must_match_exactly_one_delivery(self):
        for raw, count in ((b'submitted', 0), (b'submitted', 2), (b'unknown', 1)):
            with self.subTest(raw=raw, archive_count=count):
                f = self.fixture()
                f.query()
                f.request_result, f.archive_count = raw, count
                with self.assertRaisesRegex(RuntimeError, 'exactly one action'):
                    f.apply()
                self.assertEqual(f.delivered, [])
                self.assertNotIn('publish', f.calls)

    def test_invalid_effect_wire_never_emits_a_completed_receipt(self):
        f = self.fixture()
        f.query()
        f.effect_override = json.dumps(dict(schema='civ6-host.espionage-effect.v1',
            player_id=1, turn=17, kind='spy_mission', unit_id=9,
            confirmed=True, expected_operation=12)).encode()
        with self.assertRaisesRegex(ValueError, 'effect receipt'):
            f.apply()
        self.assertEqual(f.delivered, [f.archive])
        self.assertEqual(f.emitted, [])

    def test_invalid_native_effect_classification_is_rejected(self):
        for effect in (None, {'applied': True}, {'applied': True, 'pending': True},
                       {'applied': False, 'pending': False}, {'applied': 1, 'pending': False}):
            with self.subTest(effect=effect):
                f = self.fixture()
                f.query()
                with patch.object(native, 'read_effect', return_value=effect):
                    with self.assertRaisesRegex(RuntimeError, 'Unknown native espionage'):
                        f.apply()
                self.assertEqual(f.emitted, [])

    def test_pending_events_or_wrong_publication_count_cannot_complete(self):
        for mode in ('events', 'zero_publication', 'double_publication'):
            with self.subTest(mode=mode):
                f = self.fixture()
                f.query()
                if mode == 'events':
                    f.leave_deferred = True
                else:
                    f.publication_increment = 0 if mode == 'zero_publication' else 2
                with self.assertRaises(RuntimeError):
                    f.apply()
                self.assertEqual(f.emitted, [])
                if mode == 'events':
                    self.assertNotIn('publish', f.calls)


if __name__ == '__main__':
    unittest.main()
