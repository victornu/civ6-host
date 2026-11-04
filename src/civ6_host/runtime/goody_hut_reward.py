"""Official GoodyHutReward notification; gameplay remains in the GameCore.

The Core applies the reward and dispatches its internal event before calling
the host. This adapter copies the borrowed descriptor, reuses the existing
queue serializer, and admits only the proven empty presentation receiver.
Private event metadata is never a player observation or an action result.
"""
from __future__ import annotations

import struct
from .configuration_profiles import BASE_CORE_SHA256,XP1_CORE_SHA256,XP2_CORE_SHA256

EVENT_KIND, RECORD_TYPE, RECORD_SIZE = 0xC08FC0F9, 0x103, 0x70
SELECTOR_KEY, VALUE_KEY, SECOND_KEY = 0xA1E5A149, 0xD6FCF3E4, 0xA1FBC372
UNIT_KEY, CITY_KEY = 0xF0548BB7, 0x23739F42
PADDING_POLICY = 'headless-zero-uninitialized-stack'
CORE_PROOF_PATH = 'work/host-simultaneous/dialogue/event-c08fc0f9-core.json'
CORE_PROOF_SHA256 = '6ddafa215816e4fca42e4ebe8331758fda908ef92b7016a600498586472d23c8'
EXE_PROOF_PATH = 'work/host-simultaneous/dialogue/event-c08fc0f9-exe-followup.json'
EXE_PROOF_SHA256 = '8ec9ebfd6a1de5d024eb9fc715bdd52916165d4a951043bc515274070c23e76d'


def verify_source(*,core_sha256=BASE_CORE_SHA256):
    if core_sha256 not in (BASE_CORE_SHA256,XP1_CORE_SHA256,XP2_CORE_SHA256):
        raise ValueError('Unqualified GoodyHutReward engine')
    from .provenance import resource_root
    from .native.native_source_cache import load_pinned_json
    if not EXE_PROOF_SHA256:
        raise RuntimeError('GoodyHutReward receiver proof is not pinned')
    core = load_pinned_json(resource_root() / CORE_PROOF_PATH, CORE_PROOF_SHA256)
    exe = load_pinned_json(resource_root() / EXE_PROOF_PATH, EXE_PROOF_SHA256)
    from .native.native_configuration_finalization import CORE_SHA256, EXE_SHA256
    captures = core['captures']
    row = exe['runtime_row_initialization']
    comparison = exe['writer_comparisons']['c08_vs_a603']
    if (core['schema'] != 'civ6-host.event-c08-core-source.v1'
            or dict(core['images']) != dict(core_sha256=CORE_SHA256, exe_sha256=EXE_SHA256)
            or core['source_validation']['all_capture_bytes_checked_against_pinned_pe'] is not True
            or core['source_validation']['critical_instruction_guards_matched'] is not True
            or captures['witness_caller']['code_sha256'] != 'cb8dbbbe55af3c9190d777943c4b34dec8d5ce01376e61c9d511bde5233df419'
            or captures['descriptor_two_scalar_producer']['code_sha256'] != 'c76f0cd26d053e0e8b93195e202f142f2199336718b8cd1f2c2aa77600fd4311'
            or captures['normalizer']['code_sha256'] != 'c757d2f0c927f36e058ff5e57350a80beac1db2a89d3940fcb5e89c05545f23e'
            or exe['schema'] != 'civ6rl.native_event_c08fc0f9_exe_followup.v1'
            or exe['binary']['exe_sha256'] != EXE_SHA256
            or row['event_name']['text'] != 'GameCoreEvent::GoodyHutReward'
            or row['row']['record_type'] != '0x103'
            or row['row']['setup_rip_target'] != '0x1412c9940'
            or row['initializer']['setup_va'] != '0x1400c5ce0'
            or row['setup_body_sha256'] != '84c89f826dfdf05bea4d8df54b90b602de3deaeb12beab98ea4d9d8b240685f9'
            or row['setter']['va'] != '0x1400d4c30'
            or row['setter']['body_sha256'] != '3b84daafa48d8acac5b42b510132722c9993fce9245ab3aac391c078b1936bbb'
            or row['shared_subscriber_dispatcher_capture']['code_sha256'] != '326ad0582020365181be9ed3b3e0f595e1bf834ef24f5afdf167d9ae56292bca'
            or row['handler_shape_matches_known_empty_rows']['equal'] is not True
            or exe['callback_c08']['body_sha256'] != '30f5d982d9c67d9ed3fd0813f5c42d60207718dcea2a02baa821720575bc99bc'
            or comparison['operations_equal_after_type_normalization'] is not True
            or comparison['c08']['code_sha256'] != '9fa91896d814ffe9ca2aac1981f8775752a3e530f62459a3ca23831f892d51b6'
            or comparison['a603']['code_sha256'] != 'b92d827a1b02c9105865efc8b71a079124b59a00a40429e7a5d2fc0edf9fa38b'):
        raise ValueError('GoodyHutReward source contract changed')
    if core_sha256==XP1_CORE_SHA256:
        from .xp1_goody_hut_profile import verify_source as selected_source
        return selected_source(),exe
    if core_sha256==XP2_CORE_SHA256:
        from .xp1_goody_hut_profile import verify_source as selected_source
        return selected_source(core_sha256=core_sha256),exe
    return core, exe


