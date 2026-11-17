"""Source adapter for a human seat receiving an alliance proposal (MAKE_DEAL).

SOURCE-ONLY (lot 98d405f3, corrections 2e608d3d/28d7fb8a, reviews
03a6da9f/0cff04c6/f14c995f): reception_source establishes pair/direction/
phase/validity exactly like the official handler (MakeDeal_ApplyStatement
open condition + MakeDeal_TestValid) and reads the locked alliance items
through the v7 helper's non-terminal inventory_source() (support-owned
xp2_alliance_deal_terms.py: reads BOTH giver directions into allianceRows
and provides publicAllianceTerms()); parse_reception splits the session
envelope from the inventory field and validates the terms via the v7 parse.

OWNER-BOUND (0bd09fe3/f14c995f): both evals take the backend owner and use
the REAL Join/Retain — native_turn_continuation.validate(owner) returns the
retained TurnContinuation whose pending DiplomacyChoicePending carries
.statement (ledger entry: event_sequence TOP-LEVEL, named fields dict,
source_proof_sha256) and .session (native join from
native_pending_diplomacy.source/parse). No free ledger list, no positional
head assumption, no free-standing ints: sid/participants/subtype/response/
initiator/event_sequence all come from that retained entry and are re-read
natively in Lua (IsSessionIDOpen(sid), GetSessionInfo participants,
GetKeyName(subtype)=='NONE' per ActionView 2548/2759 — the AI-seat wire hash
is not asserted). DealAction is never stored in the entry fields and the
receiver-wide source_proof_sha256 attests nothing per-statement (c86e3c9d):
native_event with a deal_action is published only when the retained entry
carries a per-statement deal projection (deal_reply); otherwise only
ui_derived is publishable (arbitrage 9fea8f08: OnShow-deduced PROPOSED,
recorded as provenance, never as a native fact).

ack_source mirrors the loaded XP2 DiplomacyDealView (0cd3b32a...) answer
path with anti-stale authentication (b4510f27): the retained sid +
event_sequence are matched against the authenticated reception snapshot
BEFORE any send; without a match nothing is sent (matched=false).
SendWorkingDeal's return is not asserted after the mutation (the official
UI ignores its value). Archive item checking is delegated to the spy's
xp2_alliance_archive_source.py.
NOT WIRED: no session/borrowed/candidate, no H2H claim, no GameCore.
"""
from __future__ import annotations

import json

from . import xp2_alliance_human_reception_source as facts


# Statement provenance (arbitrage 9fea8f08): 'native_event' = a real
# NativeDealAction was received (attested by the pinned source proof);
# 'ui_derived' = the official OnShow/resume path deduced the PROPOSED UI
# state from open sid + FromPlayer + INCOMING copy. Both are legitimate,
# but the envelope must say which one it is.
PROVENANCES = ('native_event', 'ui_derived')


def _owner_statement(owner, pid, target):
    """Retained owner context -> (statement, identity) via the real Retain.

    native_turn_continuation.validate(owner) returns the retained
    TurnContinuation; its pending DiplomacyChoicePending carries .statement
    (ledger entry: event_sequence TOP-LEVEL, fields = named dict with
    SessionID/FromPlayer/ToPlayer/StatementSubType/ResponseType/Initiator,
    source_proof_sha256) and .session (native join: session_id/from_player/
    to_player/is_open/...). The retained session must match the entry and
    the requested pair. Returns (statement, identity dict).
    """
    from .native.native_turn_continuation import validate as validate_continuation
    from .native.native_pending_diplomacy import DiplomacyChoicePending
    c = validate_continuation(owner)
    pending = c.pending
    if type(pending) is not DiplomacyChoicePending:
        raise ValueError('Retained continuation carries no diplomacy choice')
    statement = pending.statement
    session = pending.session
    if type(statement) is not dict or type(statement.get('fields')) is not dict:
        raise ValueError('Malformed retained statement entry')
    from .native.native_diplomacy_statement import PROOF_SHA256
    if statement.get('source_proof_sha256') != PROOF_SHA256:
        raise ValueError('Retained statement was not produced by the pinned native receiver')
    f = statement['fields']
    def need(name):
        value = f.get(name)
        if type(value) is not int or not 0 <= value < (1 << 32):
            raise ValueError('Missing or invalid statement field: ' + name)
        return value
    identity = {'session_id': need('SessionID'), 'from_player': need('FromPlayer'),
                'to_player': need('ToPlayer'), 'subtype': need('StatementSubType'),
                'response_type': need('ResponseType'), 'initiator': need('Initiator')}
    sequence = statement.get('event_sequence')
    if type(sequence) is not int or sequence <= 0:
        raise ValueError('Missing or invalid statement event_sequence')
    identity['event_sequence'] = sequence
    if (type(session) is not dict or session.get('player_id') != pid
            or session.get('session_id') != identity['session_id']
            or session.get('from_player') != identity['from_player']
            or session.get('to_player') != identity['to_player']
            or session.get('is_open') is not True
            or identity['from_player'] != target or identity['to_player'] != pid):
        raise ValueError('Retained statement/session does not match the reception pair')
    return statement, identity


