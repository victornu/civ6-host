"""Source-byte and composed-owner tests; no DLL invocation or native effect."""
from contextlib import nullcontext
from copy import deepcopy
import hashlib
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from civ6_host.runtime import xp2_envoys as adapter
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256


class Xp2EnvoySourceTests(unittest.TestCase):
    def test_source_dependencies_project_captured_core_to_selected_execution_image(self):
        from civ6_host.runtime import execution_images
        image = execution_images.select(
            'xp2-gamecore-current-4de40abf',
            core_path=execution_images._GAMECORE_PATH,
        )
        pins = adapter.source_dependencies(execution_image=image)
        self.assertEqual(pins[image.path], image.image_sha256)
        self.assertNotIn(image.reference_core_sha256, pins.values())
        self.assertIn(adapter.CHECKPOINT_SOURCE[1], pins.values())
        self.assertIn(adapter.UNBLOCKED_CHECKPOINT_SOURCE[1], pins.values())

    def test_compact_runtime_keeps_every_reviewed_byte_guard(self):
        import json
        from civ6_host.runtime import xp2_envoys_source as source
        from civ6_host.runtime.paths import resource_root
        q=json.loads((resource_root()/source.SOURCE[0]).read_bytes())
        a=json.loads((resource_root()/source.APPLICATION[0]).read_bytes())
        expected=[]
        for group,bodies in (('query_registrar',q['registrar_bodies']),
                ('query_callback',q['callback_bodies']),('application',a['roots']),
                ('application_handler',a['operation_handler_roots'])):
            for name,body in bodies.items():
                expected.append((group,name,int(body['start_rva'],16),body['length'],
                    ''.join(row['bytes'] for row in body['instructions'])))
        actual=[(b['group'],b['name'],b['rva'],b['length'],b['raw_hex']) for b in source.source()['blocks']]
        self.assertEqual(actual,expected)
        self.assertEqual(sum(row[3] for row in actual),15698)

    def test_selected_ui_and_request_bodies_match_the_pinned_xp2_image(self):
        from pathlib import Path
        import pefile
        from civ6_host.runtime import xp2_envoys_source as source
        proof=source.source();source.application_source()
        image=pefile.PE(str(Path(proof['image']['path'])),fast_load=True)
        base=0x7ff800000000
        saved=SimpleNamespace(backend=SimpleNamespace(core=SimpleNamespace(_handle=base),
            load_abi=SimpleNamespace(core_sha256=XP2_CORE_SHA256),
            runtime=SimpleNamespace(read=lambda address,size:image.get_data(address-base,size))),
            prefix=object(),_check_query=lambda:None,_check_active=lambda:None)
        try:
            source.bind_owner(saved,active=False)
            self.assertTrue(hasattr(saved,'_xp2_envoy_lifetime'))
            del saved._xp2_envoy_lifetime
            saved.backend.runtime.read=lambda address,size:b'\0'*size
            with self.assertRaisesRegex(ValueError,'body differs'):
                source.bind_owner(saved,active=False)
        finally:
            image.close()


