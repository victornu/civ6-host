"""Administrative boundary fixtures; actual Save/Load needs the native group."""
import copy
import struct
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from civ6_host.runtime import network_checkpoint as checkpoint
from civ6_host.runtime.capture_profiles import LAN_PROFILE


class NetworkCheckpointTests(unittest.TestCase):
    def setUp(self):
        self.session=dict(game_mode='LAN',turn_phase='TURNPHASE_SIMULTANEOUS',turn=2,
            local_player_id=0,human_player_ids=[0],active_human_player_ids=[0])
        self.controls=dict(active=True,active_complete=True,can_unready=False,timer_elapsed=False)
        self.owner=SimpleNamespace(network_turn_rows={0:dict(active=True),1:dict(active=False)},
            control=lambda **kwargs:None,world_input_prompts={},turn_continuation=None)
        self.ps=patch('civ6_host.runtime.network_owner.state',return_value=self.session)
        self.pc=patch('civ6_host.runtime.network_turns.controls',return_value=self.controls)
        self.ps.start();self.pc.start();self.addCleanup(self.ps.stop);self.addCleanup(self.pc.stop)

    def test_save_boundary_is_explicitly_active_untimed_and_quiescent(self):
        expected=dict(session=self.session,controls=self.controls)
        self.assertEqual(checkpoint.validate_boundary(self.owner),expected)
        for key,value in [('active',False),('active_complete',False),('can_unready',True),('timer_elapsed',None),('timer_elapsed',True)]:
            original=self.controls[key];self.controls[key]=value
            with self.assertRaises(ValueError):checkpoint.validate_boundary(self.owner)
            self.controls[key]=original

    def test_close_does_not_call_the_live_checkpoint_writer_after_victory(self):
        from civ6_host.runtime.workers.network_worker import _save_before_close

        protocol = SimpleNamespace(last_outcome={'terminated': True}, sequence=4)
        request = dict(player_id=0, sequence=5)
        with patch('civ6_host.runtime.xp1_session_checkpoint.save') as expansion_save, \
             patch.object(checkpoint, 'save') as base_save, patch.object(self.owner, 'control') as emit:
            for expansion in (False, True):
                _save_before_close(self.owner, protocol, {}, None, request, expansion, emit)
            expansion_save.assert_not_called()
            base_save.assert_not_called()
            self.assertEqual(emit.call_count, 2)
            emit.assert_called_with('native_checkpoint_skipped',
                                    reason='official_native_victory', sequence=5)

    def test_other_humans_ai_or_modal_state_do_not_enter_save(self):
        self.owner.network_turn_rows[1]['active']=True
        with self.assertRaises(ValueError):checkpoint.validate_boundary(self.owner)
        self.owner.network_turn_rows[1]['active']=False
        self.owner.turn_continuation=object()
        with self.assertRaises(ValueError):checkpoint.validate_boundary(self.owner)
        self.owner.turn_continuation=None
        self.owner.world_input_prompts={0:dict(defending_player=1)}
        with self.assertRaises(ValueError):checkpoint.validate_boundary(self.owner)
        self.owner.world_input_prompts={}
        self.session['human_player_ids']=[0,1]
        with self.assertRaises(ValueError):checkpoint.validate_boundary(self.owner)

    def test_saved_and_restored_views_are_compared_without_identity_substitution(self):
        observation=dict(turn=2,player_id=0)
        decisions=dict(schema='capacity-fixture',episode_id='old',game_generation='old',sequence=4,
                       decision_id='old',candidates=[dict(candidate_id='opaque',action=dict(kind='move',unit_id=1))])
        restored=copy.deepcopy(decisions);restored.update(episode_id='new',game_generation='new',sequence=0,decision_id='new')
        owner=SimpleNamespace(inputs=SimpleNamespace(checkpoint=('work/checkpoint.json','a'*64),official_bundle=('work/capture.json','b'*64)),emit=lambda *a,**k:None)
        with patch.object(checkpoint,'manifest',return_value=dict(observation=observation,decisions=decisions)):
            checkpoint.compare_decisions(owner,observation,restored)
            restored['candidates'][0]['action']['unit_id']=2
            with self.assertRaisesRegex(ValueError,'catalogue differs'):
                checkpoint.compare_decisions(owner,observation,restored)

    def test_native_save_option_keeps_legacy_scope_and_exact_boolean(self):
        from civ6_host.runtime.native.native_session_checkpoint import validate_option
        for mode in ['single','lan']:
            self.assertTrue(validate_option(dict(checkpoint_on_close=True,input_profile=mode)))
        for mode in ['hotseat-four','unknown']:
            with self.assertRaises(ValueError):validate_option(dict(checkpoint_on_close=True,input_profile=mode))
        with self.assertRaises(ValueError):validate_option(dict(checkpoint_on_close=1,input_profile='lan'))

    def test_checkpoint_boundary_uses_saved_lan_roster_not_single_default(self):
        owner=SimpleNamespace(inputs=SimpleNamespace(profile=LAN_PROFILE),network_reference=dict(major_player_ids=(0,1,2,3,4,5)))
        with patch('civ6_host.runtime.native.native_saved_actions.boundary',return_value='prefix') as boundary:
            self.assertEqual(checkpoint.checkpoint_boundary(owner),'prefix')
            boundary.assert_called_once_with(owner,player_id=0,player_ids=(0,1,2,3,4,5))

    def test_shared_save_writer_keeps_legacy_default_and_accepts_explicit_lan_budget(self):
        from civ6_host.runtime.native import native_checkpoint_retained_save as retained
        for override in (None, 10566514):
            backend=object.__new__(retained.NativeRetainedSaveBackend)
            backend.observe=lambda:dict(identity='fixture')
            backend.state=lambda:dict(turn=2)
            backend.prefix=object();backend.memory=SimpleNamespace(read=object())
            backend.owner=SimpleNamespace(streams=[])
            if override is not None:backend.stream_call_limit=override
            with patch.object(retained.diagnostic,'bind_save',return_value=(object(),{})), \
                 patch.object(retained.diagnostic,'check_control_boundary',return_value={}), \
                 patch.object(retained,'Win64Stream') as writer:
                backend.prepare()
                writer.assert_called_once_with('writer',max_bytes=retained.MAX_BYTES,
                    max_calls=retained.MAX_CALLS if override is None else override)

    def test_lazy_private_ring_is_observed_without_inventing_a_bank(self):
        from civ6_host.runtime.native.native_checkpoint_diagnostic import check_control_boundary
        deferred=SimpleNamespace(pending=[],_sequence=0,consumed_count=0,
            host_notification_counter=0,host_metadata_counter=0,
            combat_map_registry=None,private_progress_ring=None)
        prefix=SimpleNamespace(deferred_events=deferred,actions=SimpleNamespace(pending=[]),
                               core=SimpleNamespace(_handle=0x10000000))
        sentinel=prefix.core._handle+9156296
        def read(address,size):
            if (address,size)==(sentinel,8):return struct.pack('<Q',sentinel)
            if (address,size)==(prefix.core._handle+9156608,4):return b'\x01\x01\x00\x00'
            self.fail('Unexpected memory read')
        with self.assertRaisesRegex(RuntimeError,'initialized private bank'):
            check_control_boundary(prefix,read)
        observed=check_control_boundary(prefix,read,allow_uninitialized_private=True)
        self.assertIsNone(observed['private_selector'])
        self.assertIsNone(observed['private_cursors'])
        self.assertIsNone(deferred.private_progress_ring)
        ring=SimpleNamespace(poisoned=False,selector=0,cursors=[128,0])
        deferred.private_progress_ring=ring
        with self.assertRaisesRegex(RuntimeError,'drained active private bank'):
            check_control_boundary(prefix,read,allow_uninitialized_private=True)
        self.assertEqual(ring.cursors,[128,0])
        ring.cursors[0]=0
        self.assertEqual(check_control_boundary(prefix,read)['private_cursors'],[0,0])
        ring.poisoned=True
        with self.assertRaisesRegex(RuntimeError,'drained active private bank'):
            check_control_boundary(prefix,read,allow_uninitialized_private=True)


if __name__=='__main__':unittest.main()
