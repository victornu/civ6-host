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
send; with no matching open session nothing is sent. All statement-sourced
parameters (deal_action/response_type/subtype/incoming/initiator/sequence/
turn) are REQUIRED and come from the native pending-statement ledger — no
defaults, so no check can be tautological. SendWorkingDeal's return is not
asserted after the mutation (the official UI ignores its value). Archive
item checking is delegated to the spy's xp2_alliance_archive_source.py.
NOT WIRED: no session/borrowed/candidate, no H2H claim, no GameCore.
"""
from __future__ import annotations

import json

from . import xp2_alliance_human_reception_source as facts


# Reception: session identity + official open condition + PROPOSED-from-peer
# provenance + TestValid + the locked alliance items via the v7 non-terminal
# inventory_source() (reads both directions, provides publicAllianceTerms()).
def reception_source(prefix, pid, target, deal_action, response_type, subtype, sequence, turn):
    """Eval establishing pair/sens/phase/provenance/validity + incoming term.

    Every statement-sourced parameter is REQUIRED and must come from the
    native pending-statement ledger
    (p.deferred_events.pending_diplomacy_statements[0]['fields']: DealAction,
    ResponseType, subtype, event_sequence) plus the game turn; nothing is
    defaulted here, so no check can be tautological. deal_action is the
    received statement's DealAction; a received offer must be PROPOSED (4)
    from the peer (native source 557445ff). sequence/turn are the statement's
    event_sequence and game turn: with the sid they authenticate the snapshot
    generation (anti-stale b4510f27 — a pair sid is reusable after
    close/reopen, sid calc 0x188c00).
    """
    if (type(pid) is not int or not 0 <= pid < 64 or type(target) is not int
            or not 0 <= target < 64 or pid == target
            or type(deal_action) is not int or not 0 <= deal_action < (1 << 32)
            or type(response_type) is not int or not 0 <= response_type < (1 << 32)
            or type(subtype) is not int or not 0 <= subtype < (1 << 32)
            or type(sequence) is not int or sequence <= 0
            or type(turn) is not int or not 0 <= turn < (1 << 31)):
        raise ValueError('Invalid human reception identity')
    from . import xp2_alliance_deal_terms as terms
    return (prefix + b'\nlocal me,other,dealAction,respType,stmtSubtype,sequence,reqTurn=%d,%d,%d,%d,%d,%d,%d\n'
            % (pid, target, deal_action, response_type, subtype, sequence, turn)
            + b"""
assert(Game.GetLocalPlayer()==me and Game.GetLocalObserver()==me,'Reception crossed its player')
assert(Game.GetCurrentGameTurn()==reqTurn,'Reception snapshot generation differs')
assert(Players[other] and Players[other]:IsMajor() and Players[me]:GetDiplomacy():HasMet(other),
 'Reception requires a met major')
local sessionID=DiplomacyManager.FindOpenSessionID(me,other)
assert(sessionID~=nil and type(sessionID)=='number','Open MAKE_DEAL session missing')
assert(DiplomacyManager.IsSessionIDOpen(sessionID)==true,'Session not open')
-- Only FromPlayer is proven on GetSessionInfo; ResponseType/subtype are read
-- from the received statement (ledger params), never from the session info.
local info=DiplomacyManager.GetSessionInfo(sessionID)
assert(type(info)=='table' and info.FromPlayer==other,
 'Session initiator differs from the received proposal sender')
assert(stmtSubtype==%d,'Received statement subtype differs from the pinned MAKE_DEAL wire')
-- Official open condition (ActionView 2548): subtype NONE with response
-- INITIAL or ACKNOWLEDGE opens the deal UI on the INCOMING working deal.
assert(type(DiplomacyResponseTypes)=='table','Missing native response enum')
assert(respType==DiplomacyResponseTypes.INITIAL or respType==DiplomacyResponseTypes.ACKNOWLEDGE,
 'Received statement is not an initial/acknowledge proposal')
-- Native provenance (557445ff): the offer must be PROPOSED from the peer.
assert(dealAction==DealProposalAction.PROPOSED and DealProposalAction.PROPOSED==4,
 'Received offer is not an authenticated PROPOSED from the peer')
-- MakeDeal_TestValid (2611): FromPlayer==other requires a valid non-empty
-- INCOMING working deal.
local deal=DealManager.GetWorkingDeal(DealDirection.INCOMING,me,other)
assert(deal~=nil and deal:GetItemCount()>0 and deal:IsValid()==true,
 'Incoming deal missing, empty or invalid')
""" % facts.SUBTYPE
            + terms.inventory_source()
            + b"""
return '{"session_id":'..tostring(sessionID)..',"event_sequence":'..tostring(sequence)..
 ',"turn":'..tostring(reqTurn)..',"from":'..tostring(other)..',"to":'..tostring(me)..
 ',"response_type":'..tostring(respType)..',"deal_action":'..tostring(dealAction)..
 ',"inventory":'..publicAllianceTerms()..'}'
""")


_ENVELOPE_KEYS = {'session_id', 'event_sequence', 'turn', 'from', 'to',
                  'response_type', 'deal_action', 'inventory'}


def parse_reception(raw):
    """Split the session envelope from the inventory field and validate both.

    The envelope is checked here; the inventory field goes through the v7
    terms.parse (bilateral), which enforces {'alliance_subtype','terms'} with
    alliance_subtype==ALLIANCE and signed32 durations.
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
-- Anti-stale (b4510f27): the pair sid is reusable after close/reopen, so the
-- open session must match the authenticated reception snapshot (sid +
-- event_sequence) and the live statement sequence must equal it - all
-- verified BEFORE any mutation.
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
 ',"action":'..tostring(action)..',"sent":'..tostring(sent)..'}'
"""


def ack_source(prefix, pid, target, action, incoming, initiator, response_type,
               expected_session_id, expected_sequence, sequence, turn):
    """Eval sending the native answer for a received proposal (source-only).

    action in ACCEPTED/REJECTED/CLOSED. expected_session_id/expected_sequence
    come from parse_reception (the authenticated reception snapshot);
    incoming/initiator/response_type/sequence/turn come from the live native
    pending-statement ledger. All parameters are REQUIRED — nothing defaults,
    so the sid+sequence+initiator match before any send cannot be tautological.
    """
    if action not in ('ACCEPTED', 'REJECTED', 'CLOSED'):
        raise ValueError('Alliance answers are ACCEPTED/REJECTED/CLOSED')
    if (type(pid) is not int or not 0 <= pid < 64 or type(target) is not int
            or not 0 <= target < 64 or pid == target
            or type(incoming) is not int or not 0 <= incoming < (1 << 32)
            or type(initiator) is not int or not 0 <= initiator < 64
            or type(response_type) is not int or not 0 <= response_type < (1 << 32)
            or type(expected_session_id) is not int
            or type(expected_sequence) is not int or expected_sequence <= 0
            or type(sequence) is not int or sequence <= 0
            or type(turn) is not int or not 0 <= turn < (1 << 31)):
        raise ValueError('Invalid human ack identity')
    return (prefix + b'\nlocal me,other,incoming,initiator,respType,expectedSession,expectedSequence,sequence,reqTurn=%d,%d,%d,%d,%d,%d,%d,%d,%d\n'
            b'local action=DealProposalAction.%s\n'
            % (pid, target, incoming, initiator, response_type, expected_session_id,
               expected_sequence, sequence, turn, action.encode('ascii')) + _ACK)


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
