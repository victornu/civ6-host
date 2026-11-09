"""XP1 selection for the shared district damage/combat notification queries.

No callback codec or simulation rule is implemented here. The native façade
addresses come from the already-reviewed foundation profile.
"""
from dataclasses import dataclass
from functools import lru_cache
from types import MappingProxyType
from .configuration_profiles import BASE_CORE_SHA256, XP1_CORE_SHA256, XP2_CORE_SHA256, _source

SOURCE=('work/host-extensions/xp1-district-damage-static/source-v3.json',
        '4d9253bd3d9e392489ad8ec66abd8d14b08e63f1c4f80fa3c8b2edcbdd9fa5f7')
KINDS={0xf74afc79:0x9f,0x47261a7d:0xa1}
SIZES={0x9f:144,0xa1:128}
OPERATIONS={'get_player':'get_player','release_player':'release_player',
    'player_collection':'player_districts','release_collection':'release_collection',
    'collection_index':'district_by_id','release_item':'release_district',
    'item_variant':'district_city_descriptor','item_raw':'district_type',
    'item_position':'district_position','item_hash':'district_hash'}
TABLES={'outer':'outer','player':'player','collection':'district_collection','item':'district'}


def rows(value):
    return tuple(value.get('instructions',())) or tuple(r for f in value['fragments'] for r in f['instructions'])


def bodies(proof):
    return {**proof['functions'],**{name:_source((r['path'],r['sha256']))
                                    for name,r in proof['reused_functions'].items()}}


@lru_cache(maxsize=1)
def verify_source():
    from .native import native_event_f74afc79 as damage, native_event_47261a7d as combat
    from .native import native_event_754cbd1b_city as city
    from .native.native_host_event_registry import EXE_EVENT_CALLBACKS
    p=_source(SOURCE)
    if (p['schema']!='civ6-host.xp1-district-damage.static.v1' or p['native_execution'] is not False
            or p['image']['sha256']!=XP1_CORE_SHA256
            or p['validation']['all_instruction_bytes_match_image'] is not True
            or EXE_EVENT_CALLBACKS[0xf74afc79]!=0x145120
            or EXE_EVENT_CALLBACKS[0x47261a7d]!=0x144fd0):
        raise ValueError('District damage/combat source identity changed')
    for r in p['references']:_source((r['path'],r['sha256']))
    damage.verify_source_evidence();combat.verify_source_evidence();city.verify_source_evidence()
    f=bodies(p)
    guards={
        'damage_emitter':{0x15688b:'cmp ebp, 0x5e97d629',0x156893:'cmp ebp, 0x6da56a3d',
            0x1568cb:'cmp ebx, esi',0x1568d2:'je 0x180156931',
            0x1568f3:'mov dword ptr [rsp + 0x20], 0xf74afc79',
            0x156900:'mov dword ptr [rsp + 0x24], ebp',0x156904:'mov r9d, ebx',
            0x156907:'mov r8d, esi',0x15690e:'mov eax, 3',0x15692c:'call 0x180518a80'},
        'damage_builder':{0x518ad1:'mov edx, 0xa1e5a149',0x518aff:'mov edx, 0xf343dc5a',
            0x518b41:'mov dword ptr [rsp + 0x20], 8',0x518b57:'mov edx, 0xd6fcf3e4',
            0x518b69:'mov edx, 0xa1fbc372'},
        'descriptor_builder':{0x154ea0:'movsx r8d, byte ptr [rax + 0x1c]',
            0x154ea5:'mov eax, 3',0x154eaa:'mov word ptr [rdi + 2], ax',
            0x154eae:'mov eax, dword ptr [rbx + 0xa0]',0x154eb9:'mov dword ptr [rdi + 4], eax',
            0x154ebf:'mov word ptr [rdi], r8w'},
        'combat_emitter':{0x12837a:'mov qword ptr [rsp + 0x30], 0x754cbd1b',
            0x128396:'call 0x180154e70',0x1283aa:'call 0x180517f00',
            0x12872d:'mov dword ptr [rbp + 0x110], 0x47261a7d',
            0x12873a:'mov dword ptr [rbp + 0x114], 0x599feed4',
            0x128744:'call 0x180154e70',0x128753:'call 0x1805180b0'},
        'pair_field_builder':{0x5176b4:'mov esi, 0xf0548bb7',0x5176be:'mov r14d, 0xf343dc5a',
            0x5176c4:'cmp ax, 1',0x5176e6:'mov edx, 0xf0548bb7',
            0x5176fc:'mov esi, 0x8753bb21',0x5177e2:'cmp ax, 3',
            0x5177e8:'mov edx, r14d',0x51780a:'mov dword ptr [rsp + 0x20], 8'}}
    for name,expected in guards.items():
        actual={int(r['va'],16)-0x180000000:r['text'] for r in rows(f[name])}
        if any(actual.get(rva)!=text for rva,text in expected.items()):
            raise ValueError('District producer/descriptor contract changed: '+name)
    for name in ('damage_builder','single_descriptor_builder','pair_builder'):
        text=[r['text'] for r in rows(f[name])]
        if not (text.index('call 0x180070b10')<text.index('call qword ptr [rax + 0xa0]')
                <text.index('call 0x180844580')):
            raise ValueError('District event native dispatch/host/map lifetime order changed')
    return p


def ensure_source(core_sha256):
    if core_sha256==BASE_CORE_SHA256:return
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_district_damage_event_source import source
        source();return
    if core_sha256!=XP1_CORE_SHA256:raise ValueError('Unqualified district notification engine')
    verify_source()


