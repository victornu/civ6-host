"""Source boundary for the existing EXE private notification pipeline on XP1."""
import hashlib
from types import MappingProxyType
from .configuration_profiles import XP1_CORE_SHA256,XP2_CORE_SHA256,_source
from .a0_family_source import A0FamilyProfile
from .paths import resource_root
from .resource_resolution import resolve_path

SOURCE=('work/host-extensions/xp1-private-notification-static/source-v1.json',
        '9d4cd466c7e6133a4c06665c97b152823f46c862aa565d4ab66b5bc24f1d8dd5')
KINDS=frozenset((0x1be52206,0x66ade3b3))


def verify_source(*,core_sha256=XP1_CORE_SHA256):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_turn_notification_source import source
        return source()
    if core_sha256!=XP1_CORE_SHA256:raise ValueError('Unqualified private notification engine')
    p=_source(SOURCE)
    if (p['schema']!='civ6_host.xp1_private_notifications.static.v1'
            or p['native_execution'] is not False or p['process_memory_read'] is not False
            or p['image']['sha256']!=XP1_CORE_SHA256
            or dict(p['validation'])!={'instruction_bytes_match_image':True,'exact_guard_count':18,
                                      'native_query_count_in_shared_callbacks':0}):
        raise ValueError('XP1 private notification source changed')
    if ({int(k,16):v['builder'] for k,v in p['events'].items()}
            !={0x1be52206:0x519650,0x66ade3b3:0x5195a0}):
        raise ValueError('Private notification producer ABI changed')
    from .native.native_event_1be52206 import verify_source_evidence as verify54
    from .native.native_event_66ade3b3 import verify_source_evidence as verify57
    from .native.native_private_ring_consumer import verify_source_evidence as verify_consumer
    verify54();verify57();verify_consumer()
    return p


def source_dependencies(*,core_sha256=XP1_CORE_SHA256):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_turn_notification_source import source_dependencies as selected
        return selected()
    verify_source(core_sha256=core_sha256)
    p=verify_source();rows=[{'path':SOURCE[0],'sha256':SOURCE[1]},p['extractor'],p['inventory'],
                          *p['references'].values(),*p['source_modules'].values()]
    rows.extend(i['transcript'] for i in p['base_intervals'])
    pins={}
    for row in rows:
        path=resolve_path(resource_root()/row['path']).resolve()
        with path.open('rb') as stream:actual=hashlib.file_digest(stream,'sha256').hexdigest()
        if actual!=row['sha256']:raise ValueError('Private notification source pin changed: '+str(path))
        if str(path) in pins and pins[str(path)]!=actual:raise ValueError('Conflicting source pins')
        pins[str(path)]=actual
    return pins


def verify_live(base,read,*,core_sha256=XP1_CORE_SHA256):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_turn_notification_source import verify_live as selected
        return selected(base,read)
    if core_sha256!=XP1_CORE_SHA256 or type(base) is not int or base<=0 or not callable(read):
        raise ValueError('Private notification source requires XP1 module/read binding')
    p=verify_source();count=0
    for body in p['functions'].values():
        for fragment in body.get('fragments') or (body,):
            rows=fragment['instructions'];start=int(rows[0]['va'],16)-0x180000000
            raw=b''.join(bytes.fromhex(r['bytes']) for r in rows)
            cursor=start
            for row in rows:
                if int(row['va'],16)-0x180000000!=cursor:raise ValueError('Private producer capture is not contiguous')
                cursor+=len(bytes.fromhex(row['bytes']))
            actual=read(base+start,len(raw))
            if type(actual) is not bytes or actual!=raw:raise ValueError('XP1 private producer code differs')
            count+=1
    return {'source_sha256':SOURCE[1],'core_sha256':XP1_CORE_SHA256,'verified_fragments':count,
            'native_execution':False,'private_receivers_generalized':False}


def source_reference(*,core_sha256=XP1_CORE_SHA256):
    verify_source(core_sha256=core_sha256)
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_turn_notification_source import SOURCE as selected
        return selected
    return SOURCE


def event_profile(*,core_sha256=XP1_CORE_SHA256):
    verify_source(core_sha256=core_sha256)
    # The first kind deliberately has no standard FIFO record. Its private
    # record is validated by the shared private-ring consumer, never _ROWS.
    return A0FamilyProfile(MappingProxyType({0x1be52206:frozenset(),
        0x66ade3b3:frozenset((5,))}),MappingProxyType({5:96}),source_reference(core_sha256=core_sha256)[1])
