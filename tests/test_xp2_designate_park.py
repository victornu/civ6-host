"""Installed proof and public/native-shaped park designation boundaries."""

from contextlib import contextmanager
from copy import deepcopy
from struct import pack
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

from lupa.lua51 import LuaRuntime
import pefile

from civ6_host import SessionClient
from civ6_host.contracts import national_parks, network_turn
from civ6_host.runtime import xp2_designate_park as parks, xp2_bbg_inputs, xp2_bundle_inputs
from civ6_host.runtime.a0_family_source import verify_pinned_files
from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
from civ6_host.runtime.execution_images import _PROFILE
from civ6_host.runtime.paths import resource_root
from test_xp2_great_person_activation import checked_event, checked_json, seal


class DesignateParkTests(TestCase):
    def test_current_installed_descriptor_and_both_exact_captures(self):
        with pefile.PE(_PROFILE.path, fast_load=True) as image:
            base = image.OPTIONAL_HEADER.ImageBase
            parks.verify_live(base, lambda address, size: image.get_data(address-base, size), _PROFILE)
        for reference in (xp2_bundle_inputs.REFERENCE, xp2_bbg_inputs.REFERENCE):
            pins = parks.source_dependencies(reference, _PROFILE)
            verify_pinned_files(pins)
            self.assertIn(reference[1], pins.values())

    def test_request_with_no_parameters_and_verified_new_park(self):
        lua = LuaRuntime(encoding=None)
        lua.execute(br'''
observer, moves, visible, allowed, park = 1, 1, true, true, false
local operation=0x3d7d2377
local unit={GetOwner=function() return 1 end, GetID=function() return 5 end,
            GetX=function() return 2 end, GetY=function() return 1 end,
            GetMovesRemaining=function() return moves end}
local units={Members=function() return ipairs({unit}) end,
             FindID=function(_,id) if id==5 then return unit end end}
Players={[1]={GetUnits=function() return units end, IsTurnActive=function() return true end,
              IsTurnActiveComplete=function() return true end}}
Game={GetLocalPlayer=function() return 1 end,GetLocalObserver=function() return observer end,
      GetCurrentGameTurn=function() return 16 end}
GameInfo={UnitOperations={UNITOPERATION_DESIGNATE_PARK={Hash=operation,Index=25,VisibleInUI=true}}}
OperationResultsTypes={NO_TARGETS=99}
Map={GetPlot=function(x,y) assert(x==2 and y==1); return {IsNationalPark=function() return park end} end}
UnitManager={
 CanStartOperation=function(u,op,third,visibility,flags)
  assert(u==unit and op==operation and third==nil)
  if visibility then return visible end
  assert(visibility==false and flags==99)
  return allowed
 end,
 RequestOperation=function(...)
  assert(select('#',...)==2 and select(1,...)==unit and select(2,...)==operation)
  capture()
 end}
''')
        state = lua.globals()
        observation = dict(player_id=1, turn=16, units=[dict(owner=1,id=5,x=2,y=1)])
        pending = []
        archive = pack('<IHH5I', 0x8c0f3f36, 1, 1, 5, 25, 0xffffffff, 0, 0)
        state[b'capture'] = lambda: pending.append(archive)
        transport = SimpleNamespace(pending=pending, require_empty_native_queue=Mock())
        effect_visible = True

        @contextmanager
        def guarded(verify, *, allow_no_archive):
            def deliver():
                verify(pending.pop())
                state[b'park'] = effect_visible

            transport.deliver_one = Mock(side_effect=deliver)
            yield
            self.assertTrue(allow_no_archive)
            self.assertFalse(pending)

        transport.require_xp2_single_archive = guarded
        prefix = SimpleNamespace(actions=transport, ui_child=object(),
            runtime=SimpleNamespace(evaluate_text=lambda context, code, label, capacity: lua.execute(code)),
            deferred_events=SimpleNamespace(drain_empty_receivers=Mock()),
            view_publisher=SimpleNamespace(publish=Mock()))
        saved = SimpleNamespace(prefix=prefix, _xp2_designate_park=object(),
            _check_query=Mock(), _check_active=Mock(),
            continuation=SimpleNamespace(transport=transport, trade_feedback=None))
        with (patch.object(parks.expansion_national_parks.expansion_city_growth, '_owner',
                           return_value=saved._xp2_designate_park),
              patch.object(parks, 'observe_player', return_value=observation)):
            choice, = parks.read(saved, observation, borrowed=True)
            self.assertEqual(choice, dict(kind=national_parks.DESIGNATE, unit_id=5, x=2, y=1))
            self.assertEqual(parks.apply(saved,choice,observation)['status'], 'completed')
            self.assertEqual(parks.apply(saved,choice,observation)['status'], 'refused')
            transport.deliver_one.assert_not_called()
            state[b'park'] = False
            effect_visible = False
            self.assertEqual(parks.apply(saved,choice,observation)['status'], 'submitted')
            state[b'allowed'] = False
            self.assertEqual(parks.read(saved,observation), [])
        with self.assertRaisesRegex(ValueError, 'actor, unit or operation'):
            parks.verify_archive(archive,actor=0,unit=5,opcode=25)

    def test_public_choice_and_historical_checkpoint(self):
        root = resource_root()
        ref = checked_json(root/'evidence/host-xp2-stock-great-writer-work-move-reload-native.json',
                           '7ffb1756a65b79820f90a044018b411ca7fbd1f067dcda707cd1bcc31bc9a23a')
        response = checked_event(root, ref['event_log'], 5454)
        catalogue, observation = response['decisions'], response['observation']
        historical = deepcopy(catalogue)
        unit = observation['units'][0]
        choice = dict(kind=national_parks.DESIGNATE, unit_id=unit['id'], x=unit['x'], y=unit['y'])
        network_turn.add_park_designation_choices(catalogue, [choice])
        seal(catalogue)
        client = SessionClient(SimpleNamespace(reset=lambda: response, abort=Mock()))
        decisions = client.reset()['decisions']
        selected = network_turn.select_capability(decisions, dict(
            decision_id=decisions['decision_id'],candidate_id=network_turn.digest(choice)))
        self.assertEqual(selected,choice)
        projected, transition = network_turn.checkpoint_catalogue(catalogue,historical,observation,
                                                                 core_sha256=XP2_CORE_SHA256)
        self.assertEqual(projected,historical)
        self.assertEqual(transition['added_action_families'],[national_parks.DESIGNATE])
