"""Current-image registration and receiver source for capture notifications."""
import hashlib
from pathlib import Path

from .a0_family_source import _path, verify_pinned_files
from .a0_policy_unlock_current import CURRENT_CORE_SHA256, CURRENT_EXE_SHA256, _require_image
from .configuration_profiles import _source
from .resource_resolution import resolve_path


SOURCE = ('evidence/host-xp2-capture-registered-callbacks-source.json',
          'c80da0c65da103fecc6883ae6c3677cf4bb97ba633330b17f1359b23f22fc7cd')
RECORD_TYPES = frozenset((0x73, 0xa0, 0xa8, 0x110, 0x111))


def source():
    proof = _source(SOURCE)
    if (proof['schema'] != 'civ6-host.xp2-capture-registered-callbacks.v1'
            or proof['images']['core']['sha256'] != CURRENT_CORE_SHA256
            or proof['images']['exe']['sha256'] != CURRENT_EXE_SHA256
            or {int(key) for key in proof['receivers']} != RECORD_TYPES):
        raise ValueError('XP2 capture notification source differs')
    return proof


def route(name, kind, records):
    proof = source()['routes'][name]
    if (proof['kind'] != kind or
            {(writer['type'], writer['size']) for writer in proof['writers']} != records or
            not proof['key_rva'] < proof['lookup_call_rva'] < proof['pointer_load_rva'] < proof['store_rva']):
        raise ValueError('XP2 capture notification registration differs: ' + name)
    return proof


def source_dependencies(execution_image):
    _require_image(execution_image)
    images = source()['images']
    paths = {name: resolve_path(Path(row['path'])).resolve() for name, row in images.items()}
    if paths['core'] != Path(execution_image.path).resolve():
        raise ValueError('XP2 capture notification source belongs to another Core')
    pins = {str(_path(SOURCE[0]).resolve()): SOURCE[1]}
    pins.update({str(paths[name]): row['sha256'] for name, row in images.items()})
    verify_pinned_files(pins)
    return pins


def verify_live(core, read, proof):
    _require_image(getattr(core, '_civ6_host_execution_image', None))
    for label, span in proof['core_spans'].items():
        raw = read(core._handle + span['rva'], span['bytes'])
        if type(raw) is not bytes or hashlib.sha256(raw).hexdigest() != span['sha256']:
            raise ValueError('Live XP2 capture notification producer differs: ' + label)


def receiver_row(record_type):
    row = source()['receivers'][str(record_type)]
    if row['type'] != record_type or row['row_rva'] != 0x12c78b0 + record_type * 0x30:
        raise ValueError('Current XP2 capture notification queue row differs')
    handler = row['handler']
    return dict(event_name=row['name'], handler_va=hex(0x140000000 + handler['rva']),
                handler_body_sha256=handler['sha256'], record_sizes={row['size']})
