"""Explicit default-handler choices from unchanged official support Lua.

This is a partial diplomacy adapter. Unknown statement handlers/selections and
queued-session EXIT choreography refuse; they are never silently acknowledged.
"""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import copy, hashlib, json, re
from pathlib import Path
from civ6_host.runtime.native import native_pending_diplomacy as pending
from civ6_host.runtime.native import native_turn_continuation as continuation
from civ6_host.runtime.native.native_diplomacy_statement import PROOF_SHA256
from civ6_host.runtime.native.native_diplomacy_statement import verify_source_evidence
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_diplomacy_choices.py')))).resolve().parents[1]
SCHEMA = 'civ6rl.diplomacy_decisions948.v1'
CURRENT_SCHEMA = 'civ6rl.diplomacy_decisions987.v1'
SUPPORT_SHA = 'b9d573f6a93a8dc43bc8804b4faf53510dcbe795862f64dece76e1434bc5a0fb'
VIEW_SHA = '246409606568dc3f6f2b913334dbc626d9b59e81efc02df0d28409a6ae959cfc'
KINDS = ('CHOICE_POSITIVE', 'CHOICE_EXIT')
TRANSPORT_SHA = 'bea5153e9acc32d1f0d1deedcf0cafaee40529cbfde3601d56400ac6f51777ba'

def official_source(name, digest):
    p = ROOT / 'work/diplomacy948/official-source' / digest / name
    data = _resolve_resource_path(p).read_bytes()
    if hashlib.sha256(data).hexdigest() != digest:
        raise RuntimeError('Official diplomacy UI source changed')
    return data

def is_catalog(value):
    return type(value) is dict and value.get('schema') in (SCHEMA, CURRENT_SCHEMA)

def lua_source(statement, player_id, configuration=None, *, public_display=False,
               execution_image=None):
    verify_source_evidence()
    official_source('DiplomacyActionView.lua', VIEW_SHA)
    head = b'local function identity()\n' + pending.source(statement, player_id) + b'\nend\nlocal identityText=identity()\n'
    support = official_source('DiplomacyStatementSupport.lua', SUPPORT_SHA)
    f = statement['fields']
    signed = lambda v: v if v < 2147483648 else v - (1 << 32)
    body = '\nlocal pid=%d\nlocal sid=%d\nlocal from=%d\nlocal to=%d\nlocal inputMood=%d\nlocal initiator=%d\nlocal other=from==pid and to or from\nlocal name=DiplomacyManager.GetKeyName(%d)\nlocal subtype=DiplomacyManager.GetKeyName(%d)\nassert(name~=\'MAKE_DEAL\' and name~=\'MAKE_DEMAND\', \'Special native statement handler not implemented\')\nassert(DiplomacyManager.IsSessionIDOpen(sid)==true, \'Conversation no longer open\')\nassert(Players[from] and Players[pid], \'Missing statement player\')\nlocal mood=inputMood\nif mood==DiplomacyMoodTypes.UNDEFINED then\n mood=DiplomacySupport_GetPlayerMood(Players[from],from==pid and other or pid)\nend\nlocal handler=GetStatementHandler(name)\nassert(handler==DefaultHandlers,\'Special statement handler not implemented\')\nlocal parsed=handler.ExtractStatement(handler,name,subtype,from,mood,initiator)\nhandler.RemoveInvalidSelections(parsed,pid,other)\nassert(type(parsed.Selections)==\'table\' and #parsed.Selections>0 and #parsed.Selections<=64,\'Missing or excessive choices\')\nlocal function quote(s)\n if s==nil then return \'null\' end\n assert(type(s)==\'string\' and #s<=4096,\'Malformed diplomacy text\')\n local parts={\'"\'}\n for i=1,#s do\n  local n=string.byte(s,i);local c=string.sub(s,i,i)\n  if n==34 or n==92 then parts[#parts+1]=string.char(92)..c\n  elseif n<32 then parts[#parts+1]=string.char(92)..string.format(\'u%%04x\',n)\n  else parts[#parts+1]=c end\n end\n parts[#parts+1]=\'"\';return table.concat(parts)\nend\nlocal out,seen={},{}\nfor _,s in ipairs(parsed.Selections) do\n assert(type(s.Key)==\'string\' and not seen[s.Key],\'Duplicate choice\')\n assert(s.Key==\'CHOICE_POSITIVE\' or s.Key==\'CHOICE_EXIT\',\'Unsupported native response choice\')\n assert(type(s.Sort)==\'number\' and s.Sort%%1==0,\'Invalid choice order\')\n assert(s.IsDisabled==nil or type(s.IsDisabled)==\'boolean\',\'Invalid disabled choice\')\n seen[s.Key]=true\n out[#out+1]=\'{"key":\'..quote(s.Key)..\',"sort":\'..tostring(s.Sort)..\',"text":\'..quote(s.Text)..\n  \',"tooltip":\'..quote(s.Tooltip)..\',"diplomatic_action_type":\'..quote(s.DiplomaticActionType)..\n  \',"disabled":\'..(s.IsDisabled==true and \'true\' or \'false\')..\'}\'\n assert(not s.IsDisabled or s.FailureReasons==nil,\'Disabled explanation transport not yet implemented\')\nend\nreturn \'{"identity":\'..quote(identityText)..\',"statement_text":\'..quote(parsed.StatementText)..\n \',"mood":\'..tostring(mood)..\',"selections":[\'..table.concat(out,\',\')..\']}\'\n' % (player_id, f['SessionID'], f['FromPlayer'], f['ToPlayer'], signed(f['FromPlayerMood']), signed(f['Initiator']), signed(f['StatementType']), signed(f['StatementSubType']))
    from civ6_host.runtime.native.native_diplomacy_configuration import lua_bindings
    from civ6_host.runtime.native.native_diplomacy_default import handler_source
    if type(public_display) is not bool:
        raise ValueError('Invalid public display option')
    if public_display:
        from civ6_host.runtime.native.native_diplomacy_display986 import lua_projection
        marker = 'return \'{"identity":'
        if body.count(marker) != 1:
            raise RuntimeError('Diplomacy projection insertion point changed')
        body = body[:body.index(marker)] + lua_projection(statement, execution_image=execution_image)
    bindings = b'' if configuration is None else lua_bindings(configuration)
    return bindings + head + support + b'\n' + handler_source() + body.encode('ascii')

