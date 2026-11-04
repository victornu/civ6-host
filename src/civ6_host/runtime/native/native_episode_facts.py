"""Current-actor public facts, without an RL termination or reward policy.

Run build_source() through the protected Lua evaluator after public native cache
publication. IsAlive=false is readable; an actor that is no longer both local
player and observer is outside this profile. No native pointers are retained.
"""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
from civ6_host.runtime.native.native_source_cache import load_pinned_json
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_episode_facts.py')))).resolve().parents[1]
PROOF_SHA256 = 'ecca6cc2b9910769f584851573016cbdad72d3f6a1e613d4cbd5b8ad52713232'
_PROOF = ROOT / 'evidence/native-episode-facts' / (PROOF_SHA256 + '.json')
MAX_RESPONSE = 160
_PREFIX = b'episode-facts-v1'

def verify_source(*, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'):
    if core_sha256 != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3':
        from civ6_host.runtime.xp1_session_result import verify_reader_source
        return verify_reader_source(core_sha256)
    proof = load_pinned_json(_PROOF, PROOF_SHA256)
    expected = {'Player.GetID': '0x180530f90', 'Player.GetTeam': '0x1805314a0', 'Player.IsAlive': '0x180531840', 'Player.WasEverAlive': '0x180531c30', 'Game.GetWinningTeam': '0x180523ed0', 'Game.GetCurrentGameTurn': '0x180522280', 'Game.GetLocalPlayer': '0x180522be0', 'Game.GetLocalObserver': '0x180522ba0'}
    contracts = proof.get('getter_contracts', {})
    if proof.get('schema') != 'civ6rl.native_episode_facts.static.v1' or proof.get('core_sha256') != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3' or proof.get('exe_sha256') != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or any((proof.get('bindings', {}).get(name, {}).get('callback_va') != va for name, va in expected.items())) or any((contracts.get('Player.' + name, {}).get('cache_offset') != offset for name, offset in [('GetID', 0), ('GetTeam', 4), ('IsAlive', 28), ('WasEverAlive', 12)])) or any((contracts.get('Player.' + name, {}).get('result_arity') != 1 for name in ('GetID', 'GetTeam', 'IsAlive', 'WasEverAlive'))) or (contracts.get('Game.GetWinningTeam', {}).get('absent_result_arity') != 0) or (contracts.get('Game.GetWinningTeam', {}).get('present_result_arity') != 2) or (tuple(contracts.get('Game.GetWinningTeam', {}).get('present_order', ())) != ('winning_team', 'victory_type')) or (contracts.get('Game.GetWinningTeam', {}).get('absent_native_team') != -1):
        raise RuntimeError('Native episode-facts source identity changed')
    return proof

def _bounded(value, label, maximum):
    if type(value) is not int or not 0 <= value <= maximum:
        raise ValueError('Invalid ' + label)
    return value

def _integer(raw, label, minimum, maximum):
    if not raw or len(raw) > 11:
        raise ValueError('Invalid ' + label)
    digits = raw[1:] if raw.startswith(b'-') else raw
    if not digits or any((c < 48 or c > 57 for c in digits)) or (len(digits) > 1 and digits.startswith(b'0')) or (raw == b'-0'):
        raise ValueError('Noncanonical ' + label)
    value = int(raw)
    if not minimum <= value <= maximum:
        raise ValueError('Out-of-range ' + label)
    return value

def build_source(player_id, expected_turn, *, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'):
    """Build a read-only chunk; this function itself executes no Lua/native call."""
    pid = _bounded(player_id, 'current actor ID', 63)
    turn = _bounded(expected_turn, 'expected turn', 2147483647)
    verify_source(core_sha256=core_sha256)
    return f'local pid,expectedTurn={pid},{turn}\n'.encode('ascii') + _READ_LUA
_READ_LUA = "\nlocal function one(label,...)\n assert(select('#',...)==1,'episode facts invalid '..label..' arity')\n return ...\nend\nlocal function integer(value,label,low,high)\n assert(type(value)=='number' and value%1==0 and value>=low and value<=high,\n        'episode facts invalid '..label)\n return value\nend\nlocal function boolean(value,label)\n assert(type(value)=='boolean','episode facts invalid '..label)\n return value\nend\nassert(Game and type(Game.GetLocalPlayer)=='function' and\n type(Game.GetLocalObserver)=='function' and type(Game.GetCurrentGameTurn)=='function' and\n type(Game.GetWinningTeam)=='function','episode facts Game API unavailable')\nlocal function context()\n local localID=integer(one('local player',Game.GetLocalPlayer()),'local player',0,63)\n local observer=integer(one('observer',Game.GetLocalObserver()),'observer',0,63)\n local turn=integer(one('turn',Game.GetCurrentGameTurn()),'turn',0,2147483647)\n assert(localID==pid and observer==pid and turn==expectedTurn,\n        'episode facts foreign actor or stale context')\nend\ncontext()\nlocal function readPlayer()\n local player=Players and Players[pid]\n assert(player and type(player.GetID)=='function' and type(player.GetTeam)=='function' and\n  type(player.IsAlive)=='function' and type(player.WasEverAlive)=='function',\n  'episode facts Player API unavailable')\n local id=integer(one('player ID',player:GetID()),'player ID',0,63)\n assert(id==pid,'episode facts player identity mismatch')\n -- 0..63 is this adapter's admitted team-ID profile, not a native enum rewrite.\n local team=integer(one('team',player:GetTeam()),'team',0,63)\n local ever=boolean(one('WasEverAlive',player:WasEverAlive()),'WasEverAlive')\n assert(ever==true,'episode facts actor was never alive or cache is invalid')\n local alive=boolean(one('IsAlive',player:IsAlive()),'IsAlive')\n return id,team,ever,alive\nend\nlocal function winner(...)\n local arity=select('#',...)\n if arity==0 then return 0,nil,nil end\n assert(arity==2,'episode facts invalid winner arity')\n local team,victory=...\n integer(team,'winning team',-2147483648,2147483647)\n assert(team~=-1,'episode facts invalid present-winner sentinel')\n integer(victory,'victory type',-2147483648,2147483647)\n return 2,team,victory\nend\nlocal id,team,ever,alive=readPlayer()\nlocal arity,winningTeam,victory=winner(Game.GetWinningTeam())\ncontext()\nlocal idAgain,teamAgain,everAgain,aliveAgain=readPlayer()\nassert(idAgain==id and teamAgain==team and everAgain==ever and aliveAgain==alive,\n       'episode facts player snapshot changed')\nlocal arityAgain,teamWinnerAgain,victoryAgain=winner(Game.GetWinningTeam())\nassert(arityAgain==arity and teamWinnerAgain==winningTeam and victoryAgain==victory,\n       'episode facts winner snapshot changed')\ncontext()\nlocal function dec(value) return string.format('%.0f',value) end\nlocal out={'episode-facts-v1',dec(id),dec(expectedTurn),dec(team),\n alive and '1' or '0',ever and '1' or '0',dec(arity)}\nif arity==2 then\n out[#out+1]=dec(winningTeam);out[#out+1]=dec(victory)\nend\nreturn table.concat(out,'|')\n".encode('ascii')

def parse_facts(payload, player_id, expected_turn, *, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'):
    from civ6_host.runtime.xp1_session_result import bind_facts_provenance
    'Parse facts only; no winner/alive combination applies a stop policy.'
    pid = _bounded(player_id, 'current actor ID', 63)
    turn = _bounded(expected_turn, 'expected turn', 2147483647)
    if type(payload) is not bytes or len(payload) > MAX_RESPONSE:
        raise ValueError('Invalid episode facts payload')
    tokens = payload.split(b'|')
    if len(tokens) not in (7, 9) or tokens[0] != _PREFIX:
        raise ValueError('Invalid episode facts protocol')
    actual_pid = _integer(tokens[1], 'player ID', 0, 63)
    actual_turn = _integer(tokens[2], 'game turn', 0, 2147483647)
    if (actual_pid, actual_turn) != (pid, turn):
        raise ValueError('Foreign or stale episode facts')
    team = _integer(tokens[3], 'team ID', 0, 63)
    if tokens[4] not in (b'0', b'1') or tokens[5] != b'1':
        raise ValueError('Invalid alive/ever-alive episode facts')
    if tokens[6] not in (b'0', b'2'):
        raise ValueError('Invalid episode winner arity')
    arity = int(tokens[6])
    if len(tokens) != 7 + arity:
        raise ValueError('Episode winner arity does not match payload')
    winning_team = victory_type = None
    if arity == 2:
        winning_team = _integer(tokens[7], 'winning team', -2147483648, 2147483647)
        victory_type = _integer(tokens[8], 'victory type', -2147483648, 2147483647)
        if winning_team == -1:
            raise ValueError('Present episode winner has absence sentinel')
    return bind_facts_provenance({'player_id': pid, 'current_game_turn': turn, 'team_id': team, 'is_alive': tokens[4] == b'1', 'was_ever_alive': True, 'winner_arity': arity, 'winner_present': arity == 2, 'winning_team': winning_team, 'victory_type': victory_type, 'winner_matches_player_team': winning_team == team if arity == 2 else None, 'global_terminal': None, 'global_terminal_status': 'unknown', 'stop_policy_applied': False, 'observation_only': True, 'source_proof_sha256': PROOF_SHA256, 'exposed_to_learner': False, 'eligible_for_training': False}, core_sha256)

def guard_case(*, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'):
    """Actual reader against local Lua doubles, usable under Lupa or protected HKS."""
    source = build_source(0, 17, core_sha256=core_sha256).decode('ascii')
    return ("local localID,observer,turn=0,0,17\nlocal id,team,ever,alive=0,4,true,true\nlocal winnerMode='none'\nlocal getterMode='normal'\nlocal playerReads,winnerReads=0,0\nlocal player={}\nlocal Players=setmetatable({[0]=player},{__index=function(_,key)\n error('foreign participant read '..tostring(key))\nend})\nlocal Game={GetLocalPlayer=function() return localID end,\n GetLocalObserver=function() return observer end,\n GetCurrentGameTurn=function() return turn end,\n GetWinningTeam=function()\n  winnerReads=winnerReads+1\n  if winnerMode=='none' then return end\n  if winnerMode=='same' then return 4,-123 end\n  if winnerMode=='other' then return 2,2147483647 end\n  if winnerMode=='nil' then return nil end\n  if winnerMode=='partial' then return 4 end\n  if winnerMode=='nilpair' then return nil,nil end\n  if winnerMode=='extra' then return 4,2,3 end\n  if winnerMode=='sentinel' then return -1,2 end\n  if winnerMode=='fraction' then return 4,2.5 end\n  if winnerMode=='wrongtype' then return '4',2 end\n  if winnerMode=='overflow' then return 4,2147483648 end\n  if winnerMode=='change' then return winnerReads,7 end\n  if winnerMode=='switchlocal' then localID=1;return end\n  if winnerMode=='switchobserver' then observer=1;return end\n  if winnerMode=='advanceturn' then turn=18;return end\n  if winnerMode=='replaceplayer' then Players[0]={};return end\n  if winnerMode=='error' then error('native winner error double') end\n end}\nfunction player:GetID()\n playerReads=playerReads+1\n if getterMode=='idextra' then return id,7 end\n if getterMode=='idnil' then return end\n return id\nend\nfunction player:GetTeam()\n if getterMode=='teamchange' and playerReads>1 then return team+1 end\n return team\nend\nfunction player:WasEverAlive() return ever end\nfunction player:IsAlive()\n if getterMode=='alivechange' and playerReads>1 then return not alive end\n return alive\nend\nfunction player:IsTurnActive() error('active-turn gate must not be read') end\nfunction player:IsTurnActiveComplete() error('active-complete gate must not be read') end\nlocal function collect()\n" + source + "\nend\nlocal function reset()\n localID=0;observer=0;turn=17;id=0;team=4;ever=true;alive=true\n winnerMode='none';getterMode='normal';playerReads=0;winnerReads=0;Players[0]=player\nend\nreset();assert(collect()=='episode-facts-v1|0|17|4|1|1|0')\nreset();alive=false;assert(collect()=='episode-facts-v1|0|17|4|0|1|0')\nreset();winnerMode='same';assert(collect()=='episode-facts-v1|0|17|4|1|1|2|4|-123')\nreset();winnerMode='other';alive=false\nassert(collect()=='episode-facts-v1|0|17|4|0|1|2|2|2147483647')\nfor _,mode in ipairs({'nil','partial','nilpair','extra','sentinel','fraction','wrongtype',\n 'overflow','change','switchlocal','switchobserver','advanceturn','replaceplayer','error'}) do\n reset();winnerMode=mode;assert(not pcall(collect),'bad winner/context admitted '..mode)\nend\nfor _,mode in ipairs({'idextra','idnil','teamchange','alivechange'}) do\n reset();getterMode=mode;assert(not pcall(collect),'bad player snapshot admitted '..mode)\nend\nreset();localID=1;alive=false;assert(not pcall(collect));assert(playerReads==0)\nreset();observer=1;assert(not pcall(collect));assert(playerReads==0)\nreset();turn=18;assert(not pcall(collect));assert(playerReads==0)\nreset();id=1;assert(not pcall(collect))\nreset();id=-1;assert(not pcall(collect))\nreset();team=-1;assert(not pcall(collect))\nreset();team=64;assert(not pcall(collect))\nreset();team=4.5;assert(not pcall(collect))\nreset();ever=false;alive=false;assert(not pcall(collect))\nreset();ever=1;assert(not pcall(collect))\nreset();alive=0;assert(not pcall(collect))\nreset();Players[0]=nil;assert(not pcall(collect))\nreset();assert(collect()=='episode-facts-v1|0|17|4|1|1|0')\n-- Native evidence specifies player identity/state, not userdata interning.\nPlayers=setmetatable({},{__index=function(_,key)\n assert(key==0,'foreign participant read')\n local fresh={};for k,v in pairs(player) do fresh[k]=v end;return fresh\nend})\nplayerReads=0;winnerReads=0\nassert(collect()=='episode-facts-v1|0|17|4|1|1|0')\nreturn 'native-episode-facts-guards-ok'\n").encode('ascii')