def source_sha(core_sha256,retained):
    ensure_source(core_sha256)
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_district_damage_event_source import SOURCE as selected
        return selected[1]
    return retained if core_sha256==BASE_CORE_SHA256 else SOURCE[1]


def _abi(core_sha256):
    from .foundation_facade_profiles import query_abi
    from .paths import resource_root
    ensure_source(core_sha256)
    return query_abi(core_sha256,resource_root())


def select_tables(core_sha256,retained):
    ensure_source(core_sha256)
    if core_sha256==BASE_CORE_SHA256:return retained
    abi=_abi(core_sha256)
    if set(retained)!=set(TABLES):raise ValueError('District query facade family changed')
    return {name:(abi.table(TABLES[name]),tuple((slot,abi.tables[TABLES[name]][1][slot])
                 for slot,_ in slots)) for name,(_,slots) in retained.items()}


def select_specs(core_sha256,retained):
    ensure_source(core_sha256)
    if core_sha256==BASE_CORE_SHA256:return retained
    if set(retained) not in (set(OPERATIONS),set(OPERATIONS)-{'item_position','item_hash'}):
        raise ValueError('District query operation family changed')
    abi=_abi(core_sha256)
    return {name:(abi.rva(OPERATIONS[name]),restype,args) for name,(_,restype,args) in retained.items()}


@lru_cache(maxsize=2)
def _event_profile(*,core_sha256=XP1_CORE_SHA256):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_district_damage_event_source import event_profile as selected
        return selected()
    if core_sha256!=XP1_CORE_SHA256:raise ValueError('Unqualified district event profile engine')
    from .a0_family_source import A0FamilyProfile
    from .native.native_deferred_empty_profile import resolve_empty_receiver_row
    verify_source()
    for record,size in SIZES.items():
        if set(resolve_empty_receiver_row(record)['record_sizes'])!={size}:
            raise ValueError('District damage/combat receiver changed')
    return A0FamilyProfile(MappingProxyType({k:frozenset((r,)) for k,r in KINDS.items()}),
                           MappingProxyType(SIZES),SOURCE[1])


def event_profile(*,core_sha256=XP1_CORE_SHA256,execution_image=None):
    if execution_image is not None and core_sha256!=XP2_CORE_SHA256:
        raise ValueError('Selected execution image requires XP2 district ABI')
    if execution_image is not None:
        from .execution_images import identity
        identity(execution_image)
    return _event_profile(core_sha256=core_sha256)


def source_dependencies(*,core_sha256=XP1_CORE_SHA256,execution_image=None):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_district_damage_event_source import source_dependencies as selected
        return selected(execution_image=execution_image)
    if execution_image is not None:raise ValueError('Selected execution image requires XP2 district ABI')
    if core_sha256!=XP1_CORE_SHA256:raise ValueError('Unqualified district source engine')
    from pathlib import Path
    from .paths import resource_root
    from .resource_resolution import resolve_path
    from .foundation_event_profile import source_dependencies as foundation_sources
    p=verify_source()
    refs=[dict(path=SOURCE[0],sha256=SOURCE[1]),p['image'],*p['references'],
          *p['reused_functions'].values(),p['extractor'],p['capture_helper']]
    return {**foundation_sources(),**{
        str(resolve_path(Path(r['path']) if Path(r['path']).is_absolute()
                         else resource_root()/r['path']).resolve()):r['sha256'] for r in refs}}


def verify_live(base,read,*,core_sha256=XP1_CORE_SHA256):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_district_damage_event_source import verify_live as selected
        return selected(base,read)
    if core_sha256!=XP1_CORE_SHA256:raise ValueError('Unqualified district live engine')
    count=0
    for name,value in bodies(verify_source()).items():
        for r in rows(value):
            raw=bytes.fromhex(r['bytes'])
            if read(base+int(r['va'],16)-0x180000000,len(raw))!=raw:
                raise ValueError('XP1 district source bytes differ: '+name)
            count+=1
    return count


def verify_once(core,read,*,core_sha256=XP1_CORE_SHA256):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_district_damage_event_source import verify_once as selected
        return selected(core,read)
    if core_sha256!=XP1_CORE_SHA256:raise ValueError('Unqualified district verification engine')
    from .foundation_facade_profiles import verify_xp1_once
    from .paths import resource_root
    base=int(core._handle);key=(base,SOURCE[1])
    if getattr(core,'_xp1_district_damage_verified',None)==key:return
    verify_xp1_once(core,base,read,resource_root());verify_live(base,read)
    core._xp1_district_damage_verified=key


@dataclass(frozen=True)
class VerifiedSource:
    owner:object
    core:object
    base:int
    proof_sha256:str


def bind_owner(owner,core,read,*,execution_image=None):
    if owner.load_abi.core_sha256==XP2_CORE_SHA256:
        from .xp2_district_damage_event_source import bind_owner as selected
        if execution_image is None:
            execution_image=getattr(core,'_civ6_host_execution_image',None)
        return selected(owner,core,read,execution_image=execution_image)
    if execution_image is not None:raise ValueError('Selected execution image requires XP2 district ABI')
    owner.check_thread()
    if owner.core is not core or owner.load_abi.core_sha256!=XP1_CORE_SHA256:
        raise ValueError('XP1 district source owner mismatch')
    old=getattr(owner,'_xp1_district_damage_source',None)
    if old is not None:
        if (type(old) is not VerifiedSource or old.owner is not owner or old.core is not core
                or old.base!=core._handle or old.proof_sha256!=SOURCE[1]):
            raise ValueError('XP1 district source owner lifetime changed')
        return event_profile()
    verify_once(core,read)
    owner._xp1_district_damage_source=VerifiedSource(owner,core,core._handle,SOURCE[1])
    return event_profile()
