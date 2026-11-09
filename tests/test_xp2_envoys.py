"""Source-byte and composed-owner tests; no DLL invocation or native effect."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from civ6_host.runtime import xp2_envoys as adapter
from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256


class Xp2EnvoySourceTests(unittest.TestCase):
    def test_source_dependencies_project_captured_core_to_selected_execution_image(self):
        from civ6_host.runtime import execution_images
        from civ6_host.runtime import xp2_envoys_source as source
        image = execution_images.select(
            'xp2-gamecore-current-092abfbb',
            core_path=execution_images._GAMECORE_PATH,
        )
        pins = source.source_dependencies(execution_image=image)
        self.assertEqual(pins[image.path], image.image_sha256)
        self.assertNotIn(image.reference_core_sha256, pins.values())

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
        saved=SimpleNamespace(prefix=prefix,backend=SimpleNamespace(core=object(),context=object()),
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


if __name__=='__main__':
    unittest.main()
