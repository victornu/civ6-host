"""Actual XP2 natural-wonder input/queries; reuse the existing EXE algorithms.

Raw records and controller receipts are administrative. This does not add a
player observation, callback omission, simulation rule or native qualification.
"""
from dataclasses import dataclass
import ctypes as C
import hashlib
from pathlib import Path
import struct
from types import MappingProxyType
from .configuration_profiles import XP2_CORE_SHA256,_source

SOURCE=('work/host-extensions/xp2-natural-wonder-static/source-profile-v1.json',
        'e2504565a4b2c53703bdca2f6dc810b1f3dfcf8cb8d80e84b10dc0a643d7f7f2')
KIND=0x36c9b2b4
EXE_SHA256='e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
_FIELDS={0xa1e5a149:3,0x8c468e3c:13,0xd6fcf3e4:2,0xa1fbc372:2,0x5b55a347:1024,0xf06a2af2:2}
_PROFILE=None

def _rows(p,name):
    capture=p['functions'][name]['capture']
    return capture.get('instructions') or [r for f in capture['fragments'] for r in f['instructions']]

def _texts(p,name):
    return {int(r.get('va','0'),16) or 0x180000000+int(r['rva'],16):r['text'] for r in _rows(p,name)}

def source():
    p=_source(SOURCE)
    from .xp2_turn_event_profile import fragments
    from .native.native_host_event_registry import EXE_EVENT_CALLBACKS
    if (p['schema']!='civ6-host.xp2-natural-wonder.source.v1' or p['native_execution'] is not False
            or p['process_memory_read'] is not False or p['images']['xp2']['sha256']!=XP2_CORE_SHA256
            or p['images']['exe']['sha256']!=EXE_SHA256 or p['kind']!=hex(KIND)
            or EXE_EVENT_CALLBACKS.get(KIND)!=0x149fd0 or p['callback_rva']!='0x149fd0'
            or p['normalizer_rva']!='0x1ca2d0' or {int(k,16):v for k,v in p['fields'].items()}!=_FIELDS
            or p['records']!={'0x78':112,'0x79':112} or tuple(p['literal_occurrence_rvas'])!=('0x35c379',)
            or p['contract']['omission_admitted'] is not False
            or p['contract']['core_internal_dispatch_before_host'] is not True
            or p['contract']['notification_counters_unchanged'] is not True
            or p['contract']['metadata_flag']!=6 or tuple(p['contract']['record_order'])!=(120,121)
            or len(p['functions'])!=30):
        raise ValueError('XP2 natural-wonder source/registry/field contract differs')
    for body in p['functions'].values():
        raw=b''.join(raw for _,raw in fragments(body))
        if len(raw)!=body['bytes'] or hashlib.sha256(raw).hexdigest()!=body['sha256']:
            raise ValueError('XP2 natural-wonder complete source body differs')
    expected={
      'xp2_0x35c020':{0x18035c374:'mov qword ptr [rsp + 0x40], 0x36c9b2b4',
        0x18035c3f5:'call 0x1805fc070'},
      'xp2_0x5fc070':{0x1805fc0c1:'mov edx, 0xa1e5a149',0x1805fc137:'call 0x18007c670',
        0x1805fc152:'call qword ptr [rax + 0xa0]',0x1805fc15f:'call 0x18099e5d0'},
      'xp2_0x5fd680':{0x1805fd6a9:'lea ebp, [rax + 0xd]',0x1805fd6cb:'mov dword ptr [rsp + 0x20], 8'},
      'xp2_0x5fd700':{0x1805fd729:'mov ebp, 0x400'},
      'xp2_0x5fd780':{0x1805fd78b:'mov dword ptr [rcx + 8], 2',0x1805fd796:'mov dword ptr [rcx + 0x10], r8d'},
      'exe_0x149fd0':{0x14014a01f:'call 0x140151d70'},
      'xp2_0x597560':{0x180597560:'jmp 0x18005cdf0'},
      'exe_0xf1420':{0x1400f142f:'jmp qword ptr [rax + 0x128]'},
    }
    for name,required in expected.items():
        actual=_texts(p,name)
        if any(actual.get(address)!=text for address,text in required.items()):
            raise ValueError('XP2 natural-wonder caller/ABI correspondence differs: '+name)
    cb=list(_texts(p,'exe_0x149fd0').values())
    ordered=('call 0x140151d70','call 0x1401b9c30','call qword ptr [rax + 0x60]',
             'call qword ptr [r8 + 0x90]','call 0x140131910','call 0x140131b10')
    indices=[cb.index(text) for text in ordered]
    if indices!=sorted(indices):raise ValueError('Natural-wonder effects/query/pair order differs')
    # These are EXE-only/common evidence checks, not admission of Base Core ABI.
    from .native import native_36c9b2b4 as shared
    shared.verify_source_evidence()
    from .foundation_facade_profiles import query_abi
    from .paths import resource_root
    abi=query_abi(XP2_CORE_SHA256,resource_root())
    if (abi.table('outer'),abi.rva('outer_game'),abi.table('game'),abi.rva('release_game'))!=(
            0xa101e8,0x5901a0,0xa10ee8,0x596dd0):raise ValueError('Natural-wonder Game owner ABI differs')
    from .xp2_aux_map_profile import profile as map_profile
    mapped=map_profile()
    if mapped.vtable_rva!=0xabf080 or (0x60,0x99f5c0) not in mapped.slots:
        raise ValueError('Natural-wonder input-map lookup ABI differs')
    for ref in p['references']:_source((ref['path'],ref['sha256']))
    return p

