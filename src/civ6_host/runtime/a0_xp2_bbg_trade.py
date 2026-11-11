"""Opt-in typed XP2 BBG trade activity capture into the owned A0 FIFO.

The native callback only copies its checked arguments into a bounded record.
The configured receiver runs when the host drains that record, outside native
callback dispatch, and receives immutable scalar values only.
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import struct
from types import MappingProxyType

from .a0_family_source import A0FamilyProfile
from .a0_policy_unlock_current import (
    CURRENT_CORE_SHA256, CURRENT_EXE_SHA256, CURRENT_PROFILE_ID,
    PROFILE_REF, PROFILE_SHA256, _require_image,
)
from .configuration_profiles import _source
from .paths import resource_root
from .resource_resolution import resolve_path
from . import a0_xp2_bbg_amani as amani
from . import xp2_bbg_promotion as promotion
from . import xp2_bbg_spy as spy
from .xp2_feature_reveal_source import _uint32_variant

KIND, RECORD_TYPE, RECORD_SIZE = 0x5D706996, 215, 112
TURN_KIND, TURN_RECORD_TYPE, TURN_RECORD_SIZE = 0x11C07B90, 8, 96
CITY_PROPERTY_KIND, PROPERTY_KEY = 0x30FBF8D2, 0xD6FCF3E4
_CS_TRADERS_HASH = 0x45A61D8B
PROPERTY_SOURCE_REF = ('evidence/host-xp2-bbg-trade-city-property-source.json',
                       '0885002b5ef10ad7a8cb635f1cfeacc7bcbf712e3b2b9ac220931bad8e002ac3')
TURN_SOURCE_REF = ('evidence/host-xp2-current-local-turn-begin-reconciled.json',
                   'fd30908ed96000f305e0407dbcc7c7f02cab2e5d6aebedd0da1975f9e577269e')
TURN_CORE_SLICES = ((0x5e1f0, 24), (0x7f6bf, 24), (0x91feb, 24),
                    (0xb9426, 24), (0xc3404, 24))
_RECEIVER_EXPECTED = {
    'observer_registered': False, 'state_pointer_nonnull': True,
    'pre_hook': None, 'post_hook': None, 'subscriber_count': 0,
    'state_flags': 0,
}


def _profile(image):
    _require_image(image)
    proof = _source(PROFILE_REF)
    route = proof['routes']['trade_activity']
    producer = _source(('work/trade-common-client/xp2-current-trade-core-producers.json',
                        '5d6d5cbd489f2f3f7f0d6d493a744aaf24bbabc3df1d2383123cea082ca0a39f'))
    if (proof.get('schema') != 'civ6-host.xp2-current-callback-corrections.static.v1'
            or proof.get('native_effect_verified') is not False
            or proof.get('execution_profile', {}).get('id') != CURRENT_PROFILE_ID
            or route.get('kind') != hex(KIND) or route.get('record_type') != RECORD_TYPE
            or route.get('record_size') != RECORD_SIZE
            or route.get('subscriber_name') != 'GameCoreEvent::TradeRouteActivityChanged'
            or route.get('registered_callback', {}).get('rva') != '0x1536b0'
            or route.get('registered_callback', {}).get('sha256') != 'f90cf98e9c2e0342aad4bc8ea4bb6979bbb0e1802b0b057c5d45a79099541deb'
            or route.get('writer', {}).get('rva') != '0x13a2c0'
            or route.get('writer', {}).get('sha256') != '6146bfc171c8d4960ea23d4b2103c3eb0d190ea0a06132773a61522cd9be3e20'
            or route.get('handler', {}).get('rva') != '0xda7f0'
            or route.get('handler', {}).get('sha256') != '25ce9c3f9d6813df5d85c697de9808c565c069d92faed30c4dc849d623804bc9'
            or producer.get('schema') != 'civ6-host.xp2-current-trade-core-producers.static.v1'
            or producer.get('installed_core', {}).get('sha256') != CURRENT_CORE_SHA256
            or producer.get('dispatch_kind') != hex(KIND)):
        raise ValueError('Current BBG trade activity source profile differs')
    args = _source(('work/trade-common-client/xp2-current-trade-lua-marshalling.json',
                    '3c61871ab6e3ea9523b6bf1f7bd56edba52726f811a0873209abc8e2bdf40a96'))
    expected = [('player_id', 88, 32, True), ('origin_player_id', 96, 16, True),
                ('origin_city_id', 100, 32, True), ('target_player_id', 104, 16, True),
                ('target_city_id', 108, 32, True)]
    actual = [(row['name'], row['expected_record_offset'], row['integer_width'], row['signed'])
              for row in args.get('lua_arguments', ())]
    if actual != expected or args.get('typed_record') != RECORD_TYPE:
        raise ValueError('Current BBG trade Lua marshal offsets differ')
    if (args.get('installed_exe', {}).get('sha256') != CURRENT_EXE_SHA256
            or args.get('corrected_source', {}).get('sha256') != PROFILE_SHA256):
        raise ValueError('BBG trade Lua marshalling is detached from the selected source profile')
    return proof, producer


def _turn_source(image):
    _require_image(image)
    receipt = _source(TURN_SOURCE_REF)
    if (receipt.get('schema') != 'civ6-host.xp2-current-local-turn-begin.static.v1'
            or receipt.get('static_only') is not True or receipt.get('native_execution') is not False
            or receipt.get('native_effect_verified') is not False
            or receipt.get('images') != {'execution_profile_id': CURRENT_PROFILE_ID,
                'exe_sha256': CURRENT_EXE_SHA256, 'core_sha256': CURRENT_CORE_SHA256}
            or receipt.get('event', {}).get('kind') != hex(TURN_KIND)
            or receipt.get('event', {}).get('record_type') != TURN_RECORD_TYPE
            or receipt.get('event', {}).get('record_size') != TURN_RECORD_SIZE
            or receipt.get('event', {}).get('name') != 'GameCoreEvent::LocalPlayerTurnBegin'
            or receipt.get('event', {}).get('registration', {}).get('callback_rva') != '0x148e90'
            or receipt.get('event', {}).get('registration', {}).get('callback_association_rva') != '0x14cfaf'
            or receipt.get('event', {}).get('registration', {}).get('key_insert_rva') != '0x14cf9f'
            or receipt.get('event', {}).get('callback', {}).get('writer_call_rva') != '0x148f47'
            or receipt.get('event', {}).get('callback', {}).get('writer_rva') != '0x11dc30'
            or receipt.get('event', {}).get('queue_writer', {}).get('record_type_write_rva') != '0x11dcd8'
            or receipt.get('event', {}).get('queue_writer', {}).get('record_size_write_rva') != '0x11dcd2'
            or receipt.get('event', {}).get('name_reference', {}).get('xref_rva') != '0xdbc30'
            or receipt.get('event', {}).get('name_reference', {}).get('setup_rva') != '0xc4ee0'
            or [(int(row['rva'], 16), row['bytes']) for row in receipt.get('core_producers', ())]
                != list(TURN_CORE_SLICES)):
        raise ValueError('Current LocalPlayerTurnBegin source receipt differs')
    from civ6_host.runtime.native.native_event_11c07b90 import EVENT_KIND as adapter_kind
    from civ6_host.runtime.native.native_event_11c07b90 import RECORD_SIZE as adapter_size
    if adapter_kind != TURN_KIND or adapter_size != TURN_RECORD_SIZE:
        raise ValueError('LocalPlayerTurnBegin typed adapter contract differs')
    return receipt


def source_dependencies(*, execution_image):
    """Static source dependencies for current trade and turn-begin consumers."""
    _profile(execution_image)
    _turn_source(execution_image)
    _property_source(execution_image)
    root = resolve_path(resource_root())
    refs = (TURN_SOURCE_REF, PROPERTY_SOURCE_REF, PROFILE_REF,
            ('work/trade-common-client/xp2-current-trade-core-producers.json',
             '5d6d5cbd489f2f3f7f0d6d493a744aaf24bbabc3df1d2383123cea082ca0a39f'),
            ('work/trade-common-client/xp2-current-trade-lua-marshalling.json',
             '3c61871ab6e3ea9523b6bf1f7bd56edba52726f811a0873209abc8e2bdf40a96'))
    return {**{str(resolve_path(root / row[0]).resolve()): row[1] for row in refs},
            **amani.source_dependencies(execution_image=execution_image),
            **promotion.source_dependencies(execution_image=execution_image),
            **spy.source_dependencies(execution_image=execution_image)}


def _property_source(image):
    _require_image(image)
    receipt = _source(PROPERTY_SOURCE_REF)
    sample, exe = receipt['native_sample'], receipt['executable']
    if (receipt['schema'] != 'civ6-host.xp2-bbg-trade-city-property-source.v1'
            or receipt['core_sha256'] != CURRENT_CORE_SHA256 or receipt['exe_sha256'] != CURRENT_EXE_SHA256
            or sample['script'] != 'GameplaySetCSTrader' or sample['property_name'] != 'CS_TRADERS'
            or (sample['kind'], sample['property_key']) != (hex(CITY_PROPERTY_KIND), hex(PROPERTY_KEY))
            or (sample['variant_tag'], sample['property_hash'], sample['variant_flags']) != (2, '0x45a61d8b', 0)
            or exe['callback_uses_normalized_descriptor_only'] is not True
            or (exe['writer_record_type'], exe['writer_record_size']) != (90, 96)
            or receipt['pending_scope_only'] is not True):
        raise ValueError('Current BBG city property source receipt differs')
    return receipt['core_spans']


@contextmanager
def expect_city_property(owner, player, city):
    if (owner.bbg_trade_event_profile is None or owner._bbg_trade_expected_property is not None
            or owner.active_kind is not None or owner.pending):
        raise ValueError('BBG property write requires the idle, owned feedback boundary')
    owner._bbg_trade_expected_property = (player, city)
    try:
        yield
    finally:
        owner._bbg_trade_expected_property = None


def dispatch_city_property(owner, fields, borrowed_argument):
    from .native.native_event_99e85ec6 import decode_fields

    if (owner._bbg_trade_expected_property is None
            or _uint32_variant(fields.get(PROPERTY_KEY), 2, 'CS_TRADERS property') != _CS_TRADERS_HASH):
        raise ValueError('Unqualified current BBG city property notification')
    descriptor_fields = {key: value for key, value in fields.items() if key != PROPERTY_KEY}
    city = decode_fields(descriptor_fields, owner.read)
    if (city.owner, city.item_id) != owner._bbg_trade_expected_property:
        raise ValueError('BBG city property notification refers to another city')
    # The official current EXE callback forwards only the normalized descriptor.
    # Keep the inherited record/consumer and the GameCore property write.
    result = owner._dispatch_fields(CITY_PROPERTY_KIND, descriptor_fields, borrowed_argument=borrowed_argument)
    owner.emit('xp2_bbg_trade_city_property_notification', city_id=city.item_id, player_id=city.owner,
               property_name='CS_TRADERS', source_sha256=PROPERTY_SOURCE_REF[1])
    return result


def _check_owner(owner, backend, image):
    owner._check(); backend.check_thread()
    from .xp1_continuation import SavedContinuation
    token = getattr(backend, '_xp1_continuation', None)
    if (owner._foundation_backend is not backend or backend.core is not owner.deferred.core
            or backend.host is not owner.arguments.host or backend.context != owner.deferred.context
            or type(token) is not SavedContinuation or token.owner is not backend
            or token.prefix is not backend.prefix or token.prefix.deferred_events is not owner.deferred
            or getattr(backend.profile, 'execution_image', None) is not image
            or getattr(backend.profile, 'core_sha256', None) != CURRENT_CORE_SHA256
            or getattr(backend.core, '_civ6_host_execution_image', None) is not image
            or owner.deferred.cache_core_sha256 != image.reference_core_sha256
            or owner.deferred.cache_core_sha256 != backend.load_abi.core_sha256
            or owner.per_thread_hook_present is not False
            or owner.writer_metadata_callback_present is not False
            or owner.normalizer_transform_present is not False
            or owner.dynamic_event_registration_present is not False
            or owner.entity_listener_count != 0):
        raise ValueError('BBG trade activity requires the exact current composed XP2 owner')


def enable(owner, backend, receiver, *, on_local_turn_begin, on_governor=None, on_promotion=None, on_spy=None):
    """Install exact BBG feedback receivers on one owned FIFO."""
    image = getattr(getattr(backend, 'profile', None), 'execution_image', None)
    proof, producer = _profile(image)
    turn_source = _turn_source(image)
    property_spans = _property_source(image)
    _check_owner(owner, backend, image)
    if (not callable(receiver) or not callable(on_local_turn_begin)
            or (on_governor is not None and not callable(on_governor))
            or (on_promotion is not None and not callable(on_promotion))
            or (on_spy is not None and not callable(on_spy))
            or owner.bbg_trade_event_profile is not None
            or owner.arguments.depth or owner.active_kind is not None or owner.pending
            or owner.deferred._draining_empty_receivers or owner.host_notification_counter
            or owner.host_metadata_counter):
        raise ValueError('BBG trade receiver requires one idle A0 owner and an exact callable')
    if any(owner.profile.record_sizes.get(record_type) != size
           or owner.profile.record_types_by_kind.get(kind) != frozenset({record_type})
           for kind, record_type, size in ((KIND, RECORD_TYPE, RECORD_SIZE),
                                           (TURN_KIND, TURN_RECORD_TYPE, TURN_RECORD_SIZE))):
        raise ValueError('BBG trade receiver does not match the inherited A0 records')
    raw = owner.read(backend.core._handle + int(producer['dispatch']['rva'], 16),
                     producer['dispatch']['bytes'])
    if len(raw) != producer['dispatch']['bytes'] or hashlib.sha256(raw).hexdigest() != producer['dispatch']['sha256']:
        raise ValueError('Live current BBG trade producer differs from pinned evidence')
    for row in producer['callsites']:
        call = owner.read(backend.core._handle + int(row['rva'], 16), row['bytes'])
        if len(call) != row['bytes'] or hashlib.sha256(call).hexdigest() != row['sha256']:
            raise ValueError('Live current BBG trade callsite differs from pinned evidence')
    for row in (*turn_source['core_producers'], *property_spans):
        raw = owner.read(backend.core._handle + int(row['rva'], 16), row['bytes'])
        if len(raw) != row['bytes'] or hashlib.sha256(raw).hexdigest() != row['sha256']:
            raise ValueError('Live current BBG feedback Core producer differs at ' + row['rva'])
    if owner.empty_receiver_state != _RECEIVER_EXPECTED:
        raise ValueError('BBG trade receiver requires the exact owned empty subscriber state')
    by_kind = {KIND: frozenset({RECORD_TYPE}), TURN_KIND: frozenset({TURN_RECORD_TYPE})}
    sizes = {RECORD_TYPE: RECORD_SIZE, TURN_RECORD_TYPE: TURN_RECORD_SIZE}
    source_hash = PROFILE_SHA256 + TURN_SOURCE_REF[1]
    if on_governor is not None:
        if (owner.history_event_profile is None
                or owner.history_event_profile.record_types_by_kind.get(amani.GOVERNOR_ASSIGNED)
                   != frozenset({amani.ASSIGNED_RECORD})
                or owner.profile.record_types_by_kind.get(amani.GOVERNOR_CHANGED)
                   != frozenset({amani.CHANGED_RECORD})
                or owner.handles_kind(amani.PLAYER_PROPERTY) or owner.handles_kind(amani.PLOT_PROPERTY)):
            raise ValueError('BBG Amani receiver does not match the retained governor producers')
        amani.verify_live(owner, backend, image)
        by_kind.update({amani.GOVERNOR_ASSIGNED: frozenset({amani.ASSIGNED_RECORD}),
                        amani.GOVERNOR_CHANGED: frozenset({amani.CHANGED_RECORD}),
                        amani.PLAYER_PROPERTY: frozenset(),
                        amani.PLOT_PROPERTY: frozenset({amani.PLOT_RECORD})})
        sizes.update({amani.ASSIGNED_RECORD: 112, amani.CHANGED_RECORD: 96, amani.PLOT_RECORD: 96})
        source_hash += amani.SOURCE[1] + amani.PLOT_SOURCE[1]
    if on_promotion is not None:
        if (owner.profile.record_types_by_kind.get(promotion.KIND) != frozenset({promotion.RECORD_TYPE})
                or owner.profile.record_sizes.get(promotion.RECORD_TYPE) != promotion.RECORD_SIZE):
            raise ValueError('BBG promotion receiver does not match the retained unit producer')
        promotion.verify_live(image, backend.core._handle, owner.read)
        by_kind[promotion.KIND] = frozenset({promotion.RECORD_TYPE})
        sizes[promotion.RECORD_TYPE] = promotion.RECORD_SIZE
        source_hash += promotion.SOURCE[1]
    if on_spy is not None:
        if owner.handles_kind(spy.KIND) or owner.handles_record(spy.RECORD_TYPE):
            raise ValueError('BBG spy receiver conflicts with a retained event family')
        spy.verify_live(image, backend.core._handle, owner.read)
        by_kind[spy.KIND] = frozenset({spy.RECORD_TYPE})
        sizes[spy.RECORD_TYPE] = spy.RECORD_SIZE
        source_hash += spy.SOURCE[1] + spy.FIFO_SOURCE[1]
    profile = A0FamilyProfile(MappingProxyType(by_kind), MappingProxyType(sizes),
                              hashlib.sha256(source_hash.encode('ascii')).hexdigest())
    owner.bbg_trade_event_profile = owner._bbg_trade_event_profile = profile
    owner._bbg_trade_backend = backend
    owner._bbg_trade_image_id = CURRENT_PROFILE_ID
    owner._bbg_trade_receiver = receiver
    owner._bbg_trade_callback = receiver
    owner._bbg_turn_receiver = on_local_turn_begin
    owner._bbg_turn_callback = on_local_turn_begin
    owner._bbg_amani_receiver = owner._bbg_amani_callback = on_governor
    owner._bbg_promotion_receiver = owner._bbg_promotion_callback = on_promotion
    owner._bbg_spy_receiver = owner._bbg_spy_callback = on_spy
    owner._bbg_amani_property_scope = None
    owner._bbg_trade_expected_property = None
    owner._bbg_trade_max_pending = min(owner.limit, 1024)
    owner._bbg_trade_receiver_state = dict(_RECEIVER_EXPECTED)
    return owner


def dispatch(owner, kind, fields, borrowed_argument):
    if kind not in owner.bbg_trade_event_profile.record_types_by_kind or owner._bbg_trade_image_id != CURRENT_PROFILE_ID:
        raise ValueError('BBG trade event is outside its installed source profile')
    if len(owner.pending) >= owner._bbg_trade_max_pending or owner._sequence >= 0x7fffffff:
        raise RuntimeError('BBG trade/local turn FIFO capacity exhausted; event refused losslessly')
    if kind == amani.GOVERNOR_ASSIGNED:
        from .a0_foundation_events import dispatch_history
        return dispatch_history(owner, kind, fields)
    if kind in (amani.GOVERNOR_CHANGED, promotion.KIND):
        return owner._dispatch_fields(kind, fields, borrowed_argument=borrowed_argument)
    if kind in (amani.PLAYER_PROPERTY, amani.PLOT_PROPERTY):
        return amani.dispatch_property(owner, kind, fields)
    if kind == spy.KIND:
        owner._enqueue(spy.encode_event(fields, owner._sequence + 1))
        return 0
    if kind == TURN_KIND:
        from civ6_host.runtime.native.native_event_11c07b90 import decode_fields
        from civ6_host.runtime.native.native_event_11c07b90 import encode_11c07b90_record
        event = decode_fields(fields)
        record = encode_11c07b90_record(owner._sequence + 1, selector=event['selector'])
        owner._enqueue(record)
        return 0
    from civ6_host.runtime.native.native_event_5d706996 import decode_fields
    decoded = decode_fields(fields, owner.read)
    # selector is the current player. Descriptor owners and ids are the
    # origin/target player and city values consumed by the official marshaller.
    player_id = decoded.selector if decoded.selector < 0x80000000 else decoded.selector - 0x100000000
    values = (player_id, _signed(decoded.first_owner, 16), _signed(decoded.first_id, 32),
              _signed(decoded.second_owner, 16), _signed(decoded.second_id, 32))
    sequence = owner._sequence + 1
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<IIII', record, 0, RECORD_SIZE, RECORD_TYPE, sequence, 0)
    struct.pack_into('<I', record, 80, sequence)
    struct.pack_into('<i', record, 88, values[0])
    struct.pack_into('<h', record, 96, values[1]); struct.pack_into('<i', record, 100, values[2])
    struct.pack_into('<h', record, 104, values[3]); struct.pack_into('<i', record, 108, values[4])
    owner._enqueue(bytes(record))
    return 0


def _signed(value, width):
    if type(value) is not int or not 0 <= value < 1 << width:
        raise ValueError('BBG trade scalar is outside its pinned integer width')
    return value - (1 << width) if value >= 1 << (width - 1) else value


def consume(owner, record, sequence):
    deferred = owner.deferred
    record_type = int.from_bytes(record[4:8], 'little') if len(record) >= 8 else None
    sizes = owner.bbg_trade_event_profile.record_sizes
    if (owner._bbg_trade_image_id != CURRENT_PROFILE_ID
            or owner._bbg_trade_backend is not backend_for(owner)
            or not deferred._draining_empty_receivers or not deferred.pending
            or deferred.pending[0] is not record or sequence != deferred.consumed_count + 1
            or record_type not in sizes or len(record) != sizes[record_type]
            or int.from_bytes(record[8:12], 'little') != sequence):
        raise ValueError('BBG trade consumer lost its exact owned FIFO head')
    if record_type == amani.PLOT_RECORD:
        values = amani.validate_plot_record(owner, record, sequence)
    elif record_type in (amani.ASSIGNED_RECORD, amani.CHANGED_RECORD):
        callback = owner._bbg_amani_callback
        if callback is not owner._bbg_amani_receiver or not callable(callback):
            raise RuntimeError('BBG Amani receiver callable was replaced')
        from .xp2_bbg_amani import event_request
        values = (sequence, *event_request(record, sequence))
        callback(*values)
    elif record_type == promotion.RECORD_TYPE:
        callback = owner._bbg_promotion_callback
        if callback is not owner._bbg_promotion_receiver or not callable(callback):
            raise RuntimeError('BBG promotion receiver callable was replaced')
        values = (sequence, *promotion.event_request(record, sequence))
        callback(*values)
    elif record_type == spy.RECORD_TYPE:
        callback = owner._bbg_spy_callback
        if callback is not owner._bbg_spy_receiver or not callable(callback):
            raise RuntimeError('BBG spy receiver callable was replaced')
        values = (sequence, *spy.event_fields(record, sequence))
        callback(*values)
    elif record_type == TURN_RECORD_TYPE:
        callback = owner._bbg_turn_callback
        if (callback is not owner._bbg_turn_receiver or not callable(callback)
                or int.from_bytes(record[80:84], 'little') != sequence
                or int.from_bytes(record[84:88], 'little') != 0):
            raise RuntimeError('LocalPlayerTurnBegin receiver callable or payload was replaced')
        callback(sequence)
        values = (sequence,)
    else:
        callback = owner._bbg_trade_callback
        if callback is not owner._bbg_trade_receiver or not callable(callback):
            raise RuntimeError('BBG trade receiver callable was replaced')
        if int.from_bytes(record[80:84], 'little') != sequence:
            raise ValueError('BBG trade record sequence differs')
        values = (sequence, struct.unpack_from('<i', record, 88)[0],
                  struct.unpack_from('<h', record, 96)[0], struct.unpack_from('<i', record, 100)[0],
                  struct.unpack_from('<h', record, 104)[0], struct.unpack_from('<i', record, 108)[0])
        callback(*values)
    deferred.pending.pop(0); deferred.consumed_count += 1
    deferred.consumed_bytes += len(record); deferred.consumed_digest.update(record)
    return values


def backend_for(owner):
    return owner._bbg_trade_backend
