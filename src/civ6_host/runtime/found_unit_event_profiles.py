"""Exact engine ABI for the unchanged shared E23B112D native query algorithm."""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from types import MappingProxyType

from civ6_host.runtime.unit_operation_ui_profile import instruction_spans
from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256

BASE_SHA256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'
XP1_SHA256='259b90a473a256aff6a7d621a4f3717e46f6921c59b9817475375c88b97e8c83'
SOURCE=('work/host-extensions/xp1-found-event-static/found-event-source-v2.json',
        '0d1038e52731107e6129bcf383e6fe4373d7fd0100311ad5179122d9fc61205f')
XP2_UNIT_SOURCE=('work/host-extensions/xp2-foundation-static/player-units-facade-candidate-v2.json',
                 '48dc11668c13d50316cf019f220fb30d2a4a260c4dc36e4e4be04079ae29ba56')
XP2_MAP_SOURCE=('work/host-extensions/xp2-foundation-static/found-unit-query-map-supplement-v1.json',
                '11cd341bcb9bd2eb424fadd064179b8d586cdbdfcdda33bfc615a7b1bad54b0b')
XP2_APPLICATION_SOURCE=('work/host-extensions/xp2-application-mirror/source-profile-v1.json',
                        'e1241f8dcab67dee4166b9f818f55d070fee5cf53ef79a755cb4eb77a6c7cce8')
XP2_PLAYER_SOURCE=('work/host-extensions/xp2-player-query-static/source-profile-v1.json',
                   'd5e71d1a2ff1eeceed0d316d209942c25068754716342c51540f0f8638f8af4c')
XP2_CONTEXT_SOURCE=('work/host-extensions/xp2-context-initialization/source-profile-v3.json',
                    '5d386ab8de757623da143f4e3277d62827b35ba5f784f6b31e6a3d28d1a651fe')
XP2_EXE_SOURCE=('evidence/native-event-e23b112d.json',
                 'a24ffc52b8c654c49efd7c1679f9d2fb44dc8d28dda6092da2b2d6e70fd74c00')
CONSTANTS=('CORE_PARAMETER_CTOR','CORE_PARAMETER_DTOR','CORE_PARAMETER_LOOKUP',
           'CORE_PARAMETER_VTABLE','CORE_UNIT_A8','CORE_UNIT_B0')


@dataclass(frozen=True)
class FoundUnitQueryABI:
    core_sha256:str
    tables:object
    inner_vtable_rva:int
    constants:object
    code_pins:object


def source(root=None):
    if root is None:
        from civ6_host.runtime.provenance import resource_root
        root=resource_root()
    raw=(Path(root)/SOURCE[0]).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=SOURCE[1]:raise ValueError('XP1 found-unit source changed')
    p=json.loads(raw);a=p['profile']
    if (p['schema']!='civ6_host.xp1_found_event_source.v1'
            or p['images']['xp1']['sha256']!=XP1_SHA256 or p['images']['base']['sha256']!=BASE_SHA256
            or (a['event_kind'],a['query_selector'],a['queue_type'],a['record_size'])!=(0xe23b112d,0x490cc8e1,0x23,128)
            or (a['parameter_storage_bytes'],a['parameter_canary_bytes'])!=(160,16)
            or set(a['constants'])!=set(CONSTANTS)):
        raise ValueError('Found-unit event profile changed')
    return p


def _read_profile(root,item,label):
    path=Path(root)/item[0]
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=item[1]:
        raise ValueError(f'XP2 {label} source changed')
    return json.loads(raw),path


