"""Portable checks of the direct religious request and current XP2 pantheon reader."""
from copy import deepcopy
import ctypes
import struct
import unittest
from unittest.mock import patch

from civ6_host.runtime import xp1_pantheon as pantheon, xp2_direct_religion_source as source
from civ6_host.runtime import xp2_religious_chain_source as chain, xp2_initial_choice_source
from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
from civ6_host.runtime.native import native_pantheon_actions as builders
from civ6_host.runtime.native import native_player_operation_request as operations
from civ6_host.runtime.native import native_saved_pantheon as shared
from civ6_host.runtime.xp1_research_profile import player_operation_abi
from test_xp2_religious_chain_session import Fixture


class DirectReligiousRequestTests(unittest.TestCase):
    def fixture(self):
        current = Fixture(0)
        self.addCleanup(current.close)
        return current

    def test_current_readback_uses_exact_player_turn_and_native_index(self):
        from lupa.lua51 import LuaRuntime
        chunk = builders.index_source(0,8,core_sha256=XP2_CORE_SHA256)
        lua = LuaRuntime(encoding=None)
        environment = b"""
local current,actor,observer,turn,allow = INDEX,ACTOR,OBSERVER,TURN,ALLOW
local religion={GetPantheon=function() return current end,CanCreatePantheon=function() return true end}
local player={IsAlive=function() return true end,IsTurnActive=function() return true end,
    IsTurnActiveComplete=function() return true end,GetReligion=function() return religion end}
local Game={GetLocalPlayer=function() return actor end,GetLocalObserver=function() return observer end,
    GetCurrentGameTurn=function() return turn end,IsAllowStrategicCommands=function() return allow end}
local Players={[0]=player}
"""
        for index in (-1,0,117,0x7fffffff):
            wire = lua.execute(environment.replace(b'INDEX',str(index).encode()).replace(b'ACTOR',b'0')
                .replace(b'OBSERVER',b'0').replace(b'TURN',b'8').replace(b'ALLOW',b'true')+chunk)
            self.assertEqual(builders.parse_index(wire,0,8),index)
        for wire in (b'pantheon,1,8,0',b'pantheon,0,7,0',b'pantheon,0,8,-2',
                     b'pantheon,0,8,2147483648',b'pantheon,0,8,0.0'):
            with self.subTest(wire=wire),self.assertRaises(ValueError):
                builders.parse_index(wire,0,8)
        self.assertEqual(lua.execute(builders.guard_case(core_sha256=XP2_CORE_SHA256)),b'pantheon-guards-ok')

    def test_real_parameter_builder_submits_pantheon_without_generic_canstarter(self):
        fixture = self.fixture()
        prefix = fixture.saved.prefix
        core = fixture.backend.core
        base = core._handle
        abi = player_operation_abi(XP2_CORE_SHA256,operations._METHODS)
        fixture.memory.put(prefix.context,struct.pack('<Q',base+abi.outer))
        for table,offset,_ in xp2_initial_choice_source.SLOTS:
            rva = table+offset
            value = struct.unpack('<Q',fixture.pe.get_data(rva,8))[0]
            fixture.memory.put(base+rva,struct.pack('<Q',
                value-fixture.pe.OPTIONAL_HEADER.ImageBase+base))

        current = -1
        choice = dict(kind='pantheon',index=4,hash=0x80000000)
        checked = dict(valid=True,operation=source.PANTHEON,
                       parameters={0xa44b2907:choice['hash'],0xac2fdc09:0x97fea5c6})
        checked['choice'] = dict(player_id=0,current_game_turn=8,selected_hash=choice['hash'],
                                 parameters=dict(checked['parameters']))
        native_calls,owners,maps = [],[],{}

        def construct(address,table):
            ctypes.memmove(address,struct.pack('<Q',base+table),8)
            maps[address]={}
            return address

        def set_value(address,key,value):
            native = ctypes.create_string_buffer(struct.pack('<H6xI4xQ',2,value,0),24)
            owners.append(native)
            pointer = ctypes.addressof(native)
            maps[address][key]=pointer
            return pointer

        def submit(context,player,operation,address):
            self.assertEqual((context,player,operation),(prefix.context,0,source.PANTHEON))
            admitted = dict((key,struct.unpack('<I',ctypes.string_at(ptr+8,4))[0])
                            for key,ptr in maps[address].items())
            self.assertEqual(admitted,checked['parameters'])
            native_calls.append('request')
            prefix.actions.pending.append(struct.pack('<6I',0xc45de12f,player,operation,0,0x80000001,2)
                +b''.join(struct.pack('<IHH10xI',key,0,2,value) for key,value in admitted.items()))

        def must_not_check(*args):
            raise AssertionError('The official XP2 pantheon UI does not call generic CanStart')

        native_api = dict(parameter_ctor=lambda addr: construct(addr,abi.parameters),
                          parameter_dtor=lambda addr: maps.pop(addr),
                          reason_ctor=lambda addr: construct(addr,abi.reasons),
                          reason_dtor=lambda addr: maps.pop(addr),
                          lookup=lambda addr,key: maps[addr].get(key,0),set_u32=set_value,
                          request=submit,can_start=must_not_check)

        def evaluate(child,code,name,**kw):
            from lupa.lua51 import LuaRuntime
            self.assertIs(child,prefix.ui_child)
            if name==b'@native_pantheon_guards':
                return LuaRuntime(encoding=None).execute(code)
            if name==b'@native_pantheon_turn':
                return b'8'
            if name==b'@explicit_pantheon_index':
                return f'pantheon,0,8,{current}'.encode()
            if name in (b'@explicit_pantheon_catalog',b'@native_pantheon_catalog'):
                return (b'not_due,0,8,already_has_pantheon' if current>=0 else
                    b'catalog,0,8,2524039121,2756389127,2888817673,2550048198,1,4:2147483648')
            if name==b'@native_pantheon_revalidation':
                return b'valid,0,8,4,2147483648,2524039121,2756389127,2888817673,2550048198'
            if name==b'@native_pantheon_effect' and current==4:
                return b'verified,0,8,4,2147483648,4'
            raise AssertionError(name)

        original_drain = fixture.virtual
        def virtual(native_core,pointer,slot,rva,result,*args):
            if rva==prefix.actions.transport_abi.drain_rva:
                def drain(context):
                    nonlocal current
                    self.assertEqual(context,prefix.context)
                    fixture.memory.put(fixture.sentinel,struct.pack('<QQ',fixture.sentinel,fixture.sentinel))
                    # Existing A0 receiver consumes a real typed host record;
                    # only GameCore's machine field producer is doubled.
                    fields = {key:struct.pack('<H6xQ4xI',tag,value,0) for key,tag,value in
                      ((0xa1e5a149,3,0),(0xd6fcf3e4,2,0),(0xa1fbc372,2,4))}
                    fixture.owner.dispatch(0x565abe26,fields,0)
                    current=4
                return drain
            return original_drain(native_core,pointer,slot,rva,result,*args)

        from civ6_host.runtime.native import native_action_transport
        original_operation = operations.request_player_operation
        def with_native_api(*args, **kwargs):
            return original_operation(*args,**kwargs,native_api=native_api)
        with (patch.object(prefix.runtime,'evaluate_text',evaluate),
              patch.object(shared,'observe_player',fixture.observe_native),
              patch.object(native_action_transport,'virtual',virtual),
              patch.object(operations,'request_player_operation',with_native_api)):
            self.assertEqual(pantheon.read_pantheon_index(fixture.saved,fixture.token.observation),-1)
            self.assertEqual(pantheon.actions(pantheon.catalogue(fixture.saved,fixture.token.observation)),[choice])
            fixture.set_active(True)
            permit = source._request_permit(prefix,0,8,checked)
            for invalid in ({**checked['parameters'],0xa44b2907:0},dict(reversed(tuple(checked['parameters'].items())))):
                with self.assertRaises(ValueError):
                    source.authorize_request(permit,core,prefix.context,0,source.PANTHEON,invalid,
                        core_sha256=XP2_CORE_SHA256,submit=True,allow_empty=False)
            self.assertEqual(native_calls,[])
            effect=pantheon.apply(fixture.saved,choice,fixture.token.observation)
            self.assertEqual((effect['status'],effect['selected_index'],effect['selected_hash']),
                             ('completed',4,0x80000000))
            self.assertEqual(effect['source_sha256'],source.SOURCE[1])
            self.assertEqual(native_calls,['request'])
            self.assertEqual(maps,{})
            self.assertEqual(prefix.actions.pending,[])
            self.assertEqual(prefix.deferred_events.pending,[])
            self.assertEqual(prefix.deferred_events.consumed_count,1)
            fixture.set_active(False)
            self.assertEqual(pantheon.read_pantheon_index(fixture.saved,fixture.token.observation),4)
            self.assertEqual(pantheon.catalogue(fixture.saved,fixture.token.observation)['reason'],
                             'already_has_pantheon')


if __name__=='__main__':
    unittest.main()