"""Shared populated-cache layout; source selection never admits saved Load."""
from __future__ import annotations
from dataclasses import dataclass
import struct
from .configuration_profiles import BASE_CORE_SHA256, XP1_CORE_SHA256, _source, _body
from .saved_load_profiles import XP2_CORE_SHA256
from .cache_facade_profiles import context_state, check_facades

SOURCE=('work/host-extensions/xp1-loaded-cache-static/loaded-cache-source-v1.json',
        '1309336ce69457fa1ca172d45919865e46ae3d497c149128a2397cdca30153b7')

@dataclass(frozen=True)
class LoadedCacheABI:
    core_sha256: str
    outer_vtable_rva: int
    service_global_rva: int
    service_vtable_rva: int
    service_ensure_rva: int
    service_owner_rva: int
    service_publish_rva: int
    game_global_rva: int
    cache_owner_vtable_rva: int
    map_view_offset: int
    map_view_vtable_rva: int
    notification_rva: int
    notification_byte_rva: int

_BASE=LoadedCacheABI(BASE_CORE_SHA256,0x79E020,0x8BB400,0x7C7148,0x85A0,
    0x7339C0,0x86A0,0x8BB748,0x766A70,0x1770,0x7604E8,0x42DCA0,0x89CDA0)
_XP1=LoadedCacheABI(XP1_CORE_SHA256,0x8A8DF0,0x9F22E0,0x8D7238,0x9750,
    0x94C0,0x9860,0x9F2628,0x867788,0xA8B0,0x860DC8,0x4BCDA0,0x9CDDA0)
_XP2=LoadedCacheABI(XP2_CORE_SHA256,0xA101E8,0xB8A720,0xA45040,0xA590,
    0x956030,0xA690,0xB8AA68,0x9C2878,0xA8B0,0x9BB538,0x58FF70,0xB61E00)

def loaded_cache_abi(core_sha256):
    if core_sha256==BASE_CORE_SHA256:return _BASE
    if core_sha256==XP1_CORE_SHA256:return _XP1
    if core_sha256==XP2_CORE_SHA256:
        source(core_sha256=core_sha256)
        return _XP2
    raise ValueError('Unknown loaded-cache engine')

def require_abi(abi):
    if abi is not _BASE and abi is not _XP1 and abi is not _XP2:raise ValueError('Canonical loaded-cache ABI required')
    return abi

def require_mode(abi,mode):
    require_abi(abi)
    if mode not in ('public','candidate'):raise ValueError('Unknown loaded-cache publication mode')
    if abi in (_XP1,_XP2) and mode!='candidate':
        raise ValueError('XP1 cache publication requires the explicit candidate mode; public callbacks remain unqualified')
    if abi is _BASE and mode!='public':raise ValueError('Base preserves the existing public publication mode')

def source(*,core_sha256=XP1_CORE_SHA256):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_cache_source import source as selected
        p=selected()
        if p['loaded_profile']!={k:getattr(_XP2,k) for k in _XP2.__dataclass_fields__}:
            raise ValueError('XP2 loaded-cache ABI differs')
        return p
    if core_sha256!=XP1_CORE_SHA256:raise ValueError('Unknown loaded-cache source engine')
    p=_source(SOURCE)
    expected={k:getattr(_XP1,k) for k in _XP1.__dataclass_fields__}
    if (p['schema']!='civ6_host.loaded_cache_xp1.static.v1'
            or p['image']['sha256']!=XP1_CORE_SHA256
            or any(p['profile'][k]!=v for k,v in expected.items())
            or p['validation']!=dict(instruction_bytes_rechecked=True,instruction_count=1070,
                native_execution=False,process_memory_read=False,public_admission=False)):
        raise ValueError('Loaded-cache source identity differs')
    for r in p['references'].values():_source((r['path'],r['sha256']))
    return p

