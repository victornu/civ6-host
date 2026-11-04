"""Run the pinned original setup preparation, once before the first NewGame.

These are real native configuration mutations, including player resolution.
The adapter neither fills derived fields itself nor suppresses callbacks. Its
caller owns lifecycle/ordering and must install services and finish options,
ruleset, map and player assignments first. A partial failure is not rolled back.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import ctypes as C
from pathlib import Path
import struct
from civ6_host.runtime.native.native_source_cache import load_pinned_json
from civ6_host.runtime.native.native_setup import local_reader
PROOF_SHA256 = 'b5ab78ce390d52b4da54d694e85d0545d880d500daf2913bff04ccd72cdf5172'
_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_configuration_finalization.py')))).resolve().parents[1] / 'evidence/native-configuration-finalization' / (PROOF_SHA256 + '.json')
CORE_SHA256 = 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'
EXE_SHA256 = 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
OUTER_VTABLE = 7987232
INNER_VTABLE = 8155256
CONFIG_VTABLE = 8507296
LOOKUP_RVA = 7625904
GAME_ROOT_KEY = 2266848099
PREPARATION = ((320, 4387728), (328, 4387664), (336, 4387600))
_LIVE_BODIES = ('outer_140', 'outer_148', 'outer_150', 'configuration_lookup', 'outer_initialized', 'inner_initialized')

class FinalizationError(RuntimeError):
    """Failure after a native preparation returned; previous effects remain."""

    def __init__(self, message, call_results, attempted_slots=()):
        super().__init__(message)
        self.call_results = tuple((dict(row) for row in call_results))
        self.attempted_slots = tuple(attempted_slots)
        self.native_effects_may_have_occurred = bool(attempted_slots)

def verify_source():
    proof = load_pinned_json(_PROOF, PROOF_SHA256)
    if proof.get('schema') != 'civ6rl.native_configuration_finalization.static.v1' or proof.get('images') != {'core_sha256': CORE_SHA256, 'exe_sha256': EXE_SHA256} or proof.get('native_execution') is not False or (tuple(proof.get('contract', {}).get('source_order', ())) != (320, 328, 336)) or (proof.get('contract', {}).get('source_before_new_game') is not True) or (proof.get('GAME_ROOT', {}).get('hash') != GAME_ROOT_KEY) or (proof.get('configuration_vtable', {}).get('rva') != CONFIG_VTABLE) or (proof.get('validation', {}).get('all_captured_instructions_match_pinned_pe') is not True):
        raise RuntimeError('Native configuration finalization source contract changed')
    for slot, rva in PREPARATION:
        if proof['outer_slots']['slots'].get(hex(slot)) != hex(6442450944 + rva):
            raise RuntimeError('Native preparation slot source changed')
    return proof

def _read(read, address, size):
    if type(address) is not int or address <= 0 or (not 0 < size <= 6784):
        raise ValueError('Invalid bounded configuration memory read')
    raw = read(address, size)
    if type(raw) is not bytes or len(raw) != size:
        raise ValueError('Incomplete native configuration memory copy')
    return raw

def _qword(read, address):
    return struct.unpack('<Q', _read(read, address, 8))[0]

def _invoke(call, address, result_type, receiver, arg_types=(), *arguments):
    if call is not None:
        return call(address, result_type, tuple(arg_types), receiver, *arguments)
    return C.WINFUNCTYPE(result_type, C.c_void_p, *arg_types)(address)(receiver, *arguments)

def _boolean(value, name):
    if type(value) is not bool:
        raise ValueError(name + ' must return a native Boolean')
    return value

def _live_code(proof, base, read):
    for name in _LIVE_BODIES:
        for fragment in proof['core_functions'][name]['fragments']:
            for ins in fragment['instructions']:
                raw = bytes.fromhex(ins['bytes'])
                address = base + int(ins['va'], 16) - 6442450944
                if _read(read, address, len(raw)) != raw:
                    raise ValueError('Native configuration code mismatch: ' + name)

def _snapshot(base, context, read, *, core_sha256=CORE_SHA256):
    abi = _require_owner_profile(_configuration_abi(core_sha256))
    outer, inner = struct.unpack('<QQ', _read(read, context, 16))
    if outer != base + abi.load.outer_vtable_rva or not inner or _qword(read, inner) != base + abi.load.inner_vtable_rva:
        raise ValueError('Unexpected native configuration context identity')
    for slot, rva in ((56, abi.initialized_getter_rva), *abi.preparation):
        if _qword(read, outer + slot) != base + rva:
            raise ValueError('Unverified native configuration outer slot')
    table = base + abi.vtable_rva
    if _qword(read, table + 88) != base + abi.lookup_rva:
        raise ValueError('Unverified native descriptor lookup')
    for slot, rva in ((304, abi.uint_setter_rva), (376, abi.copy_rva)):
        if _qword(read, table + slot) != base + rva:
            raise ValueError('Unverified native configuration mutation slot')
    setup = inner + 3456
    descriptor, normalized = struct.unpack('<QQ', _read(read, setup + 128, 16))
    map_descriptor, map_normalized = struct.unpack('<QQ', _read(read, setup + 3112, 16))
    if map_descriptor != descriptor:
        raise ValueError('Map and game do not share the source configuration descriptor')
    for pointer in (descriptor, normalized, map_descriptor, map_normalized):
        if not pointer or _qword(read, pointer) != table:
            raise ValueError('Missing or unverified native configuration/map object')
    begin, end, capacity = struct.unpack('<QQQ', _read(read, setup + 144, 24))
    if begin != setup + 184 or end != begin + 64 * 32 or capacity != end:
        raise ValueError('Native setup player vector is not the fixed complete 64-record layout')
    players = []
    for index in range(64):
        raw = _read(read, begin + index * 32, 32)
        observed_index = struct.unpack_from('<I', raw)[0]
        provider, value, owner = struct.unpack_from('<QQQ', raw, 8)
        if observed_index != index or provider != descriptor or owner != setup or (not value) or (_qword(read, value) != table):
            raise ValueError('Missing or unverified native player configuration at index ' + str(index))
        players.append(value)
    if not _qword(read, inner + 80) or not _qword(read, inner + 88):
        raise ValueError('Native configuration/gameplay database connection is absent')
    return {'inner': inner, 'descriptor': descriptor, 'normalized': normalized, 'map_normalized': map_normalized, 'players': tuple(players)}

def _linked_snapshot(base, context, read, call, *, core_sha256=CORE_SHA256):
    abi = _require_owner_profile(_configuration_abi(core_sha256))
    state = _snapshot(base, context, read, core_sha256=core_sha256)
    if not _boolean(_invoke(call, base + abi.initialized_getter_rva, C.c_bool, context), 'Context initialized getter'):
        raise ValueError('Native context Init must have completed before configuration preparation')
    root_key = struct.unpack('<I', _read(read, base + abi.root_key_rva, 4))[0]
    map_key = struct.unpack('<I', _read(read, base + abi.map_key_rva, 4))[0]
    player_keys = tuple((struct.unpack('<I', _read(read, base + abi.player_key_table_rva + i * 68, 4))[0] for i in range(64)))
    if root_key != GAME_ROOT_KEY or not map_key or any((not key for key in player_keys)) or (len(set((root_key, map_key, *player_keys))) != 66):
        raise ValueError('Native configuration root/player keys are not initialized uniquely')
    for key, expected in ((root_key, state['normalized']), (map_key, state['map_normalized']), *zip(player_keys, state['players'])):
        variant = _invoke(call, base + abi.lookup_rva, C.c_void_p, state['descriptor'], (C.c_uint32,), key)
        if type(variant) is not int or variant <= 0:
            raise ValueError('Native descriptor has no source tag-A submap')
        raw = _read(read, variant, 16)
        if struct.unpack_from('<H', raw)[0] != 10 or struct.unpack_from('<Q', raw, 8)[0] != expected:
            raise ValueError('Native descriptor submap differs from the already-owned setup')
    if _snapshot(base, context, read, core_sha256=core_sha256) != state:
        raise ValueError('Native configuration identities changed during validation')
    return state

def finalize_setup(core, context, *, before_new_game, configuration_ready, read=None, call=None, emit=None, application_configuration=None):
    """Call 140, 148, 150 in source order on the existing descriptor.

    Required Boolean flags are caller protocol assertions, not native getters.
    ``before_new_game`` means before the first +130; ``configuration_ready``
    means options/ruleset/map/player assignments and host services are complete.
    Native +38 is independently required to be true (context Init, not NewGame).
    Source copies, callbacks, allocation and destruction run inside the original
    functions. ``read``/``call`` are dependency seams for pure tests only.
    """
    if before_new_game is not True or configuration_ready is not True:
        raise ValueError('Configuration finalization requires an explicit complete pre-NewGame setup')
    base = getattr(core, '_handle', None)
    if type(base) is not int or base <= 0 or type(context) is not int or (context <= 0):
        raise ValueError('Invalid pinned native image/context pointer')
    if emit is not None and (not callable(emit)):
        raise ValueError('Configuration emitter must be callable')
    proof = verify_source()
    read = local_reader() if read is None else read
    _live_code(proof, base, read)
    initial = _linked_snapshot(base, context, read, call)
    external = application_configuration
    source_state = None
    descriptor = initial['descriptor']
    if external is not None:
        external.require_context(base, context)
        if external.new_game_entered:
            raise ValueError('Application preparation cannot follow NewGame')
        source_state = external.snapshot()
        descriptor = source_state['descriptor']
        if descriptor == initial['descriptor']:
            raise ValueError('The application descriptor must be separate from Core')
    results = []
    attempted = []
    for slot, rva in PREPARATION:
        try:
            if _linked_snapshot(base, context, read, call) != initial:
                raise ValueError('Native configuration identities changed before preparation')
            if external is not None and external.snapshot() != source_state:
                raise ValueError('Application configuration identities changed before preparation')
            attempted.append(slot)
            value = _boolean(_invoke(call, base + rva, C.c_bool, context, (C.c_void_p,), descriptor), 'Native preparation')
            results.append({'slot': slot, 'target_rva': rva, 'return_value': value})
            if emit is not None:
                emit('native_configuration_preparation_returned', **results[-1], source_proof_sha256=PROOF_SHA256)
            if not value:
                raise RuntimeError('Native configuration preparation returned false at ' + hex(slot))
            if _linked_snapshot(base, context, read, call) != initial:
                raise ValueError('Native configuration identities changed after preparation')
            if external is not None and external.snapshot() != source_state:
                raise ValueError('Application configuration identities changed after preparation')
        except Exception as error:
            raise FinalizationError(str(error), results, attempted) from error
    return {'source_proof_sha256': PROOF_SHA256, 'context_initialized': True, 'before_new_game_caller_asserted': True, 'configuration_ready_caller_asserted': True, 'call_results': results, 'all_returned_true': True, 'descriptor_identity_verified': True, 'player_record_count': 64, 'configuration_modified_by_native_code': True, 'descriptor_profile': 'separate-application-provider' if external is not None else 'existing-core-provider-diagnostic', 'native_new_game_called': False, 'derived_values_readback_required': True}
from civ6_host.runtime.configuration_profiles import configuration_abi as _configuration_abi
from civ6_host.runtime.configuration_profiles import require_owner_profile as _require_owner_profile
from civ6_host.runtime.configuration_profiles import application_source as _expansion_application_source
from civ6_host.runtime.configuration_profiles import codec_source as _expansion_codec_source