def _deal_action(statement, provenance):
    """Received-offer action for the envelope.

    DealAction is never stored in the entry fields and source_proof_sha256 is
    only the receiver-wide constant (c86e3c9d): neither attests THIS
    statement's action. native_event is therefore publishable only when the
    entry carries a per-statement deal projection (deal_reply, set by
    a0_diplomacy_statement.consume when project_statement_fields ran on this
    statement); otherwise the caller must use ui_derived, where the PROPOSED
    state was deduced by the official OnShow path (9fea8f08).
    """
    if provenance == 'native_event' and type(statement.get('deal_reply')) is not dict:
        raise ValueError('native_event requires a per-statement deal projection (deal_reply); otherwise use ui_derived')
    return facts.PROPOSAL_DEAL_ACTION


def _signed32(value):
    return value if value < (1 << 31) else value - (1 << 32)


# Reception: owner-bound retained statement + native session re-read +
# official open condition + TestValid + locked items via v7 inventory_source().
def reception_source(prefix, owner, pid, target, turn, provenance):
    """Eval establishing pair/sens/phase/provenance/validity + incoming term.

    owner is the backend owner; validate(owner) yields the retained
    TurnContinuation whose pending statement supplies sid/participants/
    subtype/response/initiator/event_sequence. turn is the game turn: with
    the sid and event_sequence they authenticate the snapshot generation
    (anti-stale b4510f27 - a pair sid is reusable after close/reopen, sid
    calc 0x188c00).
    """
    if provenance not in PROVENANCES:
        raise ValueError('Provenance must be native_event or ui_derived')
    if (type(pid) is not int or not 0 <= pid < 64 or type(target) is not int
            or not 0 <= target < 64 or pid == target
            or type(turn) is not int or not 0 <= turn < (1 << 31)):
        raise ValueError('Invalid human reception identity')
    statement, st = _owner_statement(owner, pid, target)
    deal_action = _deal_action(statement, provenance)
    from . import xp2_alliance_deal_terms as terms
    return (prefix + b'\nlocal me,other,sid,fromP,toP,stmtSubtype,respType,sequence,reqTurn,provenance,dealAction=%d,%d,%d,%d,%d,%d,%d,%d,%d,"%s",%d\n'
            % (pid, target, st['session_id'], st['from_player'], st['to_player'],
               _signed32(st['subtype']), _signed32(st['response_type']),
               st['event_sequence'], turn, provenance.encode('ascii'), deal_action)
            + b"""
assert(Game.GetLocalPlayer()==me and Game.GetLocalObserver()==me,'Reception crossed its player')
assert(Game.GetCurrentGameTurn()==reqTurn,'Reception snapshot generation differs')
assert(Players[other] and Players[other]:IsMajor() and Players[me]:GetDiplomacy():HasMet(other),
 'Reception requires a met major')
-- sid/participants come from the RETAINED statement entry (owner-bound) and
-- are re-read natively: the open session must be exactly that sid with that
-- speaker/recipient pair (same join as native_pending_diplomacy.source).
assert(DiplomacyManager.IsSessionIDOpen(sid)==true,'Retained statement session is not open')
local info=DiplomacyManager.GetSessionInfo(sid)
assert(type(info)=='table' and ((info.FromPlayer==fromP and info.ToPlayer==toP) or
 (info.FromPlayer==toP and info.ToPlayer==fromP)),'Session participants differ from the statement')
assert(fromP==other and toP==me,'Received proposal is not addressed to the local player')
-- Official open condition (ActionView 2548, name compare via GetKeyName at
-- 2759): subtype must be 'NONE'. The AI-seat wire hash 3069842052 is NOT
-- asserted here - unproven for the human statement (0cff04c6/f14c995f).
assert(DiplomacyManager.GetKeyName(stmtSubtype)=='NONE',
 'Received statement subtype is not NONE')
assert(type(DiplomacyResponseTypes)=='table','Missing native response enum')
assert(respType==DiplomacyResponseTypes.INITIAL or respType==DiplomacyResponseTypes.ACKNOWLEDGE,
 'Received statement is not an initial/acknowledge proposal')
-- native_event: DealAction==PROPOSED was validated at consume time against
-- the pinned proof (source_proof_sha256, checked Python-side). ui_derived
-- (9fea8f08): PROPOSED deduced by OnShow, published as provenance only.
if provenance=='native_event' then
 assert(dealAction==DealProposalAction.PROPOSED and DealProposalAction.PROPOSED==4,
  'Received offer is not an authenticated PROPOSED from the peer')
end
-- MakeDeal_TestValid (2611): a valid non-empty INCOMING working deal.
local deal=DealManager.GetWorkingDeal(DealDirection.INCOMING,me,other)
assert(deal~=nil and deal:GetItemCount()>0 and deal:IsValid()==true,
 'Incoming deal missing, empty or invalid')
local function u32(v) if v<0 then return v+4294967296 end return v end
"""
            + terms.inventory_source()
            + b"""
return '{"session_id":'..string.format('%.0f',sid)..',"event_sequence":'..tostring(sequence)..
 ',"turn":'..tostring(reqTurn)..',"from":'..tostring(fromP)..',"to":'..tostring(toP)..
 ',"response_type":'..string.format('%.0f',u32(respType))..',"deal_action":'..tostring(dealAction)..
 ',"subtype":'..string.format('%.0f',u32(stmtSubtype))..',"provenance":"'..provenance..
 '","inventory":'..publicAllianceTerms()..'}'
""")


