"""Native variant assignment for the present-source/present-destination branch."""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from civ6_host.runtime.configuration_profiles import BASE_CORE_SHA256 as _BASE_CORE
from civ6_host.runtime import application_mirror_profiles as _mirror_profiles
from civ6_host.runtime.application_mirror_profiles import mirror_abi as _mirror_abi
import ctypes as C
from pathlib import Path
import struct
from civ6_host.runtime.native import native_configuration_finalization as setup
from civ6_host.runtime.native.native_source_cache import load_pinned_json
PROOF_SHA256 = '3abc69a0ad859801ca5003a619c2e186e6f6434fa7384e29e175b748e15b6fa5'
_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_application_property_copy.py')))).resolve().parents[1] / 'evidence/native-application-property-copy' / (PROOF_SHA256 + '.json')
_TABLE, _LOOKUP, _ALLOCATOR, _ASSIGN = (8507296, 7625904, 7661648, 7633632)

def verify_source(*, core_sha256=_BASE_CORE):
    if core_sha256 != _BASE_CORE:
        return _mirror_profiles.copy_source(core_sha256)
    proof = load_pinned_json(_PROOF, PROOF_SHA256)
    contract = proof.get('contract', {})
    if proof.get('schema') != 'civ6rl.native_application_property_copy.static.v1' or proof.get('images') != {'core_sha256': setup.CORE_SHA256, 'exe_sha256': setup.EXE_SHA256} or contract.get('event_kind') != 1829978708 or (contract.get('creates_absent_destination') is not False) or (contract.get('copy_abi', {}).get('core_rva') != _ASSIGN) or (proof.get('copy_comparison', {}).get('all_normalized_instructions_identical') is not True) or (proof.get('validation', {}).get('all_captured_instructions_match_pinned_pe') is not True):
        raise RuntimeError('Application property assignment source changed')
    return proof

def copy_existing(base, source_map, destination_map, key, *, read, call=None, core_sha256=_BASE_CORE):
    """Return the native presence branch; never create an absent property.

    The native function controls every type-specific clone/release operation.
    Its return register is ignored exactly as in the original dispatcher.
    The caller owns both providers and appends the notification journal only
    after this function returns a successful copy branch.
    """
    abi = _mirror_abi(core_sha256)
    if type(key) is not int or not 0 <= key <= 4294967295:
        raise ValueError('Application property key must be uint32')
    if source_map == destination_map:
        raise ValueError('Native property source and destination must be distinct')
    proof = verify_source(core_sha256=core_sha256)
    for name in ('variant_clone_assign', 'variant_release', 'provider_allocator', 'lookup'):
        for fragment in proof['core_functions'][name]['fragments']:
            for ins in fragment['instructions']:
                raw = bytes.fromhex(ins['bytes'])
                if setup._read(read, base + int(ins['va'], 16) - 6442450944, len(raw)) != raw:
                    raise ValueError('Native application property code differs: ' + name)
    table = base + abi.configuration.vtable_rva
    for pointer in (source_map, destination_map):
        if type(pointer) is not int or pointer <= 0 or setup._qword(read, pointer) != table:
            raise ValueError('Unexpected property source/destination map')
    for slot, rva in ((88, abi.configuration.lookup_rva), (32, abi.allocator_get_rva)):
        if setup._qword(read, table + slot) != base + rva:
            raise ValueError('Native property lookup/allocator slot differs')
    source = setup._invoke(call, base + abi.configuration.lookup_rva, C.c_void_p, source_map, (C.c_uint32,), key)
    if not source:
        return {'mirrored': False, 'native_branch': 'missing_source'}
    destination = setup._invoke(call, base + abi.configuration.lookup_rva, C.c_void_p, destination_map, (C.c_uint32,), key)
    if not destination:
        return {'mirrored': False, 'native_branch': 'missing_destination'}
    if source == destination:
        raise ValueError('Native property variants unexpectedly alias')
    raw = setup._read(read, source, 24)
    setup._read(read, destination, 24)
    allocator = setup._invoke(call, base + abi.allocator_get_rva, C.c_void_p, destination_map)
    setup._invoke(call, base + abi.variant_assign_rva, None, destination, (C.c_void_p, C.c_void_p), source, allocator)
    after = setup._read(read, destination, 24)
    if setup._read(read, source, 24) != raw:
        raise ValueError('Native application assignment changed its source variant')
    tag, flags = (struct.unpack_from('<H', raw)[0], struct.unpack_from('<I', raw, 20)[0])
    if not flags & 1 << 29 and tag not in (8, 10, 11, 22):
        if struct.unpack_from('<H', after)[0] != tag or after[8:16] != raw[8:16]:
            raise ValueError('Native scalar application copy changed tag/payload')
    return {'mirrored': True, 'native_branch': 'copy_and_queue', 'source_variant_tag': tag, 'source_variant_flags': flags, 'source_proof_sha256': abi.copy_proof_sha256}

def read_civilization_result(application, index, *, expected_hash=None, core_sha256=_BASE_CORE):
    """Apply EXE114D20, including its known native zero branch, to provider B."""
    abi = _mirror_profiles.owner_abi(application, core_sha256)
    proof = _mirror_profiles.civilization_source(core_sha256)
    base, read, call = (application.base, application.read, application.call)
    record = application.player(index)
    table = base + abi.configuration.vtable_rva
    if setup._qword(read, table + 104) != base + proof['getter_rva']:
        raise ValueError('Application civilization getter slot differs')
    for fragment in proof['core_functions']['value_getter']['fragments']:
        for ins in fragment['instructions']:
            raw = bytes.fromhex(ins['bytes'])
            if setup._read(read, base + int(ins['va'], 16) - 6442450944, len(raw)) != raw:
                raise ValueError('Native application civilization getter differs')
    pointer = setup._invoke(call, base + proof['getter_rva'], C.c_void_p, record['pointer'], (C.c_uint32,), 3352777051)
    if not pointer:
        raise ValueError('Native nonnullable civilization getter returned NULL')
    raw = setup._read(read, pointer, 24)
    tag, flags = (struct.unpack_from('<H', raw)[0], struct.unpack_from('<I', raw, 20)[0])
    allowed = not flags & 1 << 29 and tag <= 21 and bool(3145774 & 1 << tag)
    value = struct.unpack_from('<I', raw, 8)[0] if allowed else 0
    if allowed and expected_hash is not None and (value != expected_hash):
        raise ValueError('Application civilization differs from the configured expected identity')
    if application.player(index) != record or setup._read(read, pointer, 24) != raw:
        raise ValueError('Application civilization value changed during native read')
    if application.emit:
        application.emit('native_application_civilization_value_read', player_index=index, value=value, source_variant_tag=tag, source_variant_flags=flags, source_default_zero=not allowed, civilization_identity_validated=allowed and expected_hash is not None, source_provider='separate-application-configuration', source_proof_sha256=proof['source_sha256'], eligible_for_training=False)
    return value
