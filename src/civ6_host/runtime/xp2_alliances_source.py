"""Static official XP2 alliance facts for propose/renew alliance requests.

Facts come from the official Gathering Storm gameplay database of the retained
capture (DiplomacySelections, DiplomacyStatementTypes, DiplomaticActions and
DiplomaticActions_XP1, Alliances, AllianceEffects) and from the pinned official
UI files. Team alliance variants (CHOICE_ALLIANCE_*_TEAM) stay unsupported.
"""
from __future__ import annotations

SCHEMA = 'civ6-host.diplomacy-overview.v9'

VIEW_SHA256 = '246409606568dc3f6f2b913334dbc626d9b59e81efc02df0d28409a6ae959cfc'
ALLIANCE_ROW_SHA256 = '34990895aecfa4330b026939fc214b8f041caa231ecdc0f69ee9b8b86e4772aa'

# GREETING selections (official DiplomacySelections rows, sorts 24-29):
# choice key -> RequestSession statement type.
ALLIANCE_REQUESTS = {
    'CHOICE_ALLIANCE_RESEARCH': 'CREATE_RESEARCH_ALLIANCE',
    'CHOICE_ALLIANCE_MILITARY': 'CREATE_MILITARY_ALLIANCE',
    'CHOICE_ALLIANCE_ECONOMIC': 'CREATE_ECONOMIC_ALLIANCE',
    'CHOICE_ALLIANCE_CULTURAL': 'CREATE_CULTURAL_ALLIANCE',
    'CHOICE_ALLIANCE_RELIGIOUS': 'CREATE_RELIGIOUS_ALLIANCE',
    'CHOICE_RENEW_ALLIANCE': 'RENEW_ALLIANCE',
}
# Same rows' DiplomaticActionType column.
ALLIANCE_ACTIONS = {
    'CHOICE_ALLIANCE_RESEARCH': 'DIPLOACTION_ALLIANCE_RESEARCH',
    'CHOICE_ALLIANCE_MILITARY': 'DIPLOACTION_ALLIANCE_MILITARY',
    'CHOICE_ALLIANCE_ECONOMIC': 'DIPLOACTION_ALLIANCE_ECONOMIC',
    'CHOICE_ALLIANCE_CULTURAL': 'DIPLOACTION_ALLIANCE_CULTURAL',
    'CHOICE_ALLIANCE_RELIGIOUS': 'DIPLOACTION_ALLIANCE_RELIGIOUS',
    'CHOICE_RENEW_ALLIANCE': 'DIPLOACTION_RENEW_ALLIANCE',
}
ALLIANCE_CHOICE_SORTS = {
    'CHOICE_ALLIANCE_RESEARCH': 24,
    'CHOICE_ALLIANCE_MILITARY': 25,
    'CHOICE_ALLIANCE_ECONOMIC': 26,
    'CHOICE_ALLIANCE_CULTURAL': 27,
    'CHOICE_ALLIANCE_RELIGIOUS': 28,
    'CHOICE_RENEW_ALLIANCE': 29,
}
# Alliances table rows / DiplomacyActions_XP1.AllianceType values.
ALLIANCE_TYPES = (
    'ALLIANCE_RESEARCH',
    'ALLIANCE_CULTURAL',
    'ALLIANCE_ECONOMIC',
    'ALLIANCE_MILITARY',
    'ALLIANCE_RELIGIOUS',
)
CHOICE_BY_ALLIANCE_TYPE = {
    'ALLIANCE_RESEARCH': 'CHOICE_ALLIANCE_RESEARCH',
    'ALLIANCE_MILITARY': 'CHOICE_ALLIANCE_MILITARY',
    'ALLIANCE_ECONOMIC': 'CHOICE_ALLIANCE_ECONOMIC',
    'ALLIANCE_CULTURAL': 'CHOICE_ALLIANCE_CULTURAL',
    'ALLIANCE_RELIGIOUS': 'CHOICE_ALLIANCE_RELIGIOUS',
}
# Team variants offered by the XP2 overlay remain non-executable.
ALLIANCE_TEAM_CHOICES = frozenset({
    'CHOICE_ALLIANCE_RESEARCH_TEAM', 'CHOICE_ALLIANCE_MILITARY_TEAM',
    'CHOICE_ALLIANCE_ECONOMIC_TEAM', 'CHOICE_ALLIANCE_CULTURAL_TEAM',
    'CHOICE_ALLIANCE_RELIGIOUS_TEAM',
})
ALLIANCE_CHOICES = frozenset(ALLIANCE_REQUESTS)

# DiplomaticActions: DIPLOACTION_ALLIANCE has Agreement set and Duration 30;
# DIPLOACTION_RENEW_ALLIANCE requires RequiresAllianceSoonToEnd and Duration 30.
# Every alliance action requires CIVIC_CIVIL_SERVICE for initiator and target.
ALLIANCE_DURATION = 30
ALLIANCE_PREREQ_CIVIC = 'CIVIC_CIVIL_SERVICE'
RENEW_REQUIRES_ALLIANCE_SOON_TO_END = True

# Statement types MAKE_ALLIANCE / RENEW_ALLIANCE with subtypes and the
# POSITIVE/NEGATIVE/EXIT response selections from DiplomacySelections.
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
    pins = dict(relationships.source_dependencies(xp2_view_path))
    return pins
