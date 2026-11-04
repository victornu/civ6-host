"""Read named UI closure upvalues through the existing Tuner, without setters.

This strict producer requires debug.getinfo/getupvalue and string.dump directly
in each uniquely named UI context. No Threads/global transfer fallback, handler
invocation, context selection change, or GameCore command is performed. Captured
bytecode is evidence for later source comparison, not source qualification.
"""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
import hashlib
import json
import math
import re
import time
import uuid
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_ui_local_state.py')))).resolve().parents[1]
SOURCE = ROOT / 'work/ui-availability/local-state-source.json'
SOURCE_SHA = 'd615e31517dd3d754095a99464cdd0a521908e782a5789e1d291b0255b3bf0fa'
SCHEMA = 'civ6rl.ui_local_state.v1'
CONTEXT_SCHEMA = 'civ6rl.ui_local_context.v1'
MAX_SECONDS = 30
MAX_UPVALUES = 256
MAX_CONTROLS = 256
MAX_DUMP_BYTES = 256 * 1024
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
CONTRACTS = {'production': ('ProductionPanel', 'RefreshQueue', ('m_isTutorialRunning', 'm_tutorialTestMode')), 'city': ('CityPanel', 'EnableIfNotTutorialBlocked', ('m_kTutorialDisabledControls',))}

class UILocalStateError(ValueError):
    pass

def _require(condition, message):
    if not condition:
        raise UILocalStateError('UI local state: ' + message)

def _digest(path):
    result = hashlib.sha256()
    with _resolve_resource_path(_resolve_resource_path(Path(path))).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()

def verify_source():
    _require(_digest(SOURCE) == SOURCE_SHA, 'source contract changed')
    value = json.loads(_resolve_resource_path(SOURCE).read_text(encoding='utf8'))
    _require(value.get('schema') == 'civ6rl.ui_local_state.source.v1' and value.get('runtime_context_sources_verified') is False and (value.get('headless_qualified') is False), 'unsupported source contract')
    for row in [value['havok'], *value['official_ui']]:
        path = _resolve_resource_path(Path(row['path']))
        _require(_resolve_resource_path(path).stat().st_size == row['bytes'] and _digest(path) == row['sha256'], 'installed source file changed: ' + path.name)
    previous = value['previous_route']
    _require(_digest(previous['path']) == previous['sha256'], 'previous route changed')
    for kind, (context, fn, names) in CONTRACTS.items():
        contract = value['contracts'][kind]
        _require(contract['context'] == context and contract['function'] == fn and (set(contract['upvalues']) == set(names)), 'upvalue contract differs')
    return value

def _request(player_id, turn, timeout_seconds):
    _require(type(player_id) is int and 0 <= player_id < 64, 'invalid player')
    _require(type(turn) is int and 0 <= turn < 2 ** 31, 'invalid turn')
    _require(type(timeout_seconds) in (int, float) and math.isfinite(timeout_seconds) and (0 < timeout_seconds <= MAX_SECONDS), 'invalid bounded timeout')

def _quote(text):
    return '"' + ''.join((chr(b) if 32 <= b <= 126 and b not in (34, 92) else '\\%03d' % b for b in text.encode('utf8'))) + '"'
