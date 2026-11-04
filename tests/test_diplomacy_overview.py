import hashlib
import json
import struct
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from civ6_host.runtime import diplomacy_overview as overview

try:
    from lupa.lua51 import LuaRuntime
except ImportError:
    LuaRuntime = None


def selection(key, *, disabled=False, supported=None):
    if supported is None:
        supported = key in overview.DIRECT_REQUEST_CHOICES
    return dict(key=key, disabled=disabled, supported=supported,
                text='LOC_' + key, tooltip=None, diplomatic_action_type=None)


def catalog(*, capability=True, paused=False, rows=None):
    return dict(schema=overview.SCHEMA, player_id=0, turn=8,
        capability=capability, paused=paused,
        targets=([dict(player_id=2, selections=list(rows or ()))] if capability else []),
        complete_action_space=False)


def configuration(*, paused=False):
    return dict(initiator=1, paused=paused,
                players={0:dict(leader='LEADER_CATHERINE_DE_MEDICI'), 1:dict(human=True)})


class DiplomacyOverviewTests(unittest.TestCase):
    def test_pause_variant_matches_source_widths_and_refuses_missing_memory(self):
        proof = overview._verify_pause_source()
        self.assertEqual(proof['pause_property']['value_hash_decimal'], 0x86c5b7d8)
        def raw(tag, value=0, flags=0):
            data=bytearray(24)
            struct.pack_into('<H', data, 0, tag)
            struct.pack_into('<Q', data, 8, value)
            struct.pack_into('<I', data, 20, flags)
            return bytes(data)
        for tag in (1,5):
            self.assertFalse(overview.paused_from_variant(raw(tag,256)))
            self.assertTrue(overview.paused_from_variant(raw(tag,1)))
        for tag in (2,3):
            self.assertFalse(overview.paused_from_variant(raw(tag,1 << 32)))
            self.assertTrue(overview.paused_from_variant(raw(tag,256)))
        for tag in (20,21):
            self.assertTrue(overview.paused_from_variant(raw(tag,1 << 32)))
        self.assertFalse(overview.paused_from_variant(raw(1,1,1 << 29)))
        self.assertFalse(overview.paused_from_variant(raw(0,1)))
        for absent in (None,b'',b'\0'*23,b'\0'*25):
            with self.assertRaises(ValueError):
                overview.paused_from_variant(absent)

    def test_pause_reader_uses_live_native_value_and_detects_provider_change(self):
        native = 'civ6_host.runtime.native.native_world_configuration.'
        owner = SimpleNamespace(check_thread=Mock(),emit=Mock(),context=9,
            core=SimpleNamespace(_handle=1000),owner=Mock(),
            runtime=SimpleNamespace(read=Mock(),call=None))
        owner.owner.snapshot.return_value={'normalized':5000}
        off=b'\x01'+b'\0'*23
        on=off[:8]+b'\x01'+off[9:]
        with patch.object(overview,'_verify_pause_source'), \
             patch(native+'verify_source'), patch(native+'_live_getter'), \
             patch(native+'_value',side_effect=[off,on,on]) as read:
            self.assertFalse(overview.read_pause(owner))
            self.assertTrue(overview.read_pause(owner))
            owner.owner.snapshot.side_effect=[{'normalized':5000},{'normalized':5001}]
            with self.assertRaisesRegex(RuntimeError,'provider changed'):
                overview.read_pause(owner)
        self.assertEqual(read.call_count,3)
        self.assertEqual(read.call_args.args[-1],'GAME_PAUSED')
        self.assertEqual(owner.emit.call_count,2)

    def test_configuration_reads_real_enum_and_existing_native_participant_getters(self):
        owner = SimpleNamespace(check_thread=Mock(), prefix=SimpleNamespace(
            runtime=SimpleNamespace(evaluate_text=Mock(return_value=b'-2')), ui_child=9))
        with patch('civ6_host.runtime.native.native_diplomacy_configuration.read',
                   return_value={0:dict(leader='LEADER_CATHERINE_DE_MEDICI')}) as read, \
             patch.object(overview, 'read_pause', return_value=True):
            result = overview.read_configuration(owner, 0)
        self.assertEqual(result['initiator'], -2)
        self.assertTrue(result['paused'])
        read.assert_called_once_with(owner, {'fields': {'FromPlayer': 0, 'Initiator': -2}})
        owner.check_thread.assert_called_once()

    def test_unknown_pause_and_incomplete_configuration_are_not_false_defaults(self):
        for value in (None, configuration(paused=None), configuration(paused=0),
                      dict(initiator=1, paused=False, players={0:dict(leader=None)})):
            with self.subTest(value=value), self.assertRaises(ValueError):
                overview._configuration_bindings(value, 0)

    def test_source_proof_is_pinned_and_contains_exact_overview_dispatchers(self):
        proof = overview._verify_proof()
        self.assertEqual(proof['official_ui_sha256'], overview.UI_SHA256)
        self.assertEqual(proof['functions']['AddStatmentOptions']['sha256'],
                         hashlib.sha256(proof['functions']['AddStatmentOptions']['source'].encode()).hexdigest())
        self.assertIn('DiplomacyManager.RequestSession(ms_LocalPlayerID, ms_SelectedPlayerID, "DENOUNCE")',
                      proof['functions']['OnSelectInitialDiplomacyStatement']['source'])
        self.assertIn('PlayerManager.GetAliveMajors()',
                      proof['functions']['PopulateDiplomacyRibbon']['source'])

    def test_official_reader_reuses_greeting_recipe_and_native_filters(self):
        with patch.object(overview, '_verify_proof', return_value={}), \
                patch.object(overview, '_verify_capability_source'), \
                patch.object(overview, '_official_source', side_effect=[b'ui', b'support']), \
                patch('civ6_host.runtime.native.native_diplomacy_default.handler_source', return_value=b'handlers'):
            generated = overview.source(0, 8, configuration=configuration())
        self.assertIn(b"ExtractStatement(handler,kind,'NONE',pid,DiplomacyMoodTypes.ANY,DiplomacyInitiatorTypes.HUMAN)", generated)
        self.assertIn(b'handler.RemoveInvalidSelections(parsed,pid,other)', generated)
        self.assertIn(b"DiplomacySupport_RemoveSelectionByKey(parsed,'CHOICE_EXIT')", generated)
        self.assertIn(b'PlayerManager.GetAliveMajors()', generated)
        self.assertIn(b'GameInfo.GameCapabilities', generated)
        self.assertIn(b"local capability=GameInfo.GameCapabilities['CAPABILITY_DIPLOMACY']~=nil", generated)
        self.assertIn(b"assert(type(paused)=='boolean'", generated)
        self.assertIn(b"Game.GetLocalObserver()==pid", generated)
        self.assertIn(b"Game.GetCurrentGameTurn()==requestedTurn", generated)
        self.assertIn(b'GameConfiguration.IsPaused()', generated)

    def test_parser_preserves_unsupported_deal_options_and_candidates_only_offer_direct_routes(self):
        value = catalog(rows=[selection('CHOICE_DECLARE_FORMAL_WAR'),
                              selection('CHOICE_DECLARE_FRIENDSHIP'),
                              selection('CHOICE_MAKE_DEAL'),
                              selection('CHOICE_MAKE_DEMAND'),
                              selection('CHOICE_VIEW_DEAL'),
                              selection('CHOICE_DENOUNCE', disabled=True)])
        parsed = overview.parse(json.dumps(value).encode(), 0, 8)
        self.assertEqual(parsed, value)
        self.assertEqual(overview.candidates(parsed), [
            dict(kind='diplomacy_initiate', target_player_id=2,
                 choice='CHOICE_DECLARE_FORMAL_WAR'),
            dict(kind='diplomacy_initiate', target_player_id=2,
                 choice='CHOICE_DECLARE_FRIENDSHIP'),
        ])
        self.assertFalse(parsed['targets'][0]['selections'][2]['supported'])
        self.assertFalse(parsed['targets'][0]['selections'][3]['supported'])
        self.assertEqual(parsed, value)

    def test_capability_pause_and_disabled_choices_close_candidate_surface(self):
        active = selection('CHOICE_DENOUNCE')
        disabled = selection('CHOICE_OPEN_BORDERS', disabled=True)
        self.assertEqual(overview.candidates(catalog(rows=[active], paused=True)), [])
        self.assertEqual(overview.candidates(catalog(rows=[active], capability=False)), [])
        self.assertEqual(overview.candidates(catalog(rows=[disabled])), [])

    def test_parse_rejects_forged_supported_mapping_identity_and_exit(self):
        forged = catalog(rows=[selection('CHOICE_MAKE_DEAL', supported=True)])
        with self.assertRaises(ValueError):
            overview.parse(json.dumps(forged).encode(), 0, 8)
        with self.assertRaises(ValueError):
            overview.parse(json.dumps(catalog(rows=[selection('CHOICE_DENOUNCE')])).encode(), 1, 8)
        with self.assertRaises(ValueError):
            overview.parse(json.dumps(catalog(rows=[selection('CHOICE_EXIT')])).encode(), 0, 8)

    def test_request_source_revalidates_and_uses_original_one_call_dispatch(self):
        proof = overview._verify_proof()
        with patch.object(overview, '_verify_capability_source'), \
                patch('civ6_host.runtime.native.native_diplomacy_default.handler_source', return_value=b'handlers'):
            request = overview.request_source(0, 8, 2, 'CHOICE_DENOUNCE', configuration=configuration())
        self.assertIn(b"assert(allowed,'Diplomacy choice is no longer available')", request)
        self.assertIn(proof['functions']['OnSelectInitialDiplomacyStatement']['source'].encode(), request)
        self.assertIn(b'calls=calls+1; return nativeDiplomacy.RequestSession(attacker,recipient,kind)', request)
        self.assertIn(b'attacker==pid and recipient==target and kind=="DENOUNCE"', request)
        self.assertNotIn(b'DiplomacyManager.RequestSession=', request)
        self.assertIn(b'Game.GetLocalObserver()==pid', request)
        self.assertIn(b'Game.GetCurrentGameTurn()==requestedTurn', request)
        self.assertIn(b"return 'requested'", request)

    def test_request_rejects_unsupported_or_malformed_keys(self):
        for key in ('CHOICE_MAKE_DEAL', 'CHOICE_VIEW_DEMAND', 'CHOICE_EXIT', 'DENOUNCE'):
            with self.subTest(key=key), self.assertRaises(ValueError):
                overview.request_source(0, 8, 2, key, configuration=configuration())
        with self.assertRaises(ValueError):
            overview.request_source(0, 8, 0, 'CHOICE_DENOUNCE', configuration=configuration())

    @unittest.skipIf(LuaRuntime is None, 'optional Lua 5.1 fixture unavailable')
    def test_request_source_lua51_calls_original_dispatch_once_without_global_mutation(self):
        with patch.object(overview, '_verify_capability_source'), \
                patch.object(overview, '_lua_helpers', return_value=b''):
            source = overview.request_source(0, 8, 2, 'CHOICE_DENOUNCE', configuration=configuration())
        lua = LuaRuntime(unpack_returned_tuples=True)
        lua.execute(LUA_FIXTURE + '\nGameConfiguration=nil; PlayerConfigurations=nil')
        result = lua.execute(source)
        self.assertEqual(result, 'requested')
        self.assertEqual(lua.eval('#nativeRequests'), 1)
        self.assertEqual(lua.eval('nativeRequests[1][1]'), 0)
        self.assertEqual(lua.eval('nativeRequests[1][2]'), 2)
        self.assertEqual(lua.eval('nativeRequests[1][3]'), 'DENOUNCE')
        self.assertTrue(lua.eval('DiplomacyManager==nativeManager'))
        self.assertTrue(lua.eval('GameConfiguration==nil and PlayerConfigurations==nil'))

    @unittest.skipIf(LuaRuntime is None, 'optional Lua 5.1 fixture unavailable')
    def test_request_source_lua51_refuses_freshly_disabled_choice_before_native_call(self):
        with patch.object(overview, '_verify_capability_source'), \
                patch.object(overview, '_lua_helpers', return_value=b''):
            source = overview.request_source(0, 8, 2, 'CHOICE_DENOUNCE', configuration=configuration())
        lua = LuaRuntime(unpack_returned_tuples=True)
        lua.execute(LUA_FIXTURE + '\noptionDisabled=true')
        with self.assertRaises(Exception):
            lua.execute(source)
        self.assertEqual(lua.eval('#nativeRequests'), 0)
        self.assertTrue(lua.eval('DiplomacyManager==nativeManager'))

    @unittest.skipIf(LuaRuntime is None, 'optional Lua 5.1 fixture unavailable')
    def test_overview_lua51_keeps_missing_capability_empty_and_refuses_unknown_pause(self):
        with patch.object(overview, '_verify_capability_source'), \
                patch.object(overview, '_lua_helpers', return_value=b''):
            source = overview.source(0, 8, configuration=configuration())
        lua = LuaRuntime(unpack_returned_tuples=True)
        lua.execute(LUA_FIXTURE)
        lua.execute('GameInfo.GameCapabilities={}')
        parsed = overview.parse(lua.execute(source).encode(), 0, 8)
        self.assertFalse(parsed['capability'])
        self.assertEqual(parsed['targets'], [])
        with self.assertRaises(ValueError):
            overview.source(0, 8, configuration=configuration(paused=None))

    @unittest.skipIf(LuaRuntime is None, 'optional Lua 5.1 fixture unavailable')
    def test_live_pause_snapshot_gates_choices_without_mutating_global_binding(self):
        with patch.object(overview, '_verify_capability_source'), \
                patch.object(overview, '_lua_helpers', return_value=b''):
            source = overview.source(0, 8, configuration=configuration(paused=True))
        lua = LuaRuntime(unpack_returned_tuples=True)
        lua.execute(LUA_FIXTURE)
        parsed = overview.parse(lua.execute(source).encode(), 0, 8)
        self.assertTrue(parsed['paused'])
        self.assertEqual(overview.candidates(parsed), [])
        self.assertFalse(lua.eval('GameConfiguration.IsPaused()'))


