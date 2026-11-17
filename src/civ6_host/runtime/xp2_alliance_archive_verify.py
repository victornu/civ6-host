"""Archive verification plan for a received alliance proposal (source-only).

Companion to xp2_alliance_human_ack: parse_reception splits the session
envelope from the v7 alliance inventory ({'alliance_subtype','terms'} with
term rows {'direction','type','duration'}); this module turns that
reception into the ordered check_archive keyword arguments expected by the
pinned alliance archive spy.

The spy source is NOT vendored here. It stays sealed in the private handoff
depot and is referenced by path + sha256 (ARCHIVE_SPY_DEPOT /
ARCHIVE_SPY_SHA256); the caller injects the loaded module as archive_module
and expected_archive_items validates its public interface (ALLIANCE,
VALUE_TYPE, ALLIANCE_VALUE_HASHES, ITEM_BYTES, check_archive) before use.

Direction mapping (working-deal inventory row -> native archive item):
  direction=='incoming' -> giver=session['from'] (peer), recipient=session['to'] (local)
  direction=='outgoing' -> giver=session['to'] (local), recipient=session['from'] (peer)
value_hash is ALLIANCE_VALUE_HASHES[row['type']] and duration is the row's
signed32 duration. Each returned plan item holds exactly the keyword
arguments of check_archive(payload, offset, *, giver, recipient,
value_hash, duration), so the caller walks the archive with
archive_module.check_archive(payload, offset, **item).
"""
from __future__ import annotations

from collections.abc import Mapping

from civ6_host.player_view import MAX_PLAYERS

# Sealed archive spy (private handoff, base64_no_wrapping transport). The
# decoded module is integrated by the orchestrator as
# src/civ6_host/runtime/xp2_alliance_archive_source.py; this file only
# references the depot entry.
ARCHIVE_SPY_DEPOT = (
    'handoffs/private-env/alliances/archive/'
    '3ccdcafffd11753f020c306ae9dfcd1552eb4a3c4b422e2dba1d95403156a49a/'
    'xp2_alliance_archive_source.py.b64'
)
ARCHIVE_SPY_SHA256 = '3ccdcafffd11753f020c306ae9dfcd1552eb4a3c4b422e2dba1d95403156a49a'

# Known spy interface (MANIFEST schema
# civ6-host.xp2-alliance-archive.private-handoff.v1).
ALLIANCE = 0x6932036b
VALUE_TYPE = 0x234988cf
ITEM_BYTES = 76
ALLIANCE_TYPES = (
    'ALLIANCE_RESEARCH',
    'ALLIANCE_CULTURAL',
    'ALLIANCE_ECONOMIC',
    'ALLIANCE_MILITARY',
    'ALLIANCE_RELIGIOUS',
)

# Session envelope keys produced by xp2_alliance_human_ack.parse_reception.
_SESSION_KEYS = frozenset({'session_id', 'event_sequence', 'turn', 'from', 'to',
                           'response_type', 'deal_action', 'subtype', 'provenance'})
_DIRECTIONS = ('incoming', 'outgoing')


def _is_int(value):
    return type(value) is int


def _is_signed32(value):
    return _is_int(value) and -(1 << 31) <= value < (1 << 31)


def _validate_archive_module(archive_module):
    """Check the injected spy module against the pinned public interface."""
    hashes = getattr(archive_module, 'ALLIANCE_VALUE_HASHES', None)
    if (getattr(archive_module, 'ALLIANCE', None) != ALLIANCE
            or getattr(archive_module, 'VALUE_TYPE', None) != VALUE_TYPE
            or getattr(archive_module, 'ITEM_BYTES', None) != ITEM_BYTES
            or not callable(getattr(archive_module, 'check_archive', None))
            or not isinstance(hashes, Mapping)
            or set(hashes) != set(ALLIANCE_TYPES)
            or any(not _is_int(hashes[key]) or not -(1 << 31) <= hashes[key] <= 0xffffffff
                   for key in ALLIANCE_TYPES)):
        raise ValueError('Archive module does not match the pinned alliance archive interface')


def expected_archive_items(reception, archive_module):
    """Ordered check_archive kwargs for every term of a received proposal.

    reception is the dict returned by xp2_alliance_human_ack.parse_reception
    ({'session': ..., 'inventory': ...}); archive_module is the pinned
    alliance archive spy (ARCHIVE_SPY_DEPOT/ARCHIVE_SPY_SHA256) injected by
    the caller. Validates that inventory['alliance_subtype'] == ALLIANCE and
    that every term duration is a signed32, then returns one kwargs dict per
    inventory term, in term order, each directly usable as
    archive_module.check_archive(payload, offset, **item).
    """
    _validate_archive_module(archive_module)
    if type(reception) is not dict or set(reception) != {'session', 'inventory'}:
        raise ValueError('Reception must be the parse_reception output dict')
    session = reception['session']
    inventory = reception['inventory']
    if type(session) is not dict or set(session) != _SESSION_KEYS:
        raise ValueError('Malformed reception session envelope')
    peer = session['from']
    local = session['to']
    if (not _is_int(peer) or not 0 <= peer < MAX_PLAYERS
            or not _is_int(local) or not 0 <= local < MAX_PLAYERS
            or peer == local):
        raise ValueError('Invalid reception participants')
    if type(inventory) is not dict or set(inventory) != {'alliance_subtype', 'terms'}:
        raise ValueError('Malformed alliance inventory')
    if not _is_int(inventory['alliance_subtype']) or inventory['alliance_subtype'] != archive_module.ALLIANCE:
        raise ValueError('Inventory alliance_subtype is not the ALLIANCE agreement subtype')
    terms = inventory['terms']
    if type(terms) is not list or not terms:
        raise ValueError('Alliance inventory carries no term')
    hashes = archive_module.ALLIANCE_VALUE_HASHES
    plan = []
    seen = set()
    for row in terms:
        if type(row) is not dict or set(row) != {'direction', 'type', 'duration'}:
            raise ValueError('Malformed alliance inventory term')
        direction = row['direction']
        if direction not in _DIRECTIONS or direction in seen:
            raise ValueError('Unknown or duplicate alliance term direction')
        if type(row['type']) is not str or row['type'] not in hashes:
            raise ValueError('Unknown alliance term type')
        if not _is_signed32(row['duration']):
            raise ValueError('Alliance term duration is not a signed32')
        seen.add(direction)
        if direction == 'incoming':
            giver, recipient = peer, local
        else:
            giver, recipient = local, peer
        plan.append({'giver': giver, 'recipient': recipient,
                     'value_hash': hashes[row['type']], 'duration': row['duration']})
    return plan
