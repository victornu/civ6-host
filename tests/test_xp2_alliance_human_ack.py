"""Offline script tests for xp2_alliance_human_ack (human-seat alliance ack).

Runs as a plain script (no pytest required):

    CIV6_HOST_RESOURCE_ROOT='C:\\civ6-current' \
        python tests/test_xp2_alliance_human_ack.py

Prints PASS/FAIL per check and exits non-zero if any check fails.

The native seams are stubbed in sys.modules BEFORE importing the module under
test: xp2_alliance_deal_terms (v7 inventory/parse API), native_turn_continuation
(validate(owner) -> object with .pending), native_pending_diplomacy
(DiplomacyChoicePending(statement, session)) and native_diplomacy_statement
(PROOF_SHA256). The retained entry is re-read from the owner on every call, so
mutating it between calls is reflected in the generated source.
"""

import json
import os
from pathlib import Path
import sys
import types

HOST = Path(__file__).resolve().parents[1]
os.environ.setdefault("CIV6_HOST_RESOURCE_ROOT", r"C:\civ6-current")
sys.path.insert(0, str(HOST / "src"))

# --- Stubbed seams (installed in sys.modules before the module under test) ---

PROOF_SHA256 = 'b78799f583992bcdb78799f583992bcdb78799f583992bcdb78799f583992b13f8'
ALLIANCE_SUBTYPE = 0x6932036b
INVENTORY_MARKER = b'-- XP2-DEAL-TERMS-V7-INVENTORY-MARKER\n'

TERMS_PARSE_CALLS = []

terms_stub = types.ModuleType('civ6_host.runtime.xp2_alliance_deal_terms')


def _inventory_source():
    return INVENTORY_MARKER


def _terms_parse(raw, *, bilateral=False):
    """v7 parse: {'alliance_subtype','terms'}, alliance_subtype pinned, rows
    {direction,type,duration}."""
    TERMS_PARSE_CALLS.append({'raw': raw, 'bilateral': bilateral})
    if type(raw) is not bytes or len(raw) > 8192:
        raise ValueError('Unbounded alliance deal readback')
    value = json.loads(raw)
    if (type(value) is not dict or set(value) != {'alliance_subtype', 'terms'}
            or value['alliance_subtype'] != ALLIANCE_SUBTYPE):
        raise ValueError('Malformed alliance deal readback')
    rows = value['terms']
    expected = ('outgoing', 'incoming') if bilateral else ('outgoing',)
    if (type(rows) is not list
            or any(type(row) is not dict or set(row) != {'direction', 'type', 'duration'}
                   or row['direction'] not in expected for row in rows)):
        raise ValueError('Malformed alliance deal terms')
    return value


terms_stub.inventory_source = _inventory_source
terms_stub.parse = _terms_parse
sys.modules[terms_stub.__name__] = terms_stub

statement_stub = types.ModuleType('civ6_host.runtime.native.native_diplomacy_statement')
statement_stub.PROOF_SHA256 = PROOF_SHA256
sys.modules[statement_stub.__name__] = statement_stub

pending_stub = types.ModuleType('civ6_host.runtime.native.native_pending_diplomacy')


class DiplomacyChoicePending(RuntimeError):
    def __init__(self, statement, session):
        super().__init__('Native diplomacy choice interrupts the turn')
        self.statement = statement
        self.session = session


pending_stub.DiplomacyChoicePending = DiplomacyChoicePending
sys.modules[pending_stub.__name__] = pending_stub

continuation_stub = types.ModuleType('civ6_host.runtime.native.native_turn_continuation')


class _Continuation:
    def __init__(self, pending):
        self.pending = pending


def _validate(owner):
    # Real Retain semantics: the retained entry is read from the owner on
    # EVERY call, never cached.
    return _Continuation(pending_stub.DiplomacyChoicePending(owner.statement, owner.session))


continuation_stub.validate = _validate
sys.modules[continuation_stub.__name__] = continuation_stub

import civ6_host.runtime as _runtime_pkg
_runtime_pkg.xp2_alliance_deal_terms = terms_stub
import civ6_host.runtime.native as _native_pkg
_native_pkg.native_turn_continuation = continuation_stub
_native_pkg.native_pending_diplomacy = pending_stub
_native_pkg.native_diplomacy_statement = statement_stub

