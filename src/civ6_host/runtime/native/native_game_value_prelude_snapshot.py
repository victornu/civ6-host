"""Read-only live A/B prelude diagnostics; never acknowledges host+130.

The caller owns A/B and supplies fresh, validated provider snapshots. Only the
real pinned +58 getter is called; there is no write, callback installation,
temporary constructor, allocator call or acknowledgement in this module.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from civ6_host.runtime.configuration_profiles import BASE_CORE_SHA256 as _BASE_CORE
from civ6_host.runtime import application_mirror_profiles as _mirror_profiles
from civ6_host.runtime.application_mirror_profiles import mirror_abi as _mirror_abi
import ctypes as C
import hashlib
import json
from pathlib import Path
import struct
from civ6_host.runtime.native.native_source_cache import load_pinned_json
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_game_value_prelude_snapshot.py')))).resolve().parents[1]
from civ6_host.runtime.native import native_game_value_mirror_inspection as _source
PROOF_SHA256 = _source.PROOF_SHA256
ALIAS_SHA256 = '8eb66f0839535c4ffc107674463a8d7b3bf1584abf2ef6d51461cdee5244dc73'
PREPARATION_SHA256 = 'b5ab78ce390d52b4da54d694e85d0545d880d500daf2913bff04ccd72cdf5172'
TREE_SHA256 = '252feb7c4316173ec44d0a0f6481f7bf1641600790965377a1c2c8418827fa73'
MAP_TABLE, LOOKUP = (_source.MAP_TABLE, _source.LOOKUP)
CLASSIFICATION = 3498329281
_read, _qword = (_source._read, _source._u64)

def _sources(*, core_sha256=_BASE_CORE):
    if core_sha256 != _BASE_CORE:
        return _mirror_profiles.snapshot_sources(core_sha256)
    proof = _source.verify_source()
    try:
        alias = load_pinned_json(ROOT / 'evidence/native-player-configuration-alias' / f'{ALIAS_SHA256}.json', ALIAS_SHA256)
    except RuntimeError as error:
        raise ValueError('Changed indexed player-map proof') from error
    keys = tuple((row['hash'] for row in alias['player_keys']))
    if len(keys) != 64 or len(set(keys)) != 64:
        raise ValueError('Changed indexed PLAYER key domain')
    fields = {'annotation': CLASSIFICATION}
    fields.update({name: proof['literals'][name]['key'] for name in ('player_id', 'slot_status', 'team', 'map_pins')})
    try:
        preparation = load_pinned_json(ROOT / 'evidence/native-configuration-finalization' / f'{PREPARATION_SHA256}.json', PREPARATION_SHA256)
    except RuntimeError as error:
        raise ValueError('Changed GAME_ROOT key proof') from error
    root_key = preparation['GAME_ROOT']['hash']
    try:
        tree = load_pinned_json(ROOT / 'evidence/native-event-argument-tree' / f'{TREE_SHA256}.json', TREE_SHA256)
    except RuntimeError as error:
        raise ValueError('Changed provider count-width proof') from error
    if tree['contract']['count_offset'] != 80 or tree['contract']['count_width'] != 4 or tree['leaves']['get_count']['raw_hex'].lower() != '8b4150c3':
        raise ValueError('Provider count source contract changed')
    return (proof, keys, fields, root_key)

def snapshot_game_value_prelude(base, source_store, *, core_snapshot, application_snapshot, read, call, core_sha256=_BASE_CORE):
    """Capture 67 maps per side and exact targeted variants, then reread them.

    `call` uses the existing inspection seam (address, result_type, arg_types,
    receiver, key). The receipt is diagnostic evidence, never permission to
    skip or emulate the EXE temporary prelude. Unknown variant types are
    recorded as raw bytes without dereferencing their payload.
    """
    abi = _mirror_abi(core_sha256)
    if type(base) is not int or base <= 0 or base >= (1 << 64) - 9437184:
        raise ValueError('Invalid Core image base')
    proof, player_keys, fields, expected_root_key = _sources(core_sha256=core_sha256)
    snapshots = {'A': core_snapshot, 'B': application_snapshot}
    labels = ('root', 'game', 'map', *(f'player_{i}' for i in range(64)))
    pointers = {}
    for side, snapshot in snapshots.items():
        players = snapshot.get('players')
        if not isinstance(players, (tuple, list)) or len(players) != 64:
            raise ValueError('Expected exactly 64 validated player maps on each side')
        values = (snapshot['descriptor'], snapshot['normalized'], snapshot['map_normalized'], *players)
        if any((type(p) is not int or p <= 0 for p in values)):
            raise ValueError('Invalid owned configuration pointer')
        pointers[side] = dict(zip(labels, values))
    all_pointers = tuple((p for side in pointers.values() for p in side.values()))
    if len(set(all_pointers)) != 134 or source_store != pointers['A']['root']:
        raise ValueError('Source/store does not match distinct owned A/B topology')
    if _qword(read, base + abi.configuration.vtable_rva + 88) != base + abi.configuration.lookup_rva:
        raise ValueError('Provider lookup vtable slot changed')
    for fragment in proof['core_functions']['property_lookup']['fragments']:
        for ins in fragment['instructions']:
            raw = bytes.fromhex(ins['bytes'])
            if _read(read, base + int(ins['va'], 16) - 6442450944, len(raw)) != raw:
                raise ValueError('Provider lookup code changed')
    root_key = struct.unpack('<I', _read(read, base + abi.configuration.root_key_rva, 4))[0]
    map_key = struct.unpack('<I', _read(read, base + abi.configuration.map_key_rva, 4))[0]
    if root_key != expected_root_key or not map_key or len(set((root_key, map_key, *player_keys))) != 66:
        raise ValueError('Native configuration keys changed')
    for index, key in enumerate(player_keys):
        if struct.unpack('<I', _read(read, base + abi.configuration.player_key_table_rva + index * 68, 4))[0] != key:
            raise ValueError('Native indexed PLAYER key changed')
    observed, cells, headers, lookups = ({}, {}, {}, [])

    def header(pointer):
        raw = _read(read, pointer, 88)
        if struct.unpack_from('<Q', raw)[0] != base + abi.configuration.vtable_rva:
            raise ValueError('Configuration/map-pins provider vtable changed')
        prior = headers.setdefault(pointer, raw)
        if prior != raw:
            raise ValueError('Provider changed between reads')
        return {'pointer': pointer, 'parent_pointer': struct.unpack_from('<Q', raw, 8)[0], 'observer_pointer': struct.unpack_from('<Q', raw, 16)[0], 'observer_control_pointer': struct.unpack_from('<Q', raw, 24)[0], 'allocator_pointer': struct.unpack_from('<Q', raw, 32)[0], 'entry_count_dword': struct.unpack_from('<I', raw, 80)[0], 'header_hex': raw.hex()}

    def cell(provider, key):
        pointer = call(base + abi.configuration.lookup_rva, C.c_void_p, (C.c_uint32,), provider, key)
        if pointer is None:
            pointer = 0
        if type(pointer) is not int or pointer < 0:
            raise ValueError('Invalid native lookup result')
        lookups.append((provider, key, pointer))
        if not pointer:
            return {'key': key, 'present': False, 'variant_pointer': 0}
        raw = _read(read, pointer, 24)
        prior = cells.setdefault(pointer, raw)
        if prior != raw:
            raise ValueError('Variant changed between reads')
        tag, flags = (struct.unpack_from('<H', raw)[0], struct.unpack_from('<I', raw, 20)[0])
        result = {'key': key, 'present': True, 'variant_pointer': pointer, 'tag_word': tag, 'flags_dword': flags, 'raw_hex': raw.hex(), 'size_dword': struct.unpack_from('<I', raw, 16)[0], 'payload_bits64': struct.unpack_from('<Q', raw, 8)[0]}
        if tag in (2, 3) and flags == 0:
            result['direct_scalar_uint32'] = struct.unpack_from('<I', raw, 8)[0]
        return result
    for side, maps in pointers.items():
        rows = {}
        for label, pointer in maps.items():
            row = header(pointer)
            row['annotation'] = cell(pointer, CLASSIFICATION)
            if label.startswith('player_'):
                for name in ('player_id', 'slot_status', 'team', 'map_pins'):
                    row[name] = cell(pointer, fields[name])
                pins = row['map_pins']
                if pins['present'] and pins['tag_word'] == 10 and (pins['flags_dword'] == 83886080):
                    pins_pointer = pins['payload_bits64']
                    if not pins_pointer:
                        raise ValueError('Owned MAP_PINS map has a NULL pointer')
                    pins['map_header'] = header(pins_pointer)
            if label == 'game':
                row['last_turn_phase'] = cell(pointer, _source.PROPERTY_KEY)
            rows[label] = row
        for key, label in zip((root_key, map_key, *player_keys), labels[1:]):
            result = cell(maps['root'], key)
            if not result['present'] or result['tag_word'] != 10 or result['flags_dword'] != 83886080 or (result['payload_bits64'] != maps[label]):
                raise ValueError('Live native submap does not match owned snapshot')
        observed[side] = rows
    for provider, key, pointer in lookups:
        again = call(base + abi.configuration.lookup_rva, C.c_void_p, (C.c_uint32,), provider, key)
        if (again or 0) != pointer:
            raise ValueError('Lookup presence/pointer changed during capture')
    for pointer, raw in cells.items():
        if _read(read, pointer, 24) != raw:
            raise ValueError('Variant bytes changed during capture')
    for pointer, raw in headers.items():
        if _read(read, pointer, 88) != raw:
            raise ValueError('Provider header changed during capture')
    return {'schema': 'civ6rl.native_game_value_prelude.live_inspection.v1', 'source_proof_sha256': abi.snapshot_proof_sha256, 'indexed_map_proof_sha256': abi.configuration.application_proof_sha256, 'count_source_proof_sha256': abi.tree_proof_sha256, 'source_store': source_store, 'sides': observed, 'owned_top_level_maps_checked': 134, 'all_targeted_reads_stable': True, 'acknowledgement_permitted': False, 'native_return_supplied': False, 'provider_mutations': 0, 'observer_bindings_changed': 0, 'allocator_bindings_changed': 0, 'eligible_for_training': False, 'limits': ['Observer pointer values are observed, never invoked.', 'Nested entries of existing MAP_PINS are not traversed.', 'No full prelude equivalence or Load continuation is granted.']}