def parse(raw, statement, player_id):
    if type(raw) is not bytes or len(raw) > 131072:
        raise ValueError('Unbounded diplomacy catalogue')
    value = json.loads(raw)
    if type(value) is not dict or set(value) != {'identity', 'statement_text', 'mood', 'selections'}:
        raise ValueError('Malformed diplomacy data')
    session = pending.parse(value.pop('identity').encode('ascii'), statement, player_id)
    value['session'] = session
    validate_data(value, statement, player_id)
    return value

def validate_data(data, statement, pid):
    if type(data) is not dict or set(data) != {'statement_text', 'mood', 'selections', 'session'}:
        raise ValueError('Malformed native diplomacy catalogue')
    s = data['session']
    f = statement['fields']
    if s != dict(player_id=pid, session_id=f['SessionID'], from_player=f['FromPlayer'], to_player=f['ToPlayer'], is_open=True, statement_type=s.get('statement_type'), statement_subtype=s.get('statement_subtype'), response_type=s.get('response_type')) or pid not in (s['from_player'], s['to_player']):
        raise ValueError('Unknown or foreign native conversation')
    from civ6_host.runtime.native.native_diplomacy_default import validate_handler
    validate_handler(s['statement_type'], s['statement_subtype'])
    if type(data['mood']) is not int or not -(1 << 31) <= data['mood'] <= 4294967295:
        raise ValueError('Invalid native mood')
    if type(data['selections']) is not list or not 1 <= len(data['selections']) <= 64:
        raise ValueError('Unbounded native selections')
    seen = set()
    order = []
    for row in data['selections']:
        if type(row) is not dict or set(row) != {'key', 'sort', 'text', 'tooltip', 'diplomatic_action_type', 'disabled'} or row['key'] not in KINDS or (row['key'] in seen) or (type(row['sort']) is not int) or (type(row['disabled']) is not bool):
            raise ValueError('Malformed native selection')
        for key in ('text', 'tooltip', 'diplomatic_action_type'):
            if row[key] is not None and (type(row[key]) is not str or len(row[key]) > 4096):
                raise ValueError('Malformed native selection text')
        seen.add(row['key'])
        order.append(row['sort'])
    if order != sorted(order):
        raise ValueError('Native choice order changed')

def actions(data, statement):
    return [dict(kind='diplomacy_response', session_id=data['session']['session_id'], statement_sequence=statement['event_sequence'], choice=row['key']) for row in data['selections'] if not row['disabled']]

