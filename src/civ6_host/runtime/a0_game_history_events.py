"""Source-qualified History/Era scalar notifications using shared codecs and FIFO."""
import struct
from . import game_history_event_profile as source
from .configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256


def _selected(kind, core_sha256=XP1_CORE_SHA256):
    if core_sha256 == XP1_CORE_SHA256:
        if type(kind) is int and kind in source.EVENTS:
            source.verify_source()
            return source.EVENTS[kind],(source.SOURCE if kind==source.HISTORY_KIND else source.ERA_SOURCE)[1]
        from . import game_era_score_event_profile as score
        if type(kind) is int and kind==score.EVENT_KIND:
            score.verify_source()
            return score.SPEC,score.SOURCE[1]
    elif core_sha256 == XP2_CORE_SHA256:
        from . import xp2_history_event_profile as xp2
        xp2.source()
        if kind == xp2.PROPERTY_KIND:
            xp2.property_source()
            return xp2.PROPERTY_SPEC, xp2.PROPERTY_SOURCE[1]
        if kind in xp2.AGE_EVENTS:
            xp2.age_source()
            return xp2.AGE_EVENTS[kind], xp2.AGE_SOURCE[1]
        from . import game_era_score_event_profile as score
        if kind == xp2.TURN21_KIND:
            xp2.turn21_source()
            return xp2.TURN21_SPEC, xp2.TURN21_SOURCE[1]
        if kind == 0x8c6b2399:
            xp2.turn21_scalar_sources()
            spec = xp2.TURN21_SCALARS[kind]
            return spec, xp2.turn21_scalar_receiver_row(spec[0])['source_sha256']
        if kind in xp2.DESCRIPTOR_EVENTS:
            xp2.descriptor_sources(kind)
            spec, refs, _ = xp2.DESCRIPTOR_EVENTS[kind]
            return spec, refs[0][1]
        if kind == xp2.DESCRIPTOR_E4_KIND:
            xp2.descriptor_e4_source()
            return xp2.DESCRIPTOR_E4_SPEC, xp2.DESCRIPTOR_E4_SOURCE[1]
        specs={source.HISTORY_KIND:source.EVENTS[source.HISTORY_KIND],
               source.ERA_KIND:source.EVENTS[source.ERA_KIND],
               score.EVENT_KIND:score.SPEC}
        if type(kind) is int and kind in specs:
            return specs[kind],xp2.SOURCE[1]
    raise ValueError('Unqualified history/era scalar event kind')


