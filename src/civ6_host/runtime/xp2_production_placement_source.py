"""Exact XP2 placement/resume source; shared native rules and UI route."""
from dataclasses import dataclass
import hashlib
from pathlib import Path
import struct

from .configuration_profiles import XP2_CORE_SHA256, _source
from .paths import resource_root
from .resource_resolution import resolve_path

SOURCE = ('work/host-extensions/xp2-production-placement-static/source-profile-v1.json',
          'c50b9e653dccbbf75b7093759be5c02d2dba2789d0562827b8093397a15a50d9')
ENUM_SOURCE = ('work/host-extensions/xp2-production-placement-static/enum-source-v1.json',
               '67a085492547ff30a6df2276bf9bffb446d7e7736f87761a2c1334003dc1fe4a')
ENUMS = {'CityOperationTypes.PARAM_X':0x53777B05, 'CityOperationTypes.PARAM_Y':0x4A6C4A44,
         'CityOperationResults.PLOTS':0x7341AB55}
CALLBACKS = {'BuildQueue.HasBeenPlaced':0x68CDA0, 'CityManager.GetOperationTargets':0x691840,
    'City.GetDistricts':0x68AAB0, 'CityBuildings.HasBuilding':0x68DAB0, 'Plot.GetOwner':0x1D4B0,
    'Plot.GetDistrictType':0x1D0C0, 'Plot.GetDistrictID':0x1D060, 'Plot.GetWonderType':0x1D900,
    'Visibility.IsRevealed':0x6B7BF0, 'Cities.GetPlotPurchaseCity':0x687640, 'CityDistricts.IsComplete':0x68ED50}
REGISTRARS = {'BuildQueue':0x68B4F0, 'CityManager':0x690DE0, 'City':0x689F60, 'CityBuildings':0x68CFE0,
    'Plot':0x1B2E0, 'Visibility':0x6B7860, 'Cities':0x6874C0, 'CityDistricts':0x68E890}
_BASE = 0x180000000


def source_reference(core_sha256=XP2_CORE_SHA256):
    if core_sha256 != XP2_CORE_SHA256:
        raise ValueError('XP2 placement requires its exact engine')
    return SOURCE


def _require_rows(proof, body, required):
    actual = {int(row['rva'],16):row['text'] for row in proof['functions'][hex(body)]['instructions']}
    if any(actual.get(at) != text for at,text in required.items()):
        raise ValueError('XP2 placement native contract changed: '+hex(body))


def _registration(proof):
    for name,rva in CALLBACKS.items():
        b=proof['bindings'][name];registrar=REGISTRARS[name.split('.')[0]]
        if (b['callback_rva'] != hex(rva) or b['registrar_rva'] != hex(registrar)
                or b['registration_helper_rva'] != '0xdab0'
                or b['lua_callback_abi'] != 'int __cdecl(LuaState*) / Windows x64'):
            raise ValueError('XP2 placement registered callback changed: '+name)
        rows={r['va']:r for r in proof['functions'][hex(registrar)]['instructions']}
        for address,prefix,target in ((b['callback_reference_va'],'488d15',_BASE+rva),
                (b['name_reference_va'],'4c8d05',int(b['name_va'],16))):
            row=rows[address];raw=bytes.fromhex(row['bytes'])
            if (len(raw)!=7 or raw[:3].hex()!=prefix
                    or int(address,16)+7+int.from_bytes(raw[3:],'little',signed=True)!=target
                    or tuple(row['rip_targets'])!=(hex(target),)
                    or row not in b['registration_instructions']):
                raise ValueError('XP2 placement actual LEA target changed: '+name)
        window=b['registration_instructions']
        if (any(rows.get(r['va'])!=r for r in window)
                or not any(r['text'] in ('call 0x18000dab0','jmp 0x18000dab0') for r in window)):
            raise ValueError('XP2 placement registration helper changed')