LUA_FIXTURE = r'''
optionDisabled=false
Game={GetLocalPlayer=function() return 0 end,
 GetLocalObserver=function() return 0 end,
 GetCurrentGameTurn=function() return 8 end}
GameInfo={GameCapabilities={CAPABILITY_DIPLOMACY=true}}
GameConfiguration={IsPaused=function() return false end}
DiplomacyMoodTypes={ANY=1}
DiplomacyInitiatorTypes={HUMAN=1}
local localDiplomacy={HasMet=function(self,id) return id==2 end}
Players={}
Players[0]={GetID=function(self) return 0 end,
 GetDiplomacy=function(self) return localDiplomacy end}
local other={GetID=function(self) return 2 end,
 IsMajor=function(self) return true end}
Players[2]=other
PlayerManager={GetAliveMajors=function() return {other} end}
local greeting={Selections={{Key='CHOICE_DENOUNCE',Sort=1,Text='LOC_DENOUNCE',
 Tooltip=nil,DiplomaticActionType='DENOUNCE',IsDisabled=false}}}
local handler={}
handler.ExtractStatement=function(self,kind,subtype,initiator,mood,initiatorType)
 assert(kind=='GREETING' and subtype=='NONE' and initiator==0 and mood==1 and initiatorType==1)
 local copy={Selections={}}
 for i,s in ipairs(greeting.Selections) do
  copy.Selections[i]={Key=s.Key,Sort=s.Sort,Text=s.Text,Tooltip=s.Tooltip,
   DiplomaticActionType=s.DiplomaticActionType,IsDisabled=optionDisabled}
 end
 return copy
end
handler.RemoveInvalidSelections=function(self,parsed,player,target) end
GetStatementHandler=function(kind) assert(kind=='GREETING'); return handler end
DiplomacySupport_RemoveSelectionByKey=function(parsed,key)
 for i=#parsed.Selections,1,-1 do
  if parsed.Selections[i].Key==key then table.remove(parsed.Selections,i) end
 end
end
nativeRequests={}
DiplomacyManager={RequestSession=function(attacker,target,kind)
 nativeRequests[#nativeRequests+1]={attacker,target,kind}; return true
end}
nativeManager=DiplomacyManager
'''


if __name__ == '__main__':
    unittest.main()
