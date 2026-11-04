"""Live read-only inventory of recursive allocator targets.

No provider setter, observer callback, allocation or payload dereference occurs.
The inventory is evidence for a future preflight; it never acknowledges host+130.
"""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from civ6_host.runtime.configuration_profiles import BASE_CORE_SHA256 as _BASE_CORE
from civ6_host.runtime import application_mirror_profiles as _mirror_profiles
from civ6_host.runtime.application_mirror_profiles import mirror_abi as _mirror_abi
import hashlib
import json
from pathlib import Path
import struct
import ctypes as C
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_player_allocator_inventory.py')))).resolve().parents[1]
from civ6_host.runtime.native import native_game_value_prelude_snapshot as snapshot
PROOF_SHA256 = '9f52d302477069a8d595541054af83168906afa338d25d49e00acf00b6802313'
PROOF_PATH = ROOT / 'work/native-game-value-prelude-primitives362.json'
TREE_PROOF_SHA256 = '252feb7c4316173ec44d0a0f6481f7bf1641600790965377a1c2c8418827fa73'
NEXT_RVA, LOOKUP_RVA = (7582736, 7625904)
RECURSIVE_TAGS = (8, 9, 10, 11, 22)
MAX_FIELDS_PER_PLAYER = 64

def verify_source(*, core_sha256=_BASE_CORE):
    if core_sha256 != _BASE_CORE:
        return _mirror_profiles.inventory_source(core_sha256)
    raw = _resolve_resource_path(PROOF_PATH).read_bytes()
    if hashlib.sha256(raw).hexdigest() != PROOF_SHA256:
        raise ValueError('Changed recursive allocator primitive evidence')
    proof = json.loads(raw)
    if proof['schema'] != 'civ6rl.native_game_value_prelude_primitives.static.v1' or proof['parents']['tree']['sha256'] != TREE_PROOF_SHA256 or (not proof['comparisons']['recursive_allocator_setter']['normalized_operations_equal']):
        raise ValueError('Unexpected recursive allocator source contract')
    raw = _resolve_resource_path(ROOT / proof['parents']['tree']['path']).read_bytes()
    if hashlib.sha256(raw).hexdigest() != TREE_PROOF_SHA256:
        raise ValueError('Changed complete tree layout evidence')
    contract = json.loads(raw)['contract']
    if any((contract[k] != v for k, v in {'count_offset': 80, 'count_width': 4, 'first_node_offset': 56, 'sentinel_offset': 48, 'node_key_offset': 32, 'node_variant_offset': 40, 'variant_size': 24, 'next_node_rva': NEXT_RVA}.items())):
        raise ValueError('Changed complete tree traversal contract')
    snapshot._sources()
    return proof

def snapshot_player_allocator_targets(base, source_store, *, core_snapshot, application_snapshot, read, call, core_sha256=_BASE_CORE):
    """call(address, result_ctype, argument_ctypes_after_this, this, *args).

    Only native property lookup and successor are invoked. Parent must retain
    the context/providers and call synchronously on their creating thread.
    Unknown recursive objects are reported, not admitted or dereferenced.
    """
    abi = _mirror_abi(core_sha256)
    proof = verify_source(core_sha256=core_sha256)
    exact = lambda address, length: snapshot._read(read, address, length)
    for fragment in proof['core_functions']['tree_successor']['fragments']:
        for instruction in fragment['instructions']:
            raw = bytes.fromhex(instruction['bytes'])
            if exact(base + int(instruction['va'], 16) - 6442450944, len(raw)) != raw:
                raise ValueError('Changed native tree successor code')
    before = snapshot.snapshot_game_value_prelude(base, source_store, core_snapshot=core_snapshot, application_snapshot=application_snapshot, read=read, call=call, core_sha256=core_sha256)
    sides, global_reads = ({}, [])
    for side in ('A', 'B'):
        sides[side] = []
        for index in range(64):
            provider = before['sides'][side][f'player_{index}']['pointer']
            header = exact(provider, 88)
            count = struct.unpack_from('<I', header, 80)[0]
            if count > MAX_FIELDS_PER_PLAYER:
                raise ValueError('Player allocator inventory resource bound exceeded')
            global_reads.append((provider, header))
            sentinel = provider + 48
            node = struct.unpack_from('<Q', header, 56)[0]
            seen, keys, entries = (set(), set(), [])
            while node != sentinel:
                if type(node) is not int or node <= 0 or node in seen or (len(seen) >= count):
                    raise ValueError('Invalid player allocator inventory node/count')
                seen.add(node)
                raw_key, raw_variant = (exact(node + 32, 4), exact(node + 40, 24))
                key = struct.unpack('<I', raw_key)[0]
                if key in keys:
                    raise ValueError('Duplicate player allocator inventory key')
                keys.add(key)
                actual = call(base + abi.configuration.lookup_rva, C.c_void_p, (C.c_uint32,), provider, key)
                if actual != node + 40:
                    raise ValueError('Player allocator inventory lookup/node mismatch')
                tag = struct.unpack_from('<H', raw_variant)[0]
                entries.append({'key': key, 'tag_word': tag, 'flags_dword': struct.unpack_from('<I', raw_variant, 20)[0], 'raw_hex': raw_variant.hex(), 'recursive_object_tag': tag in RECURSIVE_TAGS})
                global_reads.extend(((node + 32, raw_key), (node + 40, raw_variant)))
                node = call(base + abi.successor_rva, C.c_void_p, (), node)
            if len(entries) != count:
                raise ValueError('Player allocator inventory count mismatch')
            sides[side].append({'index': index, 'pointer': provider, 'entry_count_dword': count, 'entries': entries, 'recursive_object_keys': [entry['key'] for entry in entries if entry['recursive_object_tag']]})
    after = snapshot.snapshot_game_value_prelude(base, source_store, core_snapshot=core_snapshot, application_snapshot=application_snapshot, read=read, call=call, core_sha256=core_sha256)
    if before != after or any((exact(address, len(raw)) != raw for address, raw in global_reads)):
        raise ValueError('Player allocator inventory changed during complete observation')
    return {'schema': 'civ6rl.native_player_allocator_inventory.v1', 'source_proof_sha256': abi.prelude_proof_sha256, 'tree_source_proof_sha256': abi.tree_proof_sha256, 'sides': sides, 'player_maps_checked': 128, 'entry_count': sum((r['entry_count_dword'] for rows in sides.values() for r in rows)), 'recursive_object_tags': list(RECURSIVE_TAGS), 'all_variants_and_headers_stable': True, 'provider_mutations': 0, 'opaque_payload_dereferences': 0, 'acknowledgement_permitted': False, 'runtime_admission': False}