def receiver_row():
    # Importing this function from the generic row loader must not import the
    # event producer or serializer back through native_host_events.
    verify_source()
    return {
        'event_name': 'GameCoreEvent::GoodyHutReward',
        'handler_va': '0x1400d4c30',
        'handler_body_sha256': '3b84daafa48d8acac5b42b510132722c9993fce9245ab3aac391c078b1936bbb',
        'record_sizes': {RECORD_SIZE},
    }


def decode_fields(raw_fields, read, *, core_sha256=BASE_CORE_SHA256):
    verify_source(core_sha256=core_sha256)
    from .native.native_application_mirror import decode_scalar
    from .native.native_host_events import copy_eight_byte_variant
    from .native.native_event_a60328c5 import EventFields
    required = {SELECTOR_KEY, VALUE_KEY, SECOND_KEY}
    if (type(raw_fields) is not dict
            or set(raw_fields) not in (required | {UNIT_KEY}, required | {CITY_KEY})
            or any(type(raw) is not bytes or len(raw) != 24
                   for raw in raw_fields.values())):
        raise ValueError('GoodyHutReward requires the proven unit or city envelope')
    selector = decode_scalar(raw_fields[SELECTOR_KEY], 3)
    if selector != 0:
        raise ValueError('GoodyHutReward selector is outside the proven caller')
    value = decode_scalar(raw_fields[VALUE_KEY], 2)
    second = decode_scalar(raw_fields[SECOND_KEY], 2)
    key = UNIT_KEY if UNIT_KEY in raw_fields else CITY_KEY
    blob = copy_eight_byte_variant(raw_fields[key], read, expected_tag=0x400)
    owner, kind, identifier = struct.unpack('<HHI', blob)
    if kind != (1 if key == UNIT_KEY else 2):
        raise ValueError('GoodyHutReward descriptor contradicts its native key')
    if key == CITY_KEY:
        # EXE1CA2D0 puts the city in +18. EXE1480E0 reads only the unit
        # slot +8, which retains these native defaults in the city path.
        owner, identifier = 0xFFFF, 0xFFFFFFFF
    return EventFields(selector, value, second, owner, identifier)


