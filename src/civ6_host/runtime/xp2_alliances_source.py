"""Static official XP2 alliance facts for propose/renew alliance requests.

The request path is the pinned official XP1 overlay callback
OnSelectInitialDiplomacyStatement (work/bbg751-turn-source-scope/
war-confirmation/initial-diplomacy/source-profile.json): each
CHOICE_ALLIANCE_<TYPE> builds an outgoing AGREEMENTS deal item with subtype
DealAgreementTypes.ALLIANCE, value type DB.MakeHash("ALLIANCE_<TYPE>"),
locked, then dispatches RequestSession(..., "MAKE_DEAL"); CHOICE_RENEW_ALLIANCE
dispatches RequestSession(..., "RENEW_ALLIANCE") directly. The DB rows below
(DiplomacySelections sorts 24-29 -> DIPLOACTION_*, DiplomaticActions,
Alliances, AllianceEffects) are capture data only: eligibility, terms and the
effective duration come from the native providers, never from these constants.
Team variants CHOICE_ALLIANCE_*_TEAM share the exact same official branch; they
stay explicitly non-qualified because no team game is in the qualified capture.
"""
from __future__ import annotations

# Public alliance view schema; must match contracts/alliances.py (claude lot).
SCHEMA = 'civ6-host.alliances.v1'

VIEW_SHA256 = '246409606568dc3f6f2b913334dbc626d9b59e81efc02df0d28409a6ae959cfc'
ALLIANCE_ROW_SHA256 = '34990895aecfa4330b026939fc214b8f041caa231ecdc0f69ee9b8b86e4772aa'
PROFILE_PATH = 'work/bbg751-turn-source-scope/war-confirmation/initial-diplomacy/source-profile.json'
PROFILE_SHA256 = '92f83b4e4b13b336529ed2f28b6552eb6958d16a5578ba5fea23f7fde5f48055'

# Official callback: propose -> MAKE_DEAL (alliance item added by the pinned
# overlay itself), renew -> RENEW_ALLIANCE.
ALLIANCE_PROPOSALS = {
    'CHOICE_ALLIANCE_RESEARCH': 'ALLIANCE_RESEARCH',
    'CHOICE_ALLIANCE_MILITARY': 'ALLIANCE_MILITARY',
    'CHOICE_ALLIANCE_ECONOMIC': 'ALLIANCE_ECONOMIC',
    'CHOICE_ALLIANCE_CULTURAL': 'ALLIANCE_CULTURAL',
    'CHOICE_ALLIANCE_RELIGIOUS': 'ALLIANCE_RELIGIOUS',
}
RENEW_CHOICE = 'CHOICE_RENEW_ALLIANCE'
ALLIANCE_REQUESTS = {**{key: 'MAKE_DEAL' for key in ALLIANCE_PROPOSALS},
                     RENEW_CHOICE: 'RENEW_ALLIANCE'}
# Capture data: the GREETING rows' DiplomaticActionType column (sorts 24-29).
ALLIANCE_ACTIONS = {
    'CHOICE_ALLIANCE_RESEARCH': 'DIPLOACTION_ALLIANCE_RESEARCH',
    'CHOICE_ALLIANCE_MILITARY': 'DIPLOACTION_ALLIANCE_MILITARY',
    'CHOICE_ALLIANCE_ECONOMIC': 'DIPLOACTION_ALLIANCE_ECONOMIC',
    'CHOICE_ALLIANCE_CULTURAL': 'DIPLOACTION_ALLIANCE_CULTURAL',
    'CHOICE_ALLIANCE_RELIGIOUS': 'DIPLOACTION_ALLIANCE_RELIGIOUS',
    RENEW_CHOICE: 'DIPLOACTION_RENEW_ALLIANCE',
}
ALLIANCE_CHOICE_SORTS = {
    'CHOICE_ALLIANCE_RESEARCH': 24,
    'CHOICE_ALLIANCE_MILITARY': 25,
    'CHOICE_ALLIANCE_ECONOMIC': 26,
    'CHOICE_ALLIANCE_CULTURAL': 27,
    'CHOICE_ALLIANCE_RELIGIOUS': 28,
    RENEW_CHOICE: 29,
}
# Alliances table rows / DiplomacyActions_XP1.AllianceType values.
ALLIANCE_TYPES = (
    'ALLIANCE_RESEARCH',
    'ALLIANCE_CULTURAL',
    'ALLIANCE_ECONOMIC',
    'ALLIANCE_MILITARY',
    'ALLIANCE_RELIGIOUS',
)
CHOICE_BY_ALLIANCE_TYPE = {value: key for key, value in ALLIANCE_PROPOSALS.items()}
# Same official branch as the non-team choices; provisional non-qualified state
# until a team-game capture qualifies their conditions.
ALLIANCE_TEAM_CHOICES = frozenset({
    'CHOICE_ALLIANCE_RESEARCH_TEAM', 'CHOICE_ALLIANCE_MILITARY_TEAM',
    'CHOICE_ALLIANCE_ECONOMIC_TEAM', 'CHOICE_ALLIANCE_CULTURAL_TEAM',
    'CHOICE_ALLIANCE_RELIGIOUS_TEAM',
})
ALLIANCE_CHOICES = frozenset(ALLIANCE_REQUESTS)

# Capture data only (DiplomaticActions): DIPLOACTION_ALLIANCE has Agreement set
# and Duration 30; DIPLOACTION_RENEW_ALLIANCE requires alliance soon to end and
# Duration 30; every alliance action requires CIVIC_CIVIL_SERVICE both sides.
# Never enforced in Python: the effective values come from the loaded rules.
ALLIANCE_DURATION = 30
ALLIANCE_PREREQ_CIVIC = 'CIVIC_CIVIL_SERVICE'
RENEW_REQUIRES_ALLIANCE_SOON_TO_END = True

# AI-side statement types and response selections (DiplomacyStatementTypes /
# DiplomacySelections): MAKE_ALLIANCE / RENEW_ALLIANCE with FROM_AI / FROM_HUMAN
# / EXIT subtypes offering POSITIVE / NEGATIVE / EXIT.
ALLIANCE_STATEMENT_TYPES = (
    'MAKE_ALLIANCE', 'RENEW_ALLIANCE', 'CREATE_RESEARCH_ALLIANCE',
    'CREATE_MILITARY_ALLIANCE', 'CREATE_ECONOMIC_ALLIANCE',
    'CREATE_CULTURAL_ALLIANCE', 'CREATE_RELIGIOUS_ALLIANCE',
)
ALLIANCE_SUBTYPES = (
    'MAKE_ALLIANCE_FROM_AI', 'MAKE_ALLIANCE_FROM_HUMAN', 'MAKE_ALLIANCE_EXIT',
    'RENEW_ALLIANCE_FROM_AI', 'RENEW_ALLIANCE_FROM_HUMAN', 'RENEW_ALLIANCE_EXIT',
)
ALLIANCE_RESPONSE_KINDS = ('CHOICE_POSITIVE', 'CHOICE_NEGATIVE', 'CHOICE_EXIT')

# Native readback contract: GetAllianceType returns -1 without an alliance.
NO_ALLIANCE = -1


def source_dependencies(xp2_view_path):
    """Pin the alliance row overlay in addition to the XP2 view closure."""
    from . import xp2_diplomatic_relationships as relationships
    return dict(relationships.source_dependencies(xp2_view_path))