def _official_route(proof):
    texts={}
    for name,ref in proof['official_ui_sources'].items():
        raw=resolve_path(Path(ref['path'])).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=ref['sha256']:
            raise ValueError('XP2 placement official source changed: '+name)
        texts[name]=raw.decode('utf-8-sig')
    if (any(name in texts['modinfo'] for name in ('ProductionPanel','StrategicView_MapPlacement'))
            or 'include("WorldInput_Expansion1")' not in texts['world_xp2']
            or 'include("WorldInput")' not in texts['world_inherited']
            or 'include ("StrategicView_MapPlacement")' not in texts['world']
            or any(name in texts['world_xp2']+texts['world_inherited'] for name in
                ('ConfirmPlaceWonder','ConfirmPlaceDistrict','OnInterfaceModeEnter_BuildingPlacement',
                 'OnInterfaceModeEnter_DistrictPlacement'))):
        raise ValueError('XP2 placement official delegation changed')
    for key,ranges in proof['official_ui_anchors'].items():
        lines=texts[key].splitlines()
        for row in ranges:
            if '\n'.join(lines[row['first']-1:row['last']])!=row['text']:
                raise ValueError('XP2 placement official algorithm changed')


def enum_source():
    from .xp2_initial_choice_source import SOURCE as original
    p=_source(ENUM_SOURCE)
    if (p['schema']!='civ6-host.xp2-placement-enum-source.v1' or p['native_execution'] is not False
            or p['process_memory_read'] is not False or p['image']['sha256']!=XP2_CORE_SHA256
            or p['body_reference']['sha256']!=original[1] or p['body_key']!='0x5acd30'
            or set(p['enums'])!=set(ENUMS)
            or set(p['owners'])!={'CityOperationTypes','CityOperationResults'}):
        raise ValueError('XP2 placement enum source changed')
    body=_source((p['body_reference']['path'],p['body_reference']['sha256']))['functions'][p['body_key']]
    if body['sha256']!=p['body_sha256']:raise ValueError('XP2 placement enum owner body changed')
    rows=[r for f in body['fragments'] for r in f['instructions']]
    by_rva={int(r['rva'],16):r for r in rows}
    expected_sites={'CityOperationTypes':0x5B01D9,'CityOperationResults':0x5B0A78,
        'CityOperationTypes.PARAM_X':0x5B093C,'CityOperationTypes.PARAM_Y':0x5B0970,'CityOperationResults.PLOTS':0x5B0A8B}
    for name,entry in {**p['owners'],**p['enums']}.items():
        if entry['site_rva']!=expected_sites[name]:raise ValueError('XP2 placement enum namespace changed')
        row=by_rva[entry['site_rva']];raw=bytes.fromhex(row['bytes'])
        prefix='4c8d05' if name in ENUMS else '488d15'
        literal=(name.split('.')[-1] if name in ENUMS else name).encode()+b'\0'
        if (len(raw)!=7 or raw[:3].hex()!=prefix
                or entry['site_rva']+7+int.from_bytes(raw[3:],'little',signed=True)!=entry['name_rva']
                or tuple(row['rip_targets'])!=(hex(_BASE+entry['name_rva']),)
                or bytes.fromhex(entry['name_raw_hex'])!=literal
                or any(by_rva.get(int(r['rva'],16))!=r for r in entry['registration_instructions'])):
            raise ValueError('XP2 placement enum literal/registration changed')
        if name in ENUMS:
            value=by_rva[entry['site_rva']+7];code=bytes.fromhex(value['bytes'])
            if (code[:2]!=bytes.fromhex('48b9') or len(code)!=10
                    or struct.unpack('<d',code[2:])[0]!=ENUMS[name]
                    or entry['signed_value']!=ENUMS[name] or entry['u32_value']!=ENUMS[name]
                    or not any(r['text']=='call 0x18000dab0' for r in entry['registration_instructions'])):
                raise ValueError('XP2 placement native enum value changed')
    return p


