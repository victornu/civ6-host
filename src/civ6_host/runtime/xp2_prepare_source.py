"""Source and live-owner checks for the private XP2 Prepare service group."""
from __future__ import annotations

import ctypes as C
import hashlib
from pathlib import Path
import struct

from .configuration_profiles import _source
from .resource_resolution import resolve_path
from .saved_load_profiles import XP2_CORE_SHA256

SOURCE = ('work/host-extensions/xp2-prepare-services/source-profile-v1.json',
          '6902ee066de66136ef5ceac7dfe203bd7c87145d6ae2b271206a5b0141a81e6e')
PINS = ('work/host-extensions/xp2-prepare-services/pins-v1.json',
        'b81a1e8d800f9d4c069b09123e7fcf0d4365922858ea66a9f485304276ce5cfb')
TYPE_NAMES = ('Unit', 'Formation', 'City::Instance', 'Trade::Edge',
              'Control::Contract', 'District::Instance', 'AI::CityBuild',
              'BehaviorTree', 'AI::Operation', 'DynamicModifier')
CALLBACK_RVAS = ((0x64fa80,0x64fb50),(0x64fa10,0x64fb00),(0x141240,0x141c10),
    (0x38df60,0x38e1b0),(0x3fe9f0,0x3fec50),(0x1412c0,0x141e00),
    (0x3d8e60,0x3d8f40),(0x5637c0,0x5638e0),(0x4ce250,0x4ce3c0),(0x94bc70,0x94cbc0))
PREFERRED_BASE = 0x180000000
GAME_VTABLE_RVA = 0xa45160
GAME_INITIALIZED_OFFSET = 0x2a4


def _hash(raw):
    return hashlib.sha256(raw).hexdigest()


def _fragments(proof):
    for name, body in proof['bodies'].items():
        parts = []
        for fragment in body['fragments']:
            raw = bytes.fromhex(fragment['raw_hex'])
            if (not 0 < len(raw) == fragment['length'] <= 65536
                    or _hash(raw) != fragment['sha256']
                    or ''.join(row['bytes'] for row in fragment['instructions']) != raw.hex()):
                raise ValueError('XP2 Prepare source fragment differs: ' + name)
            parts.append(raw)
            yield name, int(fragment['start_rva'],16), raw
        raw = b''.join(parts)
        if (raw.hex() != body['raw_hex'] or len(raw) != body['bytes']
                or _hash(raw) != body['sha256']
                or body['all_conditional_targets_captured'] is not True
                or body['boundary_method'] not in (
                    'complete-runtime-function-chained-unwind-root-v2',
                    'complete-reachable-leaf-cfg-v1')):
            raise ValueError('XP2 Prepare complete body differs: ' + name)


