"""Player-visible native envoy choices and separate consideration action.

All influence calculations stay in GameCore. Sending consumes a native player
operation; acknowledging the panel uses its distinct native UI setter. Neither
a request return nor an empty catalog is evidence that EndTurn is legal.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import hashlib
from pathlib import Path
from civ6_host.runtime.native.native_source_cache import load_pinned_json
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_envoy_actions.py')))).resolve().parents[1]
PROOF_SHA256 = '25582a788e5b8e5d1a0d79697d8b809952af9bb3bac40690182e80cbd3f4db3c'
CORE_SHA256 = 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'
BLOCKER = -148733181
UI_PATH = _resolve_resource_path(Path("C:\\Program Files (x86)\\Steam\\steamapps\\common\\Sid Meier's Civilization VI\\Base\\Assets\\UI\\PartialScreens\\CityStates.lua"))
UI_SHA256 = 'e56c37f20ac2446f42dfe00dab5564b9989d2a76915ff99c343f31269faddb0a'

def verify_source():
    proof = load_pinned_json(ROOT / 'evidence/native-envoy-actions' / f'{PROOF_SHA256}.json', PROOF_SHA256)
    if proof.get('schema') != 'civ6rl.native_envoy_actions.static.v1' or proof.get('core_sha256') != CORE_SHA256 or hashlib.sha256(_resolve_resource_path(UI_PATH).read_bytes()).hexdigest() != UI_SHA256:
        raise RuntimeError('Native envoy source identity changed')
    bindings = {'Player.GetDiplomacy': '0x180530c80', 'Player.GetInfluence': '0x1805310a0', 'PlayerDiplomacy.HasMet': '0x180537630', 'PlayerManager.GetAliveMinors': '0x180539c30', 'PlayerInfluence.CanGiveInfluence': '0x180538b20', 'PlayerInfluence.CanGiveTokensToPlayer': '0x180538b70', 'PlayerInfluence.CanReceiveInfluence': '0x180538c30', 'PlayerInfluence.GetTokensReceived': '0x180538fb0', 'PlayerInfluence.GetTokensToGive': '0x180539020', 'PlayerInfluence.IsGivingTokensConsidered': '0x180539070', 'PlayerInfluence.SetGivingTokensConsidered': '0x1805390c0'}
    constants = {'GIVE_INFLUENCE_TOKEN': 2582383566, 'PARAM_PLAYER_ONE': 75700508, 'ENDTURN_BLOCKING_GIVE_INFLUENCE_TOKEN': BLOCKER & 4294967295}
    if any((proof['bindings'][k]['callback_va'] != v for k, v in bindings.items())) or any((proof['constants'][k]['unsigned32'] != v for k, v in constants.items())) or proof['contract']['send']['successful_spend'] != 1 or (proof['contract']['send']['parameters']['required_keys'] != (75700508,)) or (proof['contract']['retain']['request_archive'] is not False) or (proof['contract']['retain']['spend'] != 0):
        raise RuntimeError('Pinned native envoy contract differs')
    for parent in proof['parents'].values():
        load_pinned_json(ROOT / parent['path'], parent['sha256'])
    return proof

def _integer(value, name, maximum=2147483647):
    if type(value) is not int or not 0 <= value <= maximum:
        raise ValueError(f'Invalid {name}')
    return value

def _context(player_id, turn):
    return (_integer(player_id, 'player', 63), _integer(turn, 'turn', 100000))

def _common(player_id, turn):
    pid, turn = _context(player_id, turn)
    return f'local pid,expectedTurn={pid},{turn}\n'.encode() + b"\nlocal function integer(value,limit)\n assert(type(value)=='number' and value==math.floor(value) and value>=0 and value<=limit,\n  'invalid native influence integer')\n return value\nend\nlocal function boolean(value)\n assert(type(value)=='boolean','invalid native influence boolean')\n return value\nend\nlocal function context()\n assert(Game.GetLocalPlayer()==pid and Game.GetLocalObserver()==pid,\n  'influence perspective differs')\n assert(Game.GetCurrentGameTurn()==expectedTurn,'influence turn is stale')\n assert(Game.IsAllowStrategicCommands(pid)==true,'influence commands unavailable')\n local p=Players[pid]\n assert(p and p:IsAlive()==true and p:IsTurnActive()==true and p:IsTurnActiveComplete()==true,\n  'influence player is not ready')\n return p,p:GetInfluence()\nend\nlocal p,influence=context()\nassert(influence,'native influence interface absent')\nlocal function hasBlocker()\n assert(EndTurnBlockingTypes.ENDTURN_BLOCKING_GIVE_INFLUENCE_TOKEN==-148733181,\n  'influence blocker enum differs')\n local blockers=NotificationManager.GetAllEndTurnBlocking(pid)\n assert(type(blockers)=='table' and #blockers<=128,'invalid influence blockers')\n local found=false\n for _,value in ipairs(blockers) do\n  assert(type(value)=='number' and value==math.floor(value),'invalid blocker value')\n  if value==-148733181 then found=true end\n end\n return found\nend\nlocal function header()\n context()\n return integer(influence:GetTokensToGive(),2147483647),\n  boolean(influence:CanGiveInfluence()),boolean(influence:IsGivingTokensConsidered()),hasBlocker()\nend\nlocal function dec(value) return string.format('%.0f',value) end\nlocal function bit(value) return value and '1' or '0' end\nlocal function visibleTargets()\n local list=PlayerManager.GetAliveMinors()\n assert(type(list)=='table' and #list<=64,'invalid native minor list')\n local diplomacy=p:GetDiplomacy()\n assert(diplomacy,'native diplomacy unavailable')\n local rows,seen={},{}\n for _,minor in ipairs(list) do\n  local target=integer(minor:GetID(),63)\n  assert(target~=pid and not seen[target],'duplicate or self minor')\n  seen[target]=true\n  -- No target influence information is read or returned before contact.\n  if boolean(diplomacy:HasMet(target)) then\n   assert(minor:IsAlive()==true,'native minor list is stale')\n   local targetInfluence=minor:GetInfluence()\n   assert(targetInfluence,'native target influence unavailable')\n   if boolean(targetInfluence:CanReceiveInfluence()) then\n    rows[#rows+1]={target=target,canGive=boolean(influence:CanGiveTokensToPlayer(target)),\n     received=integer(targetInfluence:GetTokensReceived(pid),2147483647)}\n   end\n  end\n end\n table.sort(rows,function(a,b) return a.target<b.target end)\n context()\n return rows\nend\nlocal function serialize(label)\n local tokens,canGive,considered,blocker=header()\n local rows=visibleTargets()\n local fields={label,dec(pid),dec(expectedTurn),dec(tokens),bit(canGive),bit(considered),bit(blocker),dec(#rows)}\n for _,row in ipairs(rows) do\n  fields[#fields+1]=dec(row.target)..':'..bit(row.canGive)..':'..dec(row.received)\n end\n local t,g,c,b=header()\n assert(t==tokens and g==canGive and c==considered and b==blocker,\n  'influence state changed during collection')\n return table.concat(fields,'|')\nend\n"

def catalog_source(player_id, turn):
    verify_source()
    return _common(player_id, turn) + b"return serialize('catalog')\n"

def _number(token, name, maximum=2147483647):
    if not token or not token.isascii() or (not token.isdecimal()) or (len(token) > 1 and token[0] == '0'):
        raise ValueError(f'Malformed {name}')
    return _integer(int(token), name, maximum)

def parse_catalog(payload, player_id, turn):
    pid, turn = _context(player_id, turn)
    if type(payload) is not bytes or len(payload) > 8192:
        raise ValueError('Unbounded envoy catalog')
    try:
        parts = payload.decode('ascii').split('|')
    except UnicodeDecodeError as exc:
        raise ValueError('Non-ASCII envoy catalog') from exc
    if len(parts) < 8 or parts[0] != 'catalog':
        raise ValueError('Malformed envoy catalog')
    owner, observed_turn, tokens = (_number(parts[1], 'owner', 63), _number(parts[2], 'turn', 100000), _number(parts[3], 'tokens'))
    flags = [bool(_number(x, 'flag', 1)) for x in parts[4:7]]
    count = _number(parts[7], 'target count', 64)
    if owner != pid or observed_turn != turn or len(parts) != 8 + count:
        raise ValueError('Stale or mismatched envoy catalog')
    rows = []
    previous = -1
    for token in parts[8:]:
        cells = token.split(':')
        if len(cells) != 3:
            raise ValueError('Malformed envoy target')
        target = _number(cells[0], 'target', 63)
        if target == pid or target <= previous:
            raise ValueError('Duplicate, self or unordered envoy target')
        previous = target
        rows.append({'target_player_id': target, 'can_give': bool(_number(cells[1], 'can give', 1)), 'tokens_received': _number(cells[2], 'tokens received')})
    return {'player_id': pid, 'current_game_turn': turn, 'tokens_to_give': tokens, 'can_give_influence': flags[0], 'considered': flags[1], 'giving_tokens_blocker_present': flags[2], 'targets': tuple(rows)}

def _check_catalog(catalog):
    if not isinstance(catalog, dict):
        raise ValueError('Missing envoy catalog')
    pid, turn = _context(catalog.get('player_id'), catalog.get('current_game_turn'))
    _integer(catalog.get('tokens_to_give'), 'tokens')
    for name in ('can_give_influence', 'considered', 'giving_tokens_blocker_present'):
        if type(catalog.get(name)) is not bool:
            raise ValueError('Invalid catalog flag')
    rows = catalog.get('targets')
    if not isinstance(rows, (tuple, list)) or len(rows) > 64:
        raise ValueError('Invalid envoy target list')
    previous = -1
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('Invalid envoy target')
        target = _integer(row.get('target_player_id'), 'target', 63)
        if target == pid or target <= previous or type(row.get('can_give')) is not bool:
            raise ValueError('Invalid envoy target identity/flag')
        _integer(row.get('tokens_received'), 'received tokens')
        previous = target
    return (pid, turn)

def choose(catalog, target_player_id):
    pid, turn = _check_catalog(catalog)
    target = _integer(target_player_id, 'target', 63)
    row = next((r for r in catalog['targets'] if r['target_player_id'] == target), None)
    if not catalog['can_give_influence'] or catalog['tokens_to_give'] <= 0 or row is None or (not row['can_give']):
        raise ValueError('Envoy target is not a native candidate')
    return {'player_id': pid, 'current_game_turn': turn, 'target_player_id': target, 'tokens_to_give_before': catalog['tokens_to_give'], 'tokens_received_before': row['tokens_received']}

def _choice(choice):
    if not isinstance(choice, dict) or set(choice) != {'player_id', 'current_game_turn', 'target_player_id', 'tokens_to_give_before', 'tokens_received_before'}:
        raise ValueError('Invalid envoy choice shape')
    pid, turn = _context(choice['player_id'], choice['current_game_turn'])
    target = _integer(choice['target_player_id'], 'target', 63)
    tokens = _integer(choice['tokens_to_give_before'], 'tokens')
    received = _integer(choice['tokens_received_before'], 'received tokens')
    if target == pid or tokens == 0:
        raise ValueError('Invalid envoy choice identity or balance')
    return (pid, turn, target, tokens, received)

def revalidation_source(choice):
    pid, turn, _, _, _ = _choice(choice)
    return catalog_source(pid, turn)

def validate_fresh_choice(payload, choice):
    pid, turn, target, _, _ = _choice(choice)
    fresh = choose(parse_catalog(payload, pid, turn), target)
    if fresh != choice:
        raise ValueError('Envoy choice changed before submission')
    return fresh

def operation_parameters(choice):
    _, _, target, _, _ = _choice(choice)
    proof = verify_source()
    constants = proof['constants']
    operation = constants['GIVE_INFLUENCE_TOKEN']['unsigned32']
    key = constants['PARAM_PLAYER_ONE']['unsigned32']
    _integer(operation, 'operation', 4294967295)
    _integer(key, 'parameter', 4294967295)
    return (operation, {key: target})

def verify_sent_effect(catalog, choice):
    pid, turn, target, tokens, received = _choice(choice)
    actual_pid, actual_turn = _check_catalog(catalog)
    row = next((r for r in catalog['targets'] if r['target_player_id'] == target), None)
    if actual_pid != pid or actual_turn != turn or catalog['tokens_to_give'] != tokens - 1 or (row is None) or (row['tokens_received'] <= received):
        raise RuntimeError('Native envoy operation effect is absent or differs')
    return {'player_id': pid, 'current_game_turn': turn, 'target_player_id': target, 'tokens_spent': 1, 'tokens_received_delta': row['tokens_received'] - received, 'tokens_to_give_after': catalog['tokens_to_give'], 'native_bonus_calculation_used': True, 'eligible_for_training': False}

def consideration_source(catalog, *, require_blocker=True):
    pid, turn = _check_catalog(catalog)
    if type(require_blocker) is not bool:
        raise ValueError('Invalid consideration mode')
    if catalog['considered'] or (require_blocker and (not catalog['giving_tokens_blocker_present'])):
        raise ValueError('No pending native envoy consideration')
    access = b''
    if not require_blocker:
        from civ6_host.runtime.native.native_saved_envoy_panel import verify_source as verify_panel_source
        from civ6_host.runtime.native.native_saved_envoy_panel import ACCESS_LUA
        verify_panel_source()
        access = ACCESS_LUA + b"assert(panelAvailable,'City States panel unavailable')\n"
    verify_source()
    return _common(pid, turn) + access + f"\nlocal tokens,canGive,considered,blocker=header()\nassert(tokens=={catalog['tokens_to_give']} and not considered and blocker=={('true' if catalog['giving_tokens_blocker_present'] else 'false')},\n 'envoy consideration is stale')\ninfluence:SetGivingTokensConsidered(true)\nlocal afterTokens,afterCanGive,afterConsidered=header()\nassert(afterTokens==tokens and afterCanGive==canGive and afterConsidered,\n 'native envoy consideration effect differs')\nreturn serialize('catalog')\n".encode()

def verify_considered_effect(before, after, *, require_blocker=True):
    _check_catalog(before)
    _check_catalog(after)
    if type(require_blocker) is not bool:
        raise ValueError('Invalid consideration mode')
    if before['considered'] or (require_blocker and (not before['giving_tokens_blocker_present'])):
        raise ValueError('Envoy consideration was not due')
    unchanged = ('player_id', 'current_game_turn', 'tokens_to_give', 'can_give_influence', 'targets')
    if any((before[k] != after[k] for k in unchanged)) or not after['considered'] or after['giving_tokens_blocker_present']:
        raise RuntimeError('Native envoy consideration did not preserve tokens and clear its blocker')
    return {'player_id': before['player_id'], 'current_game_turn': before['current_game_turn'], 'tokens_retained': after['tokens_to_give'], 'considered': True, 'giving_tokens_blocker_present': False, 'eligible_for_training': False}
