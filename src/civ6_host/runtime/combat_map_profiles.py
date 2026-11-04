"""Select existing native map ownership primitives; no combat rule rewrite."""
from .configuration_profiles import (BASE_CORE_SHA256, XP1_CORE_SHA256, XP2_CORE_SHA256,
    OWNERSHIP_SOURCE, LIVE_SOURCE, _source, configuration_abi,
    require_owner_profile, application_source)

OWNER_SOURCE=('evidence/native-event-8256dbe1/21e45dc5adc360fc3371aa373e4b20ccb397f3ab7c7c0038fa4e6cb56de6d84e.json',
              '21e45dc5adc360fc3371aa373e4b20ccb397f3ab7c7c0038fa4e6cb56de6d84e')
RECEIVER_SOURCE=('evidence/native-combat-receiver-f8/200aecee4ba3ad1f5d26f02027cf65190dd0087a6a24d60acf183ad0f662be92.json',
                 '200aecee4ba3ad1f5d26f02027cf65190dd0087a6a24d60acf183ad0f662be92')


def profile_for_sha(core_sha256):
    if core_sha256 not in (BASE_CORE_SHA256,XP1_CORE_SHA256,XP2_CORE_SHA256):
        raise ValueError('Combat map owner engine is not qualified')
    return require_owner_profile(configuration_abi(core_sha256))


def owner_source(core_sha256):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_combat_event_source import map_owner_source
        return map_owner_source(core_sha256=core_sha256)
    if core_sha256!=XP1_CORE_SHA256:
        raise ValueError('Expected the exact XP1 combat map ownership profile')
    abi=profile_for_sha(core_sha256)
    source=application_source(core_sha256)
    base=_source(OWNER_SOURCE)
    if (base['schema']!='civ6rl.native_event_8256dbe1.static.v1'
            or base['images']['core_sha256']!=BASE_CORE_SHA256
            or base['images']['exe_sha256']!='e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'):
        raise ValueError('Shared combat map/EXE registry source differs')
    registry=base['contract']['registry']
    if (registry['initial_next_id']!=1 or registry['node_size']!=32
            or registry['sentinel_offset']!=8 or registry['node_fields']['0x14']!='refcountDWORD'
            or registry['node_fields']['0x18']!='owned map pointer'):
        raise ValueError('Shared EXE combat registry layout changed')
    aliases={'map_constructor':'provider_constructor','map_assign':'provider_assign',
        'map_copy':'provider_copy','map_destructor':'provider_destructor',
        'variant_clone_construct':'variant_clone_construct','variant_clone_assign':'variant_clone_assign',
        'variant_release':'variant_release'}
    captures={name:source['core_functions'][target] for name,target in aliases.items()}
    for name,rva in (('map_constructor',abi.constructor_rva),('map_assign',abi.assign_rva),
                     ('map_copy',abi.copy_rva),('map_destructor',abi.destructor_rva)):
        if int(captures[name]['fragments'][0]['start_va'],16)!=0x180000000+rva:
            raise ValueError('XP1 combat map primitive identity changed: '+name)
    return dict(core_captures=captures,source_sha256=LIVE_SOURCE[1],
                registry_source_sha256=OWNER_SOURCE[1],core_sha256=core_sha256,
                contract=dict(registry=registry))


def verify_live(base,read,*,core_sha256):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_combat_event_source import verify_map_live
        return verify_map_live(base,read,core_sha256=core_sha256)
    from .native.native_configuration_finalization import _read,_qword
    abi=profile_for_sha(core_sha256)
    if type(base) is not int or base<=0 or not callable(read):
        raise ValueError('Expected actual native map module and reader')
    proof=owner_source(core_sha256)
    for name,body in proof['core_captures'].items():
        for fragment in body['fragments']:
            raw=b''.join(bytes.fromhex(row['bytes']) for row in fragment['instructions'])
            address=base+int(fragment['start_va'],16)-0x180000000
            for offset in range(0,len(raw),4096):
                expected=raw[offset:offset+4096]
                if _read(read,address+offset,len(expected))!=expected:
                    raise ValueError('XP1 combat native copy code changed: '+name)
    if (_qword(read,base+abi.vtable_rva+0x1d0)!=base+abi.assign_rva
            or _qword(read,base+abi.vtable_rva+0x178)!=base+abi.copy_rva):
        raise ValueError('XP1 combat native map virtual primitive changed')


def source_dependencies(core_sha256=XP1_CORE_SHA256):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_combat_event_source import source_dependencies as xp2_dependencies
        return xp2_dependencies()
    if core_sha256!=XP1_CORE_SHA256:
        raise ValueError('Combat map source dependencies require exact XP1 or XP2')
    from .paths import resource_root
    from .resource_resolution import resolve_path
    owner_source(XP1_CORE_SHA256)
    references=[OWNERSHIP_SOURCE,LIVE_SOURCE,OWNER_SOURCE,RECEIVER_SOURCE]
    references.extend((r['path'],r['sha256']) for r in _source(OWNERSHIP_SOURCE)['source_refs'].values())
    result={}
    for path,sha in references:
        _source((path,sha))
        key=str(resolve_path(resource_root()/path).resolve())
        if key in result and result[key]!=sha:raise ValueError('Combat owner source dependency conflict')
        result[key]=sha
    return result
