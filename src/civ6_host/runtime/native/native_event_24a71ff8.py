"""Pinned empty EXE callback; neither an absent key nor a fabricated success."""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
from civ6_host.runtime.native.native_event_fb5f1edb import decode_fields
from civ6_host.runtime.native.native_host_event_registry import EXE_EVENT_CALLBACKS
from civ6_host.runtime.native.native_source_cache import load_pinned_json
EVENT_KIND = 614932472
PIN = 'eb2406a94d5ca05b5119dcf28971591f21b8def59bbabb3be52b5f5b947c580e'
PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_24a71ff8.py')))).resolve().parents[1] / 'evidence/native-event-24a71ff8' / f'{PIN}.json'

def dispatch_empty(kind, raw_fields, read, *, normalizer_transform_present):
    proof = load_pinned_json(PROOF, PIN)
    if proof['schema'] != 'civ6rl.native_event_24a71ff8.static.v1' or proof['callback']['raw_hex'] != 'c20000' or EXE_EVENT_CALLBACKS.get(EVENT_KIND) != 618272:
        raise RuntimeError('Empty callback source changed')
    if type(kind) is not int or kind != EVENT_KIND or normalizer_transform_present is not False:
        raise ValueError('Unverified empty callback or normalizer transform')
    fields = decode_fields(raw_fields, read)
    return {'native_dispatch_return': 0, 'callback_registered': True, 'callback_body_hex': 'c20000', 'source_sha256': PIN, 'selector': fields.descriptor.selector, 'owner': fields.owner, 'item_id': fields.descriptor.item_id, 'position_hex': fields.position_bytes.hex(), 'queue_record_produced': False}