_ENVELOPE_KEYS = {'session_id', 'event_sequence', 'turn', 'from', 'to',
                  'response_type', 'deal_action', 'subtype', 'provenance', 'inventory'}


def parse_reception(raw):
    """Split the session envelope from the inventory field and validate both.

    The envelope is checked here (provenance included); the inventory field
    goes through the v7 terms.parse (bilateral), which enforces
    {'alliance_subtype','terms'} with alliance_subtype==ALLIANCE and
    signed32 durations.
    """
    from . import xp2_alliance_deal_terms as terms
    if type(raw) is not bytes or len(raw) > 8192:
        raise ValueError('Invalid human reception readback')
    envelope = json.loads(raw)
    if (type(envelope) is not dict or set(envelope) != _ENVELOPE_KEYS
            or type(envelope['session_id']) is not int
            or type(envelope['event_sequence']) is not int or envelope['event_sequence'] <= 0
            or type(envelope['turn']) is not int or not 0 <= envelope['turn'] < (1 << 31)
            or type(envelope['from']) is not int or type(envelope['to']) is not int
            or envelope['from'] == envelope['to']
            or type(envelope['response_type']) is not int
            or not 0 <= envelope['response_type'] < (1 << 32)
            or type(envelope['deal_action']) is not int
            or type(envelope['subtype']) is not int
            or not 0 <= envelope['subtype'] < (1 << 32)
            or envelope['provenance'] not in PROVENANCES
            or type(envelope['inventory']) is not dict):
        raise ValueError('Malformed human reception envelope')
    inventory = terms.parse(json.dumps(envelope['inventory']).encode('ascii'), bilateral=True)
    if not any(row['direction'] == 'incoming' for row in inventory['terms']):
        raise ValueError('Received proposal carries no incoming alliance term')
    return {'session': {key: envelope[key] for key in _ENVELOPE_KEYS - {'inventory'}},
            'inventory': inventory}


