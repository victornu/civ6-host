"""Inspection-only proposal for GAME_VALUE_CHANGED; no acknowledgement yet.

The direct missing-destination branch is known. The original EXE temporary
constructor's mutations are not reproduced, so dispatch deliberately refuses.
Read/call seams support pure tests; this module never loads a native library.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import ctypes as C
import hashlib
import json
from pathlib import Path
import struct
from civ6_host.runtime.native.native_source_cache import load_pinned_json
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_game_value_mirror_inspection.py')))).resolve().parents[1]
PROOF_SHA256 = 'eeea976faf3f7f72bb43e5ebd383c9255867d4d135bd6bf7a21d1ee16e89db82'
KIND, ARGUMENT_KEY, PROPERTY_KEY = (779060372, 2716180809, 604523296)
ARGUMENT_TABLE, GETTER, MAP_TABLE, LOOKUP = (8509496, 7652928, 8507296, 7625904)

class UnclosedApplicationPrelude(RuntimeError):

    def __init__(self, receipt):
        super().__init__('EXE application temporary prelude is not yet reproduced; dispatch return withheld')
        self.receipt = receipt

def verify_source():
    path = ROOT / 'evidence/native-host-game-value-change' / f'{PROOF_SHA256}.json'
    try:
        doc = load_pinned_json(path, PROOF_SHA256)
    except RuntimeError as error:
        raise ValueError('Game-value source changed') from error
    contract = doc['contract']
    if doc['schema'] != 'civ6rl.native_host_game_value_change.static.v1' or contract['kind'] != KIND or contract['property_key'] != PROPERTY_KEY or (contract['native_return'] != 0) or (contract['deferred_records'] != 0) or (contract['full_EXE_temporary_lifecycle_equivalence_to_current_host_proven'] is not False):
        raise ValueError('Game-value proof contract changed')
    return doc

def _read(read, pointer, size):
    if type(pointer) is not int or pointer <= 0 or pointer > (1 << 64) - size:
        raise ValueError('Invalid bounded native address')
    raw = read(pointer, size)
    if type(raw) is not bytes or len(raw) != size:
        raise ValueError('Short native read')
    return raw

def _u64(read, pointer):
    return struct.unpack('<Q', _read(read, pointer, 8))[0]

def _scalar(raw, tag):
    if len(raw) != 24 or struct.unpack_from('<H', raw)[0] != tag or struct.unpack_from('<I', raw, 20)[0] != 0:
        raise ValueError('Unverified direct scalar tag/flags')
    return struct.unpack_from('<I', raw, 8)[0]

def inspect_game_value_notification(base, kind, argument, source_store, *, core_snapshot, application_snapshot, read, call):
    """Inspect the existing-owned-view proposal, never copy/insert/acknowledge.

    Callers must acquire snapshots via _linked_snapshot/provider_snapshot and
    validate ownership on both sides; this helper checks their pointer binding.
    call has the same ABI seam as native_configuration_finalization._invoke.
    """
    proof = verify_source()
    if type(kind) is not int or kind != KIND:
        raise ValueError('Unknown game-value kind')
    pointers = (core_snapshot['descriptor'], core_snapshot['normalized'], application_snapshot['descriptor'], application_snapshot['normalized'])
    if len(set(pointers)) != 4 or source_store != pointers[0]:
        raise ValueError('Source/store ownership does not match distinct A/B views')
    for pointer in pointers:
        if _u64(read, pointer) != base + MAP_TABLE:
            raise ValueError('Provider/map vtable changed')
    if _u64(read, base + MAP_TABLE + 88) != base + LOOKUP:
        raise ValueError('Provider lookup slot changed')
    if struct.unpack('<I', _read(read, base + 9161852, 4))[0] != PROPERTY_KEY:
        raise ValueError('LAST_TURN_PHASE_TYPE native key changed')
    if _u64(read, argument) != base + ARGUMENT_TABLE or _u64(read, base + ARGUMENT_TABLE + 104) != base + GETTER:
        raise ValueError('Argument getter/table changed')
    begin, end, capacity = struct.unpack('<QQQ', _read(read, argument + 40, 24))
    if not begin or end != begin + 32 or capacity < end:
        raise ValueError('Expected exactly one argument entry')
    if struct.unpack('<I', _read(read, begin, 4))[0] != ARGUMENT_KEY:
        raise ValueError('Argument key changed')
    for name in ('argument_getter', 'property_lookup'):
        body = proof['core_functions'][name]
        for fragment in body['fragments']:
            for ins in fragment['instructions']:
                data = bytes.fromhex(ins['bytes'])
                if _read(read, base + int(ins['va'], 16) - 6442450944, len(data)) != data:
                    raise ValueError('Native getter code changed')
    field = call(base + GETTER, C.c_void_p, (C.c_uint32,), argument, ARGUMENT_KEY)
    if field != begin + 8:
        raise ValueError('Argument getter did not return the actual single entry')
    raw_field = _read(read, field, 24)
    if _scalar(raw_field, 3) != PROPERTY_KEY:
        raise ValueError('Unadmitted game property')
    source = call(base + LOOKUP, C.c_void_p, (C.c_uint32,), pointers[1], PROPERTY_KEY)
    if not source:
        raise ValueError('Missing source branch not admitted by this diagnostic')
    source_raw = _read(read, source, 24)
    value = _scalar(source_raw, 2)
    destination = call(base + LOOKUP, C.c_void_p, (C.c_uint32,), pointers[3], PROPERTY_KEY)
    if destination:
        raise ValueError('Present destination requires a separate native-copy profile')
    if _read(read, source, 24) != source_raw or _read(read, field, 24) != raw_field or _read(read, argument + 40, 24) != struct.pack('<QQQ', begin, end, capacity):
        raise ValueError('Notification changed during inspection')
    return {'kind': KIND, 'property_key': PROPERTY_KEY, 'property_name': 'LAST_TURN_PHASE_TYPE', 'source_value': value, 'source_tag': 2, 'source_store_validated': True, 'destination_presence_checked_live': True, 'destination_present': False, 'mirrored': False, 'cell_created': False, 'journal_entries_added': 0, 'source_proof_sha256': PROOF_SHA256, 'native_branch': 'missing_destination', 'native_return_if_full_prelude_closed': 0, 'acknowledgement_permitted': False, 'logger_state_observed': False, 'full_EXE_temporary_lifecycle_equivalent': False, 'source_gameplay_modified': False, 'eligible_for_training': False}

def dispatch_game_value_notification(*args, **kwargs):
    receipt = inspect_game_value_notification(*args, **kwargs)
    raise UnclosedApplicationPrelude(receipt)