def verify_source(core_sha256=XP2_CORE_SHA256):
    from .xp2_production_queue_source import _bodies, verify_source as queue_source
    p=_source(source_reference(core_sha256))
    if (p['schema']!='civ6_host.xp2_production_placement.static.v1'
            or p['image']['sha256']!=core_sha256 or p['native_execution'] is not False
            or p['process_memory_read'] is not False or set(p['bindings'])!=set(CALLBACKS)
            or p['validation']!=dict(exact_registration_pairs=11,
                all_instruction_bytes_match_image=True,conditional_branches_included=True)):
        raise ValueError('XP2 placement source identity changed')
    _bodies(p)
    _registration(p)
    for body,rows in {
        0x68CDA0:{0x68CDB5:'call 0x18068b390',0x68CDC5:'call 0x1806c5370',0x68CDCF:'call 0x18006c9f0'},
        0x6C9F0:{0x6C9F4:'call 0x18006bd30',0x6C9FB:'setns al'},
        0x6BD30:{0x6BD4B:'call 0x1801b0270',0x6BD6C:'movsx ebx, word ptr [rax + rcx*2]',
            0x6BD95:'call qword ptr [rax + 0x40]',0x6BDBC:'call 0x180042e40',
            0x6BDD1:'call 0x1800fcdd0',0x6BDE2:'call qword ptr [rdx + 0x38]'},
        0x691840:{0x69185D:'call 0x180690c90',0x691980:'call 0x1809af8c0',
            0x691994:'xor r9d, r9d',0x6919AE:'call 0x180077230',
            0x6919C8:'call qword ptr [r10 + 0xa8]',0x6919D4:'call 0x18099e5d0',0x6919E1:'call 0x18099e5d0'},
        0x68AAB0:{0x68AAC1:'call 0x180024ef0',0x68AAC9:'lea rdx, [rax + 0x4b0]',0x68AAD0:'call 0x180688bb0'},
        0x1D4B0:{0x1D4CC:'call qword ptr [rdx + 0x30]',0x1D4D3:'movsx edx, byte ptr [rax + 0x1c]'},
        0x5E720:{0x5E746:'call qword ptr [rax + 8]',0x5E74E:'mov eax, dword ptr [rax + 0xf0]',0x5E759:'or eax, 0xffffffff'},
        0x1D900:{0x1D929:'movsx edi, word ptr [rax + 0x1e]'},
        0x687640:{0x687673:'cmp byte ptr [rax + 0x1c], 0xff',0x687679:'cmp dword ptr [rax + 0xc], -1',
            0x68768C:'movsx eax, byte ptr [rax + 0x1c]',0x6876A8:'call 0x1800773a0'},
        0x6E3B0:{0x6E3BB:'call 0x1801b0270',0x6E3CC:'movzx ecx, word ptr [rax + rdx*2]',
            0x6E3D0:'not cx',0x6E3D6:'shr eax, 0xf',0x6E3DF:'xor al, al'},
        0x716C0:{0x716E2:'call 0x1801b0590',0x716F3:'call 0x180071450',0x71701:'movzx eax, byte ptr [rax + 0x34]',
            0x71765:'cmp dword ptr [rax + 0xc], r14d',0x717A2:'mov al, 1'},
    }.items(): _require_rows(p,body,rows)
    for body,address,target in ((0x6BD30,0x6BD8B,0xB8AA80),(0x6BD30,0x6BDD8,0xB8AA80),
                                (0x691840,0x6919B3,0xB8AA88)):
        row=next(r for r in p['functions'][hex(body)]['instructions'] if r['rva']==hex(address))
        if tuple(row['rip_targets'])!=(hex(_BASE+target),):
            raise ValueError('XP2 placement service owner global changed')
    contract=p['contracts']
    if (tuple(contract['production_modes'])!=('place','resume') or tuple(contract['categories'])!=('district','building')
            or contract['targets_native'] is not True or contract['visibility_before_plot'] is not True
            or contract['hidden_targets_public'] is not False or contract['effects_admitted'] is not False):
        raise ValueError('XP2 placement action/visibility boundary changed')
    for ref in p['references']:_source((ref['path'],ref['sha256']))
    queue_source(core_sha256)
    enum_source()
    _official_route(p)
    return p