def counter_scope():
    source()
    from .native.native_36c9b2b4 import verify_counter_neutral_scope
    return dict(verify_counter_neutral_scope(),core_sha256=XP2_CORE_SHA256,source_sha256=SOURCE[1])

def comparison_abi():
    p=source();a=p['comparison_abi']
    expected=dict(outer_table=0xa101e8,get_game=0x5901a0,game_table=0xa10ee8,release_game=0x596dd0,
                  read_value=0x597560,read_slot=0xc8,read_leaf=0x5cdf0)
    if a!=expected:raise ValueError('Natural-wonder Game comparison selector differs')
    return dict(a,bodies=tuple((int(p['functions'][name]['rva'],16),
        b''.join(bytes.fromhex(r['bytes']) for r in _rows(p,name)))
        for name in ('xp2_0x597560','xp2_0x5cdf0')))

def source_dependencies():
    from .a0_family_source import _path,verify_pinned_files
    from .foundation_facade_profiles import source_dependencies as facade_dependencies
    from .xp2_weather_position import source_dependencies as position_dependencies
    from .xp2_aux_map_profile import source_dependencies as map_dependencies
    from .xp2_cache_source import source_dependencies as retained_dependencies
    from .paths import resource_root
    from .resource_resolution import resolve_path
    p=source();pins={}
    for group in (facade_dependencies(core_sha256=XP2_CORE_SHA256),position_dependencies(),map_dependencies(),
                  retained_dependencies()):
        for path,sha in group.items():
            if path in pins and pins[path]!=sha:raise ValueError('Natural-wonder dependency pin conflict')
            pins[path]=sha
    pins[str(resolve_path(resource_root()/SOURCE[0]).resolve())]=SOURCE[1]
    for ref in (*p['references'],*p['extractors']):pins[str(_path(ref['path']).resolve())]=ref['sha256']
    verify_pinned_files(pins)
    return pins

def verify_live(base,read):
    from .xp2_turn_event_profile import fragments
    p=source()
    for body in p['functions'].values():
        if body['image']!='xp2':continue
        for address,raw in fragments(body):
            for offset in range(0,len(raw),4096):
                expected=raw[offset:offset+4096]
                if read(base+address-0x180000000+offset,len(expected))!=expected:
                    raise ValueError('Natural-wonder live XP2 source bytes differ')
    for table,slot,target in ((0xa101e8,0x90,0x5901a0),(0xa10ee8,8,0x596dd0),
            (0xa10ee8,0xc8,0x597560),(0xabf080,0x60,0x99f5c0),(0xa11698,0x90,0x59b590)):
        if read(base+table+slot,8)!=struct.pack('<Q',base+target):
            raise ValueError('Natural-wonder live XP2 virtual dispatch differs')

def event_profile():
    global _PROFILE
    source()
    from .a0_family_source import A0FamilyProfile
    from .native.native_deferred_empty_profile import resolve_empty_receiver_row
    for record in (120,121):
        row=resolve_empty_receiver_row(record)
        if row is None or set(row['record_sizes'])!={112}:raise ValueError('Natural-wonder empty receiver differs')
    if _PROFILE is None:_PROFILE=A0FamilyProfile(MappingProxyType({KIND:frozenset((120,121))}),
                                                MappingProxyType({120:112,121:112}),SOURCE[1])
    return _PROFILE

@dataclass(frozen=True)
class VerifiedSource:
    owner:object
    core:object
    base:int
    source_sha256:str
    read:object

def bind_owner(backend,read):
    backend.check_thread()
    if backend.load_abi.core_sha256!=XP2_CORE_SHA256 or hasattr(backend,'_xp2_natural_wonder_source'):
        raise ValueError('Natural-wonder source requires its original XP2 backend')
    source_dependencies();verify_live(backend.core._handle,read)
    backend._xp2_natural_wonder_source=VerifiedSource(backend,backend.core,backend.core._handle,SOURCE[1],read)
    return event_profile()

def validate_fields(fields):
    if (type(fields) is not dict or set(fields)!=set(_FIELDS)
            or any(type(k) is not int or type(v) is not bytes or len(v)!=24
                   or struct.unpack_from('<H',v)[0]!=_FIELDS[k] for k,v in fields.items())):
        raise ValueError('Natural-wonder XP2 argument shape differs')
    from .native.native_event_827289e6 import decode_scalar
    if decode_scalar(fields[0xa1e5a149],3)!=0:
        raise ValueError('Natural-wonder XP2 producer selector differs')

def lookup_ignored_input_field(core,pointer,read,native_api=None):
    from .xp2_aux_map_profile import profile,verify_live as verify_map
    selected=profile();base=core._handle;verify_map(selected,base,read)
    def check():
        if (type(pointer) is not int or pointer<=0 or core._handle!=base
                or read(pointer,8)!=struct.pack('<Q',base+selected.vtable_rva)
                or read(base+selected.vtable_rva+0x60,8)!=struct.pack('<Q',base+0x99f5c0)):
            raise ValueError('Natural-wonder original input-map identity differs')
    check()
    if native_api is None:lookup=C.WINFUNCTYPE(C.c_void_p,C.c_void_p,C.c_uint32)(base+0x99f5c0)
    else:
        if type(native_api) is not dict or set(native_api)!={'lookup'} or not callable(native_api['lookup']):
            raise ValueError('Natural-wonder input-map native seam differs')
        lookup=native_api['lookup']
    result=lookup(pointer,0x5b55a347);check()
    return dict(called=True,returned_nonnull=bool(result),forced_value=0xffffffff)

def position_index(core,facades,position,*,read,native_api=None):
    from .xp2_weather_position import query_native_position_index
    result=query_native_position_index(core,facades,position,read=read,native_api=native_api)
    return result.index,result.x,result.y