def _continuation(owner, saved_context=None):
    if saved_context is None:
        return continuation.validate(owner)
    return saved_context.validate(owner)


def _snapshot(owner,phase,saved_context=None):
    if saved_context is None:
        from .native_saved_actions import snapshot
        return snapshot(owner,phase)
    from ..xp1_saved_load_owner import SavedLoadOwner
    saved=saved_context.saved
    if type(saved) is not SavedLoadOwner or saved.backend is not owner:
        raise ValueError('Diplomacy snapshot requires its exact saved-session owner')
    saved._check('commands',requested='unit_commands_candidate')
    with saved._attempt():
        return owner.jobs.query_snapshot(saved,phase)

def read(owner, sequence, *, closed=False, saved_context=None):
    from civ6_host.runtime.native.native_saved_actions import snapshot
    from civ6_host.runtime.native.native_saved_actions import digest
    from civ6_host.runtime.native.native_saved_actions import GAPS
    from civ6_host.runtime.native.native_player_observation import observe_player
    from civ6_host.runtime.native.native_episode_identity import require_episode
    from civ6_host.runtime.native import native_saved_player_map as player_map
    c = _continuation(owner, saved_context)
    p = owner.prefix
    before = _snapshot(owner, 'before', saved_context)
    ledger = p.deferred_events.pending_diplomacy_statements
    if not ledger or ledger[0] != c.pending.statement:
        raise RuntimeError('Published statement no longer first')
    statement = copy.deepcopy(ledger[0])
    pid = c.pending.session['player_id']
    obs = observe_player(p.runtime, p.ui_child, pid)
    map_view = player_map.observe(p, obs)
    if obs['turn'] not in (c.turn, c.turn + 1):
        raise RuntimeError('Interrupted turn changed unexpectedly')
    from civ6_host.runtime.native.native_diplomacy_configuration import read as read_configuration
    if saved_context is None:
        configuration = read_configuration(owner, statement)
    else:
        from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
        configuration = read_configuration(owner, statement, core_sha256=XP2_CORE_SHA256)
    if not getattr(owner, 'diplomacy_database_namespace_attached', False):
        if not p.runtime.database_bound:
            raise RuntimeError('Official gameplay database is not bound')
        p.runtime.namespaces.register(p.ui_child, 'DB')
        owner.diplomacy_database_namespace_attached = True
        owner.emit('native_diplomacy_database_namespace_attached', borrowed_gameplay_connection=True, new_database_connection=False, strategic_training_ready=False)
    data = parse(p.runtime.evaluate_text(p.ui_child, lua_source(statement, pid, configuration), b'@official_diplomacy_choices', capacity=131072), statement, pid)
    offers = [] if closed else actions(data, statement)
    identity = require_episode(p)
    result = dict(schema=SCHEMA if saved_context is not None else CURRENT_SCHEMA,
        episode_id=identity.episode_id, game_generation=identity.game_generation,
        sequence=sequence, player_id=pid, turn=obs['turn'], origin_turn=c.turn,
        player_map=map_view, statement=statement, data=data, source_sha256=PROOF_SHA256,
        ui_support_sha256=SUPPORT_SHA,
        candidates=[dict(candidate_id=digest(a), action=a) for a in offers],
        unsupported=list(GAPS), complete_action_space=False)
    if saved_context is None:
        # These rendered display readers are pinned to the Base projection. The
        # XP2 saved path exposes the native menu and omits unqualified displays.
        from civ6_host.runtime.native.native_diplomacy_display986 import read as read_display
        from civ6_host.runtime.native.native_diplomacy_display986 import PROOF_SHA as DISPLAY_SHA
        from civ6_host.runtime.native.native_saved_yield_display982 import observe as observe_yield_display
        result.update(public_display=read_display(owner, statement, data, configuration, sequence),
            public_display_source_sha256=DISPLAY_SHA, yield_display=observe_yield_display(p, obs))
    if c.origin == 'world_input':
        result['continuation_origin'] = 'world_input'
    result['decision_id'] = digest(result)
    _continuation(owner, saved_context)
    if _snapshot(owner, 'after', saved_context) != before:
        raise RuntimeError('Diplomacy read changed scheduler')
    owner.explicit_observation = copy.deepcopy(obs)
    owner.explicit_diplomacy = copy.deepcopy(result)
    owner.emit('official_explicit_diplomacy_decisions_observed', observation=obs, decisions=result, native_support_reused=True, automatic_choices_applied=False, strategic_training_ready=False)
    return (obs, result)