# Answer: mirrors the loaded XP2 DiplomacyDealView (0cd3b32a) with anti-stale
# authentication (b4510f27). The retained statement sid + event_sequence are
# matched against the authenticated reception snapshot BEFORE any send; on
# mismatch nothing is sent and the readback reports matched=false. Human
# counterparty guard; pending-deal -> CLOSED; initiator==local -> no
# REJECTED; then CloseSession. SendWorkingDeal's return is NOT asserted
# after the mutation (the official UI ignores its value) - the call itself
# is the record.
_ACK = b"""
assert(DealProposalAction.ACCEPTED==1 and DealProposalAction.REJECTED==2 and
 DealProposalAction.ADJUSTED==3 and DealProposalAction.PROPOSED==4,
 'Native deal action enum changed')
assert(DealProposalAction.CLOSED==8 and DealProposalAction.REJECTED_PERMANENT==12,
 'Native CLOSED/REJECTED_PERMANENT enum changed (support source e29ed1c3)')
assert(respType==DiplomacyResponseTypes.INITIAL or respType==DiplomacyResponseTypes.ACKNOWLEDGE,
 'Answered statement is not an initial/acknowledge proposal')
assert(Game.GetCurrentGameTurn()==reqTurn,'Answer snapshot generation differs')
assert(Players[other]:IsHuman()==true,'Human answer path requires a human counterparty')
-- Anti-stale (b4510f27 + f14c995f): sid and sequence come from the RETAINED
-- owner statement (re-validated at call time via validate(owner)), matched
-- against the reception snapshot; the sid must be natively open with the
-- statement participants. All BEFORE any mutation.
assert(DiplomacyManager.IsSessionIDOpen(sid)==true,'Retained statement session is not open')
if sid~=expectedSession or sequence~=expectedSequence then
 return '{"matched":false,"session_id":'..string.format('%.0f',sid)..
  ',"event_sequence":'..tostring(sequence)..',"turn":'..tostring(reqTurn)..',"sent":false}'
end
local info=DiplomacyManager.GetSessionInfo(sid)
assert(type(info)=='table' and ((info.FromPlayer==fromP and info.ToPlayer==toP) or
 (info.FromPlayer==toP and info.ToPlayer==fromP)),'Session participants differ from the statement')
assert(fromP==initiator,'Statement initiator differs from the session speaker')
local sent=false
if action==DealProposalAction.ACCEPTED then
 -- Official accept only for incoming ACCEPTED/PROPOSED/ADJUSTED with equal deals.
 assert(incoming==DealProposalAction.ACCEPTED or incoming==DealProposalAction.PROPOSED
  or incoming==DealProposalAction.ADJUSTED,'Accept outside the official incoming actions')
 -- Alliance ack never carries war agreements.
 local outgoing=DealManager.GetWorkingDeal(DealDirection.OUTGOING,me,other)
 assert(outgoing==nil or (outgoing:FindItemByType(DealItemTypes.AGREEMENTS,DealAgreementTypes.JOINT_WAR)==nil
  and outgoing:FindItemByType(DealItemTypes.AGREEMENTS,DealAgreementTypes.THIRD_PARTY_WAR)==nil),
  'War agreement present in an alliance answer')
 if DealManager.AreWorkingDealsEqual(me,other)==true then
  -- The official UI ignores SendWorkingDeal's return: call it and record the
  -- send, never assert the post-mutation value.
  DealManager.SendWorkingDeal(action,me,other); sent=true
 else
  DealManager.SendWorkingDeal(DealProposalAction.ADJUSTED,me,other); sent=true
 end
elseif action==DealProposalAction.REJECTED or action==DealProposalAction.CLOSED then
 local pending=DealManager.HasPendingDeal(me,other)
 if action==DealProposalAction.CLOSED or pending then
  DealManager.SendWorkingDeal(DealProposalAction.CLOSED,me,other); sent=true
 elseif initiator~=me then
  DealManager.SendWorkingDeal(DealProposalAction.REJECTED,me,other); sent=true
 end
 assert(DiplomacyManager.CloseSession(sid)==true,'Native session close refused')
else
 error('Unsupported alliance answer action')
end
return '{"matched":true,"session_id":'..string.format('%.0f',sid)..',"event_sequence":'..tostring(sequence)..
 ',"turn":'..tostring(reqTurn)..',"from":'..tostring(me)..',"to":'..tostring(other)..
 ',"action":'..tostring(action)..',"provenance":"'..provenance..'","sent":'..tostring(sent)..'}'
"""


