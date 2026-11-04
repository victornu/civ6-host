"""Bounded native provider-effects diagnostic, never a host+130 acknowledgement.

No GameCore is loaded here. The injected native invocation seam must execute the
original pinned methods. An exception poisons this one-attempt object; callers
must terminate the isolated worker. Transferred maps remain owned by A. An
ambiguous failed transfer is retained until process exit, never guessed free.
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
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_game_value_prelude_mutation.py')))).resolve().parents[1]
from civ6_host.runtime.native import native_game_value_prelude_snapshot as snapshot_module
from civ6_host.runtime.native import native_player_allocator_inventory as inventory_module
PROOF_SHA256 = '9f52d302477069a8d595541054af83168906afa338d25d49e00acf00b6802313'
LIFETIME_SHA256 = '063fae97f0a77129e780a3cbc2ad80b29836ef87f07c80aa351dae0b5d451e78'
LIVE_INSPECTION_SHA256 = '1b63af26fed98ff944729ac81eb5f83e296dd5c89103efb43d033e43033dcf3b'
VTABLE = 8507296
METHODS = {'constructor': 7621504, 'allocate': 7565552, 'hash': 7628480, 'integer': 7628192, 'owned_map': 7629056, 'allocator_set': 7627424, 'allocator_get': 7661648, 'finish': 7645984, 'delete': 7622480, 'lookup': 7625904}
SLOTS = {0: 'delete', 16: 'allocator_set', 32: 'allocator_get', 56: 'notify', 80: 'finish', 88: 'lookup', 168: 'owned_map', 296: 'hash', 304: 'integer'}
METHODS['notify'] = 7646448
METHODS['tree_next'] = 7582736
_read = snapshot_module._read

def verify_source(*, core_sha256=_BASE_CORE):
    if core_sha256 != _BASE_CORE:
        return _mirror_profiles.prelude_source(core_sha256)
    try:
        doc = load_pinned_json(ROOT / 'work/native-game-value-prelude-primitives362.json', PROOF_SHA256)
    except RuntimeError as error:
        raise ValueError('Changed native prelude primitive proof') from error
    if doc['schema'] != 'civ6rl.native_game_value_prelude_primitives.static.v1' or doc['native_execution'] is not False or doc['contract']['automatic_runtime_admission'] is not False or (doc['contract']['not_a_full_EXE_temporary_replacement'] is not True) or (not all((c['normalized_operations_equal'] for c in doc['comparisons'].values()))):
        raise ValueError('Changed prelude scope/equivalence contract')
    snapshot_module._sources()
    raw = _resolve_resource_path(ROOT / 'work/native-game-value-prelude-inspection362.json').read_bytes()
    if hashlib.sha256(raw).hexdigest() != LIVE_INSPECTION_SHA256:
        raise ValueError('Changed live prelude inspection')
    observed = json.loads(raw)
    if observed['load_return_observed'] is not False or observed['acknowledgement_permitted'] is not False or observed['inspection']['destination_present'] is not False or any((observed['sides'][side]['observer_nonnull_maps'] or observed['sides'][side]['controlblock_nonnull_maps'] or (not observed['sides'][side]['active_teams_all_present_non_sentinel']) for side in ('A', 'B'))):
        raise ValueError('Live inspection does not support the proposed narrow profile')
    probe = _resolve_resource_path(ROOT / observed['probe']['path']).read_bytes()
    if hashlib.sha256(probe).hexdigest() != observed['probe']['sha256']:
        raise ValueError('Changed native inspection witness report')
    return doc

def verify_lifetime_source(*, core_sha256=_BASE_CORE):
    if core_sha256 != _BASE_CORE:
        return _mirror_profiles.lifetime_source(core_sha256)
    try:
        document = load_pinned_json(ROOT / 'work/native-borrowed-prelude-lifetime363.json', LIFETIME_SHA256)
    except RuntimeError as error:
        raise ValueError('Changed bounded prelude lifetime source') from error
    if document['contract']['host_acknowledgement_permitted'] is not False or document['parents']['primitives']['sha256'] != PROOF_SHA256:
        raise ValueError('Changed bounded prelude lifetime admission')
    return document

class PreludeMutationFailure(RuntimeError):

    def __init__(self, owner, cause):
        super().__init__('Native prelude failed; worker must terminate without retry: ' + str(cause))
        self.prelude_owner = owner
        self.original_error = cause
        self.requires_fatal_worker_exit = True

class NativePreludeAttempt:
    """One synchronous attempt on a retained A/B context, guarded by live reads.

    invoke(address, return_ctype, argument_ctypes, *arguments) is an injectable
    Win64 ABI seam; tests replace it with local-memory fixtures. No fabricated
    return is supplied to the original host callback by this class.
    """

    def __init__(self, base, context, application_owner, *, read, invoke, current_thread_id, core_sha256=_BASE_CORE):
        self.abi = _mirror_profiles.owner_abi(application_owner, core_sha256)
        if type(base) is not int or base <= 0 or type(context) is not int or (context <= 0):
            raise ValueError('Expected live Core base/context identity')
        self.base, self.context = (base, context)
        self.application_owner = application_owner
        self.read, self.invoke, self.current_thread_id = (read, invoke, current_thread_id)
        self.thread_id = current_thread_id()
        if type(self.thread_id) is not int or self.thread_id <= 0:
            raise ValueError('Expected actual creating Win32 thread ID')
        self.started = self.busy = self.poisoned = False
        self.allocations, self.operations = ([], [])
        self.proof = verify_source(core_sha256=core_sha256)
        self.lifetime_proof = verify_lifetime_source(core_sha256=core_sha256)

    def _thread(self):
        current = self.current_thread_id()
        if type(current) is not int or current != self.thread_id:
            raise ValueError('Prelude crossed its native owner thread')

    def _call(self, name, result_type, types, *arguments):
        self._thread()
        result = self.invoke(self.base + self.abi.methods[name], result_type, types, *arguments)
        self._thread()
        return result

    def _lookup(self, pointer, key):
        return self._call('lookup', C.c_void_p, (C.c_void_p, C.c_uint32), pointer, key)

    def _snapshot(self, source_store, a, b):

        def call(address, result, types, receiver, *args):
            self._thread()
            value = self.invoke(address, result, (C.c_void_p, *types), receiver, *args)
            self._thread()
            return value
        return snapshot_module.snapshot_game_value_prelude(self.base, source_store, core_snapshot=a, application_snapshot=b, read=self.read, call=call, core_sha256=self.abi.configuration.core_sha256)

    def _code(self):
        for name, body in {**self.proof['core_functions'], **self.lifetime_proof['core_functions']}.items():
            for fragment in body['fragments']:
                for ins in fragment['instructions']:
                    raw = bytes.fromhex(ins['bytes'])
                    if _read(self.read, self.base + int(ins['va'], 16) - 6442450944, len(raw)) != raw:
                        raise ValueError('Changed native prelude method: ' + name)
        for slot, name in SLOTS.items():
            actual = struct.unpack('<Q', _read(self.read, self.base + self.abi.configuration.vtable_rva + slot, 8))[0]
            if actual != self.base + self.abi.methods[name]:
                raise ValueError('Changed native prelude vtable slot')

    @staticmethod
    def _scalar(cell, tag, *, missing=True):
        if not cell['present']:
            if missing:
                return None
            raise ValueError('Missing scalar prelude property')
        if cell['tag_word'] != tag or cell['flags_dword'] != 0:
            raise ValueError('Unexpected existing scalar prelude type/flags')
        return cell['direct_scalar_uint32']

    def _preflight(self, before):
        rows = before['sides']['A']
        addresses = {row['pointer']: row for row in rows.values()}
        reserved = {row['pointer'] for side in before['sides'].values() for row in side.values()}
        owned_pins = set()
        allocator = rows['root']['allocator_pointer']
        if not allocator:
            raise ValueError('Missing native root allocator')
        for label, row in rows.items():
            if row['observer_pointer'] or row['observer_control_pointer']:
                raise ValueError('Active observer/refcount replacement is outside this profile')
            if row['allocator_pointer'] != allocator:
                raise ValueError('Native source allocator bindings differ')
            current, visited = (row, set())
            while current['parent_pointer']:
                if current['pointer'] in visited:
                    raise ValueError('Cyclic native notification parent chain')
                visited.add(current['pointer'])
                current = addresses.get(current['parent_pointer'])
                if current is None:
                    raise ValueError('Foreign native notification parent')
            self._scalar(row['annotation'], 3)
        expected = {'annotations': 0, 'player_ids': 0, 'map_pins': 0, 'team_assignments': 0}
        for label in ('root', 'map', *(f'player_{i}' for i in range(64))):
            expected['annotations'] += not rows[label]['annotation']['present']
        for index in range(64):
            row = rows[f'player_{index}']
            self._scalar(row['player_id'], 2)
            status = self._scalar(row['slot_status'], 2)
            team = self._scalar(row['team'], 2)
            if status in (1, 3) and (team is None or team == 4294967295):
                raise ValueError('Active player requires an unadmitted TEAM assignment')
            expected['player_ids'] += not row['player_id']['present']
            pins = row['map_pins']
            if pins['present']:
                if pins['tag_word'] != 10 or pins['flags_dword'] != 83886080 or 'map_header' not in pins:
                    raise ValueError('Existing MAP_PINS is not an owned native map')
                header = pins['map_header']
                self._empty_map(header['pointer'], expected_allocator=allocator)
                if header['pointer'] in reserved or header['pointer'] in owned_pins:
                    raise ValueError('MAP_PINS aliases another owned map')
                owned_pins.add(header['pointer'])
            else:
                expected['map_pins'] += 1
            self._inventory_player(row, pins)
        expected['total'] = expected['annotations'] + expected['player_ids'] + expected['map_pins']
        self.reserved_pointers = reserved | owned_pins
        return (allocator, expected)

    def _inventory_player(self, row, pins, *, reject_opaque=True):
        """Close every recursive +10 target before calling that native method.

        The 64-field ceiling is a diagnostic resource bound, not a native
        limit. The actual native successor is used; no object payload is
        dereferenced here except the previously validated empty MAP_PINS map.
        """
        pointer = row['pointer']
        header = _read(self.read, pointer, 88)
        count = struct.unpack_from('<I', header, 80)[0]
        if count > 64:
            raise ValueError('Player inventory exceeds diagnostic resource bound')
        node = struct.unpack_from('<Q', header, 56)[0]
        sentinel, seen, keys, snapshots = (pointer + 48, set(), set(), [])
        _, _, fields, _ = snapshot_module._sources(core_sha256=self.abi.configuration.core_sha256)
        while node != sentinel:
            if type(node) is not int or node <= 0 or node in seen or (len(seen) >= count):
                raise ValueError('Invalid native player inventory traversal')
            seen.add(node)
            key_bytes = _read(self.read, node + 32, 4)
            key = struct.unpack('<I', key_bytes)[0]
            if key in keys:
                raise ValueError('Duplicate native player inventory key')
            keys.add(key)
            raw = _read(self.read, node + 40, 24)
            if self._lookup(pointer, key) != node + 40:
                raise ValueError('Player inventory lookup/node disagrees')
            tag = struct.unpack_from('<H', raw)[0]
            if tag in (8, 9, 10, 11, 22):
                if reject_opaque and (key != fields['map_pins'] or not pins['present'] or raw.hex() != pins['raw_hex'] or (tag != 10)):
                    raise ValueError('Opaque recursive allocator target is outside this profile')
            snapshots.append((node, key_bytes, raw))
            node = self._call('tree_next', C.c_void_p, (C.c_void_p,), node)
        if len(seen) != count or _read(self.read, pointer, 88) != header:
            raise ValueError('Player inventory count/header is not stable')
        for node, key_bytes, raw in snapshots:
            if _read(self.read, node + 32, 4) != key_bytes or _read(self.read, node + 40, 24) != raw:
                raise ValueError('Player inventory variant changed during copy')
        return tuple(({'key': struct.unpack('<I', key)[0], 'raw_hex': raw.hex()} for _, key, raw in snapshots))

    def inspect_recursive_targets(self, source_store, core_snapshot):
        """Read all 128 player maps, including opaque variants without deref.

        This separate diagnostic does not start or admit a mutation attempt.
        Its result cannot be supplied as an acknowledgement to host+130.
        """
        self._thread()
        if self.started or self.busy or self.poisoned:
            raise ValueError('Recursive inventory requires a fresh attempt owner')
        self.busy = True
        try:
            self.application_owner.require_context(self.base, self.context)
            self._code()
            b = self.application_owner.snapshot()
            before = self._snapshot(source_store, core_snapshot, b)
            result = {}
            for side in ('A', 'B'):
                result[side] = []
                for index in range(64):
                    row = before['sides'][side][f'player_{index}']
                    entries = self._inventory_player(row, row['map_pins'], reject_opaque=False)
                    result[side].append({'index': index, 'pointer': row['pointer'], 'entry_count': len(entries), 'entries': entries, 'recursive_object_keys': tuple((e['key'] for e in entries if struct.unpack_from('<H', bytes.fromhex(e['raw_hex']))[0] in (8, 9, 10, 11, 22)))})
            after = self._snapshot(source_store, core_snapshot, b)
            if before != after:
                raise ValueError('Provider snapshot changed during recursive inventory')
            return {'schema': 'civ6rl.native_player_allocator_inventory.v1', 'source_proof_sha256': self.abi.prelude_proof_sha256, 'sides': result, 'provider_mutations': 0, 'opaque_payload_dereferences': 0, 'host_acknowledgement_permitted': False, 'runtime_admission': False}
        finally:
            self.busy = False

    def _empty_map(self, pointer, expected_allocator=None):
        raw = _read(self.read, pointer, 88)
        if struct.unpack_from('<Q', raw)[0] != self.base + self.abi.configuration.vtable_rva or any((struct.unpack_from('<Q', raw, offset)[0] for offset in (8, 16, 24, 64))) or struct.unpack_from('<Q', raw, 48)[0] != pointer + 48 or (struct.unpack_from('<Q', raw, 56)[0] != pointer + 48) or (raw[72:80] != bytes(8)) or (struct.unpack_from('<I', raw, 80)[0] != 0):
            raise ValueError('Native newly allocated MAP_PINS is not constructed empty')
        allocator = struct.unpack_from('<Q', raw, 32)[0]
        if not allocator or (expected_allocator is not None and allocator != expected_allocator):
            raise ValueError('MAP_PINS native allocator binding differs')

    def _set(self, method, pointer, key, value):
        node = self._call(method, C.c_void_p, (C.c_void_p, C.c_uint32, C.c_uint32), pointer, key, value)
        if type(node) is not int or node <= 0 or self._lookup(pointer, key) != node:
            raise ValueError('Native scalar setter did not return actual keyed variant')
        raw = _read(self.read, node, 24)
        tag = 3 if method == 'hash' else 2
        if struct.unpack_from('<I', raw)[0] != tag or struct.unpack_from('<I', raw, 8)[0] != value or raw[16:24] != bytes(8):
            raise ValueError('Native scalar setter readback differs')
        self.operations.append({'method': method, 'provider': pointer, 'key': key, 'value': value})

    def _pins(self, player, key, allocator):
        existing = self._lookup(player, key)
        if existing:
            return
        pointer = self._call('allocate', C.c_void_p, (C.c_size_t,), 88)
        if type(pointer) is not int or pointer <= 0 or pointer % 16:
            raise ValueError('Native allocation failed or is not aligned')
        if pointer in self.reserved_pointers:
            raise ValueError('Native allocation aliases an already owned map')
        self.reserved_pointers.add(pointer)
        allocation = {'pointer': pointer, 'state': 'allocated', 'freed': False}
        self.allocations.append(allocation)
        allocation['state'] = 'constructing'
        result = self._call('constructor', C.c_void_p, (C.c_void_p,), pointer)
        self._empty_map(pointer)
        allocation['state'] = 'constructed'
        if result != pointer:
            raise ValueError('Native map constructor returned a foreign pointer')
        actual_allocator = self._call('allocator_get', C.c_void_p, (C.c_void_p,), player)
        if actual_allocator != allocator:
            raise ValueError('Native player allocator changed')
        self._call('allocator_set', None, (C.c_void_p, C.c_void_p), pointer, actual_allocator)
        self._empty_map(pointer, allocator)
        allocation['state'] = 'transfer_in_flight'
        node = self._call('owned_map', C.c_void_p, (C.c_void_p, C.c_uint32, C.c_void_p), player, key, pointer)
        allocation['state'] = 'transferred'
        if type(node) is not int or node <= 0 or self._lookup(player, key) != node:
            raise ValueError('Native owned-map setter returned an unexpected variant')
        raw = _read(self.read, node, 24)
        if struct.unpack_from('<I', raw)[0] != 10 or struct.unpack_from('<Q', raw, 8)[0] != pointer or raw[16:24] != struct.pack('<II', 0, 83886080):
            raise ValueError('Native MAP_PINS ownership transfer readback differs')
        self.operations.append({'method': 'owned_map', 'provider': player, 'key': key, 'map': pointer})

    def _release_untransferred(self):
        for allocation in reversed(self.allocations):
            if allocation['state'] not in ('allocated', 'constructing', 'constructed'):
                continue
            try:
                self._empty_map(allocation['pointer'])
            except Exception:
                allocation['state'] = 'retained_unknown_construction'
                continue
            allocation['state'] = 'delete_attempted'
            try:
                self._call('delete', C.c_void_p, (C.c_void_p, C.c_uint32), allocation['pointer'], 1)
            except Exception:
                allocation['state'] = 'delete_outcome_unknown'
                continue
            allocation['freed'] = True
            allocation['state'] = 'deleted'

    def apply(self, source_store, core_snapshot):
        self._thread()
        if self.started or self.busy or self.poisoned:
            raise ValueError('Native prelude is one-attempt and non-reentrant')
        self.started = self.busy = True
        try:
            self.application_owner.require_context(self.base, self.context)
            b = self.application_owner.snapshot()
            self._code()
            before = self._snapshot(source_store, core_snapshot, b)
            allocator, planned = self._preflight(before)
            _, _, fields, _ = snapshot_module._sources(core_sha256=self.abi.configuration.core_sha256)

            def inventory_call(address, result, types, receiver, *args):
                self._thread()
                value = self.invoke(address, result, (C.c_void_p, *types), receiver, *args)
                self._thread()
                return value
            inventory = inventory_module.snapshot_player_allocator_targets(self.base, source_store, core_snapshot=core_snapshot, application_snapshot=b, read=self.read, call=inventory_call, core_sha256=self.abi.configuration.core_sha256)
            for row in inventory['sides']['A']:
                allowed = before['sides']['A'][f"player_{row['index']}"]['map_pins']
                for entry in row['entries']:
                    if entry['recursive_object_tag'] and (entry['key'] != fields['map_pins'] or not allowed['present'] or entry['raw_hex'] != allowed['raw_hex']):
                        raise ValueError('Opaque recursive target appeared before mutation')
            if self._snapshot(source_store, core_snapshot, b) != before:
                raise ValueError('Prelude preflight state changed before first mutation')
            rows = before['sides']['A']
            root = rows['root']['pointer']
            self._set('hash', root, 3498329281, 1252977331)
            for index in range(64):
                player = rows[f'player_{index}']['pointer']
                self._set('hash', player, 3498329281, 1697843344)
                self._set('integer', player, fields['player_id'], index)
                actual_allocator = self._call('allocator_get', C.c_void_p, (C.c_void_p,), root)
                if actual_allocator != allocator:
                    raise ValueError('Native root allocator changed')
                self._call('allocator_set', None, (C.c_void_p, C.c_void_p), player, actual_allocator)
                self._pins(player, fields['map_pins'], allocator)
            self._set('hash', rows['map']['pointer'], 3498329281, 1975399942)
            finish = self._call('finish', C.c_uint8, (C.c_void_p, C.c_uint8), root, 1)
            if finish != 0:
                raise ValueError('NULL-observer finish did not return native AL0')
            after = self._snapshot(source_store, core_snapshot, b)
            if before['sides']['B'] != after['sides']['B']:
                raise ValueError('Prelude unexpectedly changed B')
            delta = 0
            for label, row in rows.items():
                post = after['sides']['A'][label]
                if any((post[key] != row[key] for key in ('parent_pointer', 'observer_pointer', 'observer_control_pointer', 'allocator_pointer'))):
                    raise ValueError('Native prelude changed observer/parent/allocator binding')
                expected_delta = 0
                if label == 'root' or label == 'map' or label.startswith('player_'):
                    expected_delta += not row['annotation']['present']
                    expected_class = 1252977331 if label == 'root' else 1975399942 if label == 'map' else 1697843344
                    if self._scalar(post['annotation'], 3, missing=False) != expected_class:
                        raise ValueError('Final native annotation differs from source class')
                if label.startswith('player_'):
                    expected_delta += not row['player_id']['present']
                    expected_delta += not row['map_pins']['present']
                    if any((post[key] != row[key] for key in ('team', 'slot_status'))):
                        raise ValueError('Native prelude changed TEAM/SLOT_STATUS')
                    if self._scalar(post['player_id'], 2, missing=False) != int(label.split('_')[1]):
                        raise ValueError('Final PLAYER_ID differs from source index')
                if label == 'game' and any((post[key] != row[key] for key in ('annotation', 'last_turn_phase'))):
                    raise ValueError('Native prelude changed the existing GAME view')
                if post['entry_count_dword'] - row['entry_count_dword'] != expected_delta:
                    raise ValueError('Native map entry count differs from planned writes')
                delta += expected_delta
            if delta != planned['total']:
                raise ValueError('Native aggregate insertion count differs')
            return {'source_proof_sha256': self.abi.prelude_proof_sha256, 'provider_effects_completed': True, 'lifetime_source_sha256': self.abi.lifetime_proof_sha256, 'live_inspection_sha256': self.abi.live_inspection_sha256, 'planned_new_cells': planned, 'observed_new_cells': delta, 'allocations': tuple((dict(a) for a in self.allocations)), 'native_scalar_calls': sum((o['method'] in ('hash', 'integer') for o in self.operations)), 'acknowledgement_permitted': False, 'whole_EXE_wrapper_emulated': False, 'TEAM_assignment_path_executed': False, 'eligible_for_training': False}
        except Exception as error:
            self.poisoned = True
            self._release_untransferred() if self.abi.configuration.core_sha256 == _BASE_CORE else None
            raise PreludeMutationFailure(self, error) from error
        finally:
            self.busy = False
