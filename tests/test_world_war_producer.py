"""Composed modal production with native memory/UI reads as fixture boundaries.

This checks publication and ownership, not availability or effects in GameCore.
"""
from contextlib import ExitStack
from copy import deepcopy
import json
import gc
import weakref
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from civ6_host.runtime import xp2_world_war as producer
from civ6_host.runtime import xp2_world_war_display as display
from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
from civ6_host.runtime import saved_load_job_observer as jobs
from test_world_war_decisions import make_catalogue, OBSERVATION, IDENTITY, PIN, PROMPT


def quiescent():
    return dict(schema=jobs.SCHEMA, profile=jobs.PROFILE,
        core_identity=dict(profile=2), source_proof_sha256=jobs.SOURCE_HASH_BY_PROFILE[2],
        stable_read=True, memory_modified=False, concurrent_scheduler_supported=False,
        native_introspection_only=True, native_methods_called=True, spawn_active=0,
        registry_lock_raw=0, pending_items=0, submission_sequence=0, groups=[],
        slots=[dict(handle=i, occupied=False, count=0, items=[]) for i in range(1, 65)])


class ProducerTests(unittest.TestCase):
    def fixture(self):
        case = make_catalogue()
        observation = deepcopy(OBSERVATION)
        continuation = NS(sequence=3, observation=deepcopy(observation),
            world_input_prompts={0: deepcopy(PROMPT)}, world_input_selections={0: 101},
            transport=NS(require_empty_native_queue=lambda: None))
        prefix = NS(ui_child=object(), runtime=NS(evaluate_text=lambda *a, **k:
            json.dumps(case['world_input']['units']).encode()))
        backend = NS(load_abi=NS(core_sha256=XP2_CORE_SHA256), control=lambda **k: None)
        saved = NS(backend=backend, continuation=continuation, prefix=prefix, war_source_sha256=PIN)
        return case, observation, saved, (backend, continuation, prefix, IDENTITY)

    def patches(self, stack, case, owners):
        stack.enter_context(patch('civ6_host.runtime.xp1_world_input._owner', return_value=owners))
        stack.enter_context(patch('civ6_host.runtime.native.native_world_input.catalog_source', return_value=b'fixture-native-catalogue'))
        stack.enter_context(patch.object(display, 'verify_source', return_value=dict(source_sha256=PIN)))
        return stack.enter_context(patch.object(display, 'read', return_value=deepcopy(case['world_input']['war_display'])))

    def test_public_protocol_revision_is_independent_from_native_continuation_revision(self):
        case, obs, saved, owners = self.fixture()
        with ExitStack() as stack:
            self.patches(stack, case, owners)
            view = producer.read(saved, obs, case['turn_controls'], 8)
        self.assertEqual(view['sequence'], 8)
        self.assertEqual(view['candidates'], case['candidates'])
        self.assertEqual(saved.continuation._xp1_world_input_catalogue.sequence, 3)
        self.assertEqual(saved.continuation._xp1_world_input_catalogue.actions,
                         tuple(row['action'] for row in case['candidates']))
        self.assertEqual(saved.continuation.observation, obs)
        self.assertEqual(saved.continuation.world_input_prompts[0], PROMPT)

    def test_changed_prompt_or_foreign_display_is_not_published(self):
        for wrong in ('prompt', 'display'):
            with self.subTest(wrong=wrong):
                case, obs, saved, owners = self.fixture()
                with ExitStack() as stack:
                    read = self.patches(stack, case, owners)
                    if wrong == 'prompt':
                        def changed(*args):
                            saved.continuation.world_input_prompts[0] = dict(PROMPT, defending_player=1)
                            return deepcopy(case['world_input']['war_display'])
                        read.side_effect = changed
                    else:
                        read.return_value['source_sha256'] = 'b'*64
                    with self.assertRaises((ValueError, RuntimeError)):
                        producer.read(saved, obs, case['turn_controls'], 8)
                self.assertIsNone(saved.continuation._xp1_world_input_catalogue)
                self.assertIsNone(saved.continuation.explicit_world_input)

    def test_absent_prompt_does_not_manufacture_a_modal(self):
        case, obs, saved, owners = self.fixture()
        saved.continuation.world_input_prompts.clear()
        with ExitStack() as stack:
            read = self.patches(stack, case, owners)
            with self.assertRaises(ValueError):
                producer.read(saved, obs, case['turn_controls'], 8)
            read.assert_not_called()

    def test_renderer_pin_is_a_session_input_not_a_value_from_the_modal(self):
        case, obs, saved, owners = self.fixture()
        with ExitStack() as stack:
            read = self.patches(stack, case, owners)
            self.assertIsNone(producer.source_pin(None, 'lan'))
            self.assertEqual(producer.source_pin(PIN, 'xp2-lan'), PIN)
            for value, profile in [(PIN, 'xp1-lan'), ('b'*64, 'xp2-lan'), (True, 'xp2-lan')]:
                with self.subTest(value=value, profile=profile), self.assertRaises(ValueError):
                    producer.source_pin(value, profile)
            saved.war_source_sha256 = None
            with self.assertRaisesRegex(ValueError, 'session source'):
                producer.read(saved, obs, case['turn_controls'], 8)
            read.assert_not_called()


