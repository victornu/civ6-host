"""Exact XP2 outer+160 route; source evidence never supplies a native result."""
import hashlib
import struct
from .configuration_profiles import XP2_CORE_SHA256,_source

SOURCE=('work/host-extensions/xp2-postload160-static/source-profile-v1.json',
        '1ec775a5195ce5bab1a6a5e7da17737d7bd80763e552c3f2b24200b54bd6eb7e')
ACTIVE_SOURCE=('work/host-extensions/xp2-postload160-static/active-source-profile-v1.json',
               'e5dfc4036f95f41d9dceec76e9448ddf4cdc7517247e153006a50ae3d8010e53')
GLOBALS=dict(current=0xb8aa50,pending=0xb8aa51,requested=0xb8aa52,remaining=0xb8aa4c,
    player_or_target=0xb60d08,stop_limit_or_parameter=0xb60d0c,auxiliary=0xb8aa88)
ROUTE=dict(outer160=0x590780,inner60=0x463a0,game_forward=0x63da70,tail1=0x4abb0,
           tail2=0x42680,transition=0x42310,aux_scope=0x26780)


def source():
    p=_source(SOURCE);c=p['contract'];functions=p['functions']['xp2']
    if (p['schema']!='civ6-host.xp2-postload160.source.v1'
            or p['native_execution'] is not False or p['process_memory_read'] is not False
            or p['core_sha256']!=XP2_CORE_SHA256 or c['core_sha256']!=XP2_CORE_SHA256
            or p['exe_sha256']!='e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
            or c['signature']!='void-like(void *outer_this, uint8 flag)'
            or c['argument']!=1 or c['native_return_ignored'] is not True
            or any(c[k] is not False for k in ('full_load_admitted','public_cache_admitted','post160_runtime_admitted'))
            or dict(c['state_globals'])!=GLOBALS or len(functions)!=17
            or {k:int(functions[k]['rva'],16) for k in ROUTE}!=ROUTE
            or tuple(c[k] for k in ('outer_vtable_rva','outer_slot','outer_target_rva','inner_offset',
                'inner_vtable_rva','inner_slot','inner_target_rva','game_offset'))!=
                (0xa101e8,0x160,0x590780,8,0xa44f70,0x60,0x463a0,0x60)
            or set(p['comparisons'])!=set(ROUTE)
            or any(row['normalized_instructions_equal'] is not True for row in p['comparisons'].values())):
        raise ValueError('XP2 post160 source/ABI differs')
    callback=c['callback']
    if (tuple(callback[k] for k in ('wrapper_rva','auxiliary_slot','raw_kind','category','arguments',
            'host_global_rva','host_owned_slot','host_release_slot','host_acquire_slot'))!=
            (0x26780,0x90,1,2,None,0xb8aa80,0x30,0x38,0x40)
            or callback['own_core_scope_bracketing'] is not True
            or tuple(callback['events'])!=('AutoPlayStart','AutoPlayEnd')
            or (functions['transition']['fragment_count'],functions['transition']['bytes'])!=(7,469)):
        raise ValueError('XP2 post160 callback/complete transition differs')
    for name,b in functions.items():
        parts=[]
        for f in b['fragments']:
            raw=bytes.fromhex(f['raw_hex']);parts.append(raw)
            if (len(raw)!=f['length'] or hashlib.sha256(raw).hexdigest()!=f['sha256']
                    or ''.join(i['bytes'] for i in f['instructions'])!=raw.hex()
                    or any(int(i['va'],16)!=0x180000000+int(i['rva'],16) for i in f['instructions'])):
                raise ValueError('XP2 post160 source fragment differs: '+name)
        raw=b''.join(parts)
        if raw.hex()!=b['raw_hex'] or len(raw)!=b['bytes'] or hashlib.sha256(raw).hexdigest()!=b['sha256']:
            raise ValueError('XP2 post160 complete body differs: '+name)
        if name=='inner60':
            if (b['all_conditional_targets_resolved_in_profile'] is not True
                    or [dict(row) for row in b['conditional_tail_targets']]!=[
                        dict(source_rva='0x463a7',target_rva='0x63da70',profile_body='game_forward')]):
                raise ValueError('XP2 post160 conditional Game tail is not captured')
        elif (b['all_conditional_targets_captured'] is not True
                or b['boundary_method'] not in ('complete-runtime-function-chained-unwind-root-v2',
                                               'complete-reachable-leaf-cfg-v1')):
            raise ValueError('XP2 post160 CFG is incomplete: '+name)
    for ref in p['references']:_source((ref['path'],ref['sha256']))
    return p


