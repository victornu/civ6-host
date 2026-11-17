"""Installed XP2 deal history producer and empty receiver correspondence."""

from hashlib import sha256
from pathlib import Path

from .configuration_profiles import _source
from .execution_images import identity
from .paths import resource_root
from .resource_resolution import resolve_path


SOURCE = ('evidence/host-xp2-deal-history-receiver-source.json',
          '8715ffb1fbbe2126d6151419992a3a6a5c7e469d4163cc9caaffd7e29742423c')
KIND = 0xe2f6f44f
RECORD = 0x87
SIZE = 96


def source():
    proof = _source(SOURCE)
    if (proof['schema'] != 'civ6-host.xp2-deal-history-receiver.static.v1'
            or (proof['kind'], proof['record_type'], proof['record_size']) != (KIND, RECORD, SIZE)
            or proof['event_name'] != 'GameCoreEvent::DiplomacyDealEnacted'
            or proof['core_internal_dispatch_preserved'] is not True):
        raise ValueError('Installed deal-history source changed')
    return proof


def source_dependencies(image):
    proof = source()
    selected = identity(image)
    if (proof['images']['core']['sha256'] != selected['image_sha256']
            or Path(proof['images']['core']['path']).resolve() != Path(selected['path']).resolve()):
        raise ValueError('Deal history belongs to another GameCore image')
    exe = proof['images']['exe']
    return {str(resolve_path(resource_root() / SOURCE[0]).resolve()): SOURCE[1],
            str(resolve_path(Path(exe['path'])).resolve()): exe['sha256']}


def verify_live(base, read):
    for span in source()['core_spans']:
        raw = read(base+span['rva'],span['size'])
        if type(raw) is not bytes or len(raw) != span['size'] or sha256(raw).hexdigest() != span['sha256']:
            raise ValueError('Live deal-history producer or acknowledgement changed')


def encode_record(sequence, fields):
    from .native.native_scalar_event_encoder import _encode_profile_record, _read_u32_variant
    from .native.native_player_event_domains import validate_sequence

    tags = {0xa1e5a149:3, 0xd6fcf3e4:2, 0xa1fbc372:2, 0x38f292c8:2}
    if type(fields) is not dict or fields.keys() != tags.keys():
        raise ValueError('Installed deal history requires its four scalar fields')
    selector, first, second, _ = (_read_u32_variant(fields[key], tag, 'deal history')
                                  for key,tag in tags.items())
    if selector != 0 or not (0 <= first < 64 and 0 <= second < 64) or first == second:
        raise ValueError('Installed deal history has foreign participants or selector')
    validate_sequence(sequence)
    # GameCore's own event uses all four fields before calling the host.
    # The installed EXE reads the two player IDs for its deferred record.
    writer = dict(payload_value_count=2,writer_record_type=hex(RECORD))
    return _encode_profile_record(writer,sequence,(first,second))
