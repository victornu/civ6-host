"""Current installed XP2 war/peace notifications on the owned empty FIFO."""
import hashlib
from pathlib import Path
import struct
from types import MappingProxyType

from .a0_family_source import A0FamilyProfile
from .a0_policy_unlock_current import CURRENT_CORE_SHA256, CURRENT_EXE_SHA256, _require_image
from .configuration_profiles import _source
from .paths import resource_root
from .resource_resolution import resolve_path


SOURCE = ('evidence/host-xp2-diplomacy-war-peace-event-source.json',
          '3f9df3262871b1cc33c3850ce7ea594d69bba49d991a9de9706fcc86d7048629')
RECORDS = {
    0x7dddaff1: (126, 'GameCoreEvent::DiplomacyDeclareWar'),
    0x41d2c9c0: (127, 'GameCoreEvent::DiplomacyMakePeace'),
}
RECORD_SIZE = 112
FIELD_TAGS = {0xa1e5a149: 3, 0xd6fcf3e4: 2, 0xa1fbc372: 2}


def source():
    proof = _source(SOURCE)
    if (proof['schema'] != 'civ6-host.xp2-diplomacy-war-peace-event-source.v1'
            or proof['images']['core']['sha256'] != CURRENT_CORE_SHA256
            or proof['images']['exe']['sha256'] != CURRENT_EXE_SHA256
            or {int(k): (v['type'], v['name']) for k, v in proof['routes'].items()} != RECORDS
            or any(r['kind'] != int(k) or r['size'] != RECORD_SIZE
                   or r['row_rva'] != 0x12c78b0 + r['type'] * 0x30
                   for k, r in proof['routes'].items())
            or proof['source_contract']['post_writer_import'] != 'KERNEL32.dll!LeaveCriticalSection'):
        raise ValueError('Current XP2 diplomacy notification source differs')
    return proof


def source_dependencies(execution_image):
    _require_image(execution_image)
    images = source()['images']
    pins = {str(resolve_path(Path(row['path'])).resolve()): row['sha256']
            for row in images.values()}
    if pins.get(str(Path(execution_image.path).resolve())) != execution_image.image_sha256:
        raise ValueError('Diplomacy notification belongs to another XP2 image')
    pins[str((resource_root() / SOURCE[0]).resolve())] = SOURCE[1]
    return pins


def event_profile(core):
    from .execution_images import _PROFILE

    if getattr(core, '_civ6_host_execution_image', None) is not _PROFILE:
        return None
    source()
    return A0FamilyProfile(
        MappingProxyType({k: frozenset((row[0],)) for k, row in RECORDS.items()}),
        MappingProxyType({row[0]: RECORD_SIZE for row in RECORDS.values()}), SOURCE[1])


def receiver_row(record_type):
    route, = (row for row in source()['routes'].values() if row['type'] == record_type)
    handler = route['handler']
    return dict(event_name=route['name'], handler_va=hex(0x140000000 + handler['rva']),
                handler_body_sha256=handler['sha256'], record_sizes={RECORD_SIZE})


def encode_record(kind, sequence, raw_fields):
    from .native.native_application_mirror import decode_scalar
    from .native.native_player_event_domains import validate_sequence
    from .native.native_unary_event_family import _METADATA

    validate_sequence(sequence)
    if type(raw_fields) is not dict or set(raw_fields) != set(FIELD_TAGS):
        raise ValueError('XP2 diplomacy notification requires three scalar fields')
    fields = {key: decode_scalar(raw_fields[key], tag) for key, tag in FIELD_TAGS.items()}
    record_type = RECORDS[kind][0]
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<4I', record, 0, RECORD_SIZE, record_type, sequence, 0)
    record[16:80] = _METADATA
    struct.pack_into('<I4xII', record, 80, sequence, fields[0xd6fcf3e4], fields[0xa1fbc372])
    return bytes(record)


def dispatch(owner, kind, raw_fields, *, core):
    from .native.native_deferred_empty_profile import validate_empty_profile_record

    image = core._civ6_host_execution_image
    _require_image(image)
    if (owner.active_kind != kind or owner.normalizer_transform_present is not False
            or owner.per_thread_hook_present is not False
            or owner.writer_metadata_callback_present is not False
            or type(owner.entity_listener_count) is not int or owner.entity_listener_count != 0):
        raise ValueError('XP2 diplomacy notification has unqualified native callbacks')
    proof = source()
    for span in (proof['routes'][str(kind)]['producer'], proof['common_producer']):
        raw = owner.read(core._handle + span['rva'], span['bytes'])
        if type(raw) is not bytes or hashlib.sha256(raw).hexdigest() != span['sha256']:
            raise ValueError('Live XP2 diplomacy notification producer differs')
    record = encode_record(kind, owner._sequence + 1, raw_fields)
    validate_empty_profile_record(record, execution_image=image, **owner.empty_receiver_state)
    owner._enqueue(record)
    owner.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind),
               queue_type=hex(RECORDS[kind][0]), record_hex=record.hex(),
               source_proof_sha256=SOURCE[1], payload_exposed_to_learner=False,
               eligible_for_training=False)
    return 0
