"""Source adapter for a human seat receiving an alliance proposal (MAKE_DEAL).

SOURCE-ONLY (lot 98d405f3, corrections 2e608d3d/28d7fb8a, review 03a6da9f):
reception_source establishes pair/direction/phase/validity exactly like the
official handler (MakeDeal_ApplyStatement open condition + MakeDeal_TestValid)
and reads the locked alliance items through the v7 helper's non-terminal
inventory_source() (support-owned xp2_alliance_deal_terms.py: reads BOTH
giver directions into allianceRows and provides publicAllianceTerms());
parse_reception splits the session envelope from the inventory field and
validates the terms via the v7 parse. ack_source mirrors the loaded XP2
DiplomacyDealView (0cd3b32a...) answer path with anti-stale authentication
(b4510f27): the session is matched against the authenticated reception
snapshot (sid + event_sequence + initiator, IsSessionIDOpen) BEFORE any
send; with no matching open session nothing is sent. Statement fields are
taken from the HEAD of the live pending-statement ledger (the entry itself,
never free-standing ints — review 0cff04c6), and the envelope carries an
explicit provenance field (native_event|ui_derived, arbitrage 9fea8f08);
the PROPOSED-from-peer gate is asserted only for native_event. The human
subtype check uses the official name compare GetKeyName(subtype)=='NONE'
(ActionView 2548/2759), not the unproven AI-seat wire hash. SendWorkingDeal's
return is not asserted after the mutation (the official UI ignores its
value). Archive item checking is delegated to the spy's
xp2_alliance_archive_source.py.
NOT WIRED: no session/borrowed/candidate, no H2H claim, no GameCore.
"""
from __future__ import annotations

import json

from . import xp2_alliance_human_reception_source as facts


# Statement provenance (arbitrage 9fea8f08): 'native_event' = a real
# NativeDealAction was received; 'ui_derived' = the official OnShow/resume
# path deduced the PROPOSED UI state from open sid + FromPlayer + INCOMING
# copy. Both are legitimate, but the envelope must say which one it is.
PROVENANCES = ('native_event', 'ui_derived')


def _statement_fields(pending_statements):
    """Extract the authenticated fields from the HEAD of the pending ledger.

    pending_statements is the owner's live ledger
    (p.deferred_events.pending_diplomacy_statements); the entry is taken by
    position, so no statement field can arrive as a free-standing int
    (review 0cff04c6: injected-then-asserted integers were tautological).
    Returns DealAction/ResponseType/subtype/Initiator/event_sequence.
    """
    if type(pending_statements) is not list or len(pending_statements) == 0:
        raise ValueError('Pending diplomacy statement ledger is empty')
    entry = pending_statements[0]
    if type(entry) is not dict or type(entry.get('fields')) is not dict:
        raise ValueError('Malformed pending diplomacy statement entry')
    fields = entry['fields']
    def need_int(name):
        value = fields.get(name)
        if type(value) is not int or not 0 <= value < (1 << 32):
            raise ValueError('Missing or invalid statement field: ' + name)
        return value
    sequence = fields.get('event_sequence')
    if type(sequence) is not int or sequence <= 0:
        raise ValueError('Missing or invalid statement event_sequence')
    return {'deal_action': need_int('DealAction'), 'response_type': need_int('ResponseType'),
            'subtype': need_int('subtype'), 'initiator': need_int('Initiator'),
            'event_sequence': sequence}


