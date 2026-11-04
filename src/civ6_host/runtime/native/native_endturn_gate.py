"""Conservative manual-EndTurn branch from the installed Base ActionPanel.

This gate only admits no-unready, no-ready-unit and no-active-city-attack
states (notification absent or natively dismissed). These predicates make the timer and optional user settings irrelevant
by short circuit, without inventing their values. Interface selection/sound
are presentation effects outside this headless decision gate.
"""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
from civ6_host.runtime.native.native_source_cache import load_pinned_json
from civ6_host.runtime.native.native_turn_decisions import blocker_source
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_endturn_gate.py')))).resolve().parents[1]
TURN_SHA = '2141fbda169602e07ec5f9453e30ea3f10aa7fd558f02a418ad98cfb27215384'
PROCESSING_SHA = 'b8a82fbdc689be02cef63abc0b9633fdeac1f8895b12a515b0f0fbcf74618c85'
NOTIFICATION_SHA = '4c87df1d7afb6d73f7a6b9a90b466438987f589324cc4e8a1fc18c8c579a3fe9'
CITY_UI_SHA = '264ce2c209d1d30f9ebc371caca8d835fbc89ca3c5975a1c74e281347a15ec9f'

def verify_source():
    turn = load_pinned_json(ROOT / 'evidence/native-player-turn-state.json', TURN_SHA)
    processing = load_pinned_json(ROOT / 'evidence/native-ui-processing-messages.json', PROCESSING_SHA)
    notification = load_pinned_json(ROOT / 'evidence/native-city-attack-notification.json', NOTIFICATION_SHA)
    city_ui = load_pinned_json(ROOT / 'evidence/native-city-range-attack-route' / f'{CITY_UI_SHA}.json', CITY_UI_SHA)
    if turn['installed_ui_source']['sha256'] != '1a290b0e33c24c5b78515b58447768a6ecc3382387e0fdf6928b10f408875da3':
        raise RuntimeError('EndTurn ActionPanel identity changed')
    if processing['schema'] != 'civ6rl.native_ui_processing_messages.static.v1':
        raise RuntimeError('EndTurn processing predicate proof changed')
    if notification['notification_manager_find_type']['registration']['callback_va'] != '0x18056ef40':
        raise RuntimeError('EndTurn notification predicate binding changed')
    if notification['notification_is_dismissed_method']['registration']['callback_va'] != '0x18056e1e0':
        raise RuntimeError('EndTurn dismissed notification predicate binding changed')
    if city_ui['official_ui']['ActionPanel.lua']['sha256'] != turn['installed_ui_source']['sha256']:
        raise RuntimeError('EndTurn dismissed branch UI source changed')

def gate_source(player_id, *, player_ids=(0, 1)):
    verify_source()
    blocker_source(player_id, player_ids=player_ids)
    return b'local pid=' + str(player_id).encode() + b"\nassert(Game.GetLocalPlayer()==pid,'end-turn perspective mismatch')\nlocal p=Players[pid]\nassert(p and p:IsAlive() and p:IsTurnActive() and p:IsTurnActiveComplete(),\n 'end-turn player not ready')\nassert(type(p.CanUnreadyTurn)=='function','native unready predicate absent')\nlocal unready=p:CanUnreadyTurn()\nassert(type(unready)=='boolean' and not unready,'unready/timer branch not admitted')\nlocal primary=NotificationManager.GetFirstEndTurnBlocking(pid)\nlocal all=NotificationManager.GetAllEndTurnBlocking(pid)\nassert(type(primary)=='number' and type(all)=='table','invalid native blockers')\nassert(primary==EndTurnBlockingTypes.NO_ENDTURN_BLOCKING and #all==0,\n 'native end-turn decisions unresolved')\nassert(p:GetUnits():GetFirstReadyUnit()==nil,'native ready unit remains')\nassert(type(NotificationManager.FindType)=='function' and NotificationTypes and\n NotificationTypes.CITY_RANGE_ATTACK==-1181197223,'native city attack notification API absent')\nlocal notification=NotificationManager.FindType(NotificationTypes.CITY_RANGE_ATTACK,pid)\nlocal state='no-city-attack'\nif notification~=nil then\n assert(type(notification.IsDismissed)=='function','city notification dismissed predicate unavailable')\n local dismissed=notification:IsDismissed()\n assert(type(dismissed)=='boolean' and dismissed,'active city attack notification remains')\n state='dismissed-city-attack'\nend\nreturn string.format('%d|%d|no-unready|no-blocker|no-unit|%s',\n Game.GetCurrentGameTurn(),pid,state)\n"

