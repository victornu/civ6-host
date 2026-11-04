"""Review staging: exact ABI selectors for existing foundation query algorithms.

This module does not admit events, execute GameCore, select notification gates,
or provide substitute query values. Integration must keep each existing query's
acquire/query/enqueue/release ordering and select this profile explicitly.
"""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from types import MappingProxyType

BASE_SHA256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'
XP1_SHA256='259b90a473a256aff6a7d621a4f3717e46f6921c59b9817475375c88b97e8c83'
from .saved_load_profiles import XP2_CORE_SHA256 as XP2_SHA256
SOURCE=('work/host-extensions/xp1-foundation-facades-static/foundation-facades-source-v1.json',
        '48f84907f528de3b78838d901c117ea37232bb4e67ac288aa2913985eb230ba8')
XP2_SOURCE=('work/host-extensions/xp2-turn-notifications-static/source-profile-v1.json',
            'e6dad3289463a09baecfb8a34a52f3fcaedc03f50f94d06ae11840363de9419b')
XP2_QUERY_SOURCE=('work/host-extensions/xp2-foundation-query-facades-static/query-facade-source-v3.json',
                  '7313418cd5d5f4f086ed41424c7f502c736e953a6bc345ab1b2da5368462a71e')
_BASE_TABLES={'outer':7987232,'map':7991792,'plot':7994424,'player':7992320,
              'district_collection':7993256,'district':7990216,
              'type_service':7988512,'game':7990488,'position':7995096}

_BASE_OPERATIONS={'district_by_id': {'abi': 'ptr(ptr,uint32)', 'rva': 4427984, 'slot': 16, 'table': 'district_collection'},
 'district_city_descriptor': {'abi': 'ptr(ptr,out8*)', 'rva': 4407024, 'slot': 48, 'table': 'district'},
 'district_hash': {'abi': 'uint32(ptr,uint32)', 'rva': 4407392, 'slot': 88, 'table': 'district'},
 'district_position': {'abi': 'ptr(ptr,out8*)', 'rva': 4407328, 'slot': 56, 'table': 'district'},
 'district_snapshot70': {'abi': 'uint8(ptr,out64*,uint32)', 'rva': 4407008, 'slot': 112, 'table': 'district'},
 'district_snapshot78': {'abi': 'ignored_RAX(ptr,out20*)', 'rva': 4406992, 'slot': 120, 'table': 'district'},
 'district_type': {'abi': 'uint32(ptr)', 'rva': 4372864, 'slot': 32, 'table': 'district'},
 'free_snapshot_vector': {'abi': 'void(ptr)', 'rva': 7565584},
 'get_player': {'abi': 'ptr(ptr,int32)', 'rva': 4382880, 'slot': 184, 'table': 'outer'},
 'get_plot': {'abi': 'ptr(ptr,int32,int32)', 'rva': 4418176, 'slot': 64, 'table': 'map'},
 'neighbor': {'abi': 'ptr(ptr,out8*,in8*,uint32)', 'rva': 4417408, 'slot': 136, 'table': 'map'},
 'optional_position': {'abi': 'ptr(ptr,out8*,int32)', 'rva': 4418768, 'slot': 104, 'table': 'map'},
 'outer_game': {'abi': 'ptr(ptr)', 'rva': 4382432, 'slot': 144, 'table': 'outer'},
 'outer_map': {'abi': 'ptr(ptr)', 'rva': 4382784, 'slot': 168, 'table': 'outer'},
 'outer_service': {'abi': 'ptr(ptr)', 'rva': 4382336, 'slot': 256, 'table': 'outer'},
 'player_districts': {'abi': 'ptr(ptr)', 'rva': 4422336, 'slot': 304, 'table': 'player'},
 'player_type': {'abi': 'int32(ptr)', 'rva': 4422464, 'slot': 24, 'table': 'player'},
 'plot_flag148': {'abi': 'uint8(ptr)', 'rva': 4437344, 'slot': 328, 'table': 'plot'},
 'plot_owner': {'abi': 'int32(ptr)', 'rva': 4436736, 'slot': 32, 'table': 'plot'},
 'plot_snapshot178': {'abi': 'ignored_RAX(ptr,out24*,uint32)', 'rva': 4435760, 'slot': 376, 'table': 'plot'},
 'plot_snapshot180': {'abi': 'ignored_RAX(ptr,out24*,uint32)', 'rva': 4435856, 'slot': 384, 'table': 'plot'},
 'plot_value': {'abi': 'uint32(ptr)', 'rva': 4435888, 'slot': 48, 'table': 'plot'},
 'position_flag': {'abi': 'uint8(ptr,in8*)', 'rva': 4440368, 'slot': 112, 'table': 'position'},
 'position_service': {'abi': 'ptr(ptr)', 'rva': 4410848, 'slot': 88, 'table': 'game'},
 'position_value': {'abi': 'uint64(ptr,in8*)', 'rva': 4440320, 'slot': 120, 'table': 'position'},
 'release_collection': {'abi': 'void(ptr)', 'rva': 4427952, 'slot': 8, 'table': 'district_collection'},
 'release_district': {'abi': 'void(ptr)', 'rva': 4406960, 'slot': 8, 'table': 'district'},
 'release_game': {'abi': 'void(ptr)', 'rva': 4409168, 'slot': 8, 'table': 'game'},
 'release_map': {'abi': 'void(ptr)', 'rva': 4416608, 'slot': 8, 'table': 'map'},
 'release_player': {'abi': 'void(ptr)', 'rva': 4421040, 'slot': 8, 'table': 'player'},
 'release_plot': {'abi': 'void(ptr)', 'rva': 4435728, 'slot': 8, 'table': 'plot'},
 'release_position': {'abi': 'void(ptr)', 'rva': 4440288, 'slot': 8, 'table': 'position'},
 'release_service': {'abi': 'void(ptr)', 'rva': 4388560, 'slot': 8, 'table': 'type_service'},
 'service_district_type_hash': {'abi': 'uint32(ptr,uint32)',
                                'rva': 4395104,
                                'slot': 224,
                                'table': 'type_service'},
 'service_player_type_hash': {'abi': 'int32(ptr,int32)',
                              'rva': 4395200,
                              'slot': 200,
                              'table': 'type_service'}}

