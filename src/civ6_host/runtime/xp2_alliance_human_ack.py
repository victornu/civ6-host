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

# The incoming-deal read reuses the frozen helper's INVENTORY (incoming
# direction) so the locked alliance item is read exactly once, live enums.
def reception_source(prefix, pid, target):
    """Eval reading the pending MAKE_DEAL identity and the incoming alliance term."""
    if (type(pid) is not int or not 0 <= pid < 64 or type(target) is not int
            or not 0 <= target < 64 or pid == target):
        raise ValueError('Invalid human reception identity')
    from . import xp2_alliance_deal_terms as terms
    return (prefix + b'\nlocal me,other=%d,%d\n' % (pid, target)
            + b"local deal=DealManager.GetWorkingDeal(DealDirection.INCOMING,me,other)\n"
            b"assert(deal~=nil,'Incoming deal is absent')\n"
            + terms._inventory_body(True)
            + b"""
return '{"alliance_subtype":'..tostring(ALLIANCE)..',"terms":['..table.concat(allianceTerms,',')..']}'
""")


def parse_reception(raw):
    """Validate the reception readback (same shape as the deal-terms parse)."""
    from . import xp2_alliance_deal_terms as terms
    value = terms.parse(raw, bilateral=True)
    if not any(row['direction'] == 'incoming' for row in value['terms']):
        raise ValueError('Received proposal carries no incoming alliance term')
    return value


_ACK = b"""
assert(DealProposalAction.ACCEPTED==1 and DealProposalAction.REJECTED==2,
 'Native deal action enum changed')
local deal=DealManager.GetWorkingDeal(DealDirection.INCOMING,me,other)
assert(deal~=nil,'Incoming deal is absent')
local before=deal:GetItemCount()
assert(DealManager.SendWorkingDeal(action,me,other)==1,'Native deal answer refused')
local after=DealManager.GetWorkingDeal(DealDirection.INCOMING,me,other)
assert(after==nil or after:GetItemCount()<=before,'Native answer changed the incoming deal scope')
return 'acknowledged'
"""


def ack_source(prefix, pid, target, action):
    """Eval sending the native ACK (ACCEPTED/REJECTED) for a received proposal."""
    if action not in ('ACCEPTED', 'REJECTED'):
        raise ValueError('Only ACCEPTED/REJECTED are alliance answers')
    if (type(pid) is not int or not 0 <= pid < 64 or type(target) is not int
            or not 0 <= target < 64 or pid == target):
        raise ValueError('Invalid human ack identity')
    return (prefix + b'\nlocal me,other=%d,%d\nlocal action=DealProposalAction.%s\n'
            % (pid, target, action.encode('ascii')) + _ACK)


def source_dependencies():
    """Pins for the reception source (native statement evidence files)."""
    from .paths import resource_root
    pins = {}
    for path, digest in (facts.STATEMENT_SOURCE, facts.DRAFT_SOURCE):
        pins[str((resource_root() / path).resolve())] = digest
    return pins