LUA = '\nlocal function check(value,why) if not value then error(\'ui_local_state: \'..why,0) end end\nlocal function integer(value,a,b) return type(value)==\'number\' and value==math.floor(value) and value>=a and value<=b end\ncheck(type(debug)==\'table\' and type(debug.getinfo)==\'function\' and type(debug.getupvalue)==\'function\',\'debug API unavailable\')\ncheck(type(string)==\'table\' and type(string.dump)==\'function\',\'bytecode dump API unavailable\')\ncheck(type(getfenv)==\'function\',\'function environment API unavailable\')\ncheck(Game and type(Game.GetLocalPlayer)==\'function\' and type(Game.GetCurrentGameTurn)==\'function\',\'identity API unavailable\')\nlocal env=getfenv(1)\nlocal closure=rawget(env,functionName)\ncheck(type(closure)==\'function\' and getfenv(closure)==env,\'missing or foreign closure\')\nlocal function quote(text)\n  check(type(text)==\'string\',\'nonstring JSON key/value\')\n  return \'"\'..text:gsub(\'[%z\\1-\\31\\\\"]\',function(c)\n    if c==\'"\' then return \'\\\\"\' end\n    if c==\'\\\\\' then return \'\\\\\\\\\' end\n    return string.format(\'\\\\u%04x\',string.byte(c))\n  end)..\'"\'\nend\nlocal function boolean(value) return value and \'true\' or \'false\' end\nlocal function tohex(text)\n  check(#text>0 and #text<=maxDump,\'bytecode dump exceeds bound\')\n  local out={};for i=1,#text do out[i]=string.format(\'%02x\',string.byte(text,i)) end\n  return table.concat(out)\nend\nlocal function strings(value)\n  if value==nil then return \'{"is_nil":true,"controls":[]}\' end\n  check(type(value)==\'table\' and getmetatable(value)==nil,\'lock list has unknown type/metatable\')\n  local count=0\n  for key,item in pairs(value) do\n    count=count+1\n    check(count<=maxControls and integer(key,1,maxControls),\'lock list bound/index\')\n    check(type(item)==\'string\' and #item>=1 and #item<=128 and not item:find(\'\\0\',1,true),\'invalid lock name\')\n  end\n  local out={}\n  for i=1,count do check(value[i]~=nil,\'sparse lock list\');out[i]=quote(value[i]) end\n  return \'{"is_nil":false,"controls":[\'..table.concat(out,\',\')..\']}\'\nend\nlocal function identity()\n  check(Game.GetLocalPlayer()==pid and Game.GetCurrentGameTurn()==turn,\'player/turn changed\')\n  check(rawget(env,functionName)==closure and getfenv(closure)==env,\'closure identity changed\')\nend\nlocal function read()\n  identity()\n  local info=debug.getinfo(closure,\'Su\')\n  check(type(info)==\'table\' and info.what==\'Lua\',\'not a Lua closure\')\n  check(type(info.source)==\'string\' and #info.source>=1 and #info.source<=4096,\'invalid source metadata\')\n  check(type(info.short_src)==\'string\' and #info.short_src<=4096,\'invalid short source metadata\')\n  check(integer(info.linedefined,0,2147483647) and integer(info.lastlinedefined,info.linedefined,2147483647),\'invalid definition lines\')\n  check(integer(info.nups,1,maxUpvalues),\'upvalue count exceeds bound\')\n  local selected={};local seen={}\n  for i=1,info.nups do\n    local name,value=debug.getupvalue(closure,i)\n    check(type(name)==\'string\' and #name>=1 and #name<=128,\'missing or stripped upvalue name\')\n    check(not seen[name],\'duplicate upvalue name\');seen[name]=true\n    if requested[name] then\n      if kind==\'production\' then\n        check(type(value)==\'boolean\',\'production upvalue is not boolean\')\n        selected[name]=\'{"index":\'..i..\',"type":"boolean","value":\'..boolean(value)..\'}\'\n      else\n        selected[name]=\'{"index":\'..i..\',"type":"nil_or_ordered_string_array","value":\'..strings(value)..\'}\'\n      end\n    end\n  end\n  local extra=debug.getupvalue(closure,info.nups+1)\n  check(extra==nil,\'upvalue metadata count differs\')\n  local parts={}\n  for _,name in ipairs(names) do check(selected[name]~=nil,\'required named upvalue absent\');parts[#parts+1]=quote(name)..\':\'..selected[name] end\n  local dumped=string.dump(closure)\n  check(type(dumped)==\'string\',\'dump returned wrong type\')\n  local hex=tohex(dumped)\n  identity()\n  return \'{"metadata":{"what":"Lua","source":\'..quote(info.source)..\',"short_src":\'..quote(info.short_src)..\n    \',"linedefined":\'..info.linedefined..\',"lastlinedefined":\'..info.lastlinedefined..\',"nups":\'..info.nups..\'},"dump_hex":\'..quote(hex)..\n    \',"upvalues":{\'..table.concat(parts,\',\')..\'}}\'\nend\nlocal first=read()\nlocal second=read()\ncheck(first==second,\'local closure/state changed between reads\')\nidentity()\nprint(prefix..\'{"schema":"civ6rl.ui_local_context.v1","nonce":\'..quote(nonce)..\n  \',"player_id":\'..pid..\',"turn":\'..turn..\',"context_name":\'..quote(contextName)..\n  \',"context_index":\'..contextIndex..\',"function_name":\'..quote(functionName)..\n  \',"closure":\'..first..\',"read_only":true,"observed_unchanged":true,"runtime_context_sources_verified":false}\')\n'