# Reception: session identity + official open condition + TestValid + the
# locked alliance items via the v7 non-terminal inventory_source() (reads
# both directions, provides publicAllianceTerms()). Statement fields come
# from the HEAD of the live pending-statement ledger, not from free ints.
def reception_source(prefix, pid, target, pending_statements, turn, provenance):
    """Eval establishing pair/sens/phase/provenance/validity + incoming term.

    pending_statements is the live p.deferred_events.pending_diplomacy_
    statements ledger; the head entry supplies DealAction/ResponseType/
    subtype/Initiator/event_sequence. turn is the game turn: with the sid
    and event_sequence they authenticate the snapshot generation (anti-stale
    b4510f27 — a pair sid is reusable after close/reopen, sid calc
    0x188c00). provenance (native_event|ui_derived) is published in the
    envelope; the PROPOSED-from-peer gate (557445ff) is asserted only for
    native_event — a ui_derived PROPOSED comes from the official OnShow
    deduction (arbitrage 9fea8f08) and is recorded, not asserted as native.
    """
    if provenance not in PROVENANCES:
        raise ValueError('Provenance must be native_event or ui_derived')
    if (type(pid) is not int or not 0 <= pid < 64 or type(target) is not int
            or not 0 <= target < 64 or pid == target
            or type(turn) is not int or not 0 <= turn < (1 << 31)):
        raise ValueError('Invalid human reception identity')
    st = _statement_fields(pending_statements)
    from . import xp2_alliance_deal_terms as terms
    return (prefix + b'\nlocal me,other,dealAction,respType,stmtSubtype,sequence,reqTurn,provenance=%d,%d,%d,%d,%d,%d,%d,"%s"\n'
            % (pid, target, st['deal_action'], st['response_type'], st['subtype'],
               st['event_sequence'], turn, provenance.encode('ascii'))
            + b"""
assert(Game.GetLocalPlayer()==me and Game.GetLocalObserver()==me,'Reception crossed its player')
assert(Game.GetCurrentGameTurn()==reqTurn,'Reception snapshot generation differs')
assert(Players[other] and Players[other]:IsMajor() and Players[me]:GetDiplomacy():HasMet(other),
 'Reception requires a met major')
local sessionID=DiplomacyManager.FindOpenSessionID(me,other)
assert(sessionID~=nil and type(sessionID)=='number','Open MAKE_DEAL session missing')
assert(DiplomacyManager.IsSessionIDOpen(sessionID)==true,'Session not open')
-- Only FromPlayer is proven on GetSessionInfo; ResponseType/subtype are read
-- from the received statement (ledger), never from the session info.
local info=DiplomacyManager.GetSessionInfo(sessionID)
assert(type(info)=='table' and info.FromPlayer==other,
 'Session initiator differs from the received proposal sender')
-- Official open condition (ActionView 2548, name compare via GetKeyName as
-- at 2759): subtype must be 'NONE'. The AI-seat wire hash 3069842052 is NOT
-- asserted here - it is unproven for the human statement (review 0cff04c6).
assert(DiplomacyManager.GetKeyName(stmtSubtype)=='NONE',
 'Received statement subtype is not NONE')
assert(type(DiplomacyResponseTypes)=='table','Missing native response enum')
assert(respType==DiplomacyResponseTypes.INITIAL or respType==DiplomacyResponseTypes.ACKNOWLEDGE,
 'Received statement is not an initial/acknowledge proposal')
-- Native provenance (557445ff): a really received offer must be PROPOSED
-- from the peer. For ui_derived the PROPOSED state was deduced by OnShow and
-- is published as provenance, not asserted as a native fact.
if provenance=='native_event' then
 assert(dealAction==DealProposalAction.PROPOSED and DealProposalAction.PROPOSED==4,
  'Received offer is not an authenticated PROPOSED from the peer')
end
-- MakeDeal_TestValid (2611): FromPlayer==other requires a valid non-empty
-- INCOMING working deal.
local deal=DealManager.GetWorkingDeal(DealDirection.INCOMING,me,other)
assert(deal~=nil and deal:GetItemCount()>0 and deal:IsValid()==true,
 'Incoming deal missing, empty or invalid')
"""
            + terms.inventory_source()
            + b"""
return '{"session_id":'..tostring(sessionID)..',"event_sequence":'..tostring(sequence)..
 ',"turn":'..tostring(reqTurn)..',"from":'..tostring(other)..',"to":'..tostring(me)..
 ',"response_type":'..tostring(respType)..',"deal_action":'..tostring(dealAction)..
 ',"subtype":'..tostring(stmtSubtype)..',"provenance":"'..provenance..
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
            or type(envelope['deal_action']) is not int
            or type(envelope['subtype']) is not int
            or envelope['provenance'] not in PROVENANCES
            or type(envelope['inventory']) is not dict):
        raise ValueError('Malformed human reception envelope')
    inventory = terms.parse(json.dumps(envelope['inventory']).encode('ascii'), bilateral=True)
    if not any(row['direction'] == 'incoming' for row in inventory['terms']):
        raise ValueError('Received proposal carries no incoming alliance term')
    return {'session': {key: envelope[key] for key in _ENVELOPE_KEYS - {'inventory'}},
            'inventory': inventory}


# Answer: mirrors the loaded XP2 DiplomacyDealView (0cd3b32a) with anti-stale
# authentication (b4510f27). The session is matched against the authenticated
# reception snapshot (sid + event_sequence + initiator, IsSessionIDOpen)
# BEFORE any send; without a matching open session nothing is sent and the
# readback reports matched=false. Human counterparty guard; pending-deal ->
# CLOSED; initiator==local -> no REJECTED; then CloseSession. SendWorkingDeal's
# return is NOT asserted after the mutation (the official UI ignores its
# value) - the call itself is the record.
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
-- Anti-stale (b4510f27 + review 0cff04c6): the pair sid is reusable after
-- close/reopen, so the open session must match the authenticated reception
-- snapshot (sid + event_sequence) and the CURRENT event_sequence re-read
-- from the live ledger head at call time must equal the reception one.
-- sequence is ledger-sourced, expectedSequence reception-sourced: the
-- comparison is not two caller-supplied ints. All BEFORE any mutation.
local sessionID=DiplomacyManager.FindOpenSessionID(me,other)
if sessionID==nil or sessionID~=expectedSession or sequence~=expectedSequence then
 return '{"matched":false,"session_id":'..tostring(sessionID)..
  ',"event_sequence":'..tostring(sequence)..',"turn":'..tostring(reqTurn)..',"sent":false}'
end
assert(DiplomacyManager.IsSessionIDOpen(sessionID)==true,'Session not open before answer')
-- Only FromPlayer is proven on GetSessionInfo; cross-check it against the
-- initiator carried by the authenticated statement.
local info=DiplomacyManager.GetSessionInfo(sessionID)
assert(type(info)=='table' and info.FromPlayer==initiator,
 'Session initiator differs from the authenticated statement')
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
 assert(DiplomacyManager.CloseSession(sessionID)==true,'Native session close refused')
else
 error('Unsupported alliance answer action')
end
return '{"matched":true,"session_id":'..tostring(sessionID)..',"event_sequence":'..tostring(sequence)..
 ',"turn":'..tostring(reqTurn)..',"from":'..tostring(me)..',"to":'..tostring(other)..
 ',"action":'..tostring(action)..',"provenance":"'..provenance..'","sent":'..tostring(sent)..'}'
"""


def ack_source(prefix, pid, target, action, pending_statements, provenance,
               expected_session_id, expected_sequence, turn):
    """Eval sending the native answer for a received proposal (source-only).

    action in ACCEPTED/REJECTED/CLOSED. expected_session_id/expected_sequence
    come from parse_reception (the authenticated reception snapshot).
    pending_statements is the live native ledger
    (p.deferred_events.pending_diplomacy_statements); its HEAD entry is
    re-read at call time, supplying incoming (DealAction), initiator,
    respType and the CURRENT event_sequence — so the anti-stale
    sequence==expectedSequence check compares a ledger-sourced value against
    the reception-sourced one, never two caller-supplied ints (0cff04c6).
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
    st = _statement_fields(pending_statements)
    return (prefix + b'\nlocal me,other,incoming,initiator,respType,expectedSession,expectedSequence,sequence,reqTurn,provenance=%d,%d,%d,%d,%d,%d,%d,%d,%d,"%s"\n'
            b'local action=DealProposalAction.%s\n'
            % (pid, target, st['deal_action'], st['initiator'], st['response_type'],
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
