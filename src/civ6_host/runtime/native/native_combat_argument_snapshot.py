"""Read borrowed combat submaps for refusal evidence, never for the learner.

The event remains unsupported. No value is sent back to the Core and no
pointer is retained beyond the synchronous callback. Lists are not followed.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import struct
from civ6_host.runtime.native.native_event_argument_tree import PROOF_SHA256
from civ6_host.runtime.native.native_event_argument_tree import read_event_fields
from civ6_host.runtime.native.native_event_argument_tree import verify_source_evidence
from civ6_host.runtime import xp1_combat_profile as _combat_source
EVENT_KIND = 2186730465
CHILD_KEYS = (1431908133, 2662870155, 787125023, 493520281)
CHILD_BLOBS = {1472654640: 1024, 2515717998: 13}

def capture_borrowed_children(kind, fields, base, read, next_node, *, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'):
    _combat_source.ensure_source(core_sha256)
    proof = verify_source_evidence()
    source_fields = proof['contract']['root_builder']['fields']
    expected_keys = {int(row['key'], 16) for row in source_fields}
    source_children = tuple((int(row['key'], 16) for row in source_fields if row['variant_tag'] == 10))
    if source_children != CHILD_KEYS or proof['captures']['child_map_builder']['code_sha256'] != '2b89a6ea0f7c0b46c8809a7583c820bf362a093578c024a70b6cee9e2cb6ac0a':
        raise RuntimeError('Combat child-map capture source changed')
    if type(kind) is not int or kind != EVENT_KIND or set(fields) != expected_keys:
        raise ValueError('Combat diagnostic requires the exact witnessed root shape')
    pointers = []
    for key in CHILD_KEYS:
        raw = fields[key]
        if not isinstance(raw, bytes) or len(raw) != 24:
            raise ValueError('Combat child map has an incomplete variant')
        tag = struct.unpack_from('<H', raw)[0]
        pointer, flags = (struct.unpack_from('<Q', raw, 8)[0], struct.unpack_from('<I', raw, 20)[0])
        if tag != 10 or flags != 83886080 or (not pointer):
            raise ValueError('Combat child map is not the source-owned map shape')
        if pointer in pointers:
            raise ValueError('Combat child maps unexpectedly alias')
        pointers.append(pointer)
    children = {}
    for key, pointer in zip(CHILD_KEYS, pointers):
        values = read_event_fields(pointer, base, read, next_node, core_sha256=core_sha256)
        blobs = {}
        for field_key, expected_tag in CHILD_BLOBS.items():
            raw = values.get(field_key)
            if raw is None:
                continue
            tag = struct.unpack_from('<H', raw)[0]
            address, size, flags = struct.unpack_from('<QII', raw, 8)
            if tag != expected_tag or size != 8 or flags != 553648129 or (not address):
                raise ValueError('Combat child blob differs from its native envelope')
            copied = read(address, 8)
            if not isinstance(copied, (bytes, bytearray, memoryview)) or len(copied) != 8:
                raise ValueError('Combat child blob copy is incomplete')
            blobs[hex(field_key)] = {'bytes_hex': bytes(copied).hex(), 'byte_count': 8}
        children[hex(key)] = {'field_count': len(values), 'fields': {hex(k): v.hex() for k, v in values.items()}, 'diagnostic_pointer_payloads': blobs}
    return {'children': children, 'source_proof_sha256': _combat_source.source_sha(core_sha256, PROOF_SHA256), 'borrowed_submap_count': len(children), 'recursive_list_capture': False, 'callback_admitted': False, 'result_substituted': False, 'exposed_to_learner': False, 'eligible_for_training': False}
