"""Real saved boundary and shared turn algorithm; only native calls are fixtures."""
import ctypes as C
import hashlib
import struct
from types import SimpleNamespace as NS
import unittest

import pefile
from lupa.lua51 import LuaRuntime

from civ6_host.runtime import network_turns, xp2_turn_segment
from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
from civ6_host.runtime.captured_session_profile import select
from civ6_host.runtime.lan_load import _LAN_MODE, _SIMULTANEOUS_PHASE
from civ6_host.runtime.xp1_turn_boundary import XP2_BOUNDARY, BOUNDARY
from test_xp2_espionage import SpySession
from test_xp2_world_configuration import Fixture as ConfigurationFixture


UI = '''
segment=1278700307; turn=61; observer=0
Game={GetLocalPlayer=function()return 0 end,GetLocalObserver=function()return observer end,
 GetCurrentGameTurn=function()return turn end,GetCurrentTurnSegment=function()return segment end,
 IsAllowTacticalCommands=function()return false end}
Players={}
for id=0,1 do
 local human=(id==0)
 Players[id]={IsHuman=function()return human end,IsAlive=function()return true end,
 IsTurnActive=function()return human end,IsTurnActiveComplete=function()return human end,
 CanUnreadyTurn=function()return false end,
 GetUnits=function()return {GetFirstReadyUnit=function()return nil end}end}
end
NotificationManager={GetFirstEndTurnBlocking=function()return -1 end,
 GetAllEndTurnBlocking=function()return {}end,FindEndTurnBlocking=function()return nil end,
 FindType=function()return nil end}
EndTurnBlockingTypes={NO_ENDTURN_BLOCKING=-1,ENDTURN_BLOCKING_STACKED_UNITS=1,
 ENDTURN_BLOCKING_UNIT_NEEDS_ORDERS=2,ENDTURN_BLOCKING_UNITS=3}
NotificationTypes={CITY_RANGE_ATTACK=1}
'''


class Fixture(SpySession):
    mapped = None

    def __init__(self):
        super().__init__()
        self.configuration = cfg = ConfigurationFixture()
        if Fixture.mapped is None:
            pe = pefile.PE(str(self.image.path))
            pe.relocate_image(cfg.base)
            Fixture.mapped = pe.get_memory_mapped_image()
        self.backend.core._handle = cfg.base
        self.backend.runtime = NS(read=self.read, call=self.call)
        self.backend.owner = cfg.backend.owner
        self.backend.context = self.saved.context = 0x1234
        self.backend.emit = self.emit
        cfg.put(cfg.base + cfg.source['vtable_rva'] + 0x58, struct.pack('<Q', cfg.base+0x99f570))
        profile = select(XP2_CORE_SHA256)
        inputs = NS(profile=profile.candidate.profile, official_bundle=profile.candidate.reference)
        self.saved.inputs = self.backend.inputs = inputs
        self.backend.captured_bundle = NS(reference=profile.candidate.reference, inputs=inputs)
        self.saved.network_reference = dict(capture_manifest_sha256=profile.candidate.reference[1],
            state=dict(game_mode_u32=_LAN_MODE,turn_phase_u32=_SIMULTANEOUS_PHASE,player_id=0,observer_id=0),
            major_player_ids=(0,1),human_player_ids=(0,))
        self.saved.world_congress_diagnostic = True
        self.prefix.game_child = object()
        self.prefix.actions.request_end_turn = self.request
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        self.lua.execute(UI)
        self.next_segment = 0xb52a667b - 2**32
        self.segment_result = None
        self.read_hook = None
        self.activate()

    def read(self, address, count):
        cfg = self.configuration
        return bytes(cfg.memory[address+i] if address+i in cfg.memory
                     else self.mapped[address+i-cfg.base] for i in range(count))

    def call(self,address,result_type,arg_types,receiver,key):
        cfg = self.configuration
        assert address == cfg.base+0x99f570 and receiver == cfg.root
        assert result_type is C.c_void_p and arg_types == (C.c_uint32,)
        return None  # Native nullable timer lookup: official no-timer state.

    def evaluate(self, child, source, label, **kwargs):
        assert child is (self.prefix.game_child if label==b'@lan_session_humans' else self.prefix.ui_child)
        self.calls.append(label.decode())
        raw = self.lua.execute(source.decode()).encode()
        if label==b'@xp2_turn_segment':
            if self.read_hook:
                self.read_hook()
            if self.segment_result is not None:
                raw = self.segment_result
        assert len(raw) < kwargs['capacity']
        return raw

    def request(self,player_id,*,player_ids,user_forced):
        assert (player_id,player_ids,user_forced)==(0,(0,1),True)
        self.calls.append('request')
        self.prefix.actions.pending.append(self.archive)

    def deliver(self):
        super().deliver()
        self.lua.globals().segment = self.next_segment

    def submit(self):
        return network_turns.submit(self.saved, {'kind':'force_end_turn'}, 0, boundary=XP2_BOUNDARY)