from civ6_host.runtime import xp2_alliance_human_ack as ack
from civ6_host.runtime import xp2_alliance_human_reception_source as facts
from civ6_host.runtime.paths import resource_root

# --- Fixtures ---------------------------------------------------------------

PREFIX = b'-- test prefix\n'
TURN = 7
PID = 1
TARGET = 2


def make_statement(**overrides):
    statement = {
        'event_sequence': 42,
        'fields': {'SessionID': 900, 'FromPlayer': 2, 'ToPlayer': 1,
                   'StatementSubType': 999888777, 'ResponseType': 3405713603,
                   'Initiator': 2, 'StatementType': 2229918858},
        'source_proof_sha256': PROOF_SHA256,
        'deal_reply': {'operation': 'accept', 'outcome': 'accepted'},
    }
    statement.update(overrides)
    return statement


def make_session(**overrides):
    session = {'player_id': PID, 'session_id': 900, 'from_player': 2,
               'to_player': 1, 'is_open': True}
    session.update(overrides)
    return session


def make_owner(**statement_overrides):
    return types.SimpleNamespace(statement=make_statement(**statement_overrides),
                                 session=make_session())


def make_envelope_raw(**overrides):
    envelope = {
        'session_id': 900, 'event_sequence': 42, 'turn': TURN, 'from': 2, 'to': 1,
        'response_type': 3405713603, 'deal_action': 4, 'subtype': 999888777,
        'provenance': 'native_event',
        'inventory': {'alliance_subtype': ALLIANCE_SUBTYPE,
                      'terms': [{'direction': 'incoming', 'type': 'ALLIANCE_MILITARY',
                                 'duration': 30}]},
    }
    envelope.update(overrides)
    return json.dumps(envelope).encode('ascii')


def expect_value_error(fn, fragment):
    try:
        fn()
    except ValueError as exc:
        assert fragment in str(exc), 'unexpected ValueError message: ' + str(exc)
        return
    raise AssertionError('expected ValueError containing ' + repr(fragment))


# --- Checks -----------------------------------------------------------------

def check_01_reception_native_event_owner_bytes():
    owner = make_owner()
    src = ack.reception_source(PREFIX, owner, PID, TARGET, TURN, 'native_event')
    assert type(src) is bytes and src.startswith(PREFIX)
    # Owner-bound identity embedded in the header (subtype/response signed32).
    assert b'=1,2,900,2,1,999888777,-889253693,42,7,"native_event",4\n' in src
    # Native session re-read, no fallback lookup.
    assert b'DiplomacyManager.IsSessionIDOpen(sid)' in src
    assert b'FindOpenSessionID' not in src
    # Official open condition: subtype name 'NONE'; the AI-seat wire hash is
    # never asserted as an equality.
    assert b"DiplomacyManager.GetKeyName(stmtSubtype)=='NONE'" in src
    assert b'==3069842052' not in src
    # PROPOSED gate only under native_event.
    assert b"if provenance=='native_event' then" in src
    assert b'dealAction==DealProposalAction.PROPOSED and DealProposalAction.PROPOSED==4' in src
    # MakeDeal_TestValid: non-empty valid INCOMING working deal.
    assert b'DealManager.GetWorkingDeal(DealDirection.INCOMING,me,other)' in src
    assert b'deal:GetItemCount()>0 and deal:IsValid()==true' in src
    # Locked items routed through the v7 inventory_source().
    assert INVENTORY_MARKER in src
    # Envelope carries provenance and subtype.
    assert b'"provenance":"' in src and b'"subtype":' in src
    assert b'"session_id":' in src and b'"inventory":' in src
    assert b'publicAllianceTerms()' in src


def check_02_deal_reply_gate():
    owner = make_owner()
    del owner.statement['deal_reply']
    expect_value_error(
        lambda: ack.reception_source(PREFIX, owner, PID, TARGET, TURN, 'native_event'),
        'deal_reply')
    src = ack.reception_source(PREFIX, owner, PID, TARGET, TURN, 'ui_derived')
    assert type(src) is bytes and b',"ui_derived",4\n' in src
    # ack_source applies the same gate.
    expect_value_error(
        lambda: ack.ack_source(PREFIX, owner, PID, TARGET, 'ACCEPTED', 'native_event', 900, 42, TURN),
        'deal_reply')


