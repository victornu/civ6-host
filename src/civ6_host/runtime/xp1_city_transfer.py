"""Source-bound CityTransfered producer for the registered Rise and Fall image."""

import hashlib
from pathlib import Path

from . import xp2_capture_notification_source as registered
from . import xp2_city_occupation_event as codec
from .a0_family_source import _path, verify_pinned_files
from .configuration_profiles import _source
from .execution_images import _XP1_PROFILE


SOURCE = (
    'evidence/host-xp1-installed-city-transfer-source.json',
    'fbd1b6f3b7bfe588b16cad4c6a432ce4cf0832e447a54c5f88cdab24f0d06024',
)
SPANS = {
    'native_transfer_producer': (0x11050f, 189),
    'descriptor_variant': (0x51a690, 118),
    'scalar_variant': (0x51a710, 27),
    'event_dispatch': (0x519330, 224),
}


def source(execution_image):
    if execution_image is not _XP1_PROFILE:
        raise ValueError('CityTransfered requires the registered Rise and Fall image')
    proof = _source(SOURCE)
    registration = proof['shared_registration']
    contract = proof['contract']
    exe = registered.source()['images']['exe']
    if (proof['schema'] != 'civ6-host.xp1-installed-city-transfer.source.v1'
            or proof['image']['path'] != execution_image.path
            or proof['image']['sha256'] != execution_image.image_sha256
            or (registration['path'].replace('\\', '/'), registration['sha256']) != registered.SOURCE
            or any(proof['shared_exe'][key] != exe[key] for key in ('path', 'sha256'))
            or proof['registration_spans_reverified'] != 4
            or proof['receiver'] != codec.receiver_row()['event_name']
            or (contract['kind'], contract['record_type'], contract['record_size']) !=
               (codec.KIND, codec.RECORD_TYPE, codec.RECORD_SIZE)
            or contract['fields'] != {hex(key): tag for key, tag in codec.FIELD_TAGS.items()}
            or (contract['selector'], contract['descriptor_type']) != (0, 2)
            or contract['native_dispatch_before_host'] is not True
            or contract['host_result_discarded_by_caller'] is not True
            or {key: (row['rva'], row['bytes']) for key, row in proof['core_spans'].items()} != SPANS):
        raise ValueError('Rise and Fall CityTransfered source contract differs')
    return proof


def source_dependencies(execution_image):
    proof = source(execution_image)
    exe = proof['shared_exe']
    pins = {
        str(_path(SOURCE[0]).resolve()): SOURCE[1],
        str(_path(registered.SOURCE[0]).resolve()): registered.SOURCE[1],
        str(Path(execution_image.path).resolve()): execution_image.image_sha256,
        str(Path(exe['path']).resolve()): exe['sha256'],
    }
    verify_pinned_files(pins)
    return pins


def verify_live(core, read):
    proof = source(getattr(core, '_civ6_host_execution_image', None))
    for label, span in proof['core_spans'].items():
        raw = read(core._handle + span['rva'], span['bytes'])
        if (type(raw) is not bytes or len(raw) != span['bytes']
                or hashlib.sha256(raw).hexdigest() != span['sha256']):
            raise ValueError('Live Rise and Fall CityTransfered producer differs: ' + label)


def dispatch(owner, fields):
    from .a0_foundation_events import require_borrow

    backend = require_borrow(owner).owner
    image = getattr(backend.core, '_civ6_host_execution_image', None)
    if image is not _XP1_PROFILE:
        raise ValueError('CityTransfered requires the registered Rise and Fall image')
    return codec.dispatch_record(owner, fields, execution_image=image, proof_sha256=SOURCE[1])
