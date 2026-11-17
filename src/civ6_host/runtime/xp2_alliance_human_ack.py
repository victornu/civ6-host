"""Source adapter for a human seat receiving an alliance proposal (MAKE_DEAL).

SOURCE-ONLY (lot 98d405f3, corrections 2e608d3d/28d7fb8a): reception_source
establishes pair/direction/phase/validity exactly like the official handler
(MakeDeal_ApplyStatement open condition + MakeDeal_TestValid), and ack_source
mirrors the loaded XP2 DiplomacyDealView (0cd3b32a...) answer path: session
resolved and authenticated BEFORE any send, incoming action read, pending-deal
and initiator guards, human-counterparty guard, refuse = CLOSED/REJECTED then
CloseSession. The v7 helper supplies inventory_source()/parse (support-owned
file); archive item checking is delegated to the spy's
xp2_alliance_archive_source.py. NOT WIRED: no session/borrowed/candidate, no
H2H claim, no GameCore.
"""
from __future__ import annotations

import json

from . import xp2_alliance_human_reception_source as facts


# Reception: session identity + official open condition + PROPOSED-from-peer
# provenance + TestValid + the locked alliance items via the v7 non-terminal
# inventory_source().
def reception_source(prefix, pid, target, deal_action=4):
    """Eval establishing pair/sens/phase/provenance/validity + incoming term.

    deal_action is the received statement's DealAction; a received offer must
    be PROPOSED (4) from the peer (native source 557445ff: INITIAL alone
    proves neither PROPOSED nor an incoming item).
    """
    if (type(pid) is not int or not 0 <= pid < 64 or type(target) is not int
            or not 0 <= target < 64 or pid == target
            or type(deal_action) is not int or not 0 <= deal_action < (1 << 32)):
        raise ValueError('Invalid human reception identity')
    from . import xp2_alliance_deal_terms as terms
    return (prefix + b'\nlocal me,other,dealAction=%d,%d,%d\n' % (pid, target, deal_action)
            + b"""
assert(Game.GetLocalPlayer()==me and Game.GetLocalObserver()==me,'Reception crossed its player')
assert(Players[other] and Players[other]:IsMajor() and Players[me]:GetDiplomacy():HasMet(other),
 'Reception requires a met major')
local sessionID=DiplomacyManager.FindOpenSessionID(me,other)
assert(sessionID~=nil and type(sessionID)=='number','Open MAKE_DEAL session missing')
assert(DiplomacyManager.IsSessionIDOpen(sessionID)==true,'Session not open')
local info=DiplomacyManager.GetSessionInfo(sessionID)
assert(type(info)=='table' and info.FromPlayer==other and info.ToPlayer==me,
 'Session pair/direction differs from the received proposal')
-- Official open condition (ActionView 2548): subtype NONE with response
-- INITIAL or ACKNOWLEDGE opens the deal UI on the INCOMING working deal.
assert(type(DiplomacyResponseTypes)=='table','Missing native response enum')
local rt=info.ResponseType
assert(rt==DiplomacyResponseTypes.INITIAL or rt==DiplomacyResponseTypes.ACKNOWLEDGE,
 'Received statement is not an initial/acknowledge proposal')
-- Native provenance (557445ff): the offer must be PROPOSED from the peer.
assert(dealAction==DealProposalAction.PROPOSED and DealProposalAction.PROPOSED==4,
 'Received offer is not an authenticated PROPOSED from the peer')
-- MakeDeal_TestValid (2611): FromPlayer==other requires a valid non-empty
-- INCOMING working deal.
local deal=DealManager.GetWorkingDeal(DealDirection.INCOMING,me,other)
assert(deal~=nil and deal:GetItemCount()>0 and deal:IsValid()==true,
 'Incoming deal missing, empty or invalid')
"""
            + terms.inventory_source()
            + b"\nreadAllianceItem(deal,me,'outgoing')\nreadAllianceItem(deal,other,'incoming')\n"
            + b"""
return '{"session_id":'..tostring(sessionID)..',"from":'..tostring(other)..',"to":'..tostring(me)..
 ',"response_type":'..tostring(rt)..',"deal_action":'..tostring(dealAction)..
 ',"terms":['..table.concat(allianceTerms,',')..']}'
""")


def parse_reception(raw):
    """Validate the reception readback through the v7 parse (bilateral)."""
    from . import xp2_alliance_deal_terms as terms
    value = terms.parse(raw, bilateral=True)
    rows = value.get('terms', []) if isinstance(value, dict) else value
    if not any(isinstance(row, dict) and row.get('direction') == 'incoming' for row in rows):
        raise ValueError('Received proposal carries no incoming alliance term')
    return value


