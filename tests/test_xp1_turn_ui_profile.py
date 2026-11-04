"""Source and ownership fixtures; no GameCore, game process, or desktop."""
from contextlib import ExitStack
import hashlib
import itertools
import os
from pathlib import Path
import re
import sys
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

HOST = Path(__file__).resolve().parents[1]
LAB = HOST.parent / 'civ6-rl-lab'
os.environ.setdefault('CIV6_HOST_RESOURCE_ROOT', str(LAB))
sys.path.insert(0, str(HOST / 'src'))

from civ6_host.runtime import xp1_turn_ui_profile as gate
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256, _body
from civ6_host.runtime.xp1_saved_load_owner import SavedLoadOwner
from civ6_host.runtime.xp1_bundle_inputs import XP1_LAN_PROFILE
from civ6_host.runtime.xp1_saved_load import REFERENCE
from civ6_host.runtime.lan_load import _LAN_MODE, _SIMULTANEOUS_PHASE


def fixture():
    saved = object.__new__(SavedLoadOwner)
    saved.thread = threading.get_ident()
    saved.phase, saved.poisoned, saved._running = 'commands', False, False
    saved.requested = dict(unit_commands_candidate=True)
    p = SimpleNamespace(runtime=SimpleNamespace(evaluate_text=Mock(return_value=
        b'1|0|0|0||1,1,1,0,1,1,0,0,0|-410341495,616404169,23669119')),
        ui_child=object(), game_child=object(), quarantined=False)
    inputs = SimpleNamespace(profile=XP1_LAN_PROFILE, official_bundle=REFERENCE)
    b = SimpleNamespace(prefix=p, core=SimpleNamespace(_handle=0x180000000),
        host=object(), context=17, inputs=inputs, raw_load_result=object(),
        runtime=SimpleNamespace(read=Mock()),
        captured_bundle=SimpleNamespace(inputs=inputs, reference=REFERENCE),
        load_abi=SimpleNamespace(core_sha256=XP1_CORE_SHA256),
        _saved_load_candidate=True, _xp1_commands_requested=True,
        stage='xp1-continuation-ready', busy=False, poisoned=False, destroyed=False,
        check_thread=Mock(), control=Mock())
    saved.backend = saved._backend = b
    saved._engine_sha256=XP1_CORE_SHA256;b._saved_stage_owner=saved
    saved.prefix, saved.core, saved.host = p, b.core, b.host
    saved.context, saved.inputs, saved.receipt = b.context, inputs, b.raw_load_result
    saved.facade = saved.post = saved.publication = saved.player_view = None
    saved.continuation = SimpleNamespace(owner=b, check=Mock(),
        transport=SimpleNamespace(require_empty_native_queue=Mock()))
    b._xp1_continuation = saved.continuation
    saved.network_reference = dict(capture_manifest_sha256=REFERENCE[1],
        state=dict(player_id=0, observer_id=0, game_mode_u32=_LAN_MODE,
                   turn_phase_u32=_SIMULTANEOUS_PHASE),
        major_player_ids=(0,1), human_player_ids=(0,))
    return saved