def command(kind, *, player_id, turn, context_index, nonce):
    _request(player_id, turn, 1)
    _require(kind in CONTRACTS and type(context_index) is int and (0 <= context_index < 2 ** 31), 'invalid context')
    _require(type(nonce) is str and re.fullmatch('[0-9a-f]{32}', nonce), 'invalid nonce')
    name, function, names = CONTRACTS[kind]
    prefix = f'CIV6RL_UI_LOCAL:{nonce}:'
    constants = f"local pid={player_id};local turn={turn};local contextIndex={context_index};local nonce={_quote(nonce)};local prefix={_quote(prefix)};local contextName={_quote(name)};local functionName={_quote(function)};local kind={_quote(kind)};local maxUpvalues={MAX_UPVALUES};local maxControls={MAX_CONTROLS};local maxDump={MAX_DUMP_BYTES};local names={{{','.join((_quote(n) for n in names))}}};local requested={{}};for _,name in ipairs(names) do requested[name]=true end;\n"
    return constants + LUA

def _decode(lines, *, kind, player_id, turn, context_index, nonce):
    _require(type(lines) is list and len(lines) == 1 and (type(lines[0]) is str), 'missing or ambiguous receipt')
    text = lines[0]
    _require(len(text.encode('utf8')) <= MAX_RESPONSE_BYTES // 2, 'response exceeds byte bound')
    prefix = f'CIV6RL_UI_LOCAL:{nonce}:'
    _require(text.startswith(prefix), 'receipt nonce prefix differs')

    def unique(pairs):
        result = {}
        for key, value in pairs:
            _require(key not in result, 'duplicate JSON field')
            result[key] = value
        return result
    value = json.loads(text[len(prefix):], object_pairs_hook=unique)
    _validate_context(value, kind=kind, player_id=player_id, turn=turn, context_index=context_index, nonce=nonce)
    dump = bytes.fromhex(value['closure']['dump_hex'])
    value['closure']['dump_sha256'] = hashlib.sha256(dump).hexdigest()
    return value

def _validate_context(value, *, kind, player_id, turn, context_index, nonce, retained=False):
    name, fn, names = CONTRACTS[kind]
    keys = {'schema', 'nonce', 'player_id', 'turn', 'context_name', 'context_index', 'function_name', 'closure', 'read_only', 'observed_unchanged', 'runtime_context_sources_verified'}
    _require(type(value) is dict and set(value) == keys and (value['schema'] == CONTEXT_SCHEMA), 'invalid context schema')
    _require(value['nonce'] == nonce and value['context_name'] == name and (value['function_name'] == fn) and (type(value['context_index']) is int) and (value['context_index'] == context_index), 'foreign context/function/nonce')
    _require(type(value['player_id']) is int and value['player_id'] == player_id and (type(value['turn']) is int) and (value['turn'] == turn), 'foreign player/turn')
    _require(value['read_only'] is True and value['observed_unchanged'] is True and (value['runtime_context_sources_verified'] is False), 'context stability/source overclaim')
    closure = value['closure']
    _require(type(closure) is dict and set(closure) == ({'metadata', 'dump_hex', 'upvalues', 'dump_sha256'} if retained else {'metadata', 'dump_hex', 'upvalues'}), 'invalid closure fields')
    info = closure['metadata']
    _require(type(info) is dict and set(info) == {'what', 'source', 'short_src', 'linedefined', 'lastlinedefined', 'nups'} and (info['what'] == 'Lua') and (type(info['source']) is str) and (1 <= len(info['source'].encode('utf8')) <= 4096) and (type(info['short_src']) is str) and (len(info['short_src'].encode('utf8')) <= 4096) and (type(info['linedefined']) is int) and (type(info['lastlinedefined']) is int) and (0 <= info['linedefined'] <= info['lastlinedefined'] < 2 ** 31) and (type(info['nups']) is int) and (1 <= info['nups'] <= MAX_UPVALUES), 'invalid closure metadata')
    dumped = closure['dump_hex']
    _require(type(dumped) is str and 0 < len(dumped) <= MAX_DUMP_BYTES * 2 and (len(dumped) % 2 == 0) and re.fullmatch('[0-9a-f]+', dumped), 'invalid complete bytecode dump')
    if retained:
        _require(closure['dump_sha256'] == hashlib.sha256(bytes.fromhex(dumped)).hexdigest(), 'dump hash differs')
    upvalues = closure['upvalues']
    _require(type(upvalues) is dict and set(upvalues) == set(names), 'requested upvalue set differs')
    indices = set()
    for name, entry in upvalues.items():
        _require(type(entry) is dict and set(entry) == {'index', 'type', 'value'} and (type(entry['index']) is int) and (1 <= entry['index'] <= info['nups']) and (entry['index'] not in indices), 'invalid named upvalue index')
        indices.add(entry['index'])
        if kind == 'production':
            _require(entry['type'] == 'boolean' and type(entry['value']) is bool, 'invalid production state')
        else:
            lock = entry['value']
            _require(entry['type'] == 'nil_or_ordered_string_array' and type(lock) is dict and (set(lock) == {'is_nil', 'controls'}) and (type(lock['is_nil']) is bool) and (type(lock['controls']) is list) and (len(lock['controls']) <= MAX_CONTROLS) and (not lock['is_nil'] or not lock['controls']), 'invalid lock state')
            for control in lock['controls']:
                _require(type(control) is str and 1 <= len(control.encode('utf8')) <= 128 and ('\x00' not in control), 'invalid lock control name')
    return value

def _states(contexts):
    prod = contexts['production']['closure']['upvalues']
    city = contexts['city']['closure']['upvalues']
    return dict(production_cached_active=prod['m_isTutorialRunning']['value'], production_test_mode=prod['m_tutorialTestMode']['value'], city_panel_locks=city['m_kTutorialDisabledControls']['value'])

def validate_capture(value, *, expected_player_id, expected_turn):
    _request(expected_player_id, expected_turn, 1)
    keys = {'schema', 'source_sha256', 'producer_source_sha256', 'nonce', 'player_id', 'turn', 'contexts', 'states', 'read_only', 'atomic_snapshot', 'runtime_context_sources_verified', 'headless_qualified', 'actor_input'}
    _require(type(value) is dict and set(value) == keys and (value['schema'] == SCHEMA) and (value['source_sha256'] == SOURCE_SHA) and (value['producer_source_sha256'] == _digest(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_ui_local_state.py'))))), 'capture source/schema differs')
    _require(type(value['player_id']) is int and value['player_id'] == expected_player_id and (type(value['turn']) is int) and (value['turn'] == expected_turn) and (type(value['nonce']) is str) and re.fullmatch('[0-9a-f]{32}', value['nonce']), 'capture identity differs')
    _require(value['read_only'] is True, 'capture not read-only')
    for flag in ('atomic_snapshot', 'runtime_context_sources_verified', 'headless_qualified', 'actor_input'):
        _require(value[flag] is False, 'capture overclaims ' + flag)
    contexts = value['contexts']
    _require(type(contexts) is dict and set(contexts) == set(CONTRACTS), 'context set differs')
    indices = []
    for kind, context in contexts.items():
        _require(type(context) is dict and type(context.get('context_index')) is int and (0 <= context['context_index'] < 2 ** 31), 'invalid retained context index')
        indices.append(context['context_index'])
        _validate_context(context, kind=kind, player_id=expected_player_id, turn=expected_turn, context_index=context['context_index'], nonce=value['nonce'], retained=True)
    _require(len(set(indices)) == len(indices), 'contexts unexpectedly share one index')
    _require(value['states'] == _states(contexts), 'projected states differ from named upvalues')
    _require(len(json.dumps(value, allow_nan=False).encode('utf8')) <= MAX_RESPONSE_BYTES, 'capture byte bound exceeded')
    return value

def capture(tuner, *, expected_player_id, expected_turn, timeout_seconds=MAX_SECONDS, clock=time.monotonic):
    """Read an existing connected Tuner only. Caller controls process provenance.

    Direct debug APIs may be unavailable in actual contexts: refusal is expected
    in that case, with no fallback mutation. This function does not connect,
    launch a game, write files, or alter UI selection/mode. Time bounds constrain
    the transport; an already submitted Lua command is not remotely cancelled.
    """
    _request(expected_player_id, expected_turn, timeout_seconds)
    deadline = clock() + timeout_seconds

    def remaining():
        left = deadline - clock()
        _require(left > 0, 'deadline exceeded; no retry')
        return left

    def refresh():
        from contextlib import nullcontext
        with getattr(tuner, '_lock', nullcontext()):
            original = getattr(tuner, 'timeout', None)
            _require(type(original) in (int, float) and math.isfinite(original) and (original > 0), 'Tuner has no bounded control-request timeout')
            tuner.timeout = min(original, remaining())
            try:
                return tuner.refresh_states()
            finally:
                tuner.timeout = original
    verify_source()
    remaining()
    inventory = refresh()
    remaining()
    selected = {}
    for kind, (name, _, _) in CONTRACTS.items():
        matches = [i for i, n in inventory.items() if n == name]
        _require(len(matches) == 1, 'missing or ambiguous context ' + name)
        selected[kind] = tuner.state_index(name)
        _require(selected[kind] == matches[0], 'context lookup differs')
    _require(len(set(selected.values())) == 2, 'contexts share index')
    nonce = uuid.uuid4().hex
    contexts = {}
    for kind, index in selected.items():
        code = command(kind, player_id=expected_player_id, turn=expected_turn, context_index=index, nonce=nonce)
        lines = tuner.execute(code, context=index, timeout=remaining())
        remaining()
        contexts[kind] = _decode(lines, kind=kind, player_id=expected_player_id, turn=expected_turn, context_index=index, nonce=nonce)
    after = refresh()
    remaining()
    for kind, index in selected.items():
        name = CONTRACTS[kind][0]
        _require([i for i, n in after.items() if n == name] == [index], 'context inventory changed during capture')
    result = dict(schema=SCHEMA, source_sha256=SOURCE_SHA, producer_source_sha256=_digest(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_ui_local_state.py')))), nonce=nonce, player_id=expected_player_id, turn=expected_turn, contexts=contexts, states=_states(contexts), read_only=True, atomic_snapshot=False, runtime_context_sources_verified=False, headless_qualified=False, actor_input=False)
    return validate_capture(result, expected_player_id=expected_player_id, expected_turn=expected_turn)
