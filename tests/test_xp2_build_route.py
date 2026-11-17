"""Installed Build Route sources and the native-style catalogue/command boundary."""

from contextlib import contextmanager
from copy import deepcopy
from struct import pack
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

from lupa.lua51 import LuaRuntime
import pefile

from civ6_host import SessionClient
from civ6_host.contracts import network_turn, unit_work
from civ6_host.runtime import xp2_build_route as routes, xp2_bbg_inputs, xp2_bundle_inputs
from civ6_host.runtime.a0_family_source import verify_pinned_files
from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
from civ6_host.runtime.execution_images import _PROFILE
from civ6_host.runtime.paths import resource_root
from test_xp2_great_person_activation import checked_event, checked_json, seal


class BuildRouteTests(TestCase):
    def test_installed_bindings_and_exact_bundles(self):
        with pefile.PE(_PROFILE.path, fast_load=True) as pe:
            base = pe.OPTIONAL_HEADER.ImageBase
            routes.verify_live(base, lambda address, size: pe.get_data(address-base, size), _PROFILE)
        for ref in (xp2_bundle_inputs.REFERENCE, xp2_bbg_inputs.REFERENCE):
            pins = routes.source_dependencies(ref, _PROFILE)
            verify_pinned_files(pins)
            self.assertIn(ref[1], pins.values())

    def test_native_route_selection_revalidation_and_effect(self):
        lua = LuaRuntime(encoding=None)
        lua.execute(br'''
            moves, allowed, route, choice = 1, true, -1, 'ROUTE_RAILROAD'
            local resultKey, operation = 0x3b130e7b, 0x06e68aef
            local unit = {GetX=function() return 2 end, GetY=function() return 1 end,
                          GetOwner=function() return 0 end, GetID=function() return 5 end,
                          GetPlotId=function() return 6 end, GetMovesRemaining=function() return moves end}
            local units = {Members=function() return ipairs({unit}) end,
                           FindID=function(_, id) return id == 5 and unit or nil end}
            Players={[0]={GetUnits=function() return units end, IsTurnActive=function() return true end,
                          IsTurnActiveComplete=function() return true end}}
            Game={GetLocalPlayer=function() return 0 end, GetLocalObserver=function() return 0 end,
                  GetCurrentGameTurn=function() return 16 end}
            GameInfo={UnitOperations={UNITOPERATION_BUILD_ROUTE={Hash=operation,Index=25,VisibleInUI=true}},
                      Routes={ROUTE_RAILROAD={Index=4}, ROUTE_MODERN_ROAD={Index=3}}}
            UnitOperationResults={ROUTE_TYPE=resultKey}
            OperationResultsTypes={NO_TARGETS=99}
            local plot = {GetX=unit.GetX, GetY=unit.GetY, GetRouteType=function() return route end}
            Map={GetPlotByIndex=function(id) assert(id==6); return plot end}
            UnitManager={
                CanStartOperation=function(u, op, third, visible, flags)
                    assert(u==unit and op==operation and third==nil)
                    if visible==true then return true end
                    assert(visible==false and flags==99)
                    return allowed, {[resultKey]=choice}
                end,
                RequestOperation=function(...)
                    assert(select('#',...)==2 and select(1,...)==unit and select(2,...)==operation)
                    capture()
                end}
        ''')
        observation = dict(player_id=0, turn=16, width=4, height=4,
                           units=[dict(owner=0, id=5, x=2, y=1)])
        core = object()
        pending = []
        archive = pack('<IHH5I', 0x8c0f3f36, 0, 1, 5, 25, 0xffffffff, 0, 0)
        lua.globals()[b'capture'] = lambda: pending.append(archive)
        transport = SimpleNamespace(pending=pending, require_empty_native_queue=Mock())

        @contextmanager
        def guarded(validate, *, allow_no_archive):
            def deliver():
                validate(pending[0])
                pending.clear()
                lua.globals()[b'route'] = 4
            transport.deliver_one = Mock(side_effect=deliver)
            yield
            self.assertTrue(allow_no_archive)
            self.assertFalse(pending)

        transport.require_xp2_single_archive = guarded
        prefix = SimpleNamespace(actions=transport, ui_child=object(),
            runtime=SimpleNamespace(evaluate_text=lambda context, code, label, capacity: lua.execute(code)),
            deferred_events=SimpleNamespace(drain_empty_receivers=Mock()),
            view_publisher=SimpleNamespace(publish=Mock()))
        saved = SimpleNamespace(prefix=prefix, _xp2_build_route_core=core, backend=SimpleNamespace(core=core),
            _check_query=Mock(), _check_active=Mock(),
            continuation=SimpleNamespace(transport=transport, trade_feedback=None))
        choice, = routes.read(saved, observation)
        self.assertEqual(choice, dict(kind=unit_work.BUILD_ROUTE, unit_id=5, plot_id=6, x=2, y=1,
                                      route_type='ROUTE_RAILROAD'))
        with patch.object(routes, 'observe_player', return_value=observation):
            self.assertEqual(routes.apply(saved, choice, observation)['status'], 'completed')
            self.assertEqual(routes.apply(saved, choice, observation)['status'], 'submitted')
        lua.globals()[b'choice'] = b'ROUTE_MODERN_ROAD'
        self.assertEqual(routes.apply(saved, choice, observation)['status'], 'refused')
        transport.deliver_one.assert_not_called()
        alternative, = routes.read(saved, observation)
        self.assertEqual(alternative['route_type'], 'ROUTE_MODERN_ROAD')
        lua.globals()[b'moves'] = 0
        self.assertEqual(routes.read(saved, observation), [])
        with self.assertRaises(ValueError):
            routes.verify_archive(archive, actor=1, unit=5, opcode=25)

    def test_public_choices_and_additive_checkpoint(self):
        root = resource_root()
        ref = checked_json(root/'evidence/host-xp2-stock-great-writer-work-move-reload-native.json',
                           '7ffb1756a65b79820f90a044018b411ca7fbd1f067dcda707cd1bcc31bc9a23a')
        response = checked_event(root, ref['event_log'], 5454)
        catalogue, observation = response['decisions'], response['observation']
        historical = deepcopy(catalogue)
        unit = observation['units'][0]
        x, y = unit['x'], unit['y']
        choice = dict(kind=unit_work.BUILD_ROUTE, unit_id=unit['id'], x=x, y=y,
                      plot_id=y * observation['width'] + x, route_type='ROUTE_RAILROAD')
        network_turn.add_build_route_choices(catalogue, [choice])
        seal(catalogue)
        client = SessionClient(SimpleNamespace(reset=lambda: response, abort=Mock()))
        decisions = client.reset()['decisions']
        self.assertEqual(network_turn.select_capability(decisions, dict(
            decision_id=decisions['decision_id'], candidate_id=network_turn.digest(choice))), choice)
        projected, transition = network_turn.checkpoint_catalogue(catalogue, historical, observation,
                                                                 core_sha256=XP2_CORE_SHA256)
        self.assertEqual(projected, historical)
        self.assertEqual(transition['added_action_families'], [unit_work.BUILD_ROUTE])
