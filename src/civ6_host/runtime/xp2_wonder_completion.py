"""Gathering Storm's extended E660 wonder completion branch."""
from functools import lru_cache
import struct

from .configuration_profiles import XP2_CORE_SHA256, _source

SOURCE = ('work/host-extensions/xp2-wonder-completion-source.json',
          '328f71f5a992c611ce3d39be69abc3f4da8b06ec17da2d08d8ca18c810ad2c61')
KIND = 0xe66012a7


@lru_cache(maxsize=1)
def source():
    from .native.native_event_e66012a7_wonder import verify_source_evidence
    from .native.native_host_event_registry import EXE_EVENT_CALLBACKS
    from .xp2_natural_wonder_source import source as comparison_source

    proof = _source(SOURCE)
    base = verify_source_evidence()
    comparison = comparison_source()
    stack_ref = proof['xp2_stack_source']
    stack = _source((stack_ref['path'], stack_ref['sha256']))
    expected_bodies = {key: base['exe_bodies'][key]['code_sha256']
                       for key in ('callback', 'writer_AE', 'writer_AF', 'comparison_effect')}
    if (proof['schema'] != 'civ6-host.xp2-wonder-completion-source.v1'
            or proof['source_only'] is not True or proof['core_sha256'] != XP2_CORE_SHA256
            or proof['exe_sha256'] != comparison['images']['exe']['sha256']
            or proof['kind'] != KIND or EXE_EVENT_CALLBACKS.get(KIND) != 0x13fd70
            or (proof['selector'], proof['district_hash']) != (0xccb6d5be, 0x62f1b509)
            or proof['record_order'] != (169, 166, 174, 175) or proof['extended_record_size'] != 144
            or proof['callback_order'] != ('call 0x1400f1420', 'call 0x1401369b0',
                                          'call 0x140151d70', 'call 0x1401b9c30', 'call 0x140136bc0')
            or proof['exe_body_sha256'] != expected_bodies
            or expected_bodies['comparison_effect'] != comparison['functions']['exe_0x151d70']['sha256']
            or proof['position_effect_body_sha256'] != comparison['functions']['exe_0x1b9c30']['sha256']
            or stack['schema'] != 'civ6-host.xp2-e660-wonder-stack-source.v1'
            or stack['core']['sha256'] != XP2_CORE_SHA256 or stack['trace'] != proof['trace']):
        raise ValueError('XP2 wonder completion source identity differs')
    return proof, stack


def source_dependencies():
    from .a0_family_source import _path

    proof, _ = source()
    pins = {str(_path(SOURCE[0]).resolve()): SOURCE[1]}
    for key in ('xp2_stack_source', 'base_writers', 'xp2_comparison'):
        row = proof[key]
        pins[str(_path(row['path']).resolve())] = row['sha256']
    return pins


def verify_live(base, read):
    _, stack = source()
    for body in stack['functions'].values():
        for fragment in body['fragments']:
            expected = bytes.fromhex(fragment['raw_hex'])
            for offset in range(0, len(expected), 4096):
                chunk = expected[offset:offset + 4096]
                if read(base + int(fragment['start_rva'], 16) + offset, len(chunk)) != chunk:
                    raise ValueError('XP2 wonder completion producer live bytes differ')


def enqueue(owner, first_sequence, fields, third_values, record_sink):
    from .a0_foundation_events import require_borrow
    from .native.native_deferred_empty_profile import validate_empty_profile_record
    from .native.native_event_e66012a7_wonder import EMPTY_PADDING_POLICY, encode_wonder_records
    from .native.native_retained_game_getter import read_retained_game_value
    from .native.native_wonder_application import apply_wonder_application_effects

    token = require_borrow(owner)
    owner.deferred._check()
    if (owner.foundation_core_sha256 != XP2_CORE_SHA256 or owner.active_kind != KIND
            or not owner.ui_cache_callbacks_enabled or first_sequence != owner._sequence + 1
            or not 1 <= first_sequence <= 0xfffffffe or len(owner.pending) + 2 > owner.limit
            or owner.controller_owner is None or owner.controller_owner.turn_begin_state is not owner.turn_begin_state
            or owner.deferred.turn_begin_state is not owner.turn_begin_state
            or type(getattr(owner, '_natural_wonder_checkpoint_pending', None)) is not bool
            or owner.normalizer_transform_present or owner.per_thread_hook_present
            or owner.writer_metadata_callback_present or owner.entity_listener_count != 0):
        raise ValueError('XP2 wonder completion requires the active FIFO and shared controller')
    for record_type in (174, 175):
        shape = bytearray(144)
        struct.pack_into('<II', shape, 0, len(shape), record_type)
        validate_empty_profile_record(shape, **owner.empty_receiver_state)
    facades = token.lease.require(token.lease.backend, token.publisher._facades)

    def retained_value():
        token.lease.require(token.lease.backend, facades)
        return read_retained_game_value(facades, owner.read, core_sha256=XP2_CORE_SHA256)

    retained = retained_value()
    records = encode_wonder_records(first_sequence, fields, third_values, retained,
        normalizer_transform_present=False, thread_hook_present=False,
        writer_metadata_callback_present=False, empty_receiver_profile_verified=True,
        padding_policy=EMPTY_PADDING_POLICY)
    record_sink(records[0])
    owner._natural_wonder_checkpoint_pending = True
    effect = apply_wonder_application_effects(owner.core, owner.context, owner.read,
        owner.turn_begin_state, retained_value, core_sha256=XP2_CORE_SHA256)
    owner.emit('native_wonder_application_effects_applied', dispatch_kind=hex(KIND),
               source_proof_sha256=SOURCE[1], metadata_retained_game_value=retained,
               **effect, eligible_for_training=False)
    record_sink(records[1])
    return records