def ack_source(prefix, owner, pid, target, action, provenance,
               expected_session_id, expected_sequence, turn):
    """Eval sending the native answer for a received proposal (source-only).

    action in ACCEPTED/REJECTED/CLOSED. owner is re-validated at call time
    (real Retain) supplying sid/participants/initiator/respType and the
    CURRENT event_sequence; expected_session_id/expected_sequence come from
    parse_reception (the authenticated reception snapshot). The match
    sid==expectedSession + sequence==expectedSequence therefore compares an
    owner-bound value against the reception record, never two free ints.
    """
    if action not in ('ACCEPTED', 'REJECTED', 'CLOSED'):
        raise ValueError('Alliance answers are ACCEPTED/REJECTED/CLOSED')
    if provenance not in PROVENANCES:
        raise ValueError('Provenance must be native_event or ui_derived')
    if (type(pid) is not int or not 0 <= pid < 64 or type(target) is not int
            or not 0 <= target < 64 or pid == target
            or type(expected_session_id) is not int
            or type(expected_sequence) is not int or expected_sequence <= 0
            or type(turn) is not int or not 0 <= turn < (1 << 31)):
        raise ValueError('Invalid human ack identity')
    statement, st = _owner_statement(owner, pid, target)
    incoming = _deal_action(statement, provenance)
    return (prefix + b'\nlocal me,other,sid,fromP,toP,incoming,initiator,respType,expectedSession,expectedSequence,sequence,reqTurn,provenance=%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,"%s"\n'
            b'local action=DealProposalAction.%s\n'
            % (pid, target, st['session_id'], st['from_player'], st['to_player'],
               incoming, st['initiator'], _signed32(st['response_type']),
               expected_session_id, expected_sequence, st['event_sequence'], turn,
               provenance.encode('ascii'), action.encode('ascii')) + _ACK)


def source_dependencies(*, execution_image=None, stock=False):
    """Full closure: evidence pins + 11 UI drop scripts + overview profile chain.

    Uses the existing verification mechanisms: the diplomacy overview source
    closure (stock/BBG profiles, official files) plus byte-exact verification
    of the private UI drop against its embedded MANIFEST.
    """
    import hashlib
    from pathlib import Path
    from .paths import resource_root
    pins = {}
    for path, digest in (facts.STATEMENT_SOURCE, facts.DRAFT_SOURCE):
        pins[str((resource_root() / path).resolve())] = digest
    if execution_image is not None:
        from . import xp2_diplomacy_overview_source as ui
        for path, digest in ui.source_dependencies(execution_image=execution_image, stock=stock).items():
            if path in pins and pins[path] != digest:
                raise ValueError('Reception source closure has conflicting pins')
            pins[path] = digest
    # The private UI drop lives under the configured resource root (no
    # machine-specific absolute path); the MANIFEST itself is pinned too.
    drop = resource_root() / facts.UI_DROP_REL
    manifest_path = drop / 'MANIFEST.json'
    raw = manifest_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != facts.UI_MANIFEST_SHA256:
        raise ValueError('Private UI drop manifest changed')
    pins[str(manifest_path.resolve())] = facts.UI_MANIFEST_SHA256
    for row in json.loads(raw)['files']:
        data = (drop / row['path']).read_bytes()
        if len(data) != row['bytes'] or hashlib.sha256(data).hexdigest() != row['sha256']:
            raise ValueError('Private UI drop script changed: ' + row['path'])
        pins[str((drop / row['path']).resolve())] = row['sha256']
    return pins
