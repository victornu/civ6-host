"""Explicit research and civic choices while the XP2 LAN UI owns a second seat."""

import hashlib
import struct

from civ6_host.contracts.capability_choices import RESEARCH_KINDS as KINDS
from .configuration_profiles import XP2_CORE_SHA256
from .execution_images import _PROFILE
from .xp1_choice_queries import read_research

_PLAYER_OPERATION = 0xc45de12f
# Installed XP2 PlayerOperation constructor and writer, followed by the
# native vector and scalar writers used for the two chooser parameters.
_SPANS = (
    (0x38990, 129, 'd0e184cb997727a312e9b27b111110996d0d7c4184b180e8f517708304bf8565'),
    (0x38c90, 131, '0a0de4c0fb18e7c9f0665176cd47d2c8ea725213829158715f0531406950b33b'),
    (0x9a6190, 105, '0b966015fc16bddbed6029d7d2e39c1c0f168190f6d51243762de37ffbfbc198'),
    (0x9a98b0, 145, '62befc302be816c7ed95dec156c4a491fcb82255171121ffed703dcea5f40109'),
    (0x9a9950, 238, 'ddf64ff273c4ea481eccf0c59b94be442b1f58ed88cba851d7b72f7793ecea22'),
    (0x99fae0, 111, 'a16fdb8bd9e39364212b4474e17b8955b1c0e958cc94b3ff89e2c6b57f5df0bb'),
    (0x9a4180, 252, '44a5d1e665b8af9c9ac82928173636bdb8238e50c4ee3872fe605afe8cc2e095'),
)
_SLOTS = ((0x9be820, 0x38c90), (0xabfb08, 0x9a6190),
          (0xabfb10, 0x9a98b0), (0xabfb18, 0x9a9950))
_HEADER = struct.Struct('<6I')
_PARAMETER = struct.Struct('<I14sI')
_UNNAMED_U32 = bytes.fromhex('0000020000000000000000000000')


def verify_writer(core, read):
    if getattr(core, '_civ6_host_execution_image', None) is not _PROFILE:
        raise ValueError('Borrowed research requires the installed XP2 execution image')
    base = core._handle
    for rva, size, expected in _SPANS:
        if hashlib.sha256(read(base + rva, size)).hexdigest() != expected:
            raise ValueError('Borrowed research operation writer changed at ' + hex(rva))
    for slot, target in _SLOTS:
        if read(base + slot, 8) != struct.pack('<Q', base + target):
            raise ValueError('Borrowed research operation writer slot changed at ' + hex(slot))


def require_archive(pending, player_id, operation, parameters):
    if len(pending) != 1 or type(pending[0]) is not bytes:
        raise RuntimeError('Borrowed research requires exactly one native archive')
    archive = pending[0]
    if (len(parameters) != 2 or len(archive) != _HEADER.size + 2 * _PARAMETER.size
            or _HEADER.unpack_from(archive) != (_PLAYER_OPERATION, player_id, operation, 0,
                                                0x80000001, 2)):
        raise RuntimeError('Borrowed research archive differs from its player or operation')
    rows = tuple(_PARAMETER.iter_unpack(archive[_HEADER.size:]))
    if (any(fields != _UNNAMED_U32 for _, fields, _ in rows)
            or {key: value for key, _, value in rows} != parameters):
        raise RuntimeError('Borrowed research archive differs from its native parameters')


def read(saved, observation, activity):
    player = observation['player_id']
    row = next(row for row in activity['rows'] if row['player_id'] == player)
    if not row['active'] or not row['active_complete'] or row['can_unready']:
        return None
    from .xp1_session_view import _borrowed_xp2_reference
    _borrowed_xp2_reference(saved, player)
    saved.continuation.transport.require_empty_native_queue()
    saved.backend.control(empty=True)
    verify_writer(saved.backend.core, saved.backend.runtime.read)
    return read_research(saved, observation, core_sha256=XP2_CORE_SHA256)


def project(state):
    if state is None:
        return None
    choices, current = state
    return {kind: dict(current_index=current[kind], choices=list(choices[kind]['choices']))
            for kind in KINDS}


def apply(saved, action, state):
    """Revalidate and submit the source-selected native parameter map once."""
    from .native import native_research_catalog as research
    from .native import native_research_actions as effects
    from .native.native_player_operation_request import request_player_operation
    p, b = saved.prefix, saved.backend
    kind = action['kind']

    def receipt(status, reason=None):
        return dict(status=status, reason=reason, requested_action=action)

    if state is None:
        return receipt('refused', 'native_research_unavailable')
    choices, current = state
    catalogue = choices[kind]
    if {'index': action['index'], 'hash': action['hash']} not in catalogue['choices']:
        return receipt('refused', 'native_research_choice_unavailable')
    candidate = research.choose(catalogue, action['index'])
    player, turn = candidate['player_id'], candidate['current_game_turn']
    source = research.revalidate_choice_source(candidate, core_sha256=XP2_CORE_SHA256)
    raw = p.runtime.evaluate_text(p.ui_child, source, b'@native_research_revalidation')
    checked = research.parse_revalidated_choice(raw, candidate)
    result = request_player_operation(b.core, b.context, player, checked['operation'],
        checked['parameters'], read=b.runtime.read, core_sha256=XP2_CORE_SHA256)
    if result['can_start'] is False and result['request_invoked'] is False:
        saved.continuation.transport.require_empty_native_queue()
        return receipt('refused', 'native_player_operation_unavailable')
    if (result['can_start'] is not True or result['request_invoked'] is not True
            or result['player_id'] != player or result['operation'] != checked['operation']):
        raise RuntimeError('Borrowed research native request receipt differs from the choice')
    require_archive(p.actions.pending, player, result['operation'], checked['parameters'])
    p.actions.deliver_one()
    p.deferred_events.drain_empty_receivers()
    p.view_publisher.publish()
    saved.continuation.transport.require_empty_native_queue()
    source = effects.effect_source(player, kind, action['index'], core_sha256=XP2_CORE_SHA256)
    raw = p.runtime.evaluate_text(p.ui_child, source, b'@native_research_after')
    effect = effects.parse_effect(raw, player, kind, action['index'], turn)
    changed = effect['confirmed'] and current[kind] != effect['observed_index']
    saved.emit('borrowed_xp2_research_readback', player_id=player, turn=turn,
        action=action, before=current[kind], after=effect['observed_index'],
        selection_changed=changed)
    return (receipt('completed') if changed
            else receipt('submitted', 'native_research_effect_unresolved'))
