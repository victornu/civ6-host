"""New government wiring at the native-call boundary; not a native witness."""
from copy import deepcopy
import struct
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch

from civ6_host.contracts import government
from civ6_host.runtime import xp2_government as runtime, xp2_government_source as source
from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256


def raw_state():
    return dict(catalog=dict(status='catalog',player_id=0,current_game_turn=23,
        current_government_index=0,can_change_government_at_all=True,
        government_change_made=False,civic_completed_this_turn=True,choices=[
            dict(index=0,hash=-1,unlocked=True,can_change=False,anarchy_turns=0,requires_anarchy_path=False),
            dict(index=3,hash=809918684,unlocked=True,can_change=True,anarchy_turns=0,requires_anarchy_path=False),
            dict(index=4,hash=99,unlocked=True,can_change=True,anarchy_turns=2,requires_anarchy_path=True)]),
        consideration=dict(player_id=0,current_game_turn=23,government_index=0,
                           considered=False,consideration_blocker_present=True))


class GovernmentRuntimeTests(unittest.TestCase):
    def test_projection_retains_locked_or_anarchy_rows_and_unsigned_identity(self):
        raw=raw_state()
        view=runtime.project(raw,0,23)
        self.assertEqual(len(view['choices']),len(raw['catalog']['choices']))
        self.assertEqual(view['choices'][0]['hash'],0xffffffff)
        self.assertEqual(view['choices'][2]['anarchy_turns'],2)
        self.assertEqual(government.actions(view),[
            dict(kind='government',index=3,hash=809918684),dict(kind='retain_government',index=0)])
        with self.assertRaises(ValueError): runtime.project(raw,0,24)
        for bad in (dict(kind='government',index=3,hash=True),
                    dict(kind='retain_government',index=0,hash=0)):
            with self.assertRaises(ValueError): government.validate_action(bad)

    def test_live_bind_checks_xp2_code_and_packet_targets_without_base_addresses(self):
        memory={}
        from civ6_host.runtime.xp2_policy_source import verify_source
        profiles=[verify_source(),source.source()]
        app=source.application_source()
        bodies=[body for proof in profiles for body in proof['functions'].values()]
        bodies.extend(row['body'] for row in app['packet']['functions'].values())
        bodies.extend(row['body'] for row in app['subtype1_application']['functions'].values())
        base=0x180000000
        for body in bodies:
            for fragment in body['fragments']:
                raw=bytes.fromhex(fragment['raw_hex'])
                rva=int(fragment['start_rva'],16)
                for offset in range(0,len(raw),4096):
                    block=raw[offset:offset+4096]
                    memory[(base+rva+offset,len(block))]=block
        for row in app['packet']['vtable_targets']:
            memory[(base+int(app['packet']['vtable_rva'],16)+row['slot']*8,8)]=(base+int(row['target_rva'],16)).to_bytes(8,'little')
        reader=Mock(side_effect=lambda address,size:memory[(address,size)])
        backend=NS(check_thread=Mock(),core=NS(_handle=base),runtime=NS(read=reader),
                   load_abi=NS(core_sha256=XP2_CORE_SHA256))
        saved=NS(backend=backend)
        source.bind_owner(saved)
        count=reader.call_count
        source.bind_owner(saved)
        self.assertEqual(reader.call_count,count)
        del backend._xp2_government_source
        memory[(base+0x9bdcc0+3*8,8)]=(base+0x02a940).to_bytes(8,'little')
        with self.assertRaisesRegex(ValueError,'packet vtable'): source.bind_owner(saved)

    def test_request_is_native_archive_then_verified_adoption_and_slot_refresh(self):
        raw=raw_state(); before=dict(player_id=0,turn=23,cities=[])
        initial=runtime.project(raw,0,23)
        after=deepcopy(initial);after.update(current_index=3,changed=True,considered=True,consideration_blocker=False)
        action=dict(kind='government',index=3,hash=809918684)
        pending=[]
        stages=[]
        def evaluate(child,code,name,**kwargs):
            if name==b'@xp2_government_request':
                self.assertIn(b'culture:RequestChangeGovernment(expectedHash)',code)
                pending.append(struct.pack('<7I',0xe57882af,0,1,3,0xffffffff,0,0))
                stages.append('request')
                return b'submitted|0|23|0|3|809918684|1'
            self.assertEqual(name,b'@xp2_government_effect')
            self.assertFalse(pending)
            stages.append('effect')
            return b'effect|0|23|0|3|809918684|3|1'
        def deliver():
            self.assertEqual(len(pending),1);pending.pop(0);stages.append('deliver')
        actions=NS(pending=pending,deliver_one=deliver)
        prefix=NS(actions=actions,deferred_events=NS(pending=[],drain=lambda:stages.append('drain')),
                  view_publisher=NS(publish=lambda:stages.append('publish')),
                  runtime=NS(evaluate_text=evaluate),ui_child=1)
        saved=NS(prefix=prefix,emit=Mock(),continuation=NS(explicit_government=initial,explicit_government_raw=raw))
        with patch.object(runtime,'read',side_effect=[initial,after]), \
             patch('civ6_host.runtime.native.native_player_observation.observe_player',return_value=before), \
             patch('civ6_host.runtime.xp2_policies.read',return_value=dict(slots=[{}, {}, {}, {}])) as slots:
            result=runtime.apply(saved,action,before)
        self.assertEqual(result['effect']['current_government_index'],3)
        self.assertEqual(stages,['request','deliver','drain','publish','effect'])
        slots.assert_called_once_with(saved,before)
        event=saved.emit.call_args.kwargs
        self.assertEqual(event['policy_slot_count'],4)
        self.assertFalse(event['automatic_choices_applied'])

    def test_submission_is_not_mistaken_for_adoption(self):
        raw=raw_state();before=dict(player_id=0,turn=23)
        initial=runtime.project(raw,0,23)
        pending=[]
        def evaluate(child,code,name,**kwargs):
            if name==b'@xp2_government_request':
                pending.append(struct.pack('<7I',0xe57882af,0,1,3,0xffffffff,0,0))
                return b'submitted|0|23|0|3|809918684|1'
            return b'effect|0|23|0|3|809918684|0|0'
        prefix=NS(actions=NS(pending=pending,deliver_one=lambda:pending.pop(0)),
            deferred_events=NS(pending=[],drain=lambda:None),view_publisher=NS(publish=lambda:None),
            runtime=NS(evaluate_text=evaluate),ui_child=1)
        saved=NS(prefix=prefix,emit=Mock(),continuation=NS(explicit_government=initial,explicit_government_raw=raw))
        with patch.object(runtime,'read',return_value=initial),self.assertRaisesRegex(RuntimeError,'adoption'):
            runtime.apply(saved,dict(kind='government',index=3,hash=809918684),before)
        self.assertEqual(saved.emit.call_count,1)

    def test_anarchy_selection_refuses_before_request(self):
        raw=raw_state();before=dict(player_id=0,turn=23)
        public=runtime.project(raw,0,23)
        saved=NS(continuation=NS(explicit_government=public),prefix=NS(),emit=Mock())
        with patch.object(runtime,'read',return_value=public),self.assertRaisesRegex(RuntimeError,'not offered'):
            runtime.apply(saved,dict(kind='government',index=4,hash=99),before)
        saved.emit.assert_not_called()