def verify_source():
    from .xp2_context_profile import verify_source as bootstrap_source
    from .native.native_host import BOOTSTRAP_TYPE_NAMES
    proof, pins = _source(SOURCE), _source(PINS)
    if (proof['schema'] != 'civ6rl.xp2-prepare-services.source-profile-v1'
            or proof['image']['sha256'] != XP2_CORE_SHA256
            or pins['profile']['sha256'] != SOURCE[1]
            or pins['image_sha256'] != XP2_CORE_SHA256
            or proof['qualification']['native_execution'] is not False):
        raise ValueError('XP2 Prepare source identity differs')
    engine = proof['engine']
    expected = dict(ruleset='xp2', core_sha256=XP2_CORE_SHA256,
        outer_vtable_rva=0xa101e8, inner_vtable_rva=0xa44f70,
        outer_prepare_slot=0x40, outer_prepare_rva=0x591870,
        inner_prepare_slot=0x50, inner_prepare_rva=0x46be0,
        outer_initialized_slot=0x38, outer_initialized_rva=0x590660,
        inner_initialized_slot=None, inner_initialized_rva=0x46290,
        inner_offset=8, initialized_byte_offset=0x40, services_offset=0x60,
        tuner_offset=0x1a20, aligned_free_iat_rva=0x9b7680)
    if (any(engine.get(k) != v for k,v in expected.items())
            or tuple(tuple(row) for row in engine['type_callback_rvas']) != CALLBACK_RVAS
            or tuple(proof['registrations']['ordered_names']) != TYPE_NAMES
            or frozenset(TYPE_NAMES) != BOOTSTRAP_TYPE_NAMES
            or tuple(proof['registrations']['descriptor']['fields'].values()) != (0,8,16)):
        raise ValueError('XP2 Prepare selected engine contract differs')
    rows = proof['registrations']['requests']
    if len(rows) != 10 or any(row['name'] != name or tuple(int(r,16) for r in row['callback_pair_rva']) != pair
                             for row,name,pair in zip(rows,TYPE_NAMES,CALLBACK_RVAS)):
        raise ValueError('XP2 Prepare registration order/callbacks differ')
    archive = proof['archive']
    if (tuple(archive[k] for k in ('host_getter_slot','register_slot','remove_slot')) != (0x108,0,8)
            or tuple(archive['descriptor_fields'][k]['offset'] for k in ('active','interface','key')) != (0x48,0x50,0x58)
            or archive['register_abi']['restype'] != 'bool/AL'
            or proof['xp1_comparisons']['archive_register_helper']['byte_identical'] is not True):
        raise ValueError('XP2 archive ABI/ownership differs')
    tuner = proof['null_tuner']
    if (tuner['name'] != 'GameCore_Tuner' or tuner['explicit_diagnostic_required'] is not True
            or tuner['gameplay_optional_proven'] is not False
            or tuner['initial_state']['head_sentinel'] != 0xfffffff):
        raise ValueError('XP2 NULL Tuner diagnostic contract differs')
    game_rows = {row['rva']:row for name in ('services_constructor','services_derived_constructor')
                 for fragment in proof['bodies'][name]['fragments'] for row in fragment['instructions']}
    if (tuple(game_rows['0x75060e']['rip_targets']) != ('0x180a45160',)
            or game_rows['0x639853']['bytes'] != 'c787a402000000000001'):
        raise ValueError('XP2 allocated Game vtable/initial flag source differs')
    from .paths import resource_root
    root = resource_root()
    for row in (proof['capture_script'], *proof['extractors'], *proof['source_predecessors']):
        path = resolve_path(Path(row['path']))
        if not path.resolve().is_relative_to(root) or _hash(path.read_bytes()) != row['sha256']:
            raise ValueError('XP2 Prepare source dependency changed: ' + str(path))
    bootstrap = bootstrap_source()
    init_rows = [row for f in bootstrap['proof']['bodies']['inner_init']['fragments'] for row in f['instructions']]
    owner_store = next(row for row in init_rows if row['rva'] == '0x45ddd')
    if owner_store['bytes'] != '48891d7c4cb400' or tuple(owner_store['rip_targets']) != ('0x180b8aa60',):
        raise ValueError('XP2 initialized inner-owner source differs')
    return dict(proof=proof, engine=engine, fragments=tuple(_fragments(proof)),
        bootstrap=bootstrap, type_names=TYPE_NAMES, callback_rvas=CALLBACK_RVAS,
        receipt=dict(schema='civ6-host.xp2-prepare-source.v1', core_sha256=XP2_CORE_SHA256,
            source_path=SOURCE[0], source_sha256=SOURCE[1], pins_sha256=PINS[1],
            saved_load_admitted=False, native_execution=False))


def exact(read, address, size):
    if (type(address) is not int or not 0 < address < (1 << 47)
            or type(size) is not int or not 0 < size <= 65536
            or address + size >= (1 << 47)):
        raise ValueError('Invalid XP2 Prepare memory range')
    raw = read(address, size)
    if type(raw) is not bytes or len(raw) != size:
        raise ValueError('Incomplete XP2 Prepare memory read')
    return raw