@dataclass(frozen=True)
class FacadeABI:
    core_sha256:str
    tables:object
    operations:object
    service_bytes:int
    service_secondary_vtable:int|None
    source_sha256:str

    def rva(self,name):
        try:return self.operations[name]['rva']
        except KeyError:raise ValueError('Unqualified foundation facade operation: '+name) from None

    def table(self,name):
        try:return self.tables[name][0]
        except KeyError:raise ValueError('Unqualified foundation facade: '+name) from None

    def slot(self,name):
        try:
            slot=self.operations[name]['slot']
            if type(slot) is not int or slot<0 or slot%8:
                raise ValueError
            return slot
        except (KeyError,TypeError):
            raise ValueError('Unqualified foundation facade slot: '+name) from None

def source(root):
    raw=(Path(root)/SOURCE[0]).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=SOURCE[1]:raise ValueError('Foundation facade evidence changed')
    p=json.loads(raw)
    if (p['schema']!='civ6_host.xp1_foundation_facades.static.v1'
        or p['images']['xp1']['sha256']!=XP1_SHA256
        or p['images']['base']['sha256']!=BASE_SHA256
        or p['validation']['native_execution'] is not False
        or p['validation']['all_instruction_bytes_match_pinned_image'] is not True
        or p['profile']['type_service']!={'bytes':8,'secondary_vtable':None,'release_slot':8}
        or len(p['operations'])!=35 or len(p['tables'])!=9):
        raise ValueError('Foundation facade evidence contract differs')
    return p

