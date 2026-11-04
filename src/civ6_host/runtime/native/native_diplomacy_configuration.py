"""Read the restored application provider for official UI configuration getters.

This transports native configuration data into two Lua read methods. It does
not change player assignments or substitute the gameplay Player:IsHuman API.
"""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import ctypes as C
import struct
from pathlib import Path
from civ6_host.runtime.native.native_source_cache import load_pinned_json
from civ6_host.runtime.native.native_game_configuration import game_configuration_hash
from civ6_host.runtime.native.native_player_configuration import _checked_object
from civ6_host.runtime.native.native_player_configuration import VALUE_GETTER_SLOT
from civ6_host.runtime.native.native_player_configuration import VALUE_GETTER_RVA
from civ6_host.runtime.native.native_configuration_finalization import _invoke
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_diplomacy_configuration.py')))).resolve().parents[1]
PROOF_SHA256 = '84fce676a2438dd67001f44658e6ccaea00bd7dc7663bfcd8307f568214d83eb'

def verify_source():
    proof = load_pinned_json(ROOT / 'evidence/native-diplomacy-configuration' / (PROOF_SHA256 + '.json'), PROOF_SHA256)
    from civ6_host.runtime.native.native_configuration_finalization import CORE_SHA256
    from civ6_host.runtime.native.native_configuration_finalization import EXE_SHA256
    if proof['schema'] != 'civ6rl.diplomacy_configuration948.static.v1' or proof['images'] != {'core_sha256': CORE_SHA256, 'exe_sha256': EXE_SHA256} or proof['contract']['human_mask'] != 3145774 or (proof['contract']['human_slot_status'] != 3) or (not proof['validation']['all_captured_instructions_match_pinned_pe']):
        raise ValueError('Diplomacy configuration getter contract changed')
    return proof

def human(raw):
    if type(raw) is not bytes or len(raw) != 24:
        raise ValueError('Invalid config variant')
    tag = struct.unpack_from('<H', raw)[0]
    flags = struct.unpack_from('<I', raw, 20)[0]
    value = struct.unpack_from('<I', raw, 8)[0] if not flags & 1 << 29 and tag <= 21 and 3145774 >> tag & 1 else 0
    return value == 3

def leader(raw, read):
    if type(raw) is not bytes or len(raw) != 24:
        raise ValueError('Invalid config variant')
    tag = struct.unpack_from('<H', raw)[0]
    pointer, flags = (struct.unpack_from('<Q', raw, 8)[0], struct.unpack_from('<I', raw, 20)[0])
    if tag != 5 or not flags & 1 << 29 or (not pointer):
        return None
    data = bytearray()
    for offset in range(256):
        value = read(pointer + offset, 1)
        if type(value) is not bytes or len(value) != 1:
            raise ValueError('Short native leader read')
        if value == b'\x00':
            return bytes(data).decode('utf8')
        data.extend(value)
    raise RuntimeError('Native leader identifier exceeds read bound')

def read(owner, statement):
    verify_source()
    app = owner.owner
    base = owner.core._handle
    reader = owner.runtime.read
    app.require_context(base, owner.context)
    before = app.snapshot()
    f = statement['fields']
    from_id = f['FromPlayer']
    initiator = f['Initiator']
    if type(from_id) is not int or not 0 <= from_id < 64:
        raise ValueError('Invalid configuration participant')
    ids = {from_id}
    if type(initiator) is int and 0 <= initiator < 64:
        ids.add(initiator)
    result = {}
    for pid in sorted(ids):
        pointer = before['players'][pid]
        getter = _checked_object(base, pointer, reader, VALUE_GETTER_SLOT, VALUE_GETTER_RVA)

        def value(key):
            address = _invoke(None, getter, C.c_void_p, pointer, (C.c_uint32,), game_configuration_hash(key))
            if type(address) is not int or address <= 0:
                raise RuntimeError('Native config getter returned null')
            return reader(address, 24)
        row = {}
        if pid == from_id:
            row['leader'] = leader(value('LEADER_TYPE_NAME'), reader)
        if pid == initiator:
            row['human'] = human(value('SLOT_STATUS'))
        result[pid] = row
    if app.snapshot() != before:
        raise RuntimeError('Application provider changed during diplomacy read')
    owner.emit('native_diplomacy_application_configuration_read', players=result, provider='restored_application_B', source_sha256=PROOF_SHA256, gameplay_player_human_substituted=False, native_configuration_written=False, eligible_for_training=False)
    return result

def lua_bindings(rows):
    from civ6_host.runtime.native.native_script_parameters import lua_string
    if type(rows) is not dict or not 1 <= len(rows) <= 2:
        raise ValueError('Invalid scoped configuration reads')
    out = ['local PlayerConfigurations={}']
    for pid, row in sorted(rows.items()):
        if type(pid) is not int or not 0 <= pid < 64 or type(row) is not dict or (not set(row) <= {'leader', 'human'}):
            raise ValueError('Invalid configuration read fields')
        methods = []
        if 'leader' in row:
            if row['leader'] is not None and type(row['leader']) is not str:
                raise ValueError('Invalid leader read')
            value = 'nil' if row['leader'] is None else lua_string(row['leader'].encode('utf8'))
            methods.append('GetLeaderTypeName=function() return ' + value + ' end')
        if 'human' in row:
            if type(row['human']) is not bool:
                raise ValueError('Invalid human flag')
            methods.append('IsHuman=function() return ' + str(row['human']).lower() + ' end')
        out.append('PlayerConfigurations[%d]={%s}' % (pid, ','.join(methods)))
    return ('\n'.join(out) + '\n').encode('ascii')
