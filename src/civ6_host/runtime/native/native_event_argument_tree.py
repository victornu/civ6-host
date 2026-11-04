"""Bounded copy of the GameCore's borrowed event argument map.

The field budget is a host resource limit, not a rule or maximum in Civ6.
Copying a map does not admit the event or interpret its nested values.
"""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
import struct
from civ6_host.runtime.native.native_source_cache import load_pinned_json
MAX_FIELDS = 64
PROOF_SHA256 = '252feb7c4316173ec44d0a0f6481f7bf1641600790965377a1c2c8418827fa73'
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_argument_tree.py')))).resolve().parents[1]
VTABLE_RVA = 8507296

class EventArgumentTreeError(ValueError):

    def __init__(self, reason, fields=None, declared_count=None):
        super().__init__('Native event argument tree: ' + reason)
        self.reason = reason
        self.fields = dict(fields or {})
        self.declared_count = declared_count

def verify_source_evidence():
    if not PROOF_SHA256:
        raise RuntimeError('Native event argument transport proof has not been pinned')
    proof = load_pinned_json(ROOT / 'evidence/native-event-argument-tree' / (PROOF_SHA256 + '.json'), PROOF_SHA256)
    if proof['schema'] != 'civ6rl.native_event_argument_tree.static.v1' or proof['images'] != {'exe_sha256': 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63', 'core_sha256': 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'}:
        raise RuntimeError('Native event argument transport source changed')
    contract = proof['contract']
    expected = {'map_vtable_rva': VTABLE_RVA, 'map_header_size': 88, 'count_offset': 80, 'count_width': 4, 'sentinel_offset': 48, 'first_node_offset': 56, 'root_node_offset': 64, 'next_node_rva': 7582736, 'node_key_offset': 32, 'node_key_width': 4, 'node_variant_offset': 40, 'variant_size': 24, 'diagnostic_resource_bound': MAX_FIELDS, 'resource_bound_is_native_rule': False}
    if any((contract.get(key) != value for key, value in expected.items())) or proof['leaves']['get_count']['raw_hex'].lower() != '8b4150c3' or proof['leaves']['iterator_next']['raw_sha256'] != 'a0978695096493b0fe7886fe4e1facb0122606de8436fe80dfe2736ccfe34347' or (proof['map_vtable_slots']['0x1d8']['target_va'] != '0x180067370'):
        raise RuntimeError('Native event argument transport layout changed')
    return proof

def read_event_fields(argument, core_base, read, next_node, *, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'):
    from civ6_host.runtime.event_argument_source import reader_abi
    from civ6_host.runtime.event_argument_source import verify_reader_live
    abi = reader_abi(core_sha256)
    if core_sha256 == 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3':
        verify_source_evidence()
    else:
        verify_reader_live(core_base, read, core_sha256=core_sha256)
    fields, seen, snapshots = ({}, set(), [])
    declared_count = None

    def fail(reason):
        raise EventArgumentTreeError(reason, fields, declared_count)

    def exact(address, size):
        try:
            raw = read(address, size)
        except (ValueError, RuntimeError, OSError) as exc:
            raise EventArgumentTreeError('bounded_read_failed', fields, declared_count) from exc
        if not isinstance(raw, (bytes, bytearray, memoryview)) or len(raw) != size:
            fail('incomplete_read')
        return bytes(raw)
    if type(argument) is not int or argument <= 0:
        fail('null_or_invalid_argument')
    vtable = exact(argument, 8)
    if struct.unpack('<Q', vtable)[0] != core_base + abi.vtable_rva:
        fail('unverified_vtable')
    declared_count = struct.unpack('<I', exact(argument + 80, 4))[0]
    if declared_count > MAX_FIELDS:
        fail('field_budget_exceeded')
    sentinel = argument + 48
    first_node = exact(argument + 56, 8)
    node = struct.unpack('<Q', first_node)[0]
    while node != sentinel:
        if not node:
            fail('null_node')
        if node in seen:
            fail('node_cycle')
        if len(fields) >= declared_count:
            fail('more_nodes_than_declared')
        if len(fields) >= MAX_FIELDS:
            fail('field_budget_exceeded')
        seen.add(node)
        raw_key = exact(node + 32, 4)
        key = struct.unpack('<I', raw_key)[0]
        if key in fields:
            fail('duplicate_key')
        fields[key] = exact(node + 40, 24)
        snapshots.append((node, raw_key, fields[key]))
        try:
            node = next_node(node)
        except (ValueError, RuntimeError, OSError) as exc:
            raise EventArgumentTreeError('iterator_failed', fields, declared_count) from exc
        if node is None:
            node = 0
        if type(node) is not int or node < 0:
            fail('invalid_next_node')
    if len(fields) != declared_count:
        fail('fewer_nodes_than_declared')
    if struct.unpack('<I', exact(argument + 80, 4))[0] != declared_count:
        fail('count_changed_during_copy')
    if exact(argument, 8) != vtable or exact(argument + 56, 8) != first_node:
        fail('header_changed_during_copy')
    for address, raw_key, raw_variant in snapshots:
        if exact(address + 32, 4) != raw_key or exact(address + 40, 24) != raw_variant:
            fail('node_changed_during_copy')
    return fields