def query_abi(core_sha256,root):
    if core_sha256==XP2_SHA256:
        from .xp2_foundation_query_source import source as proof_source
        p=proof_source()
        tables={name:(int(row['vtable_rva'],16),MappingProxyType({
            int(slot,16):int(target,16) for slot,target in row['slots'].items()}))
            for name,row in p['tables'].items()}
        operations={}
        for name,spec in p['operations'].items():
            row=dict(spec)
            row['rva']=int(row.pop('target_rva'),16)
            if 'slot' in row:row['slot']=int(row['slot'],16)
            operations[name]=MappingProxyType(row)
        abi=FacadeABI(core_sha256,MappingProxyType(tables),
            MappingProxyType(operations),16,0xA10CA8,XP2_QUERY_SOURCE[1])
        require_complete_query_abi(abi)
        return abi
    if core_sha256 not in (BASE_SHA256,XP1_SHA256):raise ValueError('Unqualified facade engine')
    if core_sha256==BASE_SHA256:
        ops={name:MappingProxyType(dict(spec)) for name,spec in _BASE_OPERATIONS.items()}
        tables={name:(vt,MappingProxyType({spec['slot']:spec['rva'] for spec in _BASE_OPERATIONS.values() if spec.get('table')==name})) for name,vt in _BASE_TABLES.items()}
        return FacadeABI(core_sha256,MappingProxyType(tables),MappingProxyType(ops),16,7989976,'retained-base-constants')
    p=source(root)
    xp1=True
    ops={name:MappingProxyType(dict(spec,rva=spec['rva'] if xp1 else spec['base_rva']))
         for name,spec in p['operations'].items()}
    tables={name:(int(vt) if xp1 else _BASE_TABLES[name],MappingProxyType({
        int(slot):next(ops[op]['rva'] for op,spec in p['operations'].items()
                       if spec.get('table')==name and spec.get('slot')==int(slot))
        for slot in slots})) for name,(vt,slots) in p['tables'].items()}
    return FacadeABI(core_sha256,MappingProxyType(tables),MappingProxyType(ops),
                     8 if xp1 else 16,None if xp1 else 7989976,SOURCE[1])

def verify_xp1_source_bytes(base,read,root):
    """One-shot admission check; caller caches only within its native lifetime."""
    if type(base) is not int or base<=0:raise ValueError('Invalid relocated engine base')
    p=source(root);seen={}
    for entry in p['functions'].values():
        for row in entry['instructions']:
            rva=int(row['va'],16)-p['images']['xp1']['base'];expected=bytes.fromhex(row['bytes'])
            if rva in seen and seen[rva]!=expected:raise ValueError('Conflicting instruction evidence')
            seen[rva]=expected
    for rva,expected in seen.items():
        if read(base+rva,len(expected))!=expected:raise ValueError('XP1 facade source bytes differ at '+hex(rva))
    for table,slots in p['tables'].values():
        for slot,target in slots.items():
            if read(base+table+int(slot),8)!=(base+target).to_bytes(8,'little'):
                raise ValueError('XP1 facade virtual target differs')
    return {'native_query_invoked':False,'event_admitted':False,'source_sha256':SOURCE[1],
            'checked_instructions':len(seen),'checked_tables':len(p['tables'])}

def verify_xp1_once(core,base,read,root,*,core_sha256=XP1_SHA256):
    """Bind immutable code admission to this loaded Core object, not globally."""
    if int(core._handle)!=base:raise ValueError('Facade source owner differs')
    if core_sha256==XP2_SHA256:
        from .xp2_foundation_query_source import verify_live as verify_xp2_live
        key=(base,XP2_QUERY_SOURCE[1])
        if getattr(core,'_civ6_host_foundation_facade_verification',None)==key:return
        verify_xp2_live(base,read)
        core._civ6_host_foundation_facade_verification=key
        return
    if core_sha256!=XP1_SHA256:
        raise ValueError('Unqualified foundation facade verification engine')
    key=(base,SOURCE[1])
    if getattr(core,'_civ6_host_foundation_facade_verification',None)==key:return
    verify_xp1_source_bytes(base,read,root)
    core._civ6_host_foundation_facade_verification=key


