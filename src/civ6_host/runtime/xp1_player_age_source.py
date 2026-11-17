"""Installed Rise and Fall player-age producers and empty receivers."""

from functools import lru_cache
from hashlib import sha256
from pathlib import Path
from types import MappingProxyType

from .a0_family_source import _path, verify_pinned_files
from .configuration_profiles import _source
from .execution_images import _XP1_PROFILE, identity
from .xp2_history_event_profile import AGE_EVENTS, AGE_SOURCE


SOURCE = ('evidence/host-xp1-installed-age-notifications-source.json',
          '32623e6d0e54ff1027ca17da694d48704ad6da9ee8c8a49bab1d88a861318051')
EVENTS = AGE_EVENTS
SIZE = 96
_RECEIVERS = MappingProxyType({
    0x107: ('GameCoreEvent::PlayerAgeChanged', 'age_receiver_handler'),
    0x108: ('GameCoreEvent::PlayerDarkAgeChanged', 'dark_age_receiver_handler'),
})


@lru_cache(maxsize=1)
def _installed_source():
    proof = _source(SOURCE)
    contract = proof['contract']
    events = proof['events']
    retained = proof['references']['retained_host_age_writer_receiver']
    if (proof['schema'] != 'civ6-host.xp1-installed-age-notifications.static.v1'
            or proof['image'] != identity(_XP1_PROFILE)
            or (retained['path'], retained['sha256']) != AGE_SOURCE
            or set(events) != {hex(kind) for kind in EVENTS}
            or contract['selector'] != 0 or contract['scalar_flags'] != 0
            or contract['key_tags'] != {'0xa1e5a149': 3, '0xd6fcf3e4': 2}
            or contract['callback_reads_second'] is not False
            or contract['absent_second_default'] != 0
            or (contract['payload_sequence_offset'], contract['payload_value_offset'],
                contract['unwritten_second_offset']) != (80, 84, 88)
            or contract['observer_registered'] is not False
            or contract['state_pointer_nonnull'] is not True
            or any(contract[k] is not None for k in ('pre_hook', 'post_hook'))
            or (contract['subscriber_count'], contract['state_flags']) != (0, 0)
            or contract['optional_callback_registered'] is not False
            or contract['queue_metadata_service_registered'] is not False):
        raise ValueError('Installed Rise and Fall player-age source differs')
    for kind, (record, flag) in EVENTS.items():
        event = events[hex(kind)]
        name, handler = _RECEIVERS[record]
        if (event['record_type'], event['size'], event['metadata_flag'], event['name'],
                event['handler_rva']) != (record, SIZE, flag, name, proof['exe'][handler]['rva']):
            raise ValueError('Installed Rise and Fall player-age receiver differs')
    return proof


def source(execution_image):
    if execution_image is not _XP1_PROFILE:
        raise ValueError('Player-age events require the exact installed Rise and Fall image')
    return _installed_source()


def source_dependencies(execution_image):
    proof = source(execution_image)
    exe = proof['executable']
    pins = {str(_path(SOURCE[0]).resolve()): SOURCE[1],
            str(Path(execution_image.path).resolve()): execution_image.image_sha256,
            str(Path(exe['path']).resolve()): exe['sha256']}
    for ref in proof['references'].values():
        pins[str(_path(ref['path']).resolve())] = ref['sha256']
    verify_pinned_files(pins)
    return pins


def verify_live(core, read):
    proof = source(getattr(core, '_civ6_host_execution_image', None))
    for label, span in proof['core'].items():
        raw = read(core._handle + span['rva'], span['bytes'])
        if (type(raw) is not bytes or len(raw) != span['bytes']
                or sha256(raw).hexdigest() != span['sha256']):
            raise ValueError('Live Rise and Fall player-age source differs: ' + label)


def receiver_row(record_type):
    name, handler = _RECEIVERS[record_type]
    span = _installed_source()['exe'][handler]
    return dict(event_name=name, handler_va=hex(0x140000000 + span['rva']),
                record_sizes={SIZE}, handler_body_sha256=span['sha256'], source_sha256=SOURCE[1])