def pointer(read, address):
    return struct.unpack('<Q', exact(read,address,8))[0]


def verify_live(base, context, host, read, contract, *, prepared=False):
    """Validate actual code, relocated tables, globals and the initialized child."""
    from .context_initialization import require_installed_globals
    from .xp2_context_profile import verify_live as bootstrap_live
    if type(base) is not int or not 0 < base < (1 << 47)-0x1000000:
        raise ValueError('Invalid XP2 Prepare module base')
    bootstrap_live(base,read,contract['bootstrap'])
    for name,rva,raw in contract['fragments']:
        if exact(read,base+rva,len(raw)) != raw:
            raise ValueError('XP2 Prepare live code differs: '+name)
    for capture in contract['proof']['vtable_captures'].values():
        raw = bytes.fromhex(capture['raw_hex'])
        if _hash(raw) != capture['sha256'] or len(raw)%8:
            raise ValueError('XP2 Prepare vtable source differs')
        values = struct.unpack('<'+'Q'*(len(raw)//8),raw)
        live = struct.pack('<'+'Q'*len(values),*(base+p-PREFERRED_BASE for p in values))
        if exact(read,base+int(capture['rva'],16),len(live)) != live:
            raise ValueError('XP2 Prepare relocated vtable differs')
    engine = contract['engine']
    inner = pointer(read,context+engine['inner_offset'])
    if (pointer(read,context) != base+engine['outer_vtable_rva'] or not inner
            or pointer(read,inner) != base+engine['inner_vtable_rva']
            or pointer(read,base+0xb8aa60) != inner
            or exact(read,inner+engine['initialized_byte_offset'],1) != b'\x01'
            or not pointer(read,inner+0x50) or not pointer(read,inner+0x58)):
        raise ValueError('XP2 Prepare initialized context owner differs')
    services = pointer(read,inner+engine['services_offset'])
    if bool(services) is not prepared:
        raise ValueError('XP2 Prepare service state differs from its lifecycle phase')
    if prepared:
        if (pointer(read,services) != base+GAME_VTABLE_RVA
                or exact(read,services+GAME_INITIALIZED_OFFSET,1) != b'\0'):
            raise ValueError('XP2 prepared Game vtable/initialized flag differs')
        archive = services + contract['proof']['archive']['initial_services_archive']['descriptor_member_offset']
        key = contract['proof']['archive']['initial_services_archive']['key']
        if (pointer(read,archive+0x50) != C.addressof(host.descriptor_object)
                or pointer(read,archive+0x58) != key
                or exact(read,archive+0x48,1) != b'\x01'
                or host.archives.entries.get(key) != archive):
            raise ValueError('XP2 prepared archive does not belong to its native services/host')
    observed = require_installed_globals(type('Core',(),{'_handle':base})(),host,read,
                                        contract['bootstrap']['globals_rvas'])
    free = pointer(read,base+engine['aligned_free_iat_rva'])
    try:
        bound = C.cast(host.native_aligned_free,C.c_void_p).value
    except (AttributeError,TypeError,C.ArgumentError) as exc:
        raise ValueError('XP2 Prepare aligned-free callable is not retained') from exc
    owner = host.context_teardown_receipt.get('aligned_free_runtime_owner',{})
    if not free or bound != free or owner.get('address') != hex(free) or owner.get('export') != '_aligned_free':
        raise ValueError('XP2 Prepare aligned-free pointer/owner differs')
    return dict(inner=inner, services=services, free_address=free,
                host_globals=observed, target=base+engine['outer_prepare_rva'])


def source_pins():
    from .paths import resource_root
    contract = verify_source()
    p = contract['proof']
    rows = [dict(path=str(resource_root()/SOURCE[0]),sha256=SOURCE[1]),
            dict(path=str(resource_root()/PINS[0]),sha256=PINS[1]),
            p['capture_script'],*p['extractors'],*p['source_predecessors']]
    return {str(resolve_path(Path(row['path']))):row['sha256'] for row in rows}