def encode(kind, fields, sequence, *, normalizer_transform_present,
           optional_callback_present, queue_metadata_service,
           core_sha256=XP1_CORE_SHA256, read=None):
    spec,_=_selected(kind,core_sha256)
    if (normalizer_transform_present is not False or optional_callback_present is not False
            or queue_metadata_service is not None):
        raise ValueError('Unqualified history/era scalar producer or optional service')
    record,flag,*_=spec
    row={'callback_shape_group':'two_value_three_key','payload_value_count':2,'writer_record_type':hex(record)}
    from .native.native_scalar_event_encoder import (
        _decode_profile_fields, _encode_profile_record, _read_u32_variant)
    if core_sha256 == XP2_CORE_SHA256 and record in (0xdf, 0xe3, 0xe4):
        from .native.native_event_99e85ec6 import DESCRIPTOR_KEY, SELECTOR_KEY, decode_fields
        scalar_keys = (0xD6FCF3E4, 0xA1FBC372)
        if type(fields) is not dict or set(fields) != {DESCRIPTOR_KEY, SELECTOR_KEY, *scalar_keys}:
            raise ValueError('XP2 descriptor record requires its exact descriptor and scalar fields')
        values = tuple(_read_u32_variant(fields[key], 2, 'value') for key in scalar_keys)
        descriptor = decode_fields({key: fields[key] for key in (DESCRIPTOR_KEY, SELECTOR_KEY)}, read)
        if descriptor.selector != 0:
            raise ValueError('XP2 descriptor record requires the selector-zero route')
        # The borrowed pointer never enters the queue. Bytes not defined by the
        # writer are zeroed only under the verified headless empty receiver.
        row['payload_value_count'] = 0
        result = bytearray(_encode_profile_record(row, sequence, ()))
        result.extend(bytes(16))
        struct.pack_into('<I', result, 0, len(result))
        if record == 0xe4:
            struct.pack_into('<IIHHI', result, 88, *values, descriptor.owner, 2, descriptor.item_id)
        else:
            struct.pack_into('<HHIII', result, 88, descriptor.owner, 2, descriptor.item_id, *values)
        return bytes(result)
    if core_sha256 == XP2_CORE_SHA256 and record == 0x106:
        row.update(callback_shape_group='one_value_two_key', payload_value_count=0)
        selector, _ = _decode_profile_fields(row, fields)
        # The callback does not read the property hash from the descriptor.
        # The writer's undefined DWORD at 84 stays zero in the owned empty row.
        values = ()
    elif core_sha256 == XP2_CORE_SHA256 and record in (0x107, 0x108):
        row.update(callback_shape_group='one_value_two_key', payload_value_count=1)
        selector, *values = _decode_profile_fields(row, fields)
    elif core_sha256==XP2_CORE_SHA256 and kind==0x788b7534:
        from .xp2_history_event_profile import decode_score_fields
        selector,*values=decode_score_fields(fields)
    elif core_sha256 == XP2_CORE_SHA256 and record == 0xe2:
        keys = (0xD6FCF3E4, 0xA1FBC372, 0x38F292C8)
        selector_key = 0xA1E5A149
        if type(fields) is not dict or set(fields) != {selector_key, *keys}:
            raise ValueError('XP2 record 0xe2 requires its four scalar fields')
        selector = _read_u32_variant(fields[selector_key], 3, 'selector')
        values = [_read_u32_variant(fields[key], 2, 'value') for key in keys]
        row['payload_value_count'] = len(keys)
    else:
        selector,*values=_decode_profile_fields(row,fields)
    if selector!=0:raise ValueError('History/era requires the source selector-zero route')
    result=bytearray(_encode_profile_record(row,sequence,values,queue_metadata=0))
    # The official callbacks supply their literal metadata descriptor (0 or 6).
    struct.pack_into('<I',result,72,flag)
    return bytes(result)


def dispatch(owner,kind,fields):
    from .a0_foundation_events import require_borrow
    from .native.native_deferred_empty_profile import validate_empty_profile_record
    token=require_borrow(owner)
    core_sha256=token.owner.load_abi.core_sha256
    spec,proof=_selected(kind,core_sha256)
    if owner.active_kind!=kind:
        raise ValueError('History/era needs its exact active saved owner')
    if core_sha256==XP1_CORE_SHA256:
        if (owner.placement_event_profile is None
                or kind not in owner.placement_event_profile.record_types_by_kind):
            raise ValueError('XP1 history/era requires its existing placement-family owner')
    elif core_sha256==XP2_CORE_SHA256:
        if (getattr(owner,'history_event_profile',None) is None
                or owner.history_event_profile is not getattr(owner,'_history_event_profile',None)
                or kind not in owner.history_event_profile.record_types_by_kind):
            raise ValueError('XP2 history/era requires its independent history-family owner')
    if len(owner.pending)>=owner.limit:raise RuntimeError('Native deferred queue bound exceeded')
    if type(owner._sequence) is not int or not 0<=owner._sequence<0x7fffffff:
        raise ValueError('History/era sequence exhausted')
    before=(owner.host_notification_counter,owner.host_metadata_counter)
    # DeferredService rejects optional producer/metadata services at construction.
    owner.deferred._check()
    record=encode(kind,fields,owner._sequence+1,normalizer_transform_present=owner.normalizer_transform_present,
                  optional_callback_present=False,queue_metadata_service=None,
                  core_sha256=core_sha256, read=owner.read)
    validate_empty_profile_record(record,**owner.empty_receiver_state)
    owner._enqueue(record)
    if before!=(owner.host_notification_counter,owner.host_metadata_counter):
        raise RuntimeError('History/era notification changed its enclosing counters')
    owner.emit('native_deferred_host_event_enqueued',dispatch_kind=hex(kind),queue_type=hex(spec[0]),
        record_hex=record.hex(),pending_count=len(owner.pending),native_queries_executed=False,
        metadata_flag=spec[1],source_proof_sha256=proof,
        optional_preprocessing_hook_registered=False,queue_metadata_service_registered=False,
        empty_receiver_state_verified=True,consumer_validated=False,eligible_for_training=False,native_dispatch_return=0)
    return 0