def validate_catalog(value, identity, sequence, turn, *, player_id, actions_closed=None):
    from civ6_host.runtime.native.native_saved_actions import digest
    from civ6_host.runtime.native.native_saved_actions import GAPS
    from civ6_host.runtime.native import native_saved_player_map as player_map
    expected = {'schema', 'episode_id', 'game_generation', 'sequence', 'player_id', 'turn', 'origin_turn', 'player_map', 'statement', 'data', 'source_sha256', 'ui_support_sha256', 'candidates', 'unsupported', 'complete_action_space', 'decision_id'}
    if actions_closed is not None and type(actions_closed) is not bool:
        raise ValueError('Explicit diplomatic action closure must be boolean')
    current = type(value) is dict and value.get('schema') == CURRENT_SCHEMA
    if current:
        expected.update(('public_display', 'public_display_source_sha256', 'yield_display'))
    action_origin = current and type(value) is dict and ('continuation_origin' in value)
    if action_origin:
        expected.add('continuation_origin')
    if not is_catalog(value) or set(value) != expected or value['episode_id'] != identity.episode_id or (value['game_generation'] != identity.game_generation) or (type(value['sequence']) is not int) or (value['sequence'] != sequence) or (type(value['player_id']) is not int) or (value['player_id'] != player_id) or (type(value['turn']) is not int) or (value['turn'] != turn) or (type(value['origin_turn']) is not int) or (turn not in (value['origin_turn'], value['origin_turn'] + 1)) or (value['source_sha256'] != PROOF_SHA256) or (value['ui_support_sha256'] != SUPPORT_SHA) or (value['unsupported'] != list(GAPS)) or (value['complete_action_space'] is not False) or (value['decision_id'] != digest({k: v for k, v in value.items() if k != 'decision_id'})):
        raise ValueError('Foreign or malformed pending-choice catalogue')
    if action_origin and (value['continuation_origin'] != 'world_input' or turn != value['origin_turn']):
        raise ValueError('Invalid action-created dialogue origin')
    player_map.validate(value['player_map'], player_id, turn)
    statement = value['statement']
    data = value['data']
    validate_data(data, statement, player_id)
    if current:
        from civ6_host.runtime.native.native_diplomacy_display986 import validate_public
        from civ6_host.runtime.native.native_diplomacy_display986 import PROOF_SHA as DISPLAY_SHA
        from civ6_host.runtime.native.native_saved_yield_display982 import validate as validate_yield_display
        if value['public_display_source_sha256'] != DISPLAY_SHA:
            raise ValueError('Diplomatic public display source differs')
        validate_public(value['public_display'], data)
        validate_yield_display(value['yield_display'], player_id, turn)
    if type(statement['event_sequence']) is not int or statement['event_sequence'] <= 0 or statement['source_proof_sha256'] != PROOF_SHA256 or (statement['automatic_response'] is not False):
        raise ValueError('Malformed statement identity')
    s = data['session']
    wire = '|'.join(map(str, (player_id, s['session_id'], s['from_player'], s['to_player'], 1, s['statement_type'], s['statement_subtype'], s['response_type'] if s['response_type'] is not None else '')))
    pending.parse(wire.encode('ascii'), statement, player_id)
    expected_rows = [dict(candidate_id=digest(a), action=a) for a in actions(data, statement)]
    allowed = ([],) if actions_closed is True else ([], expected_rows) if not current and actions_closed is None else (expected_rows,)
    if value['candidates'] not in allowed:
        raise ValueError('Offered responses differ from native selections')
    return value

def deliver_response(transport, choice):
    from civ6_host.runtime.native.native_source_cache import load_pinned_json
    proof = load_pinned_json(ROOT / 'evidence/native-diplomacy-transport' / (TRANSPORT_SHA + '.json'), TRANSPORT_SHA)
    expected = proof['contract']['message_kinds'][choice]
    _deliver_request(transport, expected, proof)

def deliver_statement_request(transport):
    """Deliver the native statement message, including generated action archives.

    RequestSession and AddResponse use A4172391. This is transport reuse, not
    an automatically selected POSITIVE response to a player's pending choice.
    """
    from civ6_host.runtime.native.native_source_cache import load_pinned_json
    proof = load_pinned_json(ROOT / 'evidence/native-diplomacy-transport' / (TRANSPORT_SHA + '.json'), TRANSPORT_SHA)
    _deliver_request(transport, proof['contract']['message_kinds']['CHOICE_POSITIVE'], proof)