def source_dependencies(core_sha256=XP2_CORE_SHA256, *, execution_image=None):
    from .xp2_production_queue_source import source_dependencies as queue
    from .xp2_world_input_source import source_dependencies as world
    from .xp2_aux_map_profile import source_dependencies as maps
    p=verify_source(core_sha256);result={}
    for provider in (queue,world,maps):
        if provider is queue:
            rows = provider(execution_image=execution_image)
        elif provider is world:
            rows = provider(core_sha256=core_sha256, execution_image=execution_image)
        else:
            rows = provider()
        for path,digest in rows.items():
            if path in result and result[path]!=digest:raise ValueError('Conflicting XP2 placement pin')
            result[path]=digest
    enum=enum_source()
    for ref in (dict(path=SOURCE[0],sha256=SOURCE[1]),p['image'],p['extractor'],*p['references'],
                *p['official_ui_sources'].values(),dict(path=ENUM_SOURCE[0],sha256=ENUM_SOURCE[1]),
                enum['extractor'],enum['body_reference']):
        if ref is p['image'] and execution_image is not None:
            continue
        path=str(resolve_path(resource_root()/ref['path']).resolve())
        if (hashlib.sha256(Path(path).read_bytes()).hexdigest()!=ref['sha256']
                or path in result and result[path]!=ref['sha256']):
            raise ValueError('XP2 placement dependency changed: '+path)
        result[path]=ref['sha256']
    from .runtime_source_dependencies import materialize_runtime_source_pins
    return materialize_runtime_source_pins(
        result, execution_image=execution_image,
        provenance_images=(p['image'],),
    )


def verify_live(base,read,core_sha256=XP2_CORE_SHA256):
    if type(base) is not int or not 0<base<(1<<47)-0x1000000 or not callable(read):
        raise ValueError('XP2 placement requires a module base and reader')
    p=verify_source(core_sha256)
    spans=[(int(f['start_rva'],16),bytes.fromhex(f['raw_hex'])) for b in p['functions'].values() for f in b['fragments']]
    spans.extend((int(t['rva'],16),bytes.fromhex(t['raw_hex'])) for t in p['embedded_tables'].values())
    spans.extend((int(b['name_va'],16)-_BASE,n.split('.')[1].encode()+b'\0') for n,b in p['bindings'].items())
    enum=enum_source()
    enum_body=_source((enum['body_reference']['path'],enum['body_reference']['sha256']))['functions'][enum['body_key']]
    spans.extend((int(f['start_rva'],16),bytes.fromhex(f['raw_hex'])) for f in enum_body['fragments'])
    spans.extend((e['name_rva'],bytes.fromhex(e['name_raw_hex'])) for e in (*enum['enums'].values(),*enum['owners'].values()))
    for rva,raw in spans:
        for offset in range(0,len(raw),4096):
            chunk=raw[offset:offset+4096];actual=read(base+rva+offset,len(chunk))
            if type(actual) is not bytes or actual!=chunk:
                raise ValueError('XP2 placement native source changed at '+hex(rva+offset))
    return len(spans)


@dataclass(frozen=True)
class VerifiedPlacementSource:
    owner:object
    core:object
    base:int
    source_sha256:str
    core_sha256:str
    queue_receipt:object
    world_receipt:object
    instruction_read_spans:int


def bind_owner(owner,core,read):
    from .xp2_production_queue_source import bind_owner as queue
    from .xp2_world_input_source import bind_owner as world
    # Queue checks concrete backend, original input lease, thread, live core and
    # selected production source. World also binds status and operation ABIs.
    q=queue(owner,core,read);w=world(owner,core,read)
    old=getattr(owner,'_xp2_production_placement_source_receipt',None)
    if old is not None:
        if (type(old) is not VerifiedPlacementSource or old.owner is not owner or old.core is not core
                or old.base!=core._handle or old.source_sha256!=SOURCE[1] or old.core_sha256!=XP2_CORE_SHA256
                or old.queue_receipt is not q or old.world_receipt is not w):
            raise ValueError('XP2 placement receipt belongs to another lifetime')
        return old
    execution_image = getattr(core, '_civ6_host_execution_image', None)
    source_dependencies(XP2_CORE_SHA256, execution_image=execution_image)
    result=VerifiedPlacementSource(owner,core,core._handle,SOURCE[1],XP2_CORE_SHA256,q,w,verify_live(core._handle,read))
    owner._xp2_production_placement_source_receipt=result
    return result


def gate_admitted(continuation):
    from .xp2_production_queue_source import gate_admitted as queue_gate
    queue_gate(continuation)
    owner=continuation.owner
    receipt=getattr(owner,'_xp2_production_placement_source_receipt',None)
    if receipt is None or bind_owner(owner,owner.core,owner.runtime.read) is not receipt:
        raise ValueError('XP2 placement gate requires its bound source')
    return True