class TurnSegmentTests(unittest.TestCase):
    def fixture(self):
        f = Fixture()
        self.addCleanup(f.close)
        return f

    def test_composed_boundary_observes_changed_segment_with_equal_readiness(self):
        f = self.fixture()
        result = f.submit()
        self.assertEqual(result,dict(status='completed',reason='endturn_segment_changed',
                                    requested_action={'kind':'force_end_turn'}))
        self.assertEqual(f.delivered,[f.archive])
        stage, event = f.emitted[-1]
        self.assertEqual(stage,'official_lan_turn_request_effect')
        self.assertEqual(event['before'],event['after'])
        self.assertEqual((event['before_turn_segment'],event['after_turn_segment']),
                         (1278700307,0xb52a667b))
        self.assertFalse(event['network_ack_inferred'])
        self.assertFalse(event['turn_advanced'])
        self.assertNotIn('turn_segment',event['before'])
        self.assertEqual(f.calls.count('@xp2_turn_segment'),2)
        self.assertLess(f.calls.index('publish'),len(f.calls)-1-f.calls[::-1].index('@xp2_turn_segment'))
        self.assertFalse(f.prefix.actions.pending)
        self.assertFalse(f.prefix.deferred_events.pending)

    def test_equal_segment_does_not_accept_equal_readiness(self):
        f = self.fixture()
        f.next_segment = 1278700307
        with self.assertRaisesRegex(RuntimeError,'effect is unresolved'):
            f.submit()
        self.assertEqual(f.delivered,[f.archive])
        self.assertFalse(any(name=='official_lan_turn_request_effect' for name,_ in f.emitted))

    def test_older_xp2_scope_performs_no_segment_read(self):
        f = self.fixture()
        f.saved.world_congress_diagnostic = False
        with self.assertRaisesRegex(RuntimeError,'effect is unresolved'):
            f.submit()
        self.assertNotIn('@xp2_turn_segment',f.calls)
        self.assertIsNone(BOUNDARY.turn_segment(object(),0,61))
        self.assertIsNone(network_turns.BASE_BOUNDARY.turn_segment(object(),0,61))

    def test_source_corruption_and_unavailable_segment_refuse_before_enqueue(self):
        for corruption in ('source','sentinel','nonintegral','foreign_observer'):
            with self.subTest(corruption=corruption):
                f = self.fixture()
                if corruption=='source':
                    f.configuration.put(f.configuration.base+0x69b030,b'\xcc')
                elif corruption=='sentinel': f.lua.globals().segment=-1
                elif corruption=='nonintegral': f.lua.globals().segment=1.5
                else: f.lua.globals().observer=1
                message = {'source':'Live turn-segment getter differs','sentinel':'segment unavailable',
                           'nonintegral':'segment unavailable','foreign_observer':'identity or observer changed'}[corruption]
                with self.assertRaisesRegex(Exception,message):
                    f.submit()
                self.assertNotIn('request',f.calls)
                self.assertFalse(f.delivered)

    def test_malformed_after_marker_never_becomes_success(self):
        f = self.fixture()
        f.next_segment = -1
        with self.assertRaisesRegex(Exception,'segment unavailable'):
            f.submit()
        self.assertEqual(f.delivered,[f.archive])
        self.assertFalse(any(name=='official_lan_turn_request_effect' for name,_ in f.emitted))

    def test_getter_checks_owner_revision_and_canonical_payload(self):
        for mutation in ('revision','payload'):
            with self.subTest(mutation=mutation):
                f=self.fixture()
                if mutation=='revision':
                    f.read_hook=lambda: setattr(f.continuation,'sequence',8)
                else: f.segment_result=b'01'
                message='owner changed' if mutation=='revision' else 'Malformed native turn-segment'
                with self.assertRaisesRegex((RuntimeError,ValueError),message):
                    xp2_turn_segment.read(f.saved,0,61)
                self.assertFalse(f.delivered)


if __name__=='__main__': unittest.main()
