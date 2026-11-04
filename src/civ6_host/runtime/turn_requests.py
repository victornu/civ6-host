"""Native turn-request emission, separate from delivery and game acceptance.

UNREADY uses the official no-parameter Core wrapper. This internal adapter does
not admit a network session, supply UI availability, drain the command queue,
or claim that a player became active. Those belong to the session boundary.
"""
from __future__ import annotations

import ctypes as C
import hashlib
import struct


UNREADY_ACTION = 0xBDAB643D
UNREADY_MESSAGE = 0xE8A26B84
_WRAPPER_RVA = 0x42E570
_WRAPPER_BYTES = 79
_WRAPPER_SHA256 = 'ee8f2e38aca1e97745e13c6fd920431480e8f351b3cee8d43d23b13314a0598d'

# Private source receipts are retained in the lab, not distributed as code.
SOURCE_RECEIPTS = {
    'unready-route.json': '594978a67634eae6b8c7a34c2775692b4105dd66167b1bb83da9ed51041765d7',
    'request-action-wrapper.json': '7b6a0524b501b51e72898fd44f33218c7adbd7edca39910439a9888daeb3522a',
}


def request_unready_turn(transport, player: int, *, player_ids=(0, 1), profile=None) -> dict:
    """Ask Core to serialize UNREADY; preserve its guard and pending order.

    A returned ``not_queued`` result is only an observation of emission. It is
    not proof of rejection, readiness or any game-state effect. A queued result
    still requires native delivery and a separately observed result. Neither
    outcome is retried automatically.
    """
    from civ6_host.runtime.native.native_diagnostic_roster import validate_player
    from civ6_host.runtime.native.native_host import virtual
    from .xp1_turn_profile import BASE, require_profile

    # The default retains the historical Base wrapper; a different transport
    # must supply its canonical selected profile rather than call a Base RVA.
    profile = BASE if profile is None else profile
    abi = getattr(transport, 'transport_abi', None)
    engine = getattr(abi, 'core_sha256', BASE.core_sha256)
    require_profile(profile, engine)

    validate_player(player, player_ids)
    if type(transport.pending) is not list or len(transport.pending) >= 64:
        raise RuntimeError('Turn request requires a bounded pending command queue')
    if any(type(row) is not bytes or not 0 < len(row) <= 0x1A80
           for row in transport.pending):
        raise RuntimeError('Turn request found an invalid pending archive')
    before = tuple(transport.pending)
    wrapper = transport.read(transport.core._handle + profile.unready_wrapper_rva, _WRAPPER_BYTES)
    if hashlib.sha256(wrapper).hexdigest() != profile.unready_wrapper_sha256:
        raise RuntimeError('Unready request wrapper differs from the pinned Core')
    request = virtual(transport.core, transport.context, 0x200, profile.unready_wrapper_rva,
                      None, C.c_uint32, C.c_int32)
    transport.emit('before_native_unready_turn_request', player_id=player,
                   action_type=UNREADY_ACTION, core_slot='0x200',
                   action_applied=False)
    # Core owns construction and destruction of the empty vector parameter
    # map, then executes the existing +0x1f8 guard and message constructor.
    request(transport.context, UNREADY_ACTION, player)
    if (type(transport.pending) is not list
            or tuple(transport.pending[:len(before)]) != before):
        raise RuntimeError('Unready request changed an earlier pending command')
    emitted = transport.pending[len(before):]
    if not emitted:
        receipt = dict(status='not_queued', player_id=player, queued=False,
                       action_applied=False, native_outcome_verified=False)
    elif len(emitted) == 1 and emitted[0] == struct.pack('<II', UNREADY_MESSAGE, player):
        receipt = dict(status='queued', player_id=player, queued=True,
                       archive_hex=emitted[0].hex(), action_applied=False,
                       native_outcome_verified=False)
    else:
        # Do not delete an unexpected archive or manufacture an ACK. The
        # owning session must refuse/abort this uncertain exchange.
        raise RuntimeError('Unready request emitted an unexpected native archive')
    transport.emit('native_unready_turn_emission_observed', **receipt)
    return receipt