def _deliver_request(transport, expected, proof):
    if len(transport.pending) != 1 or type(transport.pending[0]) is not bytes or (not 4 < len(transport.pending[0]) <= 6784) or (int.from_bytes(transport.pending[0][:4], 'little') != expected):
        raise RuntimeError('Native diplomatic request did not queue exactly one expected command')
    transport.deliver_one()
    for _ in range(8):
        if not transport.pending:
            return
        payload = transport.pending[0]
        if type(payload) is not bytes or not 4 < len(payload) <= 6784 or int.from_bytes(payload[:4], 'little') != proof['contract']['native_followup_kind']:
            raise RuntimeError('Diplomatic delivery produced an unqualified command')
        transport.deliver_one()
    if transport.pending:
        raise RuntimeError('Native diplomatic followups exceeded bounded delivery')

def apply(owner, action, *, saved_context=None):
    from civ6_host.runtime.native.native_saved_actions import snapshot
    c = _continuation(owner, saved_context)
    old = owner.explicit_diplomacy
    origin = c.origin
    obs, current = read(owner, old['sequence'], saved_context=saved_context)
    if current != old or action not in [r['action'] for r in current['candidates']]:
        raise RuntimeError('Stale diplomacy selection')
    sid = action['session_id']
    pid = current['player_id']
    p = owner.prefix
    before = _snapshot(owner, 'before', saved_context)
    if p.actions.pending:
        raise RuntimeError('Diplomacy response overlapping a round-completion echo is not qualified')
    code = pending.source(current['statement'], pid)
    source = b'local function check()\n' + code + b'\nend\ncheck()\n'
    if action['choice'] == 'CHOICE_POSITIVE':
        source += ('local ok=DiplomacyManager.AddResponse(%d,%d,"POSITIVE")\nassert(type(ok)=="boolean" and ok,"Native response refused")\nreturn "accepted"' % (sid, pid)).encode()
    elif action['choice'] == 'CHOICE_EXIT':
        source += ('assert(DiplomacyManager.HasQueuedSession(%d)==false,"Queued-session EXIT choreography not yet qualified")\nlocal ok=DiplomacyManager.CloseSession(%d)\nassert(type(ok)=="boolean" and ok,"Native close refused")\nreturn "accepted"' % (pid, sid)).encode()
    else:
        raise ValueError('Unknown explicit diplomatic response')
    owner.emit('before_official_explicit_action', action=action, player_id=pid, turn=obs['turn'], jobs_before=before, automatic_choices_applied=False, strategic_training_ready=False)
    response_started = False
    if saved_context is not None:
        saved_context.begin_response(owner)
        response_started = True
    owner.busy = True
    try:
        raw = p.runtime.evaluate_text(p.ui_child, source, b'@explicit_native_diplomacy_response', capacity=1024)
        if raw != b'accepted':
            raise RuntimeError('Native response result differs')
        deliver_response(p.actions, action['choice'])
        ledger = p.deferred_events.pending_diplomacy_statements
        if not ledger or ledger[0] != current['statement']:
            raise RuntimeError('Pending statement identity changed')
        ledger.pop(0)
        p.deferred_events.drain_empty_receivers()
        p.view_publisher.publish()
    except BaseException:
        owner.poisoned = True
        owner.stage = 'poisoned'
        if saved_context is not None:
            saved_context.poison(owner)
        raise
    finally:
        owner.busy = False
        if response_started and not owner.poisoned:
            saved_context.end_response(owner)
    owner.emit('official_explicit_diplomacy_response_applied', action=action, pending_statement_removed=True, native_success=True, native_command_delivered=True, transport_source_sha256=TRANSPORT_SHA, automatic_choices_applied=False, strategic_training_ready=False)
    after = (continuation.resume(owner) if saved_context is None
             else saved_context.resume(owner))
    if after is None:
        from civ6_host.runtime.native.native_player_observation import observe_player
        after = observe_player(p.runtime, p.ui_child, pid)
    owner.emit('official_explicit_action_observed', action=action, player_id=pid, turn=obs['turn'], observation=after, jobs_before=before, jobs_after=_snapshot(owner, 'after', saved_context), automatic_choices_applied=False, round_completed=origin == 'end_turn' and getattr(owner, 'turn_continuation', None) is None, strategic_training_ready=False)
    return after