def _xp2_source(root=None, execution_image=None):
    """Resolve the exact XP2 Unit facade, query-map, and shared callback join."""
    if root is None:
        from civ6_host.runtime.provenance import resource_root
        root=resource_root()
    root=Path(root)
    unit,unit_path=_read_profile(root,XP2_UNIT_SOURCE,'returned Unit facade')
    query_map,map_path=_read_profile(root,XP2_MAP_SOURCE,'FoundUnit query map')
    application,application_path=_read_profile(root,XP2_APPLICATION_SOURCE,'application map')
    player,player_path=_read_profile(root,XP2_PLAYER_SOURCE,'player lookup')
    context,context_path=_read_profile(root,XP2_CONTEXT_SOURCE,'inner context')
    exe_path=root/XP2_EXE_SOURCE[0]
    exe_raw=exe_path.read_bytes()
    if hashlib.sha256(exe_raw).hexdigest()!=XP2_EXE_SOURCE[1]:
        raise ValueError('Shared E23B callback evidence changed')
    exe=json.loads(exe_raw)
    if (unit.get('schema')!='civ6-host.xp2-foundation-player-unit-facade.candidate.v2'
            or unit.get('native_execution') is not False or unit.get('core_sha256')!=XP2_CORE_SHA256
            or query_map.get('schema')!='civ6-host.xp2-found-unit-query-map.source.v1'
            or query_map.get('native_execution') is not False or query_map.get('core_sha256')!=XP2_CORE_SHA256
            or application.get('core_sha256')!=XP2_CORE_SHA256
            or player.get('core_sha256')!=XP2_CORE_SHA256
            or context.get('image',{}).get('sha256')!=XP2_CORE_SHA256
            or exe.get('schema')!='civ6rl.native_event_e23b112d.v1'
            or exe.get('images',{}).get('exe_sha256')!='e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'):
        raise ValueError('XP2 FoundUnit query engine/source identity differs')
    profile=unit['player_units'];returned=profile['returned_unit_facades'];mp=query_map['profile']
    composition=mp['composition_tables']
    if (profile['player_vtable_rva']!='0xa11a80'
            or profile['facade_vtable_rva']!='0xa122f0'
            or returned['live_vtable_rva']!='0xa128e8'
            or returned['live_secondary_vtable_rva']!='0xa129b8'
            or returned['query_slots']!={'a8':'0x5a26d0','b0':'0x5a26a0','release_10':'0x5a23b0'}
            or mp['query_map_vtable_rva']!='0xabf080'
            or mp['query_lookup_slot']!='0x60' or mp['query_lookup_rva']!='0x99f5c0'
            or mp['inner_vtable_rva']!='0xa44f70'
            or application['method_rvas']['constructor']!=0x99e4b0
            or application['method_rvas']['delete']!=0x99e8b0
            or context['slots']['inner_vtable_rva']!='0xa44f70'
            or player['profile']['constants']['PLAYER_MANAGER_VTABLE_RVA']!=0xA101E8
            or composition['outer']['vtable_rva']!='0xa101e8'
            or composition['outer']['slots']!={'0xb8':'0x590360'}
            or composition['player']['vtable_rva']!='0xa11a80'
            or composition['player']['slots']!={'0x8':'0x59c8c0','0x110':'0x59d310'}
            or composition['units']['vtable_rva']!='0xa122f0'
            or composition['units']['slots']!={'0x8':'0x5a0390','0x10':'0x5a03b0'}):
        raise ValueError('XP2 FoundUnit query tables/constructor/map contract changed')
    bodies=unit['bodies']
    if int(bodies['player_units_accessor']['start_va'],16)-0x180000000!=0x59D310:
        raise ValueError('XP2 Player+0x110 accessor changed')
    callback={i['va']:i['text'] for f in exe['callback']['fragments'] for i in f['instructions']}
    for va,text in {'0x140154b1c':'call qword ptr [rax + 0xa8]',
                    '0x140154b38':'call qword ptr [rax + 0xb0]',
                    '0x140154bb3':'call qword ptr [rax + 0x10]'}.items():
        if callback.get(va)!=text:raise ValueError('Shared E23B query callback changed')
    proof=dict(root=root,unit=unit,query_map=query_map,application=application,
               player=player,context=context,exe=exe,
               paths=(unit_path,map_path,application_path,player_path,context_path,exe_path))
    _xp2_dependencies(proof, execution_image=execution_image)
    return proof