def source_dependencies(*,core_sha256=XP1_SHA256):
    """Resolve the closed native source set for one exact facade engine."""
    if core_sha256==XP2_SHA256:
        from .xp2_foundation_query_source import source_dependencies as selected
        pins=selected()
        from .xp2_turn_notification_source import source_dependencies as turn_dependencies
        for path,sha in turn_dependencies().items():
            if path in pins and pins[path]!=sha:
                raise ValueError('Conflicting XP2 foundation query dependency')
            pins[path]=sha
        return pins
    if core_sha256!=XP1_SHA256:
        raise ValueError('Unknown foundation facade source engine')
    from .a0_family_source import _path,verify_pinned_files
    from .paths import resource_root
    p=source(resource_root())
    refs=[dict(path=SOURCE[0],sha256=SOURCE[1]),*p['references'].values()]
    pins={str(_path(row['path'])):row['sha256'] for row in refs}
    verify_pinned_files(pins)
    return pins


def require_complete_query_abi(abi):
    """Fail closed unless all 35 common operations and their exact slots exist."""
    if abi.core_sha256==XP2_SHA256:
        if set(abi.operations)!=set(_BASE_OPERATIONS):
            raise ValueError('XP2 foundation query family is incomplete')
        for name,expected in _BASE_OPERATIONS.items():
            row=abi.operations[name]
            if row['abi']!=expected['abi']:
                raise ValueError('XP2 foundation query ABI is incomplete: '+name)
            if name=='free_snapshot_vector':
                if row.get('kind')!='import-wrapper':raise ValueError('XP2 vector free path is incomplete')
                continue
            table,slots=abi.tables.get(expected['table'],(None,{}))
            slot=row.get('slot')
            if row.get('table')!=expected['table'] or type(slot) is not int or slot<0 or slot%8:
                raise ValueError('XP2 foundation query selector is incomplete: '+name)
            if slots.get(slot)!=row['rva']:
                raise ValueError('XP2 foundation query slot target is incomplete: '+name)
        for label,(_,slots) in abi.tables.items():
            if any(type(slot) is not int or slot<0 or slot%8 for slot in slots):
                raise ValueError('XP2 foundation query table has an invalid slot: '+label)
    return abi


def select_tables(core_sha256,retained,root=None):
    """Select only a shared query's declared table names and slots."""
    if core_sha256==BASE_SHA256:return retained
    if core_sha256 not in (XP1_SHA256,XP2_SHA256):
        raise ValueError('Unknown foundation facade engine')
    abi=query_abi(core_sha256,root)
    result={}
    aliases={'collection':'district_collection','item':'district'}
    for name,(_,slots) in retained.items():
        semantic=aliases.get(name,name)
        table,available=abi.tables[semantic]
        if core_sha256==XP1_SHA256:
            keys=slots if isinstance(slots,dict) else tuple(slot for slot,_ in slots)
            selected={slot:available[slot] for slot in keys}
            result[name]=(table,selected if isinstance(slots,dict) else tuple(selected.items()))
            continue
        pairs=tuple(slots.items()) if isinstance(slots,dict) else tuple(slots)
        selected=[]
        for old_slot,old_target in pairs:
            matches=[(op_name,spec) for op_name,spec in _BASE_OPERATIONS.items()
                     if spec.get('table')==semantic and spec.get('slot')==old_slot
                     and spec.get('rva')==old_target]
            if len(matches)!=1:
                raise ValueError(f'Unqualified XP2 foundation table method: {name}+{old_slot:#x}')
            op_name,_=matches[0]
            operation=abi.operations[op_name]
            selected.append((operation['slot'],operation['rva']))
        result[name]=(table,dict(selected) if isinstance(slots,dict) else tuple(selected))
    return result


def select_specs(core_sha256,retained,root=None):
    """Rebind the named, already typed shared operations to selected RVAs."""
    if core_sha256==BASE_SHA256:return retained
    if core_sha256 not in (XP1_SHA256,XP2_SHA256):
        raise ValueError('Unknown foundation facade engine')
    abi=query_abi(core_sha256,root)
    result={}
    for name,(_,result_type,args) in retained.items():
        result[name]=(abi.rva(name),result_type,args)
    return result
