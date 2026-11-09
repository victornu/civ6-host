"""Shared orchestration fixtures; native stages are boundaries, not qualification."""
from contextlib import ExitStack
from copy import deepcopy
from types import SimpleNamespace as NS
import ctypes
import threading
import unittest
from unittest.mock import patch

from civ6_host.runtime.xp1_saved_load_owner import SavedLoadOwner
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256,XP2_CORE_SHA256
from civ6_host.runtime.native.native_official_load import OfficialLoadBackend
from civ6_host.runtime.native import native_official_postload as official
from civ6_host.runtime.native import native_checkpoint_postload_facades as caches
from civ6_host.runtime.native import native_checkpoint_postload160 as postload
from civ6_host.runtime import xp1_cache_publication as publication
from civ6_host.runtime import xp1_ui_binding as ui
from civ6_host.runtime import xp1_continuation as commands
from civ6_host.runtime.workers import run_official_postload909 as loader


ACTION = dict(kind='found_city', unit_id=7, x=1, y=2)


class Fixture:
    """Real retained object types and backend thread guard, no native constructors."""
    def __init__(self, *, fail=None, flags=None):
        self.calls = []
        self.fail = fail
        self.closure = dict(input_profile='xp1-lan', raw_only_candidate=True,
            post160_candidate=True, publish_cache_candidate=True, close_loaded_candidate=True,
            observe_player_candidate=True, unit_commands_candidate=True)
        self.closure.update(flags or {})
        self.backend = b = OfficialLoadBackend.__new__(OfficialLoadBackend)
        b.prefix = NS(quarantined=False)
        b.host, b.core, b.context = object(), object(), 0x12340000
        b.inputs = NS(game=b'\x05\0\0\0fixture')
        b.loaded_readback = dict(turn=1, width=74, height=46, player_id=0)
        b.loaded_roster = b'1|74|46|0|1|2|3|4|5'
        b.load_abi = NS(core_sha256=XP1_CORE_SHA256)
        b.stage, b.busy, b.poisoned, b.destroyed = 'raw-loaded', False, False, False
        b._saved_load_candidate = True
        b._xp1_commands_requested = self.closure['unit_commands_candidate']
        b.raw_load_result = dict(status=0, game_initialized=1, bytes_consumed=len(b.inputs.game),
                                 scheduler_ledger_reconciliation_pending=True)
        b.thread = (threading.get_ident(), 1357)
        b.runtime = NS(thread=lambda: (threading.get_ident(), 1357))
        b.close_loaded = self.close_loaded
        self.emit = lambda *args, **kwargs: None
        self.win = object()
        self.stack = ExitStack()

    def mark(self, name, *args):
        self.calls.append((name, *args))
        if self.fail == name:
            raise RuntimeError('partial native stage: ' + name)

    def opened(self, closure, emit, win):
        self.mark('open', closure, emit, win)
        return self.backend

    def __enter__(self):
        for name in ('WinDLL', 'CDLL'):
            self.stack.enter_context(patch.object(ctypes, name, side_effect=AssertionError('DLL forbidden')))
        self.stack.enter_context(patch.object(loader, 'open_official_backend', side_effect=self.opened))
        fixture = self

        def facade_init(obj, backend, receipt, *, publication_mode):
            fixture.mark('facade_create', backend, receipt, publication_mode)
            obj.owner, obj.receipt = backend, receipt

        def run_caches(obj, emit):
            fixture.mark('caches', obj, emit)
            obj.owner.stage = 'facades-candidate-observed'
            obj.completed_result = dict(candidate_native_cache_only=True,
                public_cache_gate_enabled=False, post160_admitted=False, marker='caches')
            return obj.completed_result

        def post_init(obj, backend, facade, cache_result, *, postload_mode):
            fixture.mark('post_create', backend, facade, cache_result, postload_mode)
            obj.owner, obj.facade, obj.facade_result = backend, facade, cache_result
            obj.candidate_diagnostics = dict(void_return_ignored=True)

        def run_post(obj, emit, *, expected_major_ids):
            fixture.mark('postload', obj, emit, expected_major_ids)
            obj.owner.stage = 'post160-candidate-observed-awaiting-controlled-stop'
            return dict(marker='postload')

        def pub_init(obj, post):
            fixture.mark('publication_create', post)
            obj.post, obj.owner, obj.completed = post, post.owner, False
            obj.owner._xp1_publication_attempt = obj

        def run_pub(obj):
            fixture.mark('publish', obj)
            obj.owner.stage = publication.COMPLETED_STAGE
            obj.completed = True
            obj.result = dict(marker='publication')
            return obj.result

        def view_init(obj, pub):
            fixture.mark('view_create', pub)
            obj.publication, obj.owner, obj.completed = pub, pub.owner, False
            obj.owner._xp1_player_view = obj

        def run_view(obj):
            fixture.mark('observe', obj)
            obj.result = dict(marker='view', observation=dict(turn=1, player_id=0))
            obj.completed = True
            return obj.result

        def continuation_init(obj, view):
            fixture.mark('commands_create', view)
            obj.view, obj.owner, obj.poisoned, obj.sequence = view, view.owner, False, 0
            obj.owner._xp1_continuation = obj
            obj.owner.stage = commands.READY

        def execute(obj, action, *, session):
            if session.continuation is not obj or not session._running:
                raise ValueError('Fixture received a foreign/inactive saved session')
            fixture.mark('execute', obj, action)
            obj.sequence += 1
            return dict(action=deepcopy(action), sequence=obj.sequence, native_fixture=True)

        for cls, init in ((official.OfficialFacadeBackend, facade_init),
                          (official.OfficialPost160Backend, post_init),
                          (publication.SavedCachePublication, pub_init),
                          (ui.SavedPlayerView, view_init),
                          (commands.SavedContinuation, continuation_init)):
            self.stack.enter_context(patch.object(cls, '__init__', init))
        for module, name, fn in ((caches, 'run_sequence', run_caches), (postload, 'run_sequence', run_post),
            (publication.SavedCachePublication, 'run', run_pub), (ui.SavedPlayerView, 'run', run_view),
            (commands.SavedContinuation, 'execute', execute)):
            self.stack.enter_context(patch.object(module, name, fn))
        return self

    def __exit__(self, *args):
        return self.stack.__exit__(*args)

    def open(self):
        return SavedLoadOwner.open(self.closure, self.emit, self.win)

    def through(self, phase):
        owner = self.open()
        for name in ('populate_caches', 'postload', 'publish', 'observe_initial', 'begin_commands'):
            getattr(owner, name)()
            if owner.phase == phase:
                break
        return owner

    def close_loaded(self, *, completed):
        self.mark('close', completed)
        self.backend.destroyed = True
        self.backend.stage = 'loaded-lifetime-closed'
        return dict(native_unload_called=True, native_destroy_called=True, marker='close')


