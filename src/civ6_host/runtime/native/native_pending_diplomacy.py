"""Preserve pending statements and refuse to auto-resolve an interrupted turn.

The official Lua namespace supplies the session and enum names. This reader
does not fabricate a session, expose another player's conversation or send a
response. The resumable-turn/action integration must consume this boundary.
"""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from civ6_host.runtime.native.native_diplomacy_statement import verify_source_evidence
from civ6_host.runtime.native.native_diplomacy_statement import PROOF_SHA256

class DiplomacyChoicePending(RuntimeError):

    def __init__(self, statement, session):
        super().__init__('Native diplomacy choice interrupts the turn; no automatic response is allowed')
        self.statement = statement
        self.session = session

def source(statement, player_id):
    verify_source_evidence()
    if type(player_id) is not int or not 0 <= player_id < 64:
        raise ValueError('Invalid diplomacy observer')
    f = statement['fields']
    if player_id not in (f['FromPlayer'], f['ToPlayer']):
        raise ValueError('Statement is not visible to this player')
    keys = ('SessionID', 'FromPlayer', 'ToPlayer', 'StatementType', 'StatementSubType', 'ResponseType')
    if any((type(f[k]) is not int or not 0 <= f[k] <= 4294967295 for k in keys)):
        raise ValueError('Invalid statement identity')
    signed = lambda v: v if v < 2147483648 else v - (1 << 32)
    return ("local function one(label,...)\n assert(select('#',...)==1,'Diplomacy invalid '..label..' arity'); return ...\nend\nlocal pid=one('player',Game.GetLocalPlayer())\nassert(pid==%d and one('observer',Game.GetLocalObserver())==pid,'Diplomacy perspective changed')\nassert(type(DiplomacyManager)=='table','Native DiplomacyManager absent')\nlocal sid=%d\nlocal open=one('open',DiplomacyManager.IsSessionIDOpen(sid))\nassert(type(open)=='boolean','Invalid native session status')\nlocal info=one('session',DiplomacyManager.GetSessionInfo(sid))\nlocal speaker,recipient=%d,%d\nassert(type(info)=='table' and\n ((info.FromPlayer==speaker and info.ToPlayer==recipient) or\n  (info.FromPlayer==recipient and info.ToPlayer==speaker)),\n 'Statement/session participants differ')\nlocal a=one('type',DiplomacyManager.GetKeyName(%d))\nlocal b=one('subtype',DiplomacyManager.GetKeyName(%d))\nlocal c=one('response',DiplomacyManager.GetKeyName(%d))\nlocal function key(label,value)\n assert(type(value)=='string' and value:match('^[A-Z0-9_]+$'),\n        'Invalid native diplomacy '..label..' key: '..tostring(value))\nend\nkey('type',a);key('subtype',b)\n-- The official generic ApplyStatement path does not name ResponseType.\n-- Preserve an actual nil lookup, never substitute INITIAL or another enum.\nif c~=nil then key('response',c) end\nreturn table.concat({string.format('%%.0f',pid),string.format('%%.0f',sid),\n                    string.format('%%.0f',speaker),string.format('%%.0f',recipient),\n                    open and '1' or '0',a,b,c==nil and '' or c},'|')\n" % (player_id, f['SessionID'], f['FromPlayer'], f['ToPlayer'], signed(f['StatementType']), signed(f['StatementSubType']), signed(f['ResponseType']))).encode('ascii')

def parse(raw, statement, player_id):
    """Session join with statement speaker/recipient, not raw initiator order."""
    if type(raw) is not bytes or len(raw) > 1024:
        raise ValueError('Invalid bounded diplomacy result')
    parts = raw.decode('ascii').split('|')
    f = statement['fields']
    if len(parts) != 8 or parts[:4] != list(map(str, (player_id, f['SessionID'], f['FromPlayer'], f['ToPlayer']))) or parts[4] not in ('0', '1'):
        raise ValueError('Native statement identity changed: ' + repr(parts) + ' expected ' + repr((player_id, f['SessionID'], f['FromPlayer'], f['ToPlayer'])) + ' enum hashes ' + repr(tuple((f[k] for k in ('StatementType', 'StatementSubType', 'ResponseType')))))
    import re, zlib
    for text, key in zip(parts[5:], ('StatementType', 'StatementSubType', 'ResponseType')):
        if key == 'ResponseType' and text == '':
            continue
        if re.fullmatch('[A-Z0-9_]+', text) is None or zlib.crc32(text.encode('ascii')) ^ 4294967295 != f[key]:
            raise ValueError('Native diplomacy name does not match its event hash')
    return dict(player_id=player_id, session_id=f['SessionID'], from_player=f['FromPlayer'], to_player=f['ToPlayer'], is_open=parts[4] == '1', statement_type=parts[5], statement_subtype=parts[6], response_type=parts[7] or None)

def require_no_unhandled_statements(prefix):
    pending = getattr(prefix.deferred_events, 'pending_diplomacy_statements', [])
    if not pending:
        return
    statement = pending[0]
    pid = 0
    try:
        raw = prefix.runtime.evaluate_text(prefix.ui_child, source(statement, pid), b'@pending_diplomacy_session', capacity=2048)
        session = parse(raw, statement, pid)
    except BaseException as exc:
        prefix.emit('native_diplomacy_pending_session_read_refused', statement=statement, error=repr(exc), pending_choices_preserved=len(pending), automatic_response=False, eligible_for_training=False)
        raise
    prefix.emit('native_diplomacy_pending_choice_observed', statement=statement, session=session, pending_choices_preserved=len(pending), source_proof_sha256=PROOF_SHA256, automatic_response=False, live_choice_catalogue_proven=False, eligible_for_training=False)
    raise DiplomacyChoicePending(statement, session)