def check_03_reception_rejects_bad_proof_session_pair():
    expect_value_error(
        lambda: ack.reception_source(PREFIX, make_owner(source_proof_sha256='0' * 64),
                                     PID, TARGET, TURN, 'native_event'),
        'pinned native receiver')
    bad_sid = make_owner()
    bad_sid.session = make_session(session_id=901)
    expect_value_error(
        lambda: ack.reception_source(PREFIX, bad_sid, PID, TARGET, TURN, 'native_event'),
        'does not match the reception pair')
    bad_player = make_owner()
    bad_player.session = make_session(player_id=5)
    expect_value_error(
        lambda: ack.reception_source(PREFIX, bad_player, PID, TARGET, TURN, 'native_event'),
        'does not match the reception pair')
    expect_value_error(
        lambda: ack.reception_source(PREFIX, make_owner(), PID, 3, TURN, 'native_event'),
        'does not match the reception pair')
    expect_value_error(
        lambda: ack.reception_source(PREFIX, make_owner(), PID, TARGET, TURN, 'bogus'),
        'Provenance')


def check_04_parse_reception_envelope_and_terms_routing():
    raw = make_envelope_raw()
    del TERMS_PARSE_CALLS[:]
    result = ack.parse_reception(raw)
    assert set(result) == {'session', 'inventory'}
    session = result['session']
    assert set(session) == {'session_id', 'event_sequence', 'turn', 'from', 'to',
                            'response_type', 'deal_action', 'subtype', 'provenance'}
    assert (session['session_id'], session['event_sequence'], session['turn'],
            session['from'], session['to'], session['provenance']) == (900, 42, TURN, 2, 1, 'native_event')
    assert session['response_type'] == 3405713603 and 0 <= session['response_type'] < (1 << 32)
    assert session['subtype'] == 999888777 and 0 <= session['subtype'] < (1 << 32)
    assert session['deal_action'] == 4
    # The inventory field was routed through the v7 terms.parse (bilateral).
    assert len(TERMS_PARSE_CALLS) == 1
    call = TERMS_PARSE_CALLS[0]
    assert call['bilateral'] is True
    assert json.loads(call['raw']) == json.loads(raw)['inventory']
    assert result['inventory']['alliance_subtype'] == ALLIANCE_SUBTYPE
    assert result['inventory']['terms'] == [{'direction': 'incoming', 'type': 'ALLIANCE_MILITARY', 'duration': 30}]
    # Negative envelopes.
    missing = json.loads(raw)
    del missing['turn']
    expect_value_error(lambda: ack.parse_reception(json.dumps(missing).encode('ascii')), 'Malformed')
    extra = json.loads(raw)
    extra['bogus'] = 1
    expect_value_error(lambda: ack.parse_reception(json.dumps(extra).encode('ascii')), 'Malformed')
    expect_value_error(lambda: ack.parse_reception(make_envelope_raw(provenance='bogus')), 'Malformed')
    expect_value_error(lambda: ack.parse_reception(make_envelope_raw(response_type=1 << 32)), 'Malformed')
    expect_value_error(lambda: ack.parse_reception(make_envelope_raw(subtype=-1)), 'Malformed')
    outgoing_only = json.loads(raw)
    outgoing_only['inventory']['terms'] = [{'direction': 'outgoing', 'type': 'ALLIANCE_MILITARY', 'duration': 30}]
    expect_value_error(lambda: ack.parse_reception(json.dumps(outgoing_only).encode('ascii')),
                       'no incoming alliance term')
    bad_subtype = json.loads(raw)
    bad_subtype['inventory']['alliance_subtype'] = 0xdeadbeef
    expect_value_error(lambda: ack.parse_reception(json.dumps(bad_subtype).encode('ascii')), 'Malformed')