class TurnUIProfileTests(unittest.TestCase):
    def test_exact_source_dependencies_live_bytes_and_receipt_identity(self):
        proof = gate.verify_source()
        pins = gate.source_dependencies()
        self.assertEqual(pins[str((LAB / gate.SOURCE[0]).resolve())], gate.SOURCE[1])
        for row in proof['official_ui_sources']:
            self.assertEqual(pins[str(Path(row['path']).resolve())], row['sha256'])
        with self.assertRaises(ValueError):
            gate.verify_source('not-xp1')
        memory = {}
        for body in proof['functions'].values():
            for fragment in _body(body)['fragments']:
                for row in fragment['instructions']:
                    for offset, value in enumerate(bytes.fromhex(row['bytes'])):
                        address = int(row['va'],16) + offset
                        self.assertEqual(memory.setdefault(address,value), value)
        for name, row in proof['bindings'].items():
            for offset, value in enumerate(name.split('.')[1].encode() + b'\0'):
                memory[0x180000000 + row['name_rva'] + offset] = value
        reader = lambda address, count: bytes(memory[address+i] for i in range(count))
        self.assertGreater(gate.verify_live(0x180000000, reader), 0)
        address = min(memory)
        memory[address] ^= 1
        with self.assertRaises(ValueError):
            gate.verify_live(0x180000000, reader)
        owner = fixture().backend
        with patch('civ6_host.runtime.xp1_status_profiles.bind_owner') as status, \
                patch.object(gate, 'verify_live', return_value=27):
            receipt = gate.bind_owner(owner)
            status.assert_called_once_with(owner, owner.core, owner.runtime.read)
            self.assertIs(gate.bind_owner(owner), receipt)
            owner.core = SimpleNamespace(_handle=owner.core._handle)
            with self.assertRaises(ValueError):
                gate.bind_owner(owner)

    def test_real_actionpanel_projection_and_lua_reader(self):
        from lupa.lua51 import LuaRuntime
        proof = gate.verify_source()
        source = Path(proof['official_ui_sources'][0]['path']).read_text(encoding='utf-8-sig')
        names = ('UnitsHaveMovesStateEnabled', 'HaveCityRangeAttackStateEnabled',
                 'CheckUnitsHaveMovesState', 'CheckCityRangeAttackState', 'DoEndTurn',
                 'OnInputHandler')
        chunks = []
        for name in names:
            start = source.index('function ' + name + '(')
            end = source.find('\nfunction ', start + 1)
            chunk = source[start:end if end != -1 else len(source)]
            chunks.append(re.sub(r':\s*(?:number|table|boolean|string)\b', '', chunk))
        lua = LuaRuntime()
        lua.execute('''
R={}; requested=nil
EndTurnBlockingTypes={NO_ENDTURN_BLOCKING=0,ENDTURN_BLOCKING_STACKED_UNITS=-410341495,
 ENDTURN_BLOCKING_UNIT_NEEDS_ORDERS=616404169,ENDTURN_BLOCKING_UNITS=23669119}
NotificationTypes={CITY_RANGE_ATTACK=99}
ActionTypes={ACTION_ENDTURN='end',ACTION_UNREADYTURN='unready'}
InterfaceModeTypes={SELECTION=1,CITY_RANGE_ATTACK=2}
Keys={VK_RETURN=13};KeyEvents={KeyUp=2}
local unit={};local city={};local notification={}
function notification:IsDismissed() return R.dismissed end
local units={GetFirstReadyUnit=function() return R.ready and unit or nil end}
local cities={GetFirstRangedAttackCity=function() return city end}
Players={[0]={IsAlive=function() return true end,IsTurnActive=function() return R.active end,
 IsTurnActiveComplete=function() return R.complete end,CanUnreadyTurn=function() return R.unready end,
 GetUnits=function() return units end,GetCities=function() return cities end}}
Game={GetCurrentGameTurn=function() return 1 end,GetLocalPlayer=function() return 0 end,
 GetLocalObserver=function() return 0 end,IsAllowTacticalCommands=function() return R.tactical end}
NotificationManager={GetFirstEndTurnBlocking=function() return R.blocker end,
 GetAllEndTurnBlocking=function() return R.blocker==0 and {} or {R.blocker} end,
 FindType=function() return R.city and notification or nil end,
 FindEndTurnBlocking=function() return R.notification and notification or nil end}
UserConfiguration={IsAutoEndTurn=function() return false end,
 IsCityRangeAttackTurnBlocking=function() return true end}
UI={IsTurnTimerElapsed=function() return R.timer end,IsProcessingMessages=function() return false end,
 RequestAction=function(action) requested=action end,GetInterfaceMode=function() return 1 end,
 SetInterfaceMode=function() end,SelectNextReadyUnit=function() end,SelectCity=function() end,
 DataError=function() end,PlaySound=function() end,CanEndTurn=function() return R.fallback end}
LuaEvents={ActionPanel_ActivateNotification=function() end}
function IsTutorialRunning() return false end
input={GetMessageType=function() return 2 end,GetKey=function() return 13 end,
 IsShiftDown=function() return true end}
''')
        lua.execute('\n'.join(chunks))
        scenarios = itertools.product((0,23669119,12345), (False,True), (False,True), (False,True))
        cases = 0
        for blocker, unready, city, timer in scenarios:
            for notification in (False, True):
                values = dict(blocker=blocker, unready=unready, city=city, timer=timer,
                    notification=notification, ready=True, tactical=True, dismissed=False,
                    active=True, complete=True, fallback=True)
                lua.globals().R = lua.table_from(values)
                raw = lua.execute(gate.query_source(0,1,player_ids=(0,1)).decode()).encode()
                readback = gate.parse_readback(raw,0,1,player_ids=(0,1))
                result = gate.classify(readback, timer)
                lua.execute('requested=nil;DoEndTurn()')
                chosen = lua.globals().requested
                availability = result['turn_availability']
                if availability['end_turn'] is not None:
                    self.assertEqual(availability['end_turn'], chosen=='end', values)
                else:
                    self.assertIn('missing_notification_UI_CanEndTurn_unqualified', result['unknown'])
                self.assertEqual(availability['unready_turn'], chosen=='unready', values)
                lua.execute('requested=nil;OnInputHandler(input)')
                self.assertEqual(lua.globals().requested, 'end')
                self.assertIs(availability['force_end_turn'], True)
                cases += 1
        self.assertEqual(cases,48)
        lua.globals().R.active=False
        lua.globals().R.complete=False
        lua.globals().R.blocker=0
        lua.globals().R.unready=False
        lua.globals().R.city=False
        raw=lua.execute(gate.query_source(0,1,player_ids=(0,1)).decode()).encode()
        inactive=gate.classify(gate.parse_readback(raw,0,1,player_ids=(0,1)),False)
        self.assertIsNone(inactive['turn_availability']['end_turn'])
        self.assertIs(inactive['turn_availability']['force_end_turn'],True)
        self.assertIs(inactive['diagnostics']['normal_handler_request'],True)
        # Missing methods and foreign perspectives are errors, never false gates.
        lua.execute('NotificationManager.GetAllEndTurnBlocking=nil')
        with self.assertRaises(Exception):
            lua.execute(gate.query_source(0,1,player_ids=(0,1)).decode())

    def test_unknown_timer_and_malformed_readbacks(self):
        raw=b'1|0|0|0||1,1,1,1,1,1,0,0,0|-410341495,616404169,23669119'
        state = gate.parse_readback(raw,0,1,player_ids=(0,1))
        result = gate.classify(state,None)
        self.assertEqual(result['turn_availability'],
            dict(end_turn=None,force_end_turn=True,unready_turn=None))
        self.assertEqual(result['unknown'], ['elapsed_timer_unqualified'])
        for bad in (raw.replace(b'1|0|',b'2|0|',1), raw.replace(b'1,1,1,1',b'1,1,1,2'),
                    raw.replace(b'0,0,0|',b'0,1,0|'), raw+b'|extra'):
            with self.assertRaises(ValueError):
                gate.parse_readback(bad,0,1,player_ids=(0,1))

    def test_real_saved_owner_idle_active_and_foreign_rejections(self):
        for active in (False,True):
            with self.subTest(active=active), ExitStack() as stack:
                saved=fixture()
                if active:
                    saved._running=True
                    saved.backend.busy=True
                    saved.backend.stage='xp1-continuation-active'
                bound=stack.enter_context(patch.object(gate,'bind_owner'))
                timer=stack.enter_context(patch('civ6_host.runtime.network_timer.read',return_value=False))
                result=gate.read(saved,0,1,active=active)
                self.assertIs(result['turn_availability']['end_turn'],True)
                bound.assert_called_once_with(saved.backend)
                timer.assert_called_once_with(saved.backend,core_sha256=XP1_CORE_SHA256)
                saved.prefix.runtime.evaluate_text.assert_called_once()
                self.assertIs(saved.prefix.runtime.evaluate_text.call_args.args[0],saved.prefix.ui_child)
                saved.continuation.check.assert_called_with(active=active)
                self.assertIs(saved._running,active)
                saved.prefix.runtime.evaluate_text.reset_mock()
                saved.backend._xp1_continuation=object()
                with self.assertRaises(ValueError):
                    gate.read(saved,0,1,active=active)
                saved.prefix.runtime.evaluate_text.assert_not_called()
                timer.assert_called_once()
        for mutate in (lambda s:setattr(s,'thread',-1),lambda s:setattr(s,'poisoned',True),
                       lambda s:setattr(s.backend,'destroyed',True),
                       lambda s:s.network_reference.update(capture_manifest_sha256='foreign')):
            saved=fixture();mutate(saved)
            with patch.object(gate,'bind_owner') as bound:
                with self.assertRaises((ValueError,RuntimeError)):
                    gate.read(saved,0,1)
                bound.assert_not_called()
                saved.prefix.runtime.evaluate_text.assert_not_called()


if __name__=='__main__':
    unittest.main(verbosity=2)
