"""Pinned XP2 Player/Treasury query ABI for the shared notification lease."""
import hashlib
import struct
from .configuration_profiles import _source, XP2_CORE_SHA256

SOURCE=('work/host-extensions/xp2-player-query-static/source-profile-v1.json',
        'd5e71d1a2ff1eeceed0d316d209942c25068754716342c51540f0f8638f8af4c')
CONSTANTS=dict(PLAYER_MANAGER_VTABLE_RVA=0xa101e8,PLAYER_MANAGER_GET_PLAYER_SLOT=0xb8,PLAYER_MANAGER_GET_PLAYER_RVA=0x590360,
    PLAYER_VTABLE_RVA=0xa11a80,PLAYER_GET_COMPONENT_SLOT=0x100,PLAYER_GET_COMPONENT_RVA=0x59d290,
    PLAYER_RELEASE_SLOT=8,PLAYER_RELEASE_RVA=0x59c8c0,COMPONENT_VTABLE_RVA=0xa12278,
    COMPONENT_GETTER_18_SLOT=0x18,COMPONENT_GETTER_18_RVA=0x5a01b0,
    COMPONENT_GETTER_10_SLOT=0x10,COMPONENT_GETTER_10_RVA=0x5a01f0,COMPONENT_RELEASE_SLOT=8,COMPONENT_RELEASE_RVA=0x5a0140)


def source():
    p=_source(SOURCE);a=p['profile']
    if (p['schema']!='civ6-host.xp2-player-query.source.v1'
            or p['native_execution'] is not False or p['core_sha256']!=XP2_CORE_SHA256
            or p['exe_sha256']!='e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
            or a['constants']!=CONSTANTS or a['lock']['host_global_rva']!=0xb8aa80
            or a['wrapper_layout']!={'size':32,'live':8,'cache':16,'refcount':24,'initial_refcount':1,'player_component_offset':0x780}
            or (a['event']['kind'],a['event']['record_type'],a['event']['size'])!=(0x20f2116e,0xc1,96)):
        raise ValueError('XP2 Player/Treasury source contract differs')
    differences={k for k,v in p['comparisons'].items() if not v['normalized_equal']}
    if differences!={'get_component','cached_component_pointer'}:
        raise ValueError('XP2 Player component changes are not the reviewed members')
    instructions={}
    for name,body in p['bodies'].items():
        parts=[]
        for f in body['fragments']:
            raw=bytes.fromhex(f['raw_hex']);parts.append(raw)
            if len(raw)!=f['length'] or hashlib.sha256(raw).hexdigest()!=f['sha256'] or ''.join(i['bytes'] for i in f['instructions'])!=raw.hex():
                raise ValueError('XP2 Player query fragment differs: '+name)
            instructions.update({i['rva']:i['text'] for i in f['instructions']})
        raw=b''.join(parts)
        if (raw.hex()!=body['raw_hex'] or hashlib.sha256(raw).hexdigest()!=body['sha256']
                or body['all_conditional_targets_captured'] is not True
                or body['boundary_method'] not in ('complete-runtime-function-chained-unwind-root-v2','complete-reachable-leaf-cfg-v1')):
            raise ValueError('XP2 Player query complete body differs: '+name)
    if any(instructions.get(rva)!=text for rva,text in p['instruction_guards'].items()):
        raise ValueError('XP2 query member/lock/output contract differs')
    return p


def source_dependencies():
    from .a0_family_source import _path, verify_pinned_files, verify_extracted_sources
    p=source()
    refs=[dict(path=SOURCE[0],sha256=SOURCE[1]),*p['references'],*p['source_pins'].values(),
          *(p[k] for k in ('generator','boundary_helper','extractor'))]
    pins={str(_path(r['path'])):r['sha256'] for r in refs}
    verify_pinned_files(pins);verify_extracted_sources(p['source_pins'].values())
    return pins


def verify_live(base,read,*,host_pointer):
    p=source();source_dependencies()
    for name,body in p['bodies'].items():
        for f in body['fragments']:
            raw=bytes.fromhex(f['raw_hex'])
            if read(base+int(f['start_rva'],16),len(raw))!=raw:
                raise ValueError('XP2 Player query native body differs: '+name)
    for row in p['profile']['targets']:
        if read(base+row['vtable_rva']+row['slot'],8)!=struct.pack('<Q',base+row['target_rva']):
            raise ValueError('XP2 Player query native virtual target differs')
    if read(base+p['profile']['lock']['host_global_rva'],8)!=struct.pack('<Q',host_pointer):
        raise ValueError('XP2 Player query HOST lock receiver differs')
    return dict(source_sha256=SOURCE[1],positive_loaded_getters_qualified=False)