def verify_xp1_live(base,read,proof=None):
    p=source() if proof is None else proof
    if p!=source():raise ValueError('Foreign loaded-cache proof')
    for name,body in p['bodies'].items():
        for f in _body(body)['fragments']:
            for i in f['instructions']:
                raw=bytes.fromhex(i['bytes'])
                if read(base+int(i['va'],16)-0x180000000,len(raw))!=raw:
                    raise ValueError('Loaded-cache instructions differ: '+name)
    for row in p['slots']:
        if qword(read,base+row['vtable_rva']+row['slot'])!=base+row['target_rva']:
            raise ValueError('Loaded-cache virtual target differs')
    return p

def verify_live(base,read,proof=None,*,core_sha256=XP1_CORE_SHA256):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_cache_source import verify_live as selected
        return selected(base,read,proof)
    if core_sha256!=XP1_CORE_SHA256:raise ValueError('Unknown loaded-cache live engine')
    return verify_xp1_live(base,read,proof)

def exact(read,address,size):
    raw=read(address,size)
    if type(raw) is not bytes or len(raw)!=size:raise ValueError('Incomplete loaded-cache read')
    return raw

def qword(read,address):return struct.unpack('<Q',exact(read,address,8))[0]

def service_state(base,context,read,abi):
    require_abi(abi)
    q=lambda addr:qword(read,addr)
    if type(context) is not int or context<=0 or q(context)!=base+abi.outer_vtable_rva:
        raise ValueError('Loaded-cache outer context differs')
    service=q(base+abi.service_global_rva)
    if not service or q(service)!=base+abi.service_vtable_rva:
        raise ValueError('Loaded-cache service unavailable')
    for slot,target in ((8,abi.service_ensure_rva),(0x80,abi.service_owner_rva),(0xA8,abi.service_publish_rva)):
        if q(base+abi.service_vtable_rva+slot)!=base+target:
            raise ValueError('Loaded-cache service target differs')
    game=q(base+abi.game_global_rva)
    if not game:raise ValueError('Loaded-cache Game unavailable')
    if abi in (_XP1,_XP2):
        state=context_state(base,context,read,core_sha256=abi.core_sha256)
        if (state['service'],state['game'])!=(service,game):raise ValueError('Loaded-cache service/Game ownership differs')
    return service,game

def validate_copy(base,context,read,abi,facades,copied,*,expected_game,expected_dimensions):
    """Validate actual returned bytes/owners only; this never opens any gate."""
    require_abi(abi)
    if type(copied) is not bytes or len(copied)!=28:raise ValueError('Expected exact native28-byte cache copy')
    if (type(expected_dimensions) is not tuple or len(expected_dimensions)!=2
            or any(type(x) is not int or x<=0 for x in expected_dimensions)):
        raise ValueError('Expected verified loaded dimensions')
    width,height,count=struct.unpack_from('<iii',copied)
    if (width,height)!=expected_dimensions or count!=width*height:
        raise ValueError('Native cache dimensions differ from loaded readback')
    service,game=service_state(base,context,read,abi);q=lambda addr:qword(read,addr)
    owner=q(service+8)
    if (type(expected_game) is not int or not expected_game or game!=expected_game
            or not owner or q(owner)!=base+abi.cache_owner_vtable_rva
            or facades is None or facades._closed or facades.outer!=context
            or facades.abi.core_sha256!=abi.core_sha256
            or not facades.backend.context_alive() or facades.backend.core_base!=base
            or q(facades.game_facade+16)!=owner
            or exact(read,owner+0x38,1)!=b'\1' or not q(owner+0x58)):
        raise ValueError('Loaded visibility cache does not belong to this live Game/facade')
    view=q(owner+abi.map_view_offset)
    if not view or q(view)!=base+abi.map_view_vtable_rva or exact(read,view+0x28,12)!=copied[:12]:
        raise ValueError('Loaded native map/cache view differs from returned copy')
    if abi in (_XP1,_XP2):
        if exact(read,game+0x2A4,1)!=b'\1':raise ValueError('XP1 Game is not initialized')
        state=context_state(base,context,read,core_sha256=abi.core_sha256)
        check_facades(facades,state,read)
        if state['member']!=view or exact(read,view+0x28,28)!=copied:
            raise ValueError('XP1 copy does not preserve all native map/cache bytes')
    return dict(service=service,game=game,owner=owner,view=view,dimensions=(width,height,count))