def _xp2_instruction_spans(bodies):
    byte_map={}
    for body in bodies:
        rows=body.get('instructions') or [r for f in body.get('fragments',[]) for r in f['instructions']]
        for row in rows:
            address=(int(row['rva'],16) if 'rva' in row
                     else int(row['va'],16)-0x180000000)
            for offset,value in enumerate(bytes.fromhex(row['bytes'])):
                location=address+offset
                if location in byte_map and byte_map[location]!=value:
                    raise ValueError('Conflicting XP2 FoundUnit instruction evidence')
                byte_map[location]=value
    spans=[];start=previous=None;data=bytearray()
    for address in sorted(byte_map):
        if previous is None or address!=previous+1:
            if data:spans.append((start,bytes(data)))
            start=address;data=bytearray()
        data.append(byte_map[address]);previous=address
    if data:spans.append((start,bytes(data)))
    return tuple(spans)


def _xp2_dependencies(proof, execution_image=None):
    from .native.native_found_city_event import SELECTOR_PROOF_SHA256
    from .resource_resolution import resolve_path
    selector=proof['root']/'evidence/native-e23b-selectors'/f'{SELECTOR_PROOF_SHA256}.json'
    pins={str(resolve_path(selector)):SELECTOR_PROOF_SHA256}
    provenance_images=[]
    docs=(proof['unit'],proof['query_map'],proof['application'],proof['player'],proof['context'])
    for doc in docs:
        refs=[]
        for field in ('references','source_pins','extractors'):
            value=doc.get(field,[])
            if isinstance(value,dict):
                for path,digest in value.items():
                    if isinstance(digest,dict) and 'path' in digest and 'sha256' in digest:
                        refs.append(digest)
                    elif isinstance(digest,str):
                        refs.append({'path':path,'sha256':digest})
            elif isinstance(value,(list,tuple)):
                refs.extend(item for item in value if isinstance(item,dict) and 'path' in item and 'sha256' in item)
        refs.extend(item for item in (doc.get('generator'),doc.get('boundary_helper'),doc.get('extractor'),
                                       doc.get('capture_script'))
                    if isinstance(item,dict) and 'path' in item and 'sha256' in item)
        image=doc.get('image')
        if isinstance(image,dict) and 'path' in image and 'sha256' in image:
            provenance_images.append(image)
            if execution_image is None:
                refs.append(image)
        images=doc.get('images',{})
        if isinstance(images,dict):
            rows=[item for item in images.values()
                  if isinstance(item,dict) and 'path' in item and 'sha256' in item]
            provenance_images.extend(rows)
            if execution_image is None:
                refs.extend(rows)
        for item in refs:
            rel=str(item['path']);digest=item['sha256']
            path=resolve_path(proof['root']/rel)
            key=str(path)
            if key in pins and pins[key]!=digest:raise ValueError('Conflicting XP2 FoundUnit dependency identity')
            pins[key]=digest
    image_paths={str(Path(resolve_path(row['path'])).resolve()) for row in provenance_images}
    for path in proof['paths']:
        key=str(path.resolve())
        if execution_image is not None and key in image_paths:
            continue
        pins[key]=hashlib.sha256(path.read_bytes()).hexdigest()
    if execution_image is not None:
        from .runtime_source_dependencies import materialize_runtime_source_pins
        pins=materialize_runtime_source_pins(pins,execution_image=execution_image,
                                             provenance_images=provenance_images)
    for path,digest in pins.items():
        p=Path(path)
        if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=digest:
            raise ValueError('XP2 FoundUnit dependency changed: '+path)
    return pins


def source_dependencies(root=None,*,core_sha256=XP1_SHA256,execution_image=None):
    if core_sha256==XP2_CORE_SHA256:
        proof=_xp2_source(root,execution_image=execution_image)
        return _xp2_dependencies(proof,execution_image=execution_image)
    if execution_image is not None:
        raise ValueError('Selected execution image requires the XP2 found-unit source')
    if core_sha256!=XP1_SHA256:
        raise ValueError('Unknown found-unit query engine')
    if root is None:
        from civ6_host.runtime.provenance import resource_root
        root=resource_root()
    p=source(root)
    return {str(Path(root)/SOURCE[0]):SOURCE[1],
            **{r['path']:r['sha256'] for r in (*p['source_dependencies'],p['extractor'],*p['images'].values())}}