class DisplayReadCompositionTests(unittest.TestCase):
    def test_namespace_marker_does_not_keep_a_finished_owner_graph_alive_globally(self):
        class Box:
            pass
        def create():
            backend, prefix, runtime, child, identity = [Box() for _ in range(5)]
            backend.core, backend.host, backend.prefix = Box(), Box(), prefix
            prefix.backend, prefix.core, prefix.host = backend, backend.core, backend.host
            prefix.runtime, prefix.ui_child = runtime, child
            prefix.closed = prefix.quarantined = False
            runtime.database_bound, runtime.service_owner = True, backend.host
            runtime.registry = NS(validate=lambda child: 1)
            runtime.namespaces = NS(register=lambda child, name: None)
            owner = NS(_check=lambda: (backend, None, prefix, identity))
            display.ensure_global_parameters_namespace(owner, backend, prefix, identity)
            return [weakref.ref(value) for value in (backend, prefix, runtime, child)]
        refs = create()
        gc.collect()
        self.assertTrue(all(ref() is None for ref in refs))

    def test_bound_owner_uses_its_backend_scheduler_without_base_owner_methods(self):
        case = make_catalogue()
        obs = deepcopy(OBSERVATION)
        scheduler = quiescent()
        phases = []
        events = []
        saved=object()
        def query_snapshot(owner,phase):
            self.assertIs(owner,saved)
            phases.append(phase)
            return deepcopy(scheduler)
        backend = NS(load_abi=NS(core_sha256=XP2_CORE_SHA256),
                     jobs=NS(query_snapshot=query_snapshot),
                     emit=lambda stage, **fields: events.append((stage, fields)))
        prefix = NS(ui_child=object(), actions=NS(pending=[]), deferred_events=NS(pending=[]),
                    runtime=NS(registry=NS(validate=lambda child: 123), evaluate_text=lambda *a, **k: b'fixture'))
        class Bound:
            __slots__ = ()
            @property
            def saved(self): return saved
            def _check(self): return backend, None, prefix, IDENTITY
            def control(self, **kwargs): self._check()
            def emit(self, *args, **kwargs):
                raise AssertionError('Read-only bound owner cannot emit an action receipt')
        with ExitStack() as stack:
            stack.enter_context(patch('civ6_host.runtime.native.native_player_observation.observe_player', return_value=obs))
            stack.enter_context(patch('civ6_host.runtime.xp2_world_configuration.read', return_value={'fixture': True}))
            stack.enter_context(patch.object(display, 'ensure_global_parameters_namespace', return_value=None))
            stack.enter_context(patch.object(display, 'display_source', return_value=b'fixture-query'))
            stack.enter_context(patch.object(display, 'parse_display', return_value=case['world_input']['war_display']))
            value = display.read(Bound(), obs, PROMPT)
        self.assertEqual(value, case['world_input']['war_display'])
        self.assertEqual(phases, ['before', 'after'])
        self.assertEqual(events[0][0], 'xp2_official_world_war_display')


if __name__ == '__main__':
    unittest.main()
