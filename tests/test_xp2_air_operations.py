"""Exercise both exact air input routes and the public action boundary."""

from contextlib import contextmanager
from copy import deepcopy
from struct import pack
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

import pefile
from lupa.lua51 import LuaRuntime

from civ6_host import SessionClient
from civ6_host.contracts import air_operations, network_turn
from civ6_host.runtime import xp2_air_operations as air, xp2_bbg_inputs, xp2_bundle_inputs
from civ6_host.runtime.a0_family_source import verify_pinned_files
from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
from civ6_host.runtime.execution_images import _PROFILE
from civ6_host.runtime.paths import resource_root
from test_xp2_great_person_activation import checked_event, checked_json, seal


class AirOperationsTests(TestCase):
    def test_current_binary_and_content_inputs(self):
        with pefile.PE(_PROFILE.path, fast_load=True) as pe:
            base = pe.OPTIONAL_HEADER.ImageBase
            air.verify_live(base, lambda address, size: pe.get_data(address-base, size), _PROFILE)
        for reference in (xp2_bundle_inputs.REFERENCE, xp2_bbg_inputs.REFERENCE):
            dependencies = air.source_dependencies(reference, _PROFILE)
            verify_pinned_files(dependencies)
            self.assertIn(reference[1], dependencies.values())
            self.assertIn(air.SOURCE[1], dependencies.values())
            self.assertIn(air.ATTACK_SOURCE[1], dependencies.values())

    def test_native_style_catalogue_request_revalidation_and_archive(self):
        lua = LuaRuntime(encoding=None)
        lua.execute(br'''
            stale, fighter, war, visible, attacks, diplomacyReads = false, false, false, true, 1, 0
            moves, panelReady = 1, true
            local function unit(id)
                return {GetID=function() return id end, GetOwner=function() return 0 end,
                    GetAttacksRemaining=function() return attacks end,
                    GetMovesRemaining=function() return moves end,
                    GetComponentID=function() assert(id == 28); return 'fighter-component' end}
            end
            local aircraft, warrior = unit(28), unit(29)
            local units = {Members=function() return ipairs({warrior, aircraft}) end,
                           FindID=function(_, id) return id == 28 and aircraft or nil end}
            Players={[0]={GetUnits=function() return units end, IsTurnActive=function() return true end,
                          IsTurnActiveComplete=function() return true end}}
            Game={GetLocalPlayer=function() return 0 end, GetLocalObserver=function() return 0 end,
                  GetCurrentGameTurn=function() return 11 end}
            local deploy, rebase, strike, x, y = 336935588, -1054550409, 526596894, 0x53777b05, 0x4a6c4a44
            GameInfo={UnitOperations={
                UNITOPERATION_DEPLOY={Hash=deploy,Index=25,VisibleInUI=true,InterfaceMode='INTERFACEMODE_DEPLOY'},
                UNITOPERATION_REBASE={Hash=rebase,Index=26,VisibleInUI=true,InterfaceMode='INTERFACEMODE_REBASE'},
                UNITOPERATION_AIR_ATTACK={Hash=strike,Index=27,VisibleInUI=true,InterfaceMode='INTERFACEMODE_AIR_ATTACK'}}}
            UnitOperationTypes={DEPLOY=deploy,REBASE=rebase,AIR_ATTACK=strike,PARAM_X=x,PARAM_Y=y}
            UnitOperationResults={PLOTS=22,MODIFIERS=23,MODIFIER_IS_TARGET=24}
            OperationResultsTypes={NO_TARGETS=40}
            WarTypes={SURPRISE_WAR=-7}
            PlayersVisibility={[0]={IsVisible=function(_, tx, ty) assert(tx == 3 and ty == 1); return visible end}}
            CombatManager={IsAttackChangeWarState=function(component, tx, ty)
                assert(component == 'fighter-component' and visible and tx == 3 and ty == 1)
                diplomacyReads = diplomacyReads + 1
                return war and {2,3} or {}
            end}
            Map={GetPlotCount=function() return 8 end,
                 GetPlotByIndex=function(i)
                    return {GetIndex=function() return i end, GetX=function() return i%4 end,
                            GetY=function() return math.floor(i/4) end}
                 end}
            UnitManager={
                CanStartOperation=function(u, op, third, parameters, flags)
                    assert(third == nil)
                    if parameters == true then return u == aircraft and (op ~= strike or fighter) end
                    if parameters == false then assert(flags == 40); return panelReady end
                    if op == strike then return attacks > 0 and not war and parameters[x] == 3 end
                    return not stale and parameters[y] == 1
                       and (parameters[x] == (op == deploy and 1 or 2))
                end,
                GetOperationTargets=function(u, op)
                    assert(u == aircraft)
                    if op == strike then return {[22]={7,4},[23]={24,25}} end
                    return {[22]={op == deploy and 5 or 6, 0}}
                end,
                RequestOperation=function(u, op, p)
                    if op == strike then attacks = attacks - 1 end
                    capture(u:GetID(), op == deploy and 25 or op == rebase and 26 or 27, p[x], p[y])
                end}
        ''')
        before = dict(player_id=0, turn=11, width=4, height=2,
                      units=[dict(id=28, owner=0, x=0, y=0), dict(id=29, owner=0, x=1, y=0)])
        pending = []
        lua.globals()[b'capture'] = lambda unit, index, x, y: pending.append(
            pack('<IHH8I', 0x8c0f3f36, 0, 1, unit, index, 0xffffffff, 0, 1, x, y, 0))
        fake_core = object()
        runtime = SimpleNamespace(evaluate_text=lambda child, code, label, capacity: lua.execute(code))
        transport = SimpleNamespace(pending=pending, require_empty_native_queue=Mock())

        @contextmanager
        def guarded(validate, *, allow_no_archive):
            def deliver():
                validate(pending[0])
                pending.clear()
            transport.deliver_one = Mock(side_effect=deliver)
            yield
            self.assertTrue(allow_no_archive)
            self.assertFalse(pending)

        transport.require_xp2_single_archive = guarded
        prefix = SimpleNamespace(runtime=runtime, ui_child=object(), actions=transport,
            deferred_events=SimpleNamespace(drain_empty_receivers=Mock()),
            view_publisher=SimpleNamespace(publish=Mock()))
        saved = SimpleNamespace(backend=SimpleNamespace(core=fake_core), prefix=prefix, war_source_sha256='verified',
            _xp2_air_operations_core=fake_core, _check_query=Mock(), _check_active=Mock(),
            continuation=SimpleNamespace(transport=transport, trade_feedback=None, world_input_prompts={}))
        deploy, rebase = air.read(saved, before)
        self.assertEqual([(row['unit_id'], row['operation'], row['plot_id']) for row in (deploy, rebase)],
                         [(28, 'DEPLOY', 5), (28, 'REBASE', 6)])
        after = deepcopy(before)
        after['units'][0].update(x=1, y=1)
        with patch.object(air, 'observe_player', side_effect=[after, before]):
            self.assertEqual(air.apply(saved, deploy, before)['status'], 'completed')
            self.assertEqual(air.apply(saved, rebase, before)['status'], 'submitted')
            lua.globals()[b'stale'] = True
            self.assertEqual(air.apply(saved, rebase, before)['status'], 'refused')
            transport.deliver_one.assert_not_called()
        with self.assertRaises(ValueError):
            air.require_archive(pack('<IHH8I', 0x8c0f3f36, 1, 1, 28, 25, 0xffffffff, 0, 1, 1, 1, 0),
                                actor=0, action=deploy, opcode=25)
        lua.globals()[b'fighter'] = True
        lua.globals()[b'war'] = True
        lua.globals()[b'moves'] = 0
        self.assertEqual(air.read(saved, before), [])
        lua.globals()[b'moves'] = 1
        lua.globals()[b'panelReady'] = False
        self.assertEqual(air.read(saved, before), [])
        lua.globals()[b'panelReady'] = True
        attack, = air.read(saved, before)
        self.assertEqual((attack['operation'], attack['plot_id']), (air_operations.ATTACK, 7))
        pending_result = air.apply(saved, attack, before)
        self.assertEqual((pending_result['status'], pending_result['refusal_code']),
                         ('pending', air.WAR_PENDING))
        self.assertEqual(saved.continuation.world_input_prompts[0],
                         dict(attacking_player=0, defending_player=2, war_type=-7))
        transport.deliver_one.assert_not_called()
        self.assertEqual(lua.globals()[b'attacks'], 1)
        saved.continuation.world_input_prompts.clear()
        lua.globals()[b'war'] = False
        lua.globals()[b'visible'] = False
        before_reads = lua.globals()[b'diplomacyReads']
        self.assertIn(attack, air.read(saved, before))
        with patch.object(air, 'observe_player', return_value=before):
            self.assertEqual(air.apply(saved, attack, before)['status'], 'completed')
        self.assertEqual(lua.globals()[b'attacks'], 0)
        self.assertEqual(lua.globals()[b'diplomacyReads'], before_reads)

    def test_public_client_and_checkpoint_keep_original_choices(self):
        root = resource_root()
        ref = checked_json(root/'evidence/host-xp2-stock-great-writer-work-move-reload-native.json',
                           '7ffb1756a65b79820f90a044018b411ca7fbd1f067dcda707cd1bcc31bc9a23a')
        response = checked_event(root, ref['event_log'], 5454)
        catalogue, observation = response['decisions'], response['observation']
        original = deepcopy(catalogue)
        own = observation['units'][0]
        action = dict(kind=air_operations.KIND, operation=air_operations.ATTACK,
                      unit_id=own['id'], plot_id=0, x=0, y=0)
        network_turn.add_air_choices(catalogue, [action])
        seal(catalogue)
        client = SessionClient(SimpleNamespace(reset=lambda: response, abort=Mock()))
        choices = client.reset()['decisions']
        self.assertEqual(network_turn.select_capability(choices, dict(decision_id=choices['decision_id'],
            candidate_id=network_turn.digest(action))), action)
        projected, transition = network_turn.checkpoint_catalogue(catalogue, original, observation,
                                                                 core_sha256=XP2_CORE_SHA256)
        self.assertEqual(projected, original)
        self.assertEqual(transition['added_action_families'], [air_operations.KIND])