class Xp2EnvoyCompositionTests(unittest.TestCase):
    def catalogue(self):
        return dict(player_id=0,current_game_turn=45,tokens_to_give=3,
            can_give_influence=True,considered=False,giving_tokens_blocker_present=True,
            targets=[dict(target_player_id=19,can_give=True,tokens_received=2)])

    def saved(self,before):
        calls=[]
        pending=[]
        def deliver():
            calls.append('deliver');pending.pop()
        prefix=SimpleNamespace(actions=SimpleNamespace(pending=pending,deliver_one=deliver),
            deferred_events=SimpleNamespace(pending=[],drain=lambda:calls.append('drain')),
            view_publisher=SimpleNamespace(publish=lambda:calls.append('publish')),
            ui_child=object(),runtime=SimpleNamespace(evaluate_text=lambda *a,**k:b'fixture'))
        saved=SimpleNamespace(prefix=prefix,backend=SimpleNamespace(core=object(),context=object(),
            load_abi=SimpleNamespace(core_sha256=XP2_CORE_SHA256)),
            continuation=SimpleNamespace(explicit_envoys=deepcopy(before)),
            emit=lambda *a,**k:calls.append(('effect',a,k)))
        return saved,calls

    def test_send_uses_selected_xp2_abi_and_preserves_native_bonus_readback(self):
        from civ6_host.runtime import xp2_envoys_source as source
        before=self.catalogue();after=deepcopy(before)
        after['tokens_to_give']=2;after['targets'][0]['tokens_received']=4
        saved,calls=self.saved(before)
        def request(core,context,pid,operation,parameters,**kwargs):
            self.assertIs(core,saved.backend.core);self.assertIs(context,saved.backend.context)
            self.assertEqual((pid,operation,parameters),(0,2582383566,{75700508:19}))
            self.assertEqual(kwargs,dict(core_sha256=XP2_CORE_SHA256))
            calls.append('request')
            saved.prefix.actions.pending.append((3294486831).to_bytes(4,'little')+b'fixture')
            return dict(can_start=True,request_invoked=True)
        with patch.object(source,'bind_owner'),patch.object(adapter,'catalogue',side_effect=[before,after]), \
             patch.object(adapter.native,'revalidation_source',return_value=b'fixture'), \
             patch.object(adapter.native,'validate_fresh_choice',side_effect=lambda raw,choice:choice), \
             patch('civ6_host.runtime.native.native_player_operation_request.request_player_operation',side_effect=request), \
             patch('civ6_host.runtime.native.native_player_observation.observe_player',return_value=dict(player_id=0,turn=45)):
            result=adapter.apply(saved,dict(kind='send_envoy',target_player_id=19),dict(player_id=0,turn=45))
        self.assertEqual(result['effect']['tokens_received_delta'],2)
        self.assertEqual(calls[:4],['request','deliver','drain','publish'])
        self.assertFalse(saved.prefix.actions.pending)

    def test_send_uses_the_selected_xp1_abi_and_native_archive(self):
        from civ6_host.runtime import xp1_city_state_envoys as xp1

        before=self.catalogue()
        after=deepcopy(before)
        after['tokens_to_give']=2
        after['targets'][0]['tokens_received']=3
        saved,calls=self.saved(before)
        saved.backend.load_abi.core_sha256=XP1_CORE_SHA256

        def request(core,context,pid,operation,parameters,**kwargs):
            self.assertEqual((pid,operation,parameters),(0,2582383566,{75700508:19}))
            self.assertEqual(kwargs,dict(core_sha256=XP1_CORE_SHA256))
            saved.prefix.actions.pending.append((3294486831).to_bytes(4,'little'))
            return dict(can_start=True,request_invoked=True)

        with patch.object(xp1,'bind_actions') as bind, \
             patch.object(adapter,'catalogue',side_effect=[before,after]), \
             patch.object(adapter.native,'revalidation_source',return_value=b'fixture'), \
             patch.object(adapter.native,'validate_fresh_choice',side_effect=lambda raw,choice:choice), \
             patch('civ6_host.runtime.native.native_player_operation_request.request_player_operation',side_effect=request), \
             patch('civ6_host.runtime.native.native_player_observation.observe_player',return_value=dict(player_id=0,turn=45)):
            result=adapter.apply(saved,dict(kind='send_envoy',target_player_id=19),dict(player_id=0,turn=45))
        bind.assert_called_once_with(saved,active=True)
        self.assertEqual(result['effect']['tokens_received_delta'],1)
        self.assertEqual(calls[:3],['deliver','drain','publish'])
        self.assertEqual(calls[3][1],('xp1_envoy_effect_verified',))

    def test_retention_is_a_setter_and_does_not_submit_a_player_operation(self):
        from civ6_host.runtime import xp2_envoys_source as source
        before=self.catalogue();after=deepcopy(before)
        after.update(considered=True,giving_tokens_blocker_present=False)
        saved,calls=self.saved(before)
        with patch.object(source,'bind_owner'),patch.object(adapter,'catalogue',side_effect=[before,after]), \
             patch.object(adapter.native,'consideration_source',return_value=b'fixture'), \
             patch.object(adapter.native,'parse_catalog',return_value=after), \
             patch('civ6_host.runtime.native.native_player_operation_request.request_player_operation') as request, \
             patch('civ6_host.runtime.native.native_player_observation.observe_player',return_value=dict(player_id=0,turn=45)):
            result=adapter.apply(saved,dict(kind='retain_envoys'),dict(player_id=0,turn=45))
        request.assert_not_called()
        self.assertEqual(result['effect']['tokens_retained'],3)
        self.assertEqual(calls[:2],['drain','publish'])

    def test_stale_catalogue_refuses_before_request_or_setter(self):
        from civ6_host.runtime import xp2_envoys_source as source
        before=self.catalogue();fresh=dict(before,tokens_to_give=2)
        saved,calls=self.saved(before)
        with patch.object(source,'bind_owner'),patch.object(adapter,'catalogue',return_value=fresh), \
             patch('civ6_host.runtime.native.native_player_operation_request.request_player_operation') as request:
            with self.assertRaisesRegex(RuntimeError,'stale'):
                adapter.apply(saved,dict(kind='send_envoy',target_player_id=19),dict(player_id=0,turn=45))
        request.assert_not_called();self.assertFalse(calls)

    def test_active_action_catalogue_uses_real_binder_phase_checks(self):
        before=self.catalogue();after=deepcopy(before)
        after.update(considered=True,giving_tokens_blocker_present=False)
        saved,calls=self.saved(before)
        saved.backend.core=SimpleNamespace(_handle=0x180000000)
        saved.backend.load_abi=SimpleNamespace(core_sha256=XP2_CORE_SHA256)
        saved.backend.busy=True
        def active():
            self.assertTrue(saved.backend.busy)
            calls.append('active_check')
        def query():
            if saved.backend.busy:
                raise ValueError('query check rejects the active graph')
        saved._check_active=active;saved._check_query=query
        # The actual session has already bound these immutable bytes on its
        # preceding read. Keep the real bind_owner, including its phase check.
        saved._xp2_envoy_lifetime=(saved.backend.core,saved.prefix)
        with patch.object(adapter.native,'catalog_source',return_value=b'fixture'), \
             patch.object(adapter.native,'parse_catalog',side_effect=[before,after,after]), \
             patch.object(adapter.native,'consideration_source',return_value=b'fixture'), \
             patch('civ6_host.runtime.native.native_player_observation.observe_player',return_value=dict(player_id=0,turn=45)):
            with self.assertRaisesRegex(ValueError,'active graph'):
                adapter.catalogue(saved,dict(player_id=0,turn=45))
            result=adapter.apply(saved,dict(kind='retain_envoys'),dict(player_id=0,turn=45))
        self.assertEqual(result['effect']['tokens_retained'],3)
        self.assertEqual(calls.count('active_check'),3)

    def checkpoint_owner(self, before):
        saved, calls = self.saved(before)
        saved.core = SimpleNamespace(_handle=0x180000000,
            _civ6_host_execution_image=SimpleNamespace(id=adapter.CURRENT_PROFILE_ID))
        saved.backend.control = Mock()
        saved.backend.jobs_snapshot = Mock()
        saved.continuation.transport = SimpleNamespace(require_empty_native_queue=Mock())
        saved._check = Mock()
        saved._check_query = Mock()
        saved._check_active = Mock()
        saved._attempt = nullcontext
        saved.prefix.runtime.evaluate_text = Mock(return_value=b'restored')
        return saved, calls

    def test_checkpoint_restores_the_omitted_flag_and_requires_real_blocker(self):
        saved_view = self.catalogue()
        after_load = dict(saved_view, considered=True, giving_tokens_blocker_present=False)
        saved, calls = self.checkpoint_owner(saved_view)
        view = dict(player_id=0, turn=45)
        with patch.object(adapter, 'catalogue', side_effect=[after_load, saved_view]) as catalogue, \
             patch.object(adapter, '_checkpoint_source', return_value={'live_spans': {}}), \
             patch.object(adapter.native, '_common', return_value=b''), \
             patch('civ6_host.runtime.saved_load_job_observer.require_quiescent'), \
             patch('civ6_host.runtime.xp1_load_capability.capability_source_scope',
                   return_value=nullcontext()):
            adapter.restore_checkpoint_consideration(saved, view, saved_view)
        self.assertIn(b'SetGivingTokensConsidered(false)',
                      saved.prefix.runtime.evaluate_text.call_args.args[1])
        self.assertEqual(catalogue.call_args_list[-1].kwargs, {'active': True})
        self.assertEqual(calls[:2], ['drain', 'publish'])
        self.assertFalse(saved.backend.busy)
        self.assertEqual(calls[-1][1][0], 'xp2_envoy_checkpoint_consideration_restored')

    def test_checkpoint_leaves_any_other_mismatch_to_the_strict_comparator(self):
        saved_view = self.catalogue()
        saved, _ = self.checkpoint_owner(saved_view)
        changed_targets = dict(saved_view, considered=True,
                               giving_tokens_blocker_present=False, targets=[])
        with patch.object(adapter, 'catalogue', return_value=changed_targets), \
             patch.object(adapter, '_checkpoint_source') as source:
            adapter.restore_checkpoint_consideration(saved, dict(player_id=0, turn=45), saved_view)
        source.assert_not_called()
        saved.prefix.runtime.evaluate_text.assert_not_called()

    def test_xp2_checkpoint_restores_unconsidered_empty_envoy_reserve(self):
        expected = dict(self.catalogue(), tokens_to_give=0, giving_tokens_blocker_present=False)
        loaded = dict(expected, considered=True)
        saved, calls = self.checkpoint_owner(expected)
        with patch.object(adapter, 'catalogue', side_effect=[loaded, expected]), \
             patch.object(adapter, '_checkpoint_source', return_value={'live_spans': {}}), \
             patch.object(adapter.native, '_common', return_value=b''), \
             patch('civ6_host.runtime.saved_load_job_observer.require_quiescent'), \
             patch('civ6_host.runtime.xp1_load_capability.capability_source_scope',
                   return_value=nullcontext()):
            adapter.restore_checkpoint_consideration(saved, dict(player_id=0, turn=45), expected)
        source = saved.prefix.runtime.evaluate_text.call_args.args[1]
        self.assertIn(b'tokens == 0', source)
        self.assertIn(b'SetGivingTokensConsidered(false)', source)
        self.assertFalse(calls[-1][2]['blocker_after'])
        self.assertFalse(calls[-1][2]['player_command_submitted'])

    def test_unblocked_positive_reserve_restores_only_the_authenticated_byte(self):
        expected = dict(self.catalogue(), tokens_to_give=2, giving_tokens_blocker_present=False)
        loaded = dict(expected, considered=True)
        saved, calls = self.checkpoint_owner(expected)
        loaded_game, registry, slots, player, influence = range(0x100000, 0x600000, 0x100000)
        saved.continuation.lease = SimpleNamespace(identity={'game': loaded_game})
        base = saved.core._handle
        memory = {}

        def put(address, data):
            memory.update({address + index: b for index, b in enumerate(data)})

        for address, value in (
                (base + 0xb8aa68, loaded_game), (loaded_game + 0x240, registry),
                (registry + 0x20, slots), (slots, player), (player + 0x748, influence)):
            put(address, value.to_bytes(8, 'little'))
        put(registry + 0x2da8, bytes(4))
        put(player + 0xd8, bytes(4))
        field = influence + 0x4a0
        put(field - 8, player.to_bytes(8, 'little') + b'\x01' + b'\xaf' * 7)
        put(base + 0x2eb3e0, b'proof')
        source = dict(source_spans={'field': dict(rva=0x2eb3e0, size=5,
                     sha256=hashlib.sha256(b'proof').hexdigest())})
        native_memory = SimpleNamespace(read=lambda address, size: bytes(memory[address + i] for i in range(size)),
                                        write=Mock(side_effect=put))
        with patch('civ6_host.runtime.native.native_checkpoint_stream.LocalMemory', return_value=native_memory), \
             patch.object(adapter, '_checkpoint_source', return_value={'live_spans': {}}), \
             patch.object(adapter, '_unblocked_checkpoint_source', return_value=source), \
             patch.object(adapter, 'catalogue', side_effect=[loaded, expected]), \
             patch('civ6_host.runtime.saved_load_job_observer.require_quiescent'), \
             patch('civ6_host.runtime.xp1_load_capability.capability_source_scope',
                   return_value=nullcontext()):
            # A stale registry must be rejected before any write.
            saved.continuation.lease.identity['game'] = loaded_game + 8
            with self.assertRaisesRegex(ValueError, 'different loaded game'):
                adapter._restore_unblocked_flag(saved, 0, source)
            native_memory.write.assert_not_called()
            saved.continuation.lease.identity['game'] = loaded_game
            adapter.restore_checkpoint_consideration(saved, dict(player_id=0, turn=45), expected)

        native_memory.write.assert_called_once_with(field, b'\x00')
        self.assertEqual(native_memory.read(field + 1, 7), b'\xaf' * 7)
        saved.prefix.runtime.evaluate_text.assert_not_called()
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][1], ('xp2_envoy_checkpoint_consideration_restored',))
        self.assertEqual(calls[0][2]['source_sha256'], adapter.UNBLOCKED_CHECKPOINT_SOURCE[1])
        self.assertFalse(calls[0][2]['blocker_after'])

    def test_rise_and_fall_restores_only_its_pinned_pending_choice(self):
        import pefile
        from civ6_host.runtime import xp1_city_state_envoys as xp1
        from civ6_host.runtime.execution_images import _XP1_PROFILE

        saved_view = self.catalogue()
        after_load = dict(saved_view, considered=True, giving_tokens_blocker_present=False)
        saved, calls = self.checkpoint_owner(saved_view)
        saved.core._civ6_host_execution_image = _XP1_PROFILE
        saved.backend.load_abi.core_sha256 = XP1_CORE_SHA256
        image = pefile.PE(_XP1_PROFILE.path, fast_load=True)
        self.addCleanup(image.close)
        saved.backend.runtime = SimpleNamespace(
            read=lambda address, size: image.get_data(address - saved.core._handle, size))

        with patch.object(adapter, 'catalogue', side_effect=[after_load, saved_view]), \
             patch.object(adapter.native, '_common', return_value=b''), \
             patch('civ6_host.runtime.saved_load_job_observer.require_quiescent'), \
             patch('civ6_host.runtime.xp1_load_capability.capability_source_scope',
                   return_value=nullcontext()):
            adapter.restore_checkpoint_consideration(saved, dict(player_id=0, turn=45), saved_view)
        self.assertIn(b'SetGivingTokensConsidered(false)',
                      saved.prefix.runtime.evaluate_text.call_args.args[1])
        self.assertEqual(calls[-1][1][0], 'xp1_envoy_checkpoint_consideration_restored')
        self.assertEqual(calls[-1][2]['source_sha256'], xp1.CHECKPOINT_SOURCE[1])
        self.assertTrue(calls[-1][2]['blocker_after'])
        self.assertFalse(calls[-1][2]['player_command_submitted'])


if __name__=='__main__':
    unittest.main()
