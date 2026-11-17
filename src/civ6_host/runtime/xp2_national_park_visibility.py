"""Installed XP2 NationalParkVisibilityChanged on the saved-game A0 owner."""

from functools import lru_cache
from pathlib import Path
import struct

from .a0_family_source import _path, verify_pinned_files
from .a0_policy_unlock_current import _require_image
from .configuration_profiles import XP2_CORE_SHA256, _source
from .native.native_event_827289e6 import _copy_blob, query_optional_position
from .xp2_feature_reveal_source import _read_exact, _uint32_variant

SOURCE = ('evidence/host-xp2-national-park-visibility-source.json',
          '8f32c5c374ce33f297d673c1406b77dfa066ac1432d731a53ec6681cfa4f6a25')
KIND, RECORD_TYPE, RECORD_SIZE = 0xD5243371, 0xF6, 128
SELECTOR, PARK, POSITION, VISIBILITY = 0xA1E5A149, 0x1C6A0A9E, 0x8C468E3C, 0xF36F4928
PAIR, INDEX, VALUE, PLAYER = 0x5B55A347, 0xA1FBC372, 0x38F292C8, 0xF06A2AF2
_COMPACT = {SELECTOR: 3, PARK: 1024, POSITION: 13, VISIBILITY: 2}
_EXPANDED = {**_COMPACT, PAIR: 1024, INDEX: 2, VALUE: 2, PLAYER: 2}
_NO_COORDINATES = struct.pack('<ii', -9999, -9999)
_NO_PAIR = struct.pack('<HHI', 0xFFFF, 0, 0xFFFFFFFF)


@lru_cache(maxsize=1)
def source():
    proof = _source(SOURCE)
    route = proof['route']
    if (proof['schema'] != 'civ6-host.xp2-national-park-visibility-source.static.v1'
            or (route['kind'], route['record_type'], route['record_size']) !=
               (hex(KIND), RECORD_TYPE, RECORD_SIZE)
            or route['receiver_subscribers'] != 0 or route['receiver_pre_post_hook_count'] != 0
            or any(proof['fields'][name] != {hex(k): tag for k, tag in fields.items()}
                   for name, fields in (('compact', _COMPACT), ('expanded', _EXPANDED)))):
        raise ValueError('National park visibility source differs')
    return proof


def source_dependencies():
    proof = source()
    pins = {str(_path(SOURCE[0]).resolve()): SOURCE[1]}
    pins.update((str(_path(row['path']).resolve()), row['sha256']) for row in proof['references'])
    pins.update((str(Path(row['path']).resolve()), row['sha256']) for row in proof['images'].values())
    verify_pinned_files(pins)
    return pins


def core_fragments():
    for row in source()['spans'].values():
        if row['image'] == 'core':
            raw = bytes.fromhex(row['bytes_hex'])
            if len(raw) != row['size']:
                raise ValueError('National park visibility live source span differs')
            yield int(row['rva'], 16), raw


def verify_live(core, read):
    image = getattr(core, '_civ6_host_execution_image', None)
    _require_image(image)
    if image.image_sha256 != source()['images']['core']['sha256']:
        raise ValueError('National park visibility image differs')
    for rva, raw in core_fragments():
        if _read_exact(read, core._handle + rva, len(raw)) != raw:
            raise ValueError('National park visibility live producer differs')


def receiver_row():
    proof = source()
    handler = proof['spans']['receiver']
    return dict(event_name=proof['route']['receiver_name'], record_sizes={RECORD_SIZE},
                handler_va=hex(0x140000000 + int(handler['rva'], 16)),
                handler_body_sha256=handler['sha256'])


def dispatch(owner, fields):
    from .a0_foundation_events import require_borrow
    from .native.native_notification_metadata import metadata_scope_transition
    from .native.native_player_event_domains import validate_sequence
    from .native.native_unary_event_family import _METADATA

    # The foundation dispatcher already checked this continuation's populated
    # cache. This owner cannot enter from the EXE's LoadGame front-end view.
    backend = require_borrow(owner).owner
    owner._require_no_f391_reentry()
    verify_live(backend.core, owner.read)
    if (owner.active_kind != KIND or owner.foundation_core_sha256 != XP2_CORE_SHA256
            or len(owner.pending) >= owner.limit):
        raise ValueError('National park visibility requires its installed A0 record owner')
    if type(fields) is not dict or fields.keys() not in (_COMPACT.keys(), _EXPANDED.keys()):
        raise ValueError('National park visibility field set differs')
    if _uint32_variant(fields[SELECTOR], 3, 'park selector') != 0:
        raise ValueError('National park visibility selector differs')
    visibility = _uint32_variant(fields[VISIBILITY], 2, 'park visibility')
    expanded = INDEX in fields
    if not expanded and visibility not in (0, 1, 2):
        raise ValueError('Compact national park visibility differs from the producer')
    descriptor = _copy_blob(fields[PARK], owner.read, 1024, 'national park descriptor')
    position = _copy_blob(fields[POSITION], owner.read, 13, 'national park position')
    pair, auxiliary_position, auxiliary_value = _NO_PAIR, _NO_COORDINATES, 0
    queried = False
    if expanded:
        pair = _copy_blob(fields[PAIR], owner.read, 1024, 'national park metadata pair')
        index = _uint32_variant(fields[INDEX], 2, 'park auxiliary index')
        value = _uint32_variant(fields[VALUE], 2, 'park auxiliary value')
        _uint32_variant(fields[PLAYER], 2, 'park perspective')
        if index < 1 << 31:
            auxiliary_position = query_optional_position(backend.core, backend.context, index,
                read=owner.read, core_sha256=XP2_CORE_SHA256)
            if type(auxiliary_position) is not bytes or len(auxiliary_position) != 8:
                raise ValueError('National park auxiliary map position has an invalid extent')
            auxiliary_value, queried = value, True

    n, m = owner.host_notification_counter, owner.host_metadata_counter
    flag, next_metadata = metadata_scope_transition(n, m)
    sequence = validate_sequence(owner._sequence + 1)
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<IIII', record, 0, RECORD_SIZE, RECORD_TYPE, sequence, 0)
    record[16:80] = _METADATA
    struct.pack_into('<I', record, 72, flag)
    struct.pack_into('<I4xI8sI8s8s8s', record, 80, sequence, visibility,
                     auxiliary_position, auxiliary_value, pair, descriptor, position)
    owner._enqueue(bytes(record))
    owner.host_metadata_counter = next_metadata
    owner.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(KIND),
               queue_type=hex(RECORD_TYPE), sequence=sequence, record_hex=record.hex(),
               source_proof_sha256=SOURCE[1], expanded_input=expanded, native_map_query=queried,
               host_notification_counter=n, metadata_counter_before=m, metadata_counter_after=next_metadata,
               consumer_validated=False, payload_exposed_to_learner=False, eligible_for_training=False)
    return 0
