from __future__ import annotations

import json
import unittest
from types import SimpleNamespace

try:
    from lupa.lua51 import LuaRuntime
except ImportError:
    LuaRuntime = None

from civ6_host.runtime import xp2_world_war_display as display


PID, TURN, DEFENDER, WAR = 0, 47, 2, 1133958949
CONFIG = {'is_any_multiplayer': False, 'players': {
    DEFENDER: {'short_description': 'LOC_TEST_CIV',
               'civilization_type_name': 'CIVILIZATION_TEST',
               'is_human': False, 'player_name': None,
               'level_type_id': 0}}}


FIXTURE = b'''\
callFromPlayer=nil
Game={GetLocalPlayer=function() return 0 end,
 GetLocalObserver=function() return 0 end,
 GetCurrentGameTurn=function() return 47 end}
WarTypes={SURPRISE_WAR=1133958949}
DiplomacyActionTypes={SET_WAR_STATE=71}
GlobalParameters={GRIEVANCES_SUZERAIN_CITY_STATE_DOW=17,
 GRIEVANCES_HAVE_ENVOYS_CITY_STATE_DOW=23}
local diplomacy={
 ComputeDOWWarmongerPoints=function(_,target,war) assert(target==2 and war==1133958949); return 9 end,
 GetWarmongerLevel=function(_,points) return points end}
local attacker={GetDiplomacy=function() return diplomacy end,
 IsMajor=function() return true end, GetID=function() return 0 end}
targetMajor=false
suzerain=-1
tokens=0
local influence={GetSuzerain=function() return suzerain end,
 GetTokensReceived=function(_,player) assert(player==1); return tokens end}
local target={IsMajor=function() return targetMajor end,
 GetInfluence=function() return influence end, GetID=function() return 2 end}
local otherMajor={GetID=function() return 1 end}
Players={[0]=attacker,[1]=otherMajor,[2]=target}
PlayerManager={GetAliveMajors=function() return {attacker,otherMajor} end}
DiplomacyManager={TestAction=function(from,targetID,action,params)
 assert(targetID==2 and action==71 and params.WarState==1133958949)
 callFromPlayer=from; return true,{} end}
Locale={Lookup=function(key,value)
 if value~=nil then return key..':'..tostring(value) end
 if key=='LOC_TEST_CIV' then return 'Test Civilization' end
 if key=='LOC_DIPLO_WARNING_DECLARE_WAR_FROM_UNIT_ATTACK_INFO_MULTIPLE' then return 'Warning' end
 if key=='LOC_DECLARE_WAR_BUTTON' then return 'Confirm' end
 if key=='LOC_DIPLOMACY_DEAL_EXIT_DEAL' then return 'Cancel' end
 if key=='{LOC_DECLARE_WAR_HEADER:upper}' then return 'Declare War' end
 if key=='LOC_DECLARE_WAR_WARMONGER_HEADING' then return 'Consequences' end
 return key end}
'''


