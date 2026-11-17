"""Source adapter for a human seat receiving an alliance proposal (MAKE_DEAL).

SOURCE-ONLY (lot 98d405f3): builds the Lua evals that (a) read the pending
MAKE_DEAL statement fields and the INCOMING working deal's locked
AGREEMENTS/ALLIANCE item, and (b) send the native answer
(DealManager.SendWorkingDeal ACCEPTED/REJECTED on the incoming deal, locked
item preserved). Archive item checking is DELEGATED to the spy worker's
xp2_alliance_archive_source.py (real 76-byte item ABI with ValueType map) —
this module keeps only the wrapper/Lua and never parses archive items itself.

NOT WIRED: no session, no borrowed seat, no candidate, no H2H claim. The
human-side UI custom handler for MAKE_DEAL is not pinned (no Steam install
here) and the upstream support flags stay false for human counterparties, so
nothing here is executable until api_worker branches the common seams.
"""
from __future__ import annotations

import json

from . import xp2_alliance_human_reception_source as facts

# The incoming-deal read consumes the v7 helper's non-terminal
# inventory_source() (support-owned xp2_alliance_deal_terms.py); the locked
# alliance item is read exactly once, with live enums.
def reception_source(prefix, pid, target):
    """Eval reading the pending MAKE_DEAL identity and the incoming alliance term."""
    if (type(pid) is not int or not 0 <= pid < 64 or type(target) is not int
            or not 0 <= target < 64 or pid == target):
        raise ValueError('Invalid human reception identity')
    from . import xp2_alliance_deal_terms as terms
    return (prefix + b'\nlocal me,other=%d,%d\n' % (pid, target)
            + b"local deal=DealManager.GetWorkingDeal(DealDirection.INCOMING,me,other)\n"
            b"assert(deal~=nil,'Incoming deal is absent')\n"
            + terms.inventory_source()
            + b"\nreadAllianceItem(deal,me,'outgoing')\nreadAllianceItem(deal,other,'incoming')\n"
            + b"""
return '{"terms":['..table.concat(allianceTerms,',')..']}'
""")


def parse_reception(raw):
    """Validate the reception readback through the v7 parse (bilateral)."""
    from . import xp2_alliance_deal_terms as terms
    value = terms.parse(raw, bilateral=True)
    terms_ = value['terms'] if isinstance(value, dict) and 'terms' in value else value
    rows = terms_ if isinstance(terms_, list) else terms_.get('terms', [])
    if not any(isinstance(row, dict) and row.get('direction') == 'incoming' for row in rows):
        raise ValueError('Received proposal carries no incoming alliance term')
    return value


# Real answer path from DiplomacyDealView.lua (DEAL_VIEW_SHA256): accept
# requires AreWorkingDealsEqual then SendWorkingDeal(ACCEPTED) — which also
# emits the POSITIVE response statement natively; refuse sends REJECTED then
# closes the open session. All enum values are asserted live.
# Envelope: the open session is resolved and authenticated BEFORE any send
# (lifetime), with pair and sid echoed back; accept mirrors
# OnProposeOrAcceptDeal, refuse mirrors OnRefuseDeal (send REJECTED, then
# CloseSession). Phase is asserted via IsSessionIDOpen around the send.
_ACK = b"""
assert(DealProposalAction.ACCEPTED==1 and DealProposalAction.REJECTED==2,
 'Native deal action enum changed')
local sessionID=DiplomacyManager.FindOpenSessionID(me,other)
assert(sessionID~=nil and type(sessionID)=='number','Open session missing before answer')
assert(DiplomacyManager.IsSessionIDOpen(sessionID)==true,'Session not open before answer')
if action==DealProposalAction.ACCEPTED then
 assert(DealManager.AreWorkingDealsEqual(me,other)==true,'Working deals differ before accept')
end
assert(DealManager.SendWorkingDeal(action,me,other)==1,'Native deal answer refused')
if action==DealProposalAction.REJECTED then
 assert(DiplomacyManager.CloseSession(sessionID)==true,'Native session close refused')
end
return '{"session_id":'..tostring(sessionID)..',"from":'..tostring(me)..',"to":'..tostring(other)..
 ',"action":'..tostring(action)..'}'
"""


def ack_source(prefix, pid, target, action):
    """Eval sending the native answer (ACCEPTED/REJECTED) for a received proposal.

    Mirrors OnProposeOrAcceptDeal/OnRefuseDeal in the official
    DiplomacyDealView.lua; SOURCE-ONLY, not wired to any session.
    """
    if action not in ('ACCEPTED', 'REJECTED'):
        raise ValueError('Only ACCEPTED/REJECTED are alliance answers')
    if (type(pid) is not int or not 0 <= pid < 64 or type(target) is not int
            or not 0 <= target < 64 or pid == target):
        raise ValueError('Invalid human ack identity')
    return (prefix + b'\nlocal me,other=%d,%d\nlocal action=DealProposalAction.%s\n'
            % (pid, target, action.encode('ascii')) + _ACK)


def source_dependencies():
    """Full closure: native statement evidence + the 11-file private UI drop.

    Verifies each UI script byte-exact against the drop's embedded MANIFEST
    (sha 3195e4b127b4...) at UI_DROP_ROOT, plus the two evidence pins under
    the resource root.
    """
    import hashlib
    import json
    from pathlib import Path
    from .paths import resource_root
    pins = {}
    for path, digest in (facts.STATEMENT_SOURCE, facts.DRAFT_SOURCE):
        pins[str((resource_root() / path).resolve())] = digest
    drop = Path(facts.UI_DROP_ROOT)
    manifest = drop / 'MANIFEST.json'
    raw = manifest.read_bytes()
    if hashlib.sha256(raw).hexdigest() != facts.UI_MANIFEST_SHA256:
        raise ValueError('Private UI drop manifest changed')
    for row in json.loads(raw)['files']:
        data = (drop / row['path']).read_bytes()
        if len(data) != row['bytes'] or hashlib.sha256(data).hexdigest() != row['sha256']:
            raise ValueError('Private UI drop script changed: ' + row['path'])
        pins[str((drop / row['path']).resolve())] = row['sha256']
    return pins