class SavedLoadOwnerTests(unittest.TestCase):
    def test_xp2_open_uses_shared_loader_once_with_selected_engine(self):
        with Fixture(flags=dict(input_profile='xp2-lan',unit_commands_candidate=False)) as f:
            f.backend.load_abi=NS(core_sha256=XP2_CORE_SHA256)
            f.backend._xp2_postload_requested=True
            f.backend.loaded_roster=b'1|44|26|0|1'
            o=f.open()
            self.assertIs(o.backend,f.backend)
            self.assertEqual(o._engine_sha256,XP2_CORE_SHA256)
            self.assertEqual([c[0] for c in f.calls],['open'])
            o.populate_caches();o.postload();o.publish();o.observe_initial();o.close()
            self.assertEqual(o.phase,'closed')
            self.assertEqual([row[-1] for row in f.calls if row[0]=='postload'],[(0,1)])

    def test_xp2_adopts_completed_load_without_loading_again_and_uses_shared_stages(self):
        with Fixture(flags=dict(observe_player_candidate=False,unit_commands_candidate=False)) as f:
            b=f.backend;b.load_abi=NS(core_sha256=XP2_CORE_SHA256)
            b._xp2_postload_requested=True;b.captured_bundle=object()
            b.loaded_readback=dict(turn=1,width=44,height=26,player_id=0)
            b.loaded_roster=b'1|44|26|0|1'
            closure=dict(f.closure,input_profile='xp2-lan')
            with patch('civ6_host.runtime.captured_saved_load.validate_candidate_inputs') as validate:
                o=SavedLoadOwner.from_loaded(b,closure,f.emit)
                validate.assert_called_once_with(b.inputs,b.captured_bundle)
                with self.assertRaises(TypeError):SavedLoadOwner.from_loaded(b,closure,f.emit)
                self.assertFalse(b.poisoned)
            self.assertFalse(f.calls)
            o.populate_caches();o.postload();o.publish();o.close()
            self.assertNotIn('open',[row[0] for row in f.calls])
            self.assertEqual(o.phase,'closed')
            self.assertEqual([row[-1] for row in f.calls if row[0]=='postload'],[(0,1)])

    def test_bbg_view_listener_runs_after_publication_before_observation(self):
        from civ6_host.runtime import xp2_bbg_inputs, xp2_bbg_view_ready

        with Fixture(flags=dict(unit_commands_candidate=False)) as f:
            backend = f.backend
            backend.load_abi = NS(core_sha256=XP2_CORE_SHA256)
            backend._xp2_postload_requested = True
            backend.loaded_roster = b'1|44|26|0|1'
            backend.inputs.official_bundle = xp2_bbg_inputs.REFERENCE
            backend.captured_bundle = NS(reference=xp2_bbg_inputs.REFERENCE)
            closure = dict(f.closure, input_profile='xp2-lan')
            with patch('civ6_host.runtime.captured_saved_load.validate_candidate_inputs'):
                owner = SavedLoadOwner.from_loaded(backend, closure, f.emit)
            with patch.object(xp2_bbg_view_ready, 'deliver', side_effect=lambda pub: f.mark('view_ready', pub)):
                owner.populate_caches()
                owner.postload()
                self.assertNotIn('view_ready', [row[0] for row in f.calls])
                owner.publish()
                owner.observe_initial()
            stages = [row[0] for row in f.calls]
            self.assertEqual(stages.count('view_ready'), 1)
            self.assertEqual(stages[stages.index('view_ready')-1:stages.index('view_ready')+2],
                             ['publish', 'view_ready', 'view_create'])

    def test_xp2_attachment_refuses_incomplete_command_lifecycle_before_work(self):
        with Fixture() as f:
            closure=dict(f.closure,input_profile='xp2-lan',observe_player_candidate=False)
            with self.assertRaisesRegex(ValueError,'dependencies are incomplete'):
                SavedLoadOwner.from_loaded(f.backend,closure,f.emit)
            self.assertFalse(f.calls)

    def test_xp2_observation_uses_the_existing_stage_graph_and_closes(self):
        with Fixture(flags=dict(unit_commands_candidate=False)) as f:
            b=f.backend;b.load_abi=NS(core_sha256=XP2_CORE_SHA256)
            b._xp2_postload_requested=True;b.captured_bundle=object()
            b.loaded_roster=b'1|44|26|0|1'
            with patch('civ6_host.runtime.captured_saved_load.validate_candidate_inputs'):
                o=SavedLoadOwner.from_loaded(b,dict(f.closure,input_profile='xp2-lan'),f.emit)
            o.populate_caches();o.postload();o.publish()
            self.assertIs(o.observe_initial(),o.player_view.result)
            self.assertEqual(o.phase,'observed')
            with self.assertRaises(ValueError):o.begin_commands()
            o.close()
            self.assertEqual(o.phase,'closed')
            self.assertNotIn('open',[c[0] for c in f.calls])

    def test_query_guard_requires_ready_graph_inside_retained_attempt(self):
        with Fixture() as f:
            owner=f.through('commands')
            with self.assertRaises(RuntimeError):owner._check_query()
            # This lifecycle fixture replaces the continuation constructor.
            # Its inner graph is exercised by the composed adapter tests.
            with owner._attempt(), patch.object(owner.continuation,'check') as inner:
                owner._check_query()
                inner.assert_called_once_with(active=False)
                with self.assertRaises(RuntimeError):
                    owner._check('commands',active=True,query=True)
                f.backend.busy=True
                with self.assertRaises(ValueError):owner._check_query()
                f.backend.busy=False
                actual=owner.context;owner.context=actual+8
                with self.assertRaises(ValueError):owner._check_query()
                owner.context=actual
                owner._check_query()
            self.assertFalse(owner.poisoned)

    def test_exact_stage_calls_retained_roots_and_results(self):
        with Fixture() as f:
            o = f.open()
            self.assertIs(o.raw_result['raw_load_receipt'], f.backend.raw_load_result)
            self.assertIs(o.raw_result['readback'], f.backend.loaded_readback)
            cache = o.populate_caches()
            self.assertIs(cache, o.facade.completed_result)
            self.assertIs(f.backend.saved_load_cache_attempt, o.facade)
            post = o.postload()
            self.assertEqual(post, dict(marker='postload', candidate_diagnostics=dict(void_return_ignored=True)))
            self.assertIs(f.backend.saved_load_post160_attempt, o.post)
            self.assertIs(o.post.facade_result, cache)
            self.assertIs(o.publish(), o.publication.result)
            self.assertIs(f.backend.saved_load_publication_attempt, o.publication)
            self.assertIs(o.observe_initial(), o.player_view.result)
            token = o.begin_commands()
            self.assertIs(type(token), commands.SavedContinuation)
            self.assertEqual(o.execute(ACTION)['sequence'], 1)
            self.assertEqual(o.execute(ACTION)['sequence'], 2)
            self.assertEqual(next(c[-1] for c in f.calls if c[0] == 'postload'), tuple(range(6)))
            self.assertEqual([c[0] for c in f.calls], ['open', 'facade_create', 'caches', 'post_create',
                'postload', 'publication_create', 'publish', 'view_create', 'observe', 'commands_create', 'execute', 'execute'])

    def test_phase_order_and_ui_registration_are_one_shot(self):
        with Fixture() as f:
            o = f.open()
            for name in ('postload', 'publish', 'observe_initial', 'begin_commands', 'close'):
                with self.subTest(name=name), self.assertRaises(RuntimeError):
                    getattr(o, name)()
            self.assertEqual(len(f.calls), 1)
            o.populate_caches(); o.postload(); o.publish(); o.observe_initial()
            count = len(f.calls)
            with self.assertRaises(RuntimeError):
                o.observe_initial()
            self.assertEqual(len(f.calls), count)
            o.begin_commands()
            with self.assertRaises(RuntimeError):
                o.begin_commands()
            self.assertFalse(o.poisoned)

    def test_close_selects_exact_completed_owner_and_never_repeats_destroy(self):
        for phase, attribute in (('postload', 'post'), ('published', 'publication'),
                                 ('observed', 'publication'), ('commands', 'continuation')):
            with self.subTest(phase=phase), Fixture() as f:
                o = f.through(phase)
                result = o.close()
                self.assertIs(f.calls[-1][1], getattr(o, attribute))
                self.assertTrue(f.backend.destroyed)
                self.assertIs(o.close(), result)
                self.assertEqual(sum(c[0] == 'close' for c in f.calls), 1)
                with self.assertRaises(RuntimeError):
                    o.execute(ACTION)

    def test_partial_stage_failures_poison_and_never_guess_cleanup(self):
        methods = [('populate_caches', 'caches'), ('postload', 'postload'), ('publish', 'publish'),
                   ('observe_initial', 'observe'), ('begin_commands', 'commands_create'), ('execute', 'execute'), ('close', 'close')]
        for failed_method, failed_call in methods:
            with self.subTest(stage=failed_call), Fixture(fail=failed_call) as f:
                o = f.open()
                for method, _ in methods:
                    if method == failed_method:
                        with self.assertRaisesRegex(RuntimeError, 'partial native stage'):
                            getattr(o, method)(ACTION) if method == 'execute' else getattr(o, method)()
                        break
                    getattr(o, method)(ACTION) if method == 'execute' else getattr(o, method)()
                self.assertTrue(o.poisoned); self.assertTrue(f.backend.poisoned)
                self.assertTrue(f.backend.prefix.quarantined); self.assertEqual(o.phase, 'poisoned')
                before = len(f.calls)
                with self.assertRaises(RuntimeError):
                    o.close()
                self.assertEqual(len(f.calls), before)

    def test_foreign_identity_and_thread_refuse_before_native_stage(self):
        mutations = {
            'prefix': lambda o, f: setattr(f.backend, 'prefix', object()),
            'core': lambda o, f: setattr(f.backend, 'core', object()),
            'receipt': lambda o, f: setattr(f.backend, 'raw_load_result', dict(o.receipt)),
            'attempt': lambda o, f: setattr(f.backend, 'saved_load_post160_attempt', object()),
            'backend': lambda o, f: setattr(o, 'backend', object()),
            'thread': lambda o, f: setattr(o, 'thread', -1),
            'native_thread': lambda o, f: setattr(f.backend, 'thread', (threading.get_ident(), 999)),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name), Fixture() as f:
                o = f.through('postload'); mutate(o, f); before = len(f.calls)
                with self.assertRaises((ValueError, RuntimeError)):
                    o.publish()
                self.assertEqual(len(f.calls), before)

    def test_closure_requests_and_malformed_actions_do_not_admit_work(self):
        with Fixture() as f:
            for change in (dict(input_profile='lan'), dict(raw_only_candidate=False),
                           dict(post160_candidate=1), dict(post160_candidate=False),
                           dict(observe_player_candidate=False)):
                with self.subTest(change=change), self.assertRaises(ValueError):
                    SavedLoadOwner.open(dict(f.closure, **change), f.emit, f.win)
            self.assertFalse(f.calls)
        with Fixture(flags=dict(unit_commands_candidate=False)) as f:
            o = f.through('observed')
            f.closure['unit_commands_candidate'] = True
            with self.assertRaises(ValueError):
                o.begin_commands()
            self.assertIs(o.requested['unit_commands_candidate'], False)
        with Fixture() as f:
            o = f.through('commands'); before = len(f.calls)
            for action in ({'kind': 'end_turn','extra':True}, dict(ACTION, extra=True),
                           {'kind':'world_deselect_unit','unit_id':7}):
                with self.assertRaises(ValueError):
                    o.execute(action)
            self.assertEqual(len(f.calls), before); self.assertFalse(o.poisoned)

    def test_invalid_raw_receipt_and_cache_gate_fail_closed(self):
        with Fixture() as f:
            f.backend.raw_load_result['status'] = 1
            with self.assertRaises(ValueError):
                f.open()
            self.assertTrue(f.backend.poisoned)
            self.assertEqual([c[0] for c in f.calls], ['open'])
        with Fixture() as f:
            o = f.open()
            with patch.object(caches, 'run_sequence', return_value=dict(candidate_native_cache_only=True,
                public_cache_gate_enabled=True, post160_admitted=False)), self.assertRaises(RuntimeError):
                o.populate_caches()
            self.assertTrue(o.poisoned)
            self.assertFalse(any(c[0] == 'close' for c in f.calls))


if __name__ == '__main__':
    unittest.main()