def active_source():
    """Pin every captured native branch; unsupported receiver families stay fatal."""
    p=_source(ACTIVE_SOURCE);c=p['contract'];functions=p['functions']
    if (p['schema']!='civ6-host.xp2-postload160-active.source.v1'
            or p['core_sha256']!=XP2_CORE_SHA256 or p['native_execution'] is not False
            or p['process_memory_read'] is not False or len(functions)!=57
            or sum(b['bytes'] for b in functions.values())!=13200
            or c['native_player_transition_preserved'] is not True
            or c['host_does_not_write_transition_state'] is not True
            or c['pending_zero_only_gate'] is not False
            or c['native_active_player_qualification'] is not False
            or set(c['host_boundaries'])!={'0x130','0xa0','0xe8','0xf0'}
            or tuple(c['config_native_slots'])!=(0x58,0x68,0x130,0x138)
            or len(c['events'])!=15
            or sum(row['common_record_types'] is None for row in c['events'])!=13):
        raise ValueError('XP2 post160 active-branch source scope differs')
    for name,b in functions.items():
        parts=[]
        for f in b['fragments']:
            raw=bytes.fromhex(f['raw_hex']);parts.append(raw)
            if (len(raw)!=f['length'] or hashlib.sha256(raw).hexdigest()!=f['sha256']
                    or ''.join(i['bytes'] for i in f['instructions'])!=raw.hex()):
                raise ValueError('XP2 post160 active source fragment differs: '+name)
        raw=b''.join(parts)
        if raw.hex()!=b['raw_hex'] or len(raw)!=b['bytes'] or hashlib.sha256(raw).hexdigest()!=b['sha256']:
            raise ValueError('XP2 post160 active complete body differs: '+name)
        if name=='current_player':
            if (b['all_conditional_targets_resolved_in_profile'] is not True
                    or [dict(row) for row in b['conditional_tail_targets']]!=[
                        dict(source_rva='0x44dfa',target_rva='0x63d170',profile_body='game_current_player')]):
                raise ValueError('XP2 post160 active conditional tail is not captured')
        elif (b['all_conditional_targets_captured'] is not True
                or b['boundary_method'] not in ('complete-runtime-function-chained-unwind-root-v2',
                                               'complete-reachable-leaf-cfg-v1')):
            raise ValueError('XP2 post160 active CFG is incomplete: '+name)
    for ref in p['references']:_source((ref['path'],ref['sha256']))
    return p


def source_dependencies():
    from .a0_family_source import _path,verify_pinned_files
    p=source();refs=[dict(path=SOURCE[0],sha256=SOURCE[1]),*p['references'],
        *(p[k] for k in ('generator','boundary_helper','extractor')),
        p['retained_interval']['events'],p['retained_interval']['qualification']]
    active=active_source()
    refs.extend([dict(path=ACTIVE_SOURCE[0],sha256=ACTIVE_SOURCE[1]),*active['references'],
        *(active[k] for k in ('generator','boundary_helper','extractor'))])
    pins={str(_path(ref['path'])):ref['sha256'] for ref in refs};verify_pinned_files(pins)
    return pins


def verify_live(base,read,proof,*,core_sha256):
    if (core_sha256!=XP2_CORE_SHA256 or type(base) is not int or base<65536 or base%65536
            or base>(1<<47)-0x10000000 or not callable(read) or proof!=source()):
        raise ValueError('Invalid XP2 post160 source/image/reader')
    bodies=dict(proof['functions']['xp2']);bodies.update(active_source()['functions'])
    for name,b in bodies.items():
        for f in b['fragments']:
            for i in f['instructions']:
                raw=bytes.fromhex(i['bytes']);rva=int(i['rva'],16)
                if read(base+rva,len(raw))!=raw:raise ValueError('XP2 post160 instruction differs: '+name)
    for row in proof['tables']['xp2'].values():
        if read(base+row['vtable_rva']+row['slot'],8)!=struct.pack('<Q',base+row['target_rva']):
            raise ValueError('XP2 post160 virtual dispatch target differs')
    for address,literal in proof['literals'].items():
        raw=read(base+int(address,16)-0x180000000,literal['bytes'])
        if type(raw) is not bytes or len(raw)!=literal['bytes'] or hashlib.sha256(raw).hexdigest()!=literal['sha256']:
            raise ValueError('XP2 post160 event literal differs')
