"""Read the official manager's resolved lists without selecting content again.

The caller supplies a read-only memory transport. This module never writes,
calls game code, substitutes a component filter, or admits a training profile.
Re-reading detects observed changes; it is not an atomic snapshot guarantee.
"""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
import hashlib
import json
import struct
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_resolved_content.py')))).resolve().parents[1]
PROVIDER_SHA = '195332488e5f10d5144992d7113d9da225866791bcfd5bd61d361e7fa72ad730'
ACTIVE_SHA = '1834968828bc7ab614f29eae7458e56dfadddcf6dd9b3d65b36d4c3b169b6583'
EXE_SHA = 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
MAX_HANDLES = 65536
MAX_READ_BYTES = 2 * 1024 * 1024
MAX_USER_ADDRESS = (1 << 47) - 1

class ContentSnapshotError(ValueError):
    pass

def source_profile():
    paths = ((ROOT / 'work/official-content929/provider-source.json', PROVIDER_SHA), (ROOT / 'work/official-content928/active-content-source.json', ACTIVE_SHA))
    captured = []
    for path, expected in paths:
        raw = _resolve_resource_path(path).read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ContentSnapshotError('Resolved-content source pin changed')
        captured.append(json.loads(raw))
    provider, active = captured
    if provider['image']['sha256'] != EXE_SHA or active['image']['sha256'] != EXE_SHA or (not all(provider['checks'].values())):
        raise ContentSnapshotError('Unqualified provider/layout source')
    return provider

def read_resolved_content(read_memory, image_base):
    """Return the lists exactly as observed; never sort/filter or resolve IDs.

    In particular, the ordered component vector retains native ordering. Empty
    vectors are explicit empty lists, while absent/uninitialized managers fail.
    The result is internal capture data, never a player observation.
    """
    if not callable(read_memory) or type(image_base) is not int or (not 65536 <= image_base <= MAX_USER_ADDRESS - 50331648) or image_base % 65536:
        raise ContentSnapshotError('Invalid Win64 image base or memory reader')
    source = source_profile()
    layout = source['layout']
    journal = []
    consumed = 0

    def read(address, size, label, *, remember=True):
        nonlocal consumed
        if type(address) is not int or type(size) is not int or size <= 0 or (address < 65536) or (address > MAX_USER_ADDRESS - size) or (consumed + size > MAX_READ_BYTES):
            raise ContentSnapshotError('Memory read outside capture bounds: ' + label)
        raw = read_memory(address, size)
        consumed += size
        if type(raw) is not bytes or len(raw) != size:
            raise ContentSnapshotError('Incomplete memory read: ' + label)
        if remember:
            journal.append((address, raw, label))
        return raw

    def pointer(address, label):
        value = struct.unpack('<Q', read(address, 8, label))[0]
        if not 65536 <= value <= MAX_USER_ADDRESS or value % 8:
            raise ContentSnapshotError('Absent/unaligned native pointer: ' + label)
        return value
    manager = pointer(image_base + layout['manager_global_rva'], 'manager')
    registry = manager + layout['registry_offset']
    provider = pointer(registry + layout['provider_offset_in_registry'], 'component provider')
    for name, obj, rva in (('registry', registry, layout['registry_vtable_rva']), ('component_provider', provider, layout['provider_vtable_rva'])):
        table = pointer(obj, name + ' vtable')
        if table != image_base + rva:
            raise ContentSnapshotError('Unexpected native vtable: ' + name)
        expected = tuple((image_base + int(v, 16) - int(source['image']['base'], 16) for v in source['vtables'][name]['qwords_le']))
        observed = struct.unpack('<4Q', read(table, 32, name + ' methods'))
        if observed != expected:
            raise ContentSnapshotError('Unexpected native method targets: ' + name)
    if pointer(provider + layout['provider_framework_offset'], 'provider framework') != registry:
        raise ContentSnapshotError('Component provider belongs to another framework')
    vectors = {}
    headers = {}
    for name, offset in layout['vectors'].items():
        raw = read(manager + offset, 24, name + ' header')
        begin, end, capacity = struct.unpack('<3Q', raw)
        headers[name] = raw.hex()
        if (begin, end, capacity) == (0, 0, 0):
            vectors[name] = []
            continue
        if not 65536 <= begin <= end <= capacity <= MAX_USER_ADDRESS or any((v % 4 for v in (begin, end, capacity))) or (end - begin) // 4 > MAX_HANDLES:
            raise ContentSnapshotError('Invalid native vector bounds: ' + name)
        count = (end - begin) // 4
        vectors[name] = list(struct.unpack('<' + 'I' * count, read(begin, count * 4, name + ' payload'))) if count else []
    for address, raw, label in reversed(journal):
        if read(address, len(raw), label, remember=False) != raw:
            raise ContentSnapshotError('Content changed during capture: ' + label)
    return {'schema': 'civ6rl.resolved_content929.memory_snapshot.v1', 'source_sha256': PROVIDER_SHA, 'active_population_source_sha256': ACTIVE_SHA, 'executable_sha256': EXE_SHA, 'image_base': hex(image_base), 'manager_address': hex(manager), 'provider_address': hex(provider), 'vector_headers_hex': headers, **vectors, 'memory_bytes_read': consumed, 'memory_ranges_checked_twice': len(journal), 'observed_ranges_unchanged': True, 'atomic_snapshot_proven': False, 'content_application_success_proven': False, 'save_identity_bound': False, 'database_identity_bound': False, 'gameplay_scripts_bound': False, 'strategic_training_ready': False, 'player_observation': False, 'read_only': True}