def encode_record(sequence, fields, *, normalizer_transform_present,
                  per_thread_hook_present, writer_metadata_callback_present,
                  entity_listener_count, empty_receiver_state,
                  padding_policy=PADDING_POLICY,core_sha256=BASE_CORE_SHA256):
    verify_source(core_sha256=core_sha256)
    from .native import native_event_a60328c5 as sibling
    from .native.native_deferred_empty_profile import validate_empty_profile_record
    if type(entity_listener_count) is not int or entity_listener_count != 0:
        raise ValueError('GoodyHutReward requires the empty entity listener profile')
    if (type(empty_receiver_state) is not dict
            or set(empty_receiver_state) != {'observer_registered',
                'state_pointer_nonnull', 'pre_hook', 'post_hook',
                'subscriber_count', 'state_flags'}):
        raise ValueError('GoodyHutReward requires the complete receiver state')
    shape = bytearray(RECORD_SIZE)
    struct.pack_into('<II', shape, 0, RECORD_SIZE, RECORD_TYPE)
    validate_empty_profile_record(shape, **empty_receiver_state)
    # Source comparison proves identical writer operations except record type.
    # Callback differences are applied explicitly below, not inferred by size.
    record = bytearray(sibling.encode_record(sequence, fields,
        normalizer_transform_present=normalizer_transform_present,
        per_thread_hook_present=per_thread_hook_present,
        writer_metadata_callback_present=writer_metadata_callback_present,
        padding_policy=padding_policy))
    struct.pack_into('<I', record, 4, RECORD_TYPE)
    struct.pack_into('<I', record, 0x48, 4)
    if fields.owner == 0xFFFF or fields.unit_id == 0xFFFFFFFF:
        struct.pack_into('<HHI', record, 0x18, 0xFFFF, 0, 0xFFFFFFFF)
    validate_empty_profile_record(record, **empty_receiver_state)
    return bytes(record)


def enqueue(owner, raw_fields, *, core_sha256=BASE_CORE_SHA256):
    from .native.native_absent_305c2e09 import REGISTRY_PROFILE
    from .native.native_host_event_registry import EXE_EVENT_CALLBACKS
    from .native.native_player_event_domains import validate_sequence
    if (owner.callback_registry_profile != REGISTRY_PROFILE
            or owner.dynamic_event_registration_present is not False
            or EXE_EVENT_CALLBACKS.get(EVENT_KIND) != 0x1480E0):
        raise ValueError('GoodyHutReward callback registry differs')
    if len(owner.pending) >= owner.limit:
        raise RuntimeError('Native deferred queue bound exceeded')
    validate_sequence(owner._sequence + 1)
    fields = decode_fields(raw_fields, owner.read,core_sha256=core_sha256)
    record = encode_record(owner._sequence + 1, fields,
        normalizer_transform_present=owner.normalizer_transform_present,
        per_thread_hook_present=False, writer_metadata_callback_present=False,
        entity_listener_count=owner.entity_listener_count,
        empty_receiver_state=owner.empty_receiver_state,core_sha256=core_sha256)
    core_proof=CORE_PROOF_SHA256
    if core_sha256==XP1_CORE_SHA256:
        from .xp1_goody_hut_profile import SOURCE
        core_proof=SOURCE[1]
    elif core_sha256==XP2_CORE_SHA256:
        from .xp2_placement_event_source import SOURCE
        core_proof=SOURCE[1]
    owner._enqueue(record)
    owner.emit('native_deferred_host_event_enqueued',
        dispatch_kind=hex(EVENT_KIND), queue_type=hex(RECORD_TYPE),
        record_hex=record.hex(), pending_count=len(owner.pending),
        source_proof_sha256=EXE_PROOF_SHA256,
        core_proof_sha256=core_proof,
        source_descriptor='unit' if UNIT_KEY in raw_fields else 'city',
        native_internal_dispatch_repeated=False,
        reward_calculated_by_host=False,
        undefined_value_policy=PADDING_POLICY,
        undefined_value_is_native_default=False,
        undefined_record_ranges=[[0x4C, 0x50], [0x54, 0x58], [0x68, 0x70]],
        optional_preprocessing_hook_registered=False,
        queue_metadata_service_registered=False,
        empty_receiver_state_verified=True, consumer_validated=False,
        payload_exposed_to_learner=False, eligible_for_training=False,
        native_dispatch_return=0)
    # EXE1CA2D0 returns zero after dispatch, not a gameplay success value.
    return 0