def parse_gate(payload, player_id, expected_turn, *, player_ids=(0, 1)):
    from civ6_host.runtime.native.native_diagnostic_roster import validate_player
    validate_player(player_id, player_ids)
    if type(expected_turn) is not int or not 0 <= expected_turn <= 100000:
        raise ValueError('Unknown turn')
    expected = f'{expected_turn}|{player_id}|no-unready|no-blocker|no-unit|no-city-attack'.encode()
    dismissed = f'{expected_turn}|{player_id}|no-unready|no-blocker|no-unit|dismissed-city-attack'.encode()
    if type(payload) is not bytes or payload not in (expected, dismissed):
        raise ValueError('End-turn decision gate result is stale or invalid')
    result = {'player_id': player_id, 'turn': expected_turn, 'manual_endturn_decision_branch_verified': True, 'processing_messages': False, 'processing_messages_source': 'Pinned EXE039FF0 constant false; not a queue-empty oracle', 'timer_not_queried_reason': 'Native CanUnreadyTurn is false', 'user_options_not_queried_reason': 'No ready unit and no city attack notification', 'presentation_profile': 'Headless; selection mode and audio are not instantiated', 'eligible_for_training': False}
    if payload == dismissed:
        result['city_attack_notification_status'] = 'dismissed'
        result['user_options_not_queried_reason'] = 'No ready unit; native city attack notification is dismissed'
    return result

def guard_case():
    return b'local state={pid=0,turn=3,alive=true,active=true,complete=true,\n unready=false,primary=0,all={},unit=nil,notification=nil}\nlocal Game={GetLocalPlayer=function() return state.pid end,\n GetCurrentGameTurn=function() return state.turn end}\nlocal p={IsAlive=function() return state.alive end,\n IsTurnActive=function() return state.active end,\n IsTurnActiveComplete=function() return state.complete end,\n CanUnreadyTurn=function() return state.unready end,\n GetUnits=function() return {GetFirstReadyUnit=function() return state.unit end} end}\nlocal Players={[0]=p,[1]=p}\nlocal NotificationManager={\n GetFirstEndTurnBlocking=function(pid) assert(pid==0); return state.primary end,\n GetAllEndTurnBlocking=function(pid) assert(pid==0); return state.all end,\n FindType=function(kind,pid) assert(kind==-1181197223 and pid==0); return state.notification end}\nlocal EndTurnBlockingTypes={NO_ENDTURN_BLOCKING=0}\nlocal NotificationTypes={CITY_RANGE_ATTACK=-1181197223}\nlocal function gate()\n' + gate_source(0) + b"end\nassert(gate()=='3|0|no-unready|no-blocker|no-unit|no-city-attack')\nstate.pid=1; assert(not pcall(gate)); state.pid=0\nstate.alive=false; assert(not pcall(gate)); state.alive=true\nstate.active=false; assert(not pcall(gate)); state.active=true\nstate.complete=false; assert(not pcall(gate)); state.complete=true\nstate.unready=true; assert(not pcall(gate)); state.unready=false\nstate.primary=7; assert(not pcall(gate)); state.primary=0\nstate.all={7}; assert(not pcall(gate)); state.all={}\nstate.unit={}; assert(not pcall(gate)); state.unit=nil\nstate.notification={}; assert(not pcall(gate)); state.notification=nil\nstate.notification={IsDismissed=function() return false end}; assert(not pcall(gate))\nstate.notification={IsDismissed=function() return 1 end}; assert(not pcall(gate))\nstate.notification={IsDismissed=function() return true end}\nassert(gate()=='3|0|no-unready|no-blocker|no-unit|dismissed-city-attack')\nstate.unit={}; assert(not pcall(gate)); state.unit=nil\nstate.primary=7; assert(not pcall(gate)); state.primary=0\nstate.notification=nil\nlocal saved=NotificationManager.FindType; NotificationManager.FindType=nil\nassert(not pcall(gate)); NotificationManager.FindType=saved\nassert(gate()=='3|0|no-unready|no-blocker|no-unit|no-city-attack')\nreturn 'endturn-gates-ok'\n"
