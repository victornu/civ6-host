"""Source-qualified engine dispatch for the common CacheUpdate wire contract."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import struct

from .configuration_profiles import BASE_CORE_SHA256,XP1_CORE_SHA256,XP2_CORE_SHA256,_source,_body

SOURCE=('work/host-extensions/cache-update-static/cache-update-xp1-source-v1.json',
        'a6f2e50a466c8f473c39bc6acaa20e21c89751e9221d28285ef66a347f412ca5')


def source():
    proof=_source(SOURCE)
    if (proof['schema']!='civ6_host.cache_update_xp1.static.v1'
            or proof['images']['xp1']['sha256']!=XP1_CORE_SHA256
            or proof['images']['base']['sha256']!=BASE_CORE_SHA256
            or proof['validation']['all_captured_instruction_bytes_match_images'] is not True
            or proof['validation']['native_execution'] is not False):
        raise ValueError('CacheUpdate source identity or validation differs')
    expected={'outer_vtable_rva':0x8A8DF0,'dispatch_slot':0x198,'dispatch_rva':0x4BE750,
              'keyed_dispatch_rva':0x70620,'register_rva':0x706B0,
              'registry_buckets_rva':0x9CDDB0,'registry_bucket_count_rva':0x9CDDB8,
              'registry_key_count_rva':0x9CDDBC,'host_global_rva':0x9F2640}
    if any(int(proof['profile'][k],16)!=v for k,v in expected.items()):
        raise ValueError('XP1 CacheUpdate source profile differs')
    for name in ('keyed_dispatch','keyed_register'):
        if proof['comparisons'][name]['normalized_instructions_and_CFG_equal'] is not True:
            raise ValueError('XP1 CacheUpdate shared ABI comparison is incomplete')
    from .paths import resource_root
    from .resource_resolution import resolve_path
    for ref in proof['references'].values():
        path=resolve_path(resource_root()/ref['path'])
        if path.suffix=='.json':_source((ref['path'],ref['sha256']))
        elif hashlib.sha256(path.read_bytes()).hexdigest()!=ref['sha256']:
            raise ValueError('CacheUpdate source dependency changed: '+str(path))
    return proof


@dataclass(frozen=True)
class DispatchABI:
    outer_vtable_rva:int
    dispatch_rva:int


def dispatch_abi(core_sha256):
    if core_sha256==BASE_CORE_SHA256:return DispatchABI(0x79E020,0x42F650)
    if core_sha256==XP1_CORE_SHA256:
        source()
        return DispatchABI(0x8A8DF0,0x4BE750)
    if core_sha256==XP2_CORE_SHA256:
        # The dispatch caller separately runs verify_dispatch_live for every
        # event. Its pinned proof and live checks use these same constants.
        from .xp2_preload_source import CACHE_OUTER_VTABLE_RVA, CACHE_DISPATCH_RVA
        return DispatchABI(CACHE_OUTER_VTABLE_RVA,CACHE_DISPATCH_RVA)
    raise ValueError('Unknown CacheUpdate engine profile')


def _exact(read,address,size):
    if type(address) is not int or address<=0 or type(size) is not int or not 0<size<=131072:
        raise ValueError('Invalid bounded CacheUpdate memory read')
    value=read(address,size)
    if type(value) is not bytes or len(value)!=size:
        raise ValueError('Incomplete CacheUpdate memory read')
    return value


def _qword(read,address):return struct.unpack('<Q',_exact(read,address,8))[0]


def registry_snapshot(base,read,key,*,core_sha256=XP1_CORE_SHA256):
    """Inspect the relevant native bucket; never invent an empty registry.

    Subscriber pointers remain native and borrowed. This administrative snapshot
    is not a public player observation or a source of gameplay action masks.
    """
    if core_sha256==XP1_CORE_SHA256:
        registry_rva=0x9CDDB0
    elif core_sha256==XP2_CORE_SHA256:
        from .xp2_preload_source import _validated_source as xp2_source
        registry_rva=int(xp2_source()['deferred']['cache_registry']['buckets_rva'],16)
    else:raise ValueError('Unqualified registry snapshot engine')
    return _registry_snapshot(base, read, key, registry_rva)


def _registry_snapshot(base, read, key, registry_rva):
    if type(key) is not int or not 0<=key<1<<32:
        raise ValueError('CacheUpdate registry key must be uint32')
    header=_exact(read,base+registry_rva,16)
    buckets,count,entries=struct.unpack('<QII',header)
    if not buckets or not 0<count<=65536 or entries>262144:
        raise ValueError('Native CacheUpdate registry is uninitialized or outside resource bounds')
    sentinel=_qword(read,buckets+8*count)
    head_address=buckets+8*(key%count);head=_qword(read,head_address)
    node=head;seen=set();reads=[];matched=None;rows=[]
    while node and node!=sentinel:
        if node in seen or len(seen)>=4096:
            raise ValueError('Native CacheUpdate bucket is cyclic or exceeds resource bounds')
        seen.add(node);raw=_exact(read,node,0x30);reads.append((node,raw))
        found=struct.unpack_from('<I',raw)[0]
        if found==key:
            begin,end,capacity=struct.unpack_from('<QQQ',raw,8)
            if (end<begin or capacity<end or (end-begin)%32 or (capacity-begin)%32
                    or (not begin and (end or capacity)) or end-begin>131072):
                raise ValueError('Native CacheUpdate subscriber vector is malformed or oversized')
            data=_exact(read,begin,end-begin) if end!=begin else b''
            if data:reads.append((begin,data))
            rows=[struct.unpack_from('<QQQQ',data,i) for i in range(0,len(data),32)]
            if any(receiver and not function for _,_,receiver,function in rows):
                raise ValueError('Native CacheUpdate subscriber would call a NULL function')
            matched=node
            break
        node=struct.unpack_from('<Q',raw,0x28)[0]
    if (_exact(read,base+registry_rva,16)!=header or _qword(read,head_address)!=head
            or _qword(read,buckets+8*count)!=sentinel
            or any(_exact(read,p,len(raw))!=raw for p,raw in reads)):
        raise ValueError('Native CacheUpdate registry changed during its snapshot')
    return {'key':key,'bucket_count':count,'entry_count':entries,'node':matched,
            'subscribers':tuple(rows),'receiver_count':sum(bool(r[2] or r[3]) for r in rows)}


def verify_dispatch_live(base,context,read,*,core_sha256,registry_key=0):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_preload_source import verify_cache
        return verify_cache(base,context,read,registry_key=registry_key)
    if core_sha256!=XP1_CORE_SHA256:raise ValueError('No expansion dispatch proof for this engine')
    verify_bodies(base,read,('outer_dispatch','keyed_dispatch'))
    if _qword(read,context)!=base+0x8A8DF0 or _qword(read,base+0x8A8DF0+0x198)!=base+0x4BE750:
        raise ValueError('XP1 CacheUpdate outer context or dispatch slot differs')
    # The native dispatcher divides by the bucket count before searching; do
    # not call it with an uninitialized registry even for an absent key.
    registry=registry_snapshot(base,read,registry_key)
    return {'source_sha256':SOURCE[1],'bucket_count':registry['bucket_count'],
            'registry_entries':registry['entry_count'],'native_dispatch_called':False,
            'saved_game_load_admitted':False}


def verify_notification_live(base,read,*,host_pointer,core_sha256=XP1_CORE_SHA256):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_preload_source import verify_notifications
        return verify_notifications(base,read,host_pointer=host_pointer)
    if core_sha256!=XP1_CORE_SHA256:raise ValueError('Unqualified notification engine')
    verify_bodies(base,read,('notification_begin','notification_end'))
    if _qword(read,base+0x9F2640)!=host_pointer:
        raise ValueError('XP1 notification host belongs to another owner')


def verify_bodies(base,read,names):
    for name in names:
        for fragment in body(name)['fragments']:
            for instruction in fragment['instructions']:
                raw=bytes.fromhex(instruction['bytes'])
                if _exact(read,base+int(instruction['va'],16)-0x180000000,len(raw))!=raw:
                    raise ValueError('XP1 CacheUpdate instruction differs: '+name)


def _select(document,selector):
    for key in selector:document=document[key]
    return document


def body(name):
    proof=source();route=proof['profile']['live_body_sources'][name]
    if route['kind']=='local_body':return _body(_select(proof,route['selector']))
    if route['kind']!='referenced_body':raise ValueError('Unknown cache body source')
    row=proof['referenced_bodies'][route['key']];ref=proof['references'][row['reference']]
    value=_body(_select(_source((ref['path'],ref['sha256'])),row['selector']))
    raw=b''.join(bytes.fromhex(i['bytes']) for f in value['fragments'] for i in f['instructions'])
    if hashlib.sha256(raw).hexdigest()!=row['instruction_bytes_sha256']:
        raise ValueError('CacheUpdate referenced function differs')
    return value


def source_pins():
    from .paths import resource_root
    from .resource_resolution import resolve_path
    proof=source()
    refs=[{'path':SOURCE[0],'sha256':SOURCE[1]},*proof['references'].values()]
    return {str(resolve_path(resource_root()/r['path'])):r['sha256'] for r in refs}
