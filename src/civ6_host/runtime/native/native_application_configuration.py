"""Own a separate native application descriptor for the original NewGame copy.

Python owns only the outer storage. The pinned Core constructor, deep copy and
destructor own all entries and nested maps. This is not an EXE singleton, nor
proof of the complete application lifecycle or a training-ready environment.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import ctypes as C
from pathlib import Path
import struct
from civ6_host.runtime.native import native_configuration_finalization as setup
from civ6_host.runtime.native.native_source_cache import load_pinned_json
PROOF_SHA256 = '8eb66f0839535c4ffc107674463a8d7b3bf1584abf2ef6d51461cdee5244dc73'
_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_application_configuration.py')))).resolve().parents[1] / 'evidence/native-player-configuration-alias' / (PROOF_SHA256 + '.json')
VTABLE = 8507296
CTOR, DTOR, ASSIGN, LOOKUP = (7621504, 7621792, 7649872, 7625904)
STORAGE_SIZE = 88
_GUARD = b'\xd6' * 16
_LIVE = ('provider_constructor', 'provider_base_constructor', 'provider_destructor', 'provider_assign', 'provider_copy', 'variant_clone_construct', 'variant_clone_assign', 'variant_release', 'lookup')

def verify_source(*, core_sha256=setup.CORE_SHA256):
    if core_sha256 != setup.CORE_SHA256:
        return _expansion_application_source(core_sha256)
    proof = load_pinned_json(_PROOF, PROOF_SHA256)
    contract = proof.get('contract', {})
    if proof.get('schema') != 'civ6rl.native_player_configuration_alias.static.v1' or proof.get('images') != {'core_sha256': setup.CORE_SHA256, 'exe_sha256': setup.EXE_SHA256} or proof.get('native_execution') is not False or (contract.get('record_count') != 64) or (contract.get('core_key_table_rva') != 9162064) or (contract.get('owned_map_flags') != 83886080) or (proof.get('validation', {}).get('all_captured_instructions_match_pinned_pe') is not True):
        raise RuntimeError('Application configuration source contract changed')
    rows = {ins['va']: ins['text'] for fragment in proof['core_functions']['variant_clone_assign']['fragments'] for ins in fragment['instructions']}
    if rows.get('0x180747b45') != 'lea ecx, [rdi + 0x58]' or rows.get('0x180747b55') != 'call 0x180744b80' or rows.get('0x180747b7d') != 'call qword ptr [rax + 0x1d0]':
        raise RuntimeError('Native configuration allocation/copy source changed')
    return proof

def _live_code(base, read, *, core_sha256=setup.CORE_SHA256):
    proof = verify_source(core_sha256=core_sha256)
    for name in (*_LIVE, *proof.get('additional_live_names', ())):
        for fragment in proof['core_functions'][name]['fragments']:
            for ins in fragment['instructions']:
                raw = bytes.fromhex(ins['bytes'])
                if setup._read(read, base + int(ins['va'], 16) - 6442450944, len(raw)) != raw:
                    raise ValueError('Application configuration code mismatch: ' + name)

def provider_snapshot(base, provider, read, call=None, *, core_sha256=setup.CORE_SHA256):
    abi = _require_owner_profile(_configuration_abi(core_sha256))
    'Borrow the existing keyed root, map and 64 players without creating cells.'
    proof = verify_source(core_sha256=core_sha256)
    table = base + abi.vtable_rva
    if type(provider) is not int or provider <= 0 or setup._qword(read, provider) != table:
        raise ValueError('Unexpected application configuration provider')
    for slot, rva in ((88, abi.lookup_rva), (376, abi.copy_rva), (464, abi.assign_rva)):
        if setup._qword(read, table + slot) != base + rva:
            raise ValueError('Unverified application provider virtual slot')
    root = struct.unpack('<I', setup._read(read, base + abi.root_key_rva, 4))[0]
    map_key = struct.unpack('<I', setup._read(read, base + abi.map_key_rva, 4))[0]
    keys = tuple((row['hash'] for row in proof['player_keys']))
    if root != setup.GAME_ROOT_KEY or not map_key or len(set((root, map_key, *keys))) != 66:
        raise ValueError('Application configuration keys are not initialized')
    for index, key in enumerate(keys):
        if struct.unpack('<I', setup._read(read, base + abi.player_key_table_rva + index * 68, 4))[0] != key:
            raise ValueError('Native PLAYER key differs from the original indexed name')

    def child(key):
        node = setup._invoke(call, base + abi.lookup_rva, C.c_void_p, provider, (C.c_uint32,), key)
        if type(node) is not int or node <= 0:
            raise LookupError('Application provider has no existing keyed submap')
        raw = setup._read(read, node, 24)
        tag, pointer, flags = (struct.unpack_from('<H', raw)[0], struct.unpack_from('<Q', raw, 8)[0], struct.unpack_from('<I', raw, 20)[0])
        if tag != 10 or flags != 83886080 or (not pointer) or (setup._qword(read, pointer) != table):
            raise ValueError('Application provider submap is not the native owned map profile')
        return pointer
    values = tuple((child(key) for key in (root, map_key, *keys)))
    if len(set((provider, *values))) != 67:
        raise ValueError('Application configuration submaps unexpectedly alias')
    return {'descriptor': provider, 'normalized': values[0], 'map_normalized': values[1], 'players': values[2:]}

class NativeApplicationConfiguration:
    """A guarded, native-owned clone kept alive through every application reader."""

    def __init__(self, core, context, *, read=None, call=None, emit=None, core_sha256=setup.CORE_SHA256):
        self._configuration_abi = _require_owner_profile(_configuration_abi(core_sha256))
        self.base, self.context = (core._handle, context)
        self.read = setup.local_reader() if read is None else read
        self.call, self.emit = (call, emit)
        self.closed = False
        self.new_game_entered = False
        if type(self.base) is not int or self.base <= 0 or type(context) is not int or (context <= 0):
            raise ValueError('Expected live native configuration context')
        _live_code(self.base, self.read, core_sha256=self._configuration_abi.core_sha256)
        source = setup._linked_snapshot(self.base, context, self.read, call, core_sha256=self._configuration_abi.core_sha256)
        self.source_provider = source['descriptor']
        source_children = provider_snapshot(self.base, self.source_provider, self.read, call, core_sha256=self._configuration_abi.core_sha256)
        self.storage = C.create_string_buffer(STORAGE_SIZE + 2 * len(_GUARD))
        start = C.addressof(self.storage)
        C.memmove(start, _GUARD, len(_GUARD))
        C.memmove(start + len(_GUARD) + STORAGE_SIZE, _GUARD, len(_GUARD))
        self.pointer = start + len(_GUARD)
        result = setup._invoke(call, self.base + self._configuration_abi.constructor_rva, C.c_void_p, self.pointer)
        if result != self.pointer:
            raise RuntimeError('Native application provider constructor result differs')
        self._check_guard()
        if setup._qword(self.read, self.pointer) != self.base + self._configuration_abi.vtable_rva:
            raise ValueError('Native application provider constructor vtable differs')
        cleanup_safe = True
        try:
            if self.pointer == self.source_provider:
                raise ValueError('Native application provider cannot alias the Core source')
            cleanup_safe = False
            result = setup._invoke(call, self.base + self._configuration_abi.assign_rva, C.c_void_p, self.pointer, (C.c_void_p,), self.source_provider)
            if result != self.pointer:
                raise RuntimeError('Native application provider copy result differs')
            copied = self.snapshot()
            if set((copied['descriptor'], copied['normalized'], copied['map_normalized'], *copied['players'])) & set((source_children['descriptor'], source_children['normalized'], source_children['map_normalized'], *source_children['players'])):
                raise ValueError('Native application clone shares owned submaps with Core')
            cleanup_safe = True
            if provider_snapshot(self.base, self.source_provider, self.read, call, core_sha256=self._configuration_abi.core_sha256) != source_children:
                raise ValueError('Native application clone changed the source map topology')
            if emit:
                emit('native_application_configuration_cloned', source_proof_sha256=self._configuration_abi.application_proof_sha256, source_provider=self.source_provider, application_provider=self.pointer, distinct_owned_submaps=66, scalar_value_equality_not_yet_checked=True, original_prep_then_new_game_order_required=True, eligible_for_training=False)
        except Exception as error:
            error.native_configuration_owner = self
            if cleanup_safe and self.storage.raw[:16] == _GUARD and (self.storage.raw[-16:] == _GUARD):
                if setup._qword(self.read, self.pointer) == self.base + self._configuration_abi.vtable_rva:
                    try:
                        setup._invoke(call, self.base + self._configuration_abi.destructor_rva, None, self.pointer)
                    finally:
                        self.closed = True
            raise

    def _check_guard(self):
        if self.closed:
            raise RuntimeError('Native application configuration has been closed')
        if self.storage.raw[:16] != _GUARD or self.storage.raw[-16:] != _GUARD:
            raise RuntimeError('Native application provider exceeded its 0x58-byte storage')

    def require_context(self, base, context):
        self._check_guard()
        if (base, context) != (self.base, self.context):
            raise ValueError('Application configuration belongs to another native context')

    def snapshot(self):
        self._check_guard()
        return provider_snapshot(self.base, self.pointer, self.read, self.call, core_sha256=self._configuration_abi.core_sha256)

    def verify_core_copy_topology(self):
        """Reacquire A after NewGame; do not reuse its pre-copy child pointers."""
        if not self.new_game_entered:
            raise ValueError('Core copy topology can only be checked after entering NewGame')
        self._check_guard()
        current = setup._linked_snapshot(self.base, self.context, self.read, self.call, core_sha256=self._configuration_abi.core_sha256)
        application = self.snapshot()

        def addresses(snapshot):
            return {snapshot['descriptor'], snapshot['normalized'], snapshot['map_normalized'], *snapshot['players']}
        if addresses(current) & addresses(application):
            raise ValueError('Core and application configurations share an owned submap')
        return {'core_application_submaps_distinct': True, 'checked_submap_count': 66, 'core_player_records_reacquired': 64, 'all_property_values_compared': False, 'source_proof_sha256': self._configuration_abi.application_proof_sha256, 'eligible_for_training': False}

    def player(self, index, *, candidate_backend=None):
        if type(index) is not int or not 0 <= index < 64:
            raise ValueError('Application configuration player index is outside 0..63')
        self._check_guard()
        table = self.base + self._configuration_abi.vtable_rva
        if setup._qword(self.read, self.pointer) != table or setup._qword(self.read, table + 88) != self.base + self._configuration_abi.lookup_rva:
            raise ValueError('Application player provider/lookup identity changed')
        if candidate_backend is None:
            key = verify_source(core_sha256=self._configuration_abi.core_sha256)['player_keys'][index]['hash']
        else:
            from civ6_host.runtime.xp1_load_capability import candidate_player_key
            key = candidate_player_key(self, index, candidate_backend)
        key_address = self.base + self._configuration_abi.player_key_table_rva + index * 68
        if struct.unpack('<I', setup._read(self.read, key_address, 4))[0] != key:
            raise ValueError('Application PLAYER key changed')
        node = setup._invoke(self.call, self.base + self._configuration_abi.lookup_rva, C.c_void_p, self.pointer, (C.c_uint32,), key)
        if not node:
            raise LookupError('Application PLAYER submap is absent')
        raw = setup._read(self.read, node, 24)
        pointer = struct.unpack_from('<Q', raw, 8)[0]
        if struct.unpack_from('<H', raw)[0] != 10 or struct.unpack_from('<I', raw, 20)[0] != 83886080 or (not pointer) or (setup._qword(self.read, pointer) != table):
            raise ValueError('Application PLAYER submap is not the native owned profile')
        return {'index': index, 'pointer': pointer, 'provider': self.pointer, 'pointer_is_borrowed': True, 'source_proof_sha256': self._configuration_abi.application_proof_sha256}

    def close(self):
        self._check_guard()
        try:
            setup._invoke(self.call, self.base + self._configuration_abi.destructor_rva, None, self.pointer)
        finally:
            self.closed = True
        if self.storage.raw[:16] != _GUARD or self.storage.raw[-16:] != _GUARD:
            raise RuntimeError('Native application destructor exceeded its guarded storage')
        if self.emit:
            self.emit('native_application_configuration_destroyed', source_proof_sha256=self._configuration_abi.application_proof_sha256, outer_storage_freed_by_native=False, eligible_for_training=False)
from civ6_host.runtime.configuration_profiles import configuration_abi as _configuration_abi
from civ6_host.runtime.configuration_profiles import require_owner_profile as _require_owner_profile
from civ6_host.runtime.configuration_profiles import application_source as _expansion_application_source
from civ6_host.runtime.configuration_profiles import codec_source as _expansion_codec_source