def check_05_ack_anti_stale_and_send_semantics():
    owner = make_owner()
    src = ack.ack_source(PREFIX, owner, PID, TARGET, 'ACCEPTED', 'native_event', 900, 42, TURN)
    assert type(src) is bytes and src.startswith(PREFIX)
    assert b'=1,2,900,2,1,4,2,-889253693,900,42,42,7,"native_event"\n' in src
    assert b'local action=DealProposalAction.ACCEPTED\n' in src
    # Anti-stale match block: sid/seq mismatch -> matched=false, nothing sent.
    assert b'if sid~=expectedSession or sequence~=expectedSequence then' in src
    assert b'{"matched":false' in src and b'"sent":false}' in src
    # The open-session read happens BEFORE the match and BEFORE any send.
    assert src.index(b'DiplomacyManager.IsSessionIDOpen(sid)') < src.index(b'sid~=expectedSession')
    assert src.index(b'DiplomacyManager.IsSessionIDOpen(sid)') < src.index(b'DealManager.SendWorkingDeal(')
    # Initiator must be the session speaker.
    assert b'assert(fromP==initiator,' in src
    # SendWorkingDeal is called bare: no assert on its return, no captured r.
    assert b'assert(DealManager.SendWorkingDeal' not in src
    assert b'assert(type(r)' not in src
    assert b'local r=DealManager.SendWorkingDeal' not in src
    assert src.count(b'DealManager.SendWorkingDeal(') == 4
    assert b'sent=true' in src
    # Pending-deal -> CLOSED path then CloseSession.
    assert b'assert(DiplomacyManager.CloseSession(sid)==true,' in src
    # sid mismatch is representable: expected sid differs from the retained sid.
    bad_sid = ack.ack_source(PREFIX, owner, PID, TARGET, 'ACCEPTED', 'native_event', 901, 42, TURN)
    assert b',901,42,42,7,"native_event"\n' in bad_sid
    # sequence mismatch likewise.
    bad_seq = ack.ack_source(PREFIX, owner, PID, TARGET, 'ACCEPTED', 'native_event', 900, 43, TURN)
    assert b',900,43,42,7,"native_event"\n' in bad_seq
    # The retained entry is re-read at call time: mutating event_sequence is
    # reflected in the next generated source.
    owner.statement['event_sequence'] = 43
    try:
        reread = ack.ack_source(PREFIX, owner, PID, TARGET, 'ACCEPTED', 'native_event', 900, 42, TURN)
        assert b',42,43,7,"native_event"\n' in reread
        assert b',42,42,7,"native_event"\n' not in reread
    finally:
        owner.statement['event_sequence'] = 42


def check_06_source_dependencies_pins_drop_and_evidence():
    pins = ack.source_dependencies()
    assert type(pins) is dict and len(pins) == 14
    root = resource_root()
    drop = root / facts.UI_DROP_REL
    drop_keys = [k for k in pins if 'alliances-ui-drop' in k]
    evidence_keys = [k for k in pins if 'evidence' in k]
    assert len(drop_keys) == 12 and len(evidence_keys) == 2
    # MANIFEST pinned with the embedded manifest digest.
    manifest_key = str((drop / 'MANIFEST.json').resolve())
    assert pins[manifest_key] == facts.UI_MANIFEST_SHA256
    # 11 drop scripts pinned exactly as the on-disk MANIFEST rows say.
    rows = json.loads((drop / 'MANIFEST.json').read_bytes())['files']
    assert len(rows) == 11
    for row in rows:
        key = str((drop / row['path']).resolve())
        assert pins[key] == row['sha256'], row['path']
    # 2 evidence pins carry the retained source digests.
    by_name = {Path(k).name: v for k, v in ((k, pins[k]) for k in evidence_keys)}
    assert by_name[Path(facts.STATEMENT_SOURCE[0]).name] == facts.STATEMENT_SOURCE[1]
    assert by_name[Path(facts.DRAFT_SOURCE[0]).name] == facts.DRAFT_SOURCE[1]


CHECKS = [
    ('01 reception native_event owner bytes', check_01_reception_native_event_owner_bytes),
    ('02 deal_reply gate (native_event vs ui_derived)', check_02_deal_reply_gate),
    ('03 reception rejects bad proof/session/pair', check_03_reception_rejects_bad_proof_session_pair),
    ('04 parse_reception envelope + terms routing', check_04_parse_reception_envelope_and_terms_routing),
    ('05 ack anti-stale + send semantics + re-read', check_05_ack_anti_stale_and_send_semantics),
    ('06 source_dependencies pins drop + evidence', check_06_source_dependencies_pins_drop_and_evidence),
]


def main():
    failures = 0
    for name, fn in CHECKS:
        try:
            fn()
        except BaseException as exc:
            failures += 1
            print('FAIL %s: %r' % (name, exc))
        else:
            print('PASS %s' % name)
    total = len(CHECKS)
    print('%d/%d checks passed' % (total - failures, total))
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