# Answer: mirrors the loaded XP2 DiplomacyDealView (0cd3b32a). The session is
# resolved and authenticated BEFORE any send; without an open session nothing
# is sent. Human counterparty guard; pending-deal -> CLOSED; initiator==local
# -> no REJECTED; then CloseSession. SendWorkingDeal's return is only checked
# for boolean type (the official UI ignores its value).
_ACK = b"""
assert(DealProposalAction.ACCEPTED==1 and DealProposalAction.REJECTED==2 and
 DealProposalAction.ADJUSTED==3 and DealProposalAction.PROPOSED==4,
 'Native deal action enum changed')
assert(DealProposalAction.CLOSED==8 and DealProposalAction.REJECTED_PERMANENT==12,
 'Native CLOSED/REJECTED_PERMANENT enum changed (support source e29ed1c3)')
assert(Players[other]:IsHuman()==true,'Human answer path requires a human counterparty')
local sessionID=DiplomacyManager.FindOpenSessionID(me,other)
if sessionID==nil then return '{"session_id":null,"sent":false}' end
assert(DiplomacyManager.IsSessionIDOpen(sessionID)==true,'Session not open before answer')
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
  local r=DealManager.SendWorkingDeal(action,me,other)
  assert(type(r)=='boolean','Native SendWorkingDeal result unavailable'); sent=r==true
 else
  local r=DealManager.SendWorkingDeal(DealProposalAction.ADJUSTED,me,other)
  assert(type(r)=='boolean','Native SendWorkingDeal result unavailable'); sent=r==true
 end
elseif action==DealProposalAction.REJECTED or action==DealProposalAction.CLOSED then
 local pending=DealManager.HasPendingDeal(me,other)
 if action==DealProposalAction.CLOSED or pending then
  local r=DealManager.SendWorkingDeal(DealProposalAction.CLOSED,me,other)
  assert(type(r)=='boolean','Native SendWorkingDeal result unavailable'); sent=r==true
 elseif initiator~=me then
  local r=DealManager.SendWorkingDeal(DealProposalAction.REJECTED,me,other)
  assert(type(r)=='boolean','Native SendWorkingDeal result unavailable'); sent=r==true
 end
 assert(DiplomacyManager.CloseSession(sessionID)==true,'Native session close refused')
else
 error('Unsupported alliance answer action')
end
return '{"session_id":'..tostring(sessionID)..',"from":'..tostring(me)..',"to":'..tostring(other)..
 ',"action":'..tostring(action)..',"sent":'..tostring(sent)..'}'
"""


def ack_source(prefix, pid, target, action, incoming=4, initiator=None):
    """Eval sending the native answer for a received proposal (source-only).

    action in ACCEPTED/REJECTED/CLOSED; incoming is the received statement's
    DealAction; initiator defaults to the counterparty (other-initiated).
    """
    if action not in ('ACCEPTED', 'REJECTED', 'CLOSED'):
        raise ValueError('Alliance answers are ACCEPTED/REJECTED/CLOSED')
    if type(incoming) is not int or not 0 <= incoming < (1 << 32):
        raise ValueError('Invalid incoming deal action')
    if initiator is None:
        initiator = target
    if (type(pid) is not int or not 0 <= pid < 64 or type(target) is not int
            or not 0 <= target < 64 or pid == target
            or type(initiator) is not int or not 0 <= initiator < 64):
        raise ValueError('Invalid human ack identity')
    return (prefix + b'\nlocal me,other,incoming,initiator=%d,%d,%d,%d\nlocal action=DealProposalAction.%s\n'
            % (pid, target, incoming, initiator, action.encode('ascii')) + _ACK)


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
    drop = Path(facts.UI_DROP_ROOT)
    raw = (drop / 'MANIFEST.json').read_bytes()
    if hashlib.sha256(raw).hexdigest() != facts.UI_MANIFEST_SHA256:
        raise ValueError('Private UI drop manifest changed')
    for row in json.loads(raw)['files']:
        data = (drop / row['path']).read_bytes()
        if len(data) != row['bytes'] or hashlib.sha256(data).hexdigest() != row['sha256']:
            raise ValueError('Private UI drop script changed: ' + row['path'])
        pins[str((drop / row['path']).resolve())] = row['sha256']
    return pins
