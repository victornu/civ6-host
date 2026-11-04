import hashlib
import struct
import unittest
import re
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from civ6_host.runtime import unit_panel_gate as panel
from civ6_host.runtime.capture_profiles import LAN_PROFILE


def record(seq, pid, active=True, first=True):
    raw=bytearray(96)
    struct.pack_into('<III',raw,0,96,15 if active else 16,seq)
    struct.pack_into('<Ii',raw,80,seq,pid)
    raw[88]=int(first)
    return bytes(raw)


class UnitPanelGateTests(unittest.TestCase):
    def test_guard_matches_shipped_lua_handlers_for_local_and_other_players(self):
        from lupa.lua51 import LuaRuntime
        from civ6_host.runtime.provenance import resource_root
        import json
        proof=json.loads((resource_root()/panel.SOURCE[0]).read_text())
        ref=next(r for r in proof['sources'] if r['path'].endswith('UnitPanel.lua'))
        raw=Path(ref['path']).read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),ref['sha256'])
        text=raw.decode('utf-8-sig')
        chunks=[]
        for name in ('OnPlayerTurnDeactivated','OnPlayerTurnActivated','ShowHideSelectedUnit'):
            at=text.index('function '+name+'(')
            end=text.index('\n-- ===========================================================================',at)
            chunks.append(re.sub(r'\s*:\s*(?:number|boolean|table)\b','',text[at:end]))
        lua=LuaRuntime()
        lua.execute('Game={GetLocalPlayer=function() return 0 end}; UI={GetHeadSelectedUnit=function() return nil end}; Hide=function() end; '+re.search(r'g_isOkayToProcess\s*=\s*true;',text).group(0))
        lua.execute('\n'.join(chunks))
        state=panel.UnitPanelEventState()
        for seq,(pid,active,first) in enumerate(((1,False,False),(0,False,False),(2,True,True),(0,True,False),(0,False,False),(0,True,True)),1):
            event=state.consume(record(seq,pid,active,first))
            if active:lua.globals().OnPlayerTurnActivated(pid,first)
            else:lua.globals().OnPlayerTurnDeactivated(pid)
            self.assertEqual(state.view(0)['processing_allowed'],lua.globals().g_isOkayToProcess)

    def test_signed_player_and_boolean_argument_order(self):
        event=panel.decode_record(record(1,-1,first=False))
        self.assertEqual((event['player_id'],event['first_time']),(-1,False))
        self.assertTrue(event['processing_allowed'])
        event=panel.decode_record(record(2,4,active=False))
        self.assertIsNone(event['first_time'])
        self.assertFalse(event['processing_allowed'])
        bad=bytearray(record(3,0));struct.pack_into('<I',bad,80,4)
        with self.assertRaises(ValueError):panel.decode_record(bytes(bad))

    def test_only_local_events_change_each_viewpoint_and_order_is_preserved(self):
        state=panel.UnitPanelEventState()
        self.assertTrue(state.view(0)['processing_allowed'])
        state.consume(record(2,0,active=False))
        state.consume(record(4,1))
        self.assertFalse(state.view(0)['processing_allowed'])
        self.assertTrue(state.view(1)['processing_allowed'])
        state.consume(record(7,0,first=False))
        self.assertTrue(state.view(0)['processing_allowed'])
        with self.assertRaises(ValueError):state.consume(record(7,0,active=False))
        self.assertTrue(state.view(0)['processing_allowed'])
        self.assertEqual(state.view(0)['event_sequence'],7)

    def owner(self):
        configuration=b'fixture-only'
        events=SimpleNamespace(pending=[],unit_panel_event_state=panel.UnitPanelEventState())
        return SimpleNamespace(inputs=SimpleNamespace(profile=LAN_PROFILE,
                configuration=configuration,official_bundle=('fixture','hash')),
            prefix=SimpleNamespace(deferred_events=events),
            network_reference={'state':{'player_id':0}},
            network_ui_admission=dict(schema='civ6-host.lan-ui-gates.v4',
                configuration_sha256=hashlib.sha256(configuration).hexdigest(),
                bundle_reference=('fixture','hash'),unit_panel_source_sha256=panel.SOURCE[1],
                captured_tutorial_inactive=True))

    def test_catalogue_and_dispatch_use_same_gate_without_native_flag_substitution(self):
        owner=self.owner();native={'native':'fixture'}
        target='civ6_host.runtime.unit_work_info.read_catalog'
        with patch(target,return_value=(native,{'public':'fixture'})) as read:
            self.assertIs(panel.catalog(owner,owner.prefix,1,player_id=0),native)
            self.assertTrue(read.call_args.kwargs['processing'])
            owner.prefix.deferred_events.unit_panel_event_state.consume(record(1,0,active=False))
            panel.catalog(owner,owner.prefix,1,player_id=0)
            self.assertFalse(read.call_args.kwargs['processing'])
            self.assertEqual(owner.unit_work_information_by_player[0],{'public':'fixture'})
            self.assertEqual(read.call_count,2)
            with self.assertRaisesRegex(ValueError,'guard is closed'):panel.require_command(owner,0)
            owner.prefix.deferred_events.unit_panel_event_state.consume(record(2,0))
            panel.require_command(owner,0)

    def test_unadmitted_content_and_pending_events_do_not_grant_access(self):
        owner=self.owner();owner.prefix.deferred_events.pending=[record(1,0,active=False)]
        with self.assertRaisesRegex(ValueError,'drained'):panel.gate(owner,0)
        owner.prefix.deferred_events.pending=[]
        with self.assertRaisesRegex(ValueError,'viewpoint'):panel.gate(owner,1)
        owner.network_ui_admission['unit_panel_source_sha256']='unknown'
        with self.assertRaisesRegex(ValueError,'not admitted'):panel.gate(owner,0)

    def test_actual_fifo_consumer_updates_gate_before_removing_validated_record(self):
        from civ6_host.runtime.native.native_host_events import NativeDeferredHostEvents
        events=object.__new__(NativeDeferredHostEvents)
        events.pending=[record(1,0,active=False),record(2,1),record(3,0)]
        events.consumed_count=events.consumed_bytes=0
        events.consumed_digest=hashlib.sha256()
        events.empty_receiver_state={}
        captured=[];events.emit=lambda stage,**kw:captured.append((stage,kw))
        with patch('civ6_host.runtime.native.native_deferred_empty_profile.validate_empty_profile_record',return_value={}):
            self.assertEqual(events._drain_empty_receivers_once(),3)
        self.assertFalse(events.pending)
        self.assertTrue(events.unit_panel_event_state.view(0)['processing_allowed'])
        self.assertEqual(events.unit_panel_event_state.view(0)['event_sequence'],3)
        self.assertEqual(sum(stage=='native_unit_panel_gate_event' for stage,_ in captured),3)

    def terrain_case(self, *, consumed=False, available=True):
        from civ6_host.runtime.native import native_world_input as world
        owner=self.owner();owner.world_input_selections={0:5}
        owner.emit=lambda *args,**kwargs:None
        action=dict(kind='build_improvement',unit_id=7,x=1,y=1,plot_id=11,
                    charges=1 if consumed else 2,moves_token='1',index=1,hash=123,
                    item_type='IMPROVEMENT_FARM',selector=1)
        before=dict(player_id=0,turn=2,units=[dict(id=5),dict(id=7)])
        after=dict(before,units=[dict(id=5)] if consumed else before['units'])
        def observe(owner,obs):
            return dict(schema=world.SCHEMA,player_id=0,turn=2,width=10,height=10,
                units=[dict(unit_id=u['id'],ignore_moves=False) for u in obs['units']],
                selected_unit_id=owner.world_input_selections[0],war_prompt=None)
        def select(owner,choice,turn,obs):
            self.assertEqual(choice,dict(kind='world_select_unit',unit_id=7))
            owner.world_input_selections[0]=7
            return obs
        def apply(owner,prefix,choice,turn,obs,**kw):
            self.assertEqual(owner.world_input_selections[0],7)
            return after
        with patch('civ6_host.runtime.native.native_saved_unit_work.catalog',return_value=dict(
                offers=[dict(action=action,legal=True)] if available else [])), \
             patch('civ6_host.runtime.native.native_world_input.observe',side_effect=observe), \
             patch('civ6_host.runtime.native.native_world_input.apply',side_effect=select) as selected, \
             patch('civ6_host.runtime.native.native_saved_unit_work.apply',side_effect=apply) as applied:
            if available:
                self.assertEqual(panel.apply_terrain(owner,owner.prefix,action,2,before,player_id=0),after)
                self.assertEqual(selected.call_count,1);self.assertEqual(applied.call_count,1)
            else:
                with self.assertRaisesRegex(ValueError,'before selecting'):
                    panel.apply_terrain(owner,owner.prefix,action,2,before,player_id=0)
                selected.assert_not_called();applied.assert_not_called()
        return owner

    def test_compound_command_selects_requested_unit_before_one_native_operation(self):
        owner=self.terrain_case()
        self.assertEqual(owner.world_input_selections[0],7)

    def test_consumed_unit_clears_selection_without_selecting_another_ready_unit(self):
        owner=self.terrain_case(consumed=True)
        self.assertIsNone(owner.world_input_selections[0])

    def test_stale_terrain_choice_does_not_change_existing_selection(self):
        owner=self.terrain_case(available=False)
        self.assertEqual(owner.world_input_selections[0],5)


if __name__=='__main__':unittest.main()
