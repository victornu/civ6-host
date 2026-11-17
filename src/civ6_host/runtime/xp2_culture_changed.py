"""Current Gathering Storm CultureChanged notification on the owned FIFO."""

from hashlib import sha256
from pathlib import Path
import struct
from types import MappingProxyType

from .a0_family_source import A0FamilyProfile
from .a0_policy_unlock_current import CURRENT_CORE_SHA256, CURRENT_EXE_SHA256, _require_image
from .configuration_profiles import _source
from .execution_images import _PROFILE
from .native.native_application_mirror import decode_scalar
from .native.native_deferred_empty_profile import validate_empty_profile_record
from .native.native_player_event_domains import validate_sequence
from .native.native_unary_event_family import _METADATA
from .paths import resource_root
from .resource_resolution import resolve_path


KIND = 0x7124e66b
RECORD_TYPE = 0x10d
RECORD_SIZE = 96
METADATA_FLAG = 4
SOURCE = ('evidence/host-xp2-culture-changed-event-source.json',
          'a041ded47132475153296dc173c3cd7c51ffd8d2c3a6d120372b3b4e562b3311')
SELECTOR, FIRST_VALUE, SECOND_VALUE = 0xa1e5a149, 0xd6fcf3e4, 0xa1fbc372


def source():
    proof = _source(SOURCE)
    contract = proof['contract']
    if (proof['schema'] != 'civ6-host.xp2-culture-changed-event-source.v1'
            or proof['images']['core']['sha256'] != CURRENT_CORE_SHA256
            or proof['images']['exe']['sha256'] != CURRENT_EXE_SHA256
            or proof['static_only'] is not True or proof['native_execution'] is not False
            or (contract['kind'], contract['record_type'], contract['record_size'], contract['metadata_flag'])
                != (KIND, RECORD_TYPE, RECORD_SIZE, METADATA_FLAG)
            or contract['event_name'] != 'GameCoreEvent::CultureChanged'
            or contract['row_rva'] != 0x12c78b0 + RECORD_TYPE * 48
            or not contract['empty_subscriber_receiver'] or contract['native_gameplay_write'] is not False
            or (contract['normalizer_return'], contract['header_sequence_offset'], contract['sequence_offset'],
                contract['first_value_offset'], contract['second_value_offset']) != (0, 8, 80, 84, 88)):
        raise ValueError('Gathering Storm CultureChanged notification source differs')
    return proof


def source_dependencies(image):
    _require_image(image)
    proof = source()
    normalizer = proof['shared_normalizer']
    rows = [(resource_root() / SOURCE[0], SOURCE[1]),
            (resource_root() / normalizer['path'], normalizer['sha256'])]
    rows.extend((Path(row['path']), row['sha256']) for row in proof['images'].values())
    return {str(resolve_path(path).resolve()): digest for path, digest in rows}


def event_profile(core):
    if getattr(core, '_civ6_host_execution_image', None) is not _PROFILE:
        return None
    source()
    return A0FamilyProfile(MappingProxyType({KIND: frozenset((RECORD_TYPE,))}),
                           MappingProxyType({RECORD_TYPE: RECORD_SIZE}), SOURCE[1])


def receiver_row():
    proof = source()
    handler = proof['exe_spans']['handler']
    return dict(event_name=proof['contract']['event_name'], handler_va=hex(0x140000000 + handler['rva']),
                handler_body_sha256=handler['sha256'], record_sizes={RECORD_SIZE})


def encode_record(sequence, fields):
    validate_sequence(sequence)
    if type(fields) is not dict or set(fields) != {SELECTOR, FIRST_VALUE, SECOND_VALUE}:
        raise ValueError('Gathering Storm CultureChanged requires exactly three scalar variants')
    if decode_scalar(fields[SELECTOR], 3) != 0:
        raise ValueError('Gathering Storm CultureChanged selector differs')
    first = decode_scalar(fields[FIRST_VALUE], 2)
    second = decode_scalar(fields[SECOND_VALUE], 2)
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<4I', record, 0, RECORD_SIZE, RECORD_TYPE, sequence, 0)
    record[16:80] = _METADATA
    struct.pack_into('<I', record, 72, METADATA_FLAG)
    struct.pack_into('<III', record, 80, sequence, first, second)
    return bytes(record)


def dispatch(owner, fields, *, core):
    image = core._civ6_host_execution_image
    _require_image(image)
    if (owner.active_kind != KIND or owner.normalizer_transform_present is not False
            or owner.per_thread_hook_present is not False or owner.writer_metadata_callback_present is not False
            or type(owner.entity_listener_count) is not int or owner.entity_listener_count != 0):
        raise ValueError('Gathering Storm CultureChanged has an unqualified callback profile')
    for span in source()['core_spans'].values():
        raw = owner.read(core._handle + span['rva'], span['bytes'])
        if type(raw) is not bytes or len(raw) != span['bytes'] or sha256(raw).hexdigest() != span['sha256']:
            raise ValueError('Live Gathering Storm CultureChanged producer differs')
    record = encode_record(owner._sequence + 1, fields)
    validate_empty_profile_record(record, execution_image=image, **owner.empty_receiver_state)
    owner._enqueue(record)
    owner.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(KIND), queue_type=hex(RECORD_TYPE),
               record_hex=record.hex(), source_proof_sha256=SOURCE[1], payload_exposed_to_learner=False,
               eligible_for_training=False)
    return 0