@unittest.skipIf(LuaRuntime is None, 'optional Lua 5.1 fixture unavailable')
class XP2WorldWarDisplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = display.verify_source()

    def render(self, *, major=False, suzerain=-1, tokens=0, e_from_player=None,
               global_parameters=True):
        lua = LuaRuntime(encoding=None)
        lua.execute(FIXTURE)
        lua.globals().targetMajor = major
        lua.globals().suzerain = suzerain
        lua.globals().tokens = tokens
        if not global_parameters:
            lua.globals().GlobalParameters = None
        if e_from_player is not None:
            lua.globals().eFromPlayer = e_from_player
        code = display.display_source(PID, TURN, [DEFENDER], WAR, CONFIG)
        envelope = lua.execute(code)
        if type(envelope) is str:
            envelope = envelope.encode('utf-8')
        result = display.parse_display(envelope, PID, TURN, [DEFENDER], WAR)
        return result, envelope

    def test_source_selection_and_xp2_schema_keeps_final_text_separate(self):
        self.assertEqual(self.source['source_sha256'], display.verify_source()['source_sha256'])
        self.assertEqual(self.source['selected_popup_chain'], [
            'Expansion1.modinfo: Expansion1_DeclareWarPopup',
            'Expansion2.modinfo: Expansion2_DeclareWarPopup',
            'DeclareWarPopup_Expansion2', 'DeclareWarPopup_Expansion1', 'DeclareWarPopup'])
        result, _ = self.render(major=True)
        self.assertEqual(result['schema'], 'civ6-host.xp2-world-war-display.v1')
        self.assertEqual(result['consequences'], 'LOC_DIPLO_CHOICE_GENERATES_GRIEVANCES_INFO:9')
        self.assertNotIn('warmonger_text', result)
        self.assertEqual(result['buttons'], [
            {'accept': False, 'text': 'Cancel'}, {'accept': True, 'text': 'Confirm'}])
        self.assertEqual(result['static_text'],
                         {'title': 'Declare War', 'warmonger_heading': 'Consequences'})

    def test_suzerain_and_foreign_envoy_city_state_branches_use_official_overlay(self):
        suzerain, _ = self.render(suzerain=1)
        envoys, _ = self.render(suzerain=-1, tokens=1)
        self.assertEqual(suzerain['consequences'],
                         'LOC_DIPLO_CHOICE_GENERATES_GRIEVANCES_INFO_SUZERAIN:17')
        self.assertEqual(envoys['consequences'],
                         'LOC_DIPLO_CHOICE_GENERATES_GRIEVANCES_INFO_ENVOYS_PRESENT:23')

    def test_global_parameters_is_required_only_when_official_overlay_reads_it(self):
        major, _ = self.render(major=True, global_parameters=False)
        no_suzerain_or_other_envoys, _ = self.render(
            suzerain=0, tokens=0, global_parameters=False)
        self.assertEqual(major['consequences'],
                         'LOC_DIPLO_CHOICE_GENERATES_GRIEVANCES_INFO:9')
        self.assertEqual(no_suzerain_or_other_envoys['consequences'],
                         'LOC_DIPLO_CHOICE_GENERATES_GRIEVANCES_INFO:0')
        with self.assertRaisesRegex(Exception, 'GlobalParameters'):
            self.render(suzerain=1, global_parameters=False)

    def test_unbound_e_from_player_is_preserved_and_non_nil_context_refuses(self):
        lua = LuaRuntime(encoding=None)
        lua.execute(FIXTURE)
        code = display.display_source(PID, TURN, [DEFENDER], WAR, CONFIG)
        lua.execute(code)
        self.assertIsNone(lua.globals().callFromPlayer)
        lua = LuaRuntime(encoding=None)
        lua.execute(FIXTURE)
        lua.globals().eFromPlayer = 9
        with self.assertRaises(Exception):
            lua.execute(code)

    def test_malformed_envelope_identity_and_source_refuse(self):
        _, envelope_bytes = self.render(major=True)
        envelope = json.loads(envelope_bytes)
        for changes in ({'player_id': 4}, {'turn': TURN + 1},
                        {'source_sha256': '0' * 64}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                value = dict(envelope, **changes)
                display.parse_display(json.dumps(value).encode(), PID, TURN, [DEFENDER], WAR)

    def test_native_namespace_registration_is_once_per_retained_child(self):
        class Child:
            def __init__(self, pointer):
                self.active, self.pointer = True, pointer

        class Registry:
            def validate(self, child):
                if not child.active:
                    raise ValueError('released child')
                return child.pointer

        child = Child(0x1234)
        registrations = []
        class Runtime:
            pass

        runtime = Runtime()
        runtime.database_bound, runtime.service_owner = True, object()
        runtime.registry = Registry()
        runtime.namespaces = SimpleNamespace(register=lambda context, name:
                                              registrations.append((context, name)))
        host = runtime.service_owner
        backend = SimpleNamespace(core=object(), host=host)
        prefix = SimpleNamespace(
            runtime=runtime, ui_child=child, backend=backend, core=backend.core,
            host=host, closed=False, quarantined=False)
        identity = object()

        class Owner:
            def _check(self):
                return backend, object(), prefix, identity

        owner = Owner()
        display.ensure_global_parameters_namespace(owner, backend, prefix, identity)
        display.ensure_global_parameters_namespace(owner, backend, prefix, identity)
        self.assertEqual(registrations, [(child, 'GlobalParameters')])
        original_identity = identity
        identity = object()
        with self.assertRaisesRegex(RuntimeError, 'rebound'):
            display.ensure_global_parameters_namespace(owner, backend, prefix, identity)
        identity = original_identity
        prefix.ui_child = Child(0x5678)
        with self.assertRaisesRegex(RuntimeError, 'child'):
            display.ensure_global_parameters_namespace(owner, backend, prefix, identity)
        self.assertEqual(len(registrations), 1)

    def test_namespace_registration_refuses_without_bound_core_database(self):
        class Runtime:
            pass

        runtime = Runtime()
        runtime.database_bound, runtime.service_owner = False, object()
        runtime.registry = SimpleNamespace(validate=lambda child: child.pointer)
        runtime.namespaces = SimpleNamespace(register=lambda *args: self.fail('registered without DB'))
        backend = SimpleNamespace(core=object(), host=runtime.service_owner)
        class Child:
            pointer = 1

        prefix = SimpleNamespace(runtime=runtime, ui_child=Child(),
            backend=backend, core=backend.core, host=backend.host,
            closed=False, quarantined=False)
        identity = object()

        class Owner:
            def _check(self):
                return backend, object(), prefix, identity

        with self.assertRaisesRegex(RuntimeError, 'gameplay database'):
            display.ensure_global_parameters_namespace(Owner(), backend, prefix, identity)


if __name__ == '__main__':
    unittest.main()