def _tables(raw):
    return MappingProxyType({name:(vt,MappingProxyType({int(k):v for k,v in slots.items()}))
                             for name,(vt,slots) in raw.items()})


def query_abi(core_sha256,root=None,*,execution_image=None):
    if execution_image is not None and core_sha256!=XP2_CORE_SHA256:
        raise ValueError('Selected execution image requires the XP2 FoundUnit source ABI')
    if core_sha256==BASE_SHA256:
        from civ6_host.runtime.native import native_found_city_event as m
        from civ6_host.runtime.native.native_unit_created_event import TABLES
        return FoundUnitQueryABI(core_sha256,_tables(TABLES),0x7c7078,
            MappingProxyType({name:getattr(m,name) for name in CONSTANTS}),MappingProxyType(dict(m.CORE_CODE_PINS)))
    if core_sha256==XP2_CORE_SHA256:
        proof=_xp2_source(root,execution_image=execution_image)
        unit=proof['unit']['player_units'];mp=proof['query_map']['profile']
        tables={
            'outer':(0xA101E8,{0xB8:0x590360}),
            'player':(0xA11A80,{0x08:0x59C8C0,0x110:0x59D310}),
            'units':(0xA122F0,{0x08:0x5A0390,0x10:0x5A03B0}),
            'unit':(0xA128E8,{0x10:0x5A23B0,0xA8:0x5A26D0,0xB0:0x5A26A0}),
        }
        constants=MappingProxyType({'CORE_PARAMETER_CTOR':0x99E4B0,'CORE_PARAMETER_DTOR':0x99E8B0,
            'CORE_PARAMETER_LOOKUP':0x99F5C0,'CORE_PARAMETER_VTABLE':0xABF080,
            'CORE_UNIT_A8':0x5A26D0,'CORE_UNIT_B0':0x5A26A0})
        bodies=list(proof['unit']['bodies'].values())
        bodies.extend(proof['query_map']['bodies'].values())
        for name in ('constructor','delete'):
            bodies.append(proof['application']['bodies'][name])
        spans=_xp2_instruction_spans(bodies)
        pins=MappingProxyType({(rva,len(raw)):hashlib.sha256(raw).hexdigest() for rva,raw in spans})
        return FoundUnitQueryABI(core_sha256,_tables(tables),int(mp['inner_vtable_rva'],16),
                                 constants,pins)
    if core_sha256!=XP1_SHA256:raise ValueError('Unqualified found-unit query engine')
    proof=source(root);p=proof['profile']
    return FoundUnitQueryABI(core_sha256,_tables(p['tables']),p['inner_vtable_rva'],
        MappingProxyType(dict(p['constants'])),MappingProxyType({(rva,len(raw)):hashlib.sha256(raw).hexdigest()
            for rva,raw in instruction_spans(proof)}))


def verify_live(base,read,*,core_sha256=XP1_SHA256,root=None,execution_image=None):
    if core_sha256 not in (XP1_SHA256,XP2_CORE_SHA256) or type(base) is not int or base<=0:
        raise ValueError('Expected an exact supported query module')
    abi=query_abi(core_sha256,root,execution_image=execution_image)
    for (rva,size),digest in abi.code_pins.items():
        if hashlib.sha256(read(base+rva,size)).hexdigest()!=digest:
            raise ValueError('Found-unit instructions changed at '+hex(rva))
    for vt,slots in abi.tables.values():
        for slot,target in slots.items():
            if read(base+vt+slot,8)!=(base+target).to_bytes(8,'little'):
                raise ValueError('Found-unit virtual target changed')
    if read(base+abi.constants['CORE_PARAMETER_VTABLE']+0x60,8)!=(base+abi.constants['CORE_PARAMETER_LOOKUP']).to_bytes(8,'little'):
        raise ValueError('Found-unit parameter lookup target changed')
    return dict(source_sha256=XP2_MAP_SOURCE[1] if core_sha256==XP2_CORE_SHA256 else SOURCE[1],
                native_query_invoked=False,event_admitted=False)
