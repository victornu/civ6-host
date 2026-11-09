"""Exact XP2 first-turn notification ABI; reuses existing EXE algorithms.

Private captures contain complete selected bodies. This selection proves the
callable interfaces and typed fields, not transitive gameplay or live effects.
"""
import hashlib
import re
from types import MappingProxyType
from .configuration_profiles import XP2_CORE_SHA256, _source
from .a0_family_source import _path, verify_pinned_files, verify_extracted_sources

SOURCE = ('work/host-extensions/xp2-turn-notifications-static/source-profile-v1.json',
          'e6dad3289463a09baecfb8a34a52f3fcaedc03f50f94d06ae11840363de9419b')
FILTER_SOURCE = ('work/host-extensions/xp2-turn-notifications-static/filter-registration-v1.json',
                 'ade0dc9783e39d4d5302f0242f04748ebb17572b8af335e392224e989652040e')

TABLES = {'component': (10206040, {8: 86352, 16: 86544, 24: 86480, 48: 86384}),
 'data': (10553072,
          {8: 5839264, 200: 5846240, 608: 5854800, 776: 5854160, 872: 5857328}),
 'game': (10555112, {8: 5860816, 296: 5864080}),
 'map': (10557080, {8: 5875920, 64: 5878256}),
 'outer': (10551784, {144: 5833120, 168: 5833472, 184: 5833568, 256: 5833024}),
 'parameters': (11268224,
                {0: 10086576, 96: 10089920, 176: 10094736, 304: 10092256}),
 'player': (10558080, {8: 5884096, 24: 5885520, 40: 5885872, 272: 5886736}),
 'plot': (10560656,
          {8: 5902288,
           48: 5902448,
           96: 5903008,
           192: 5903600,
           200: 5904064,
           224: 5904000,
           376: 5902320,
           384: 5902416}),
 'unit': (10561768,
          {16: 5907376,
           40: 5908448,
           80: 5908000,
           88: 5907808,
           136: 5908720,
           184: 5907536}),
 'units': (10560240, {8: 5899152, 16: 5899184})}
SNAPSHOT = {'bytes': 184,
 'free_iat': 10188416,
 'live_pointer_offset': 16,
 'method_rva': 5907536,
 'scalar_offset': 28,
 'string_assign': 10041088,
 'string_empty': 10042160,
 'string_free': 10029296,
 'string_offset': 16,
 'target_rva': 849568}

_VALIDATED_BODY_PROFILES = None
PRIVATE_EVENTS = {'0x1be52206': {'builder': 6276512,
                'fields': {'0xa1e5a149': 3, '0xa1fbc372': 2, '0xd6fcf3e4': 2},
                'private_type': 84,
                'producer': 379840,
                'standard_types': ()},
 '0x66ade3b3': {'builder': 6276336,
                'fields': {'0xa1e5a149': 3, '0xd6fcf3e4': 2},
                'private_type': 87,
                'producer': 301296,
                'standard_types': (5,)}}
EVENT_BUILDERS = {'0x6e7ef927': {'builder': 6271248,
                'fields': {'0x8c468e3c': 0,
                           '0xa1e5a149': 3,
                           '0xf0548bb7': 1024},
                'producer': 3865776},
 '0xa625c726': {'builder': 6269728,
                'fields': {'0x8c468e3c': 0, '0xa1e5a149': 3, '0xd6fcf3e4': 2},
                'producer': 397992},
 '0xb8515a41': {'builder': 6274880,
                'fields': {'0x15808e44': 3,
                           '0x6e3a8f43': 1,
                           '0x8c468e3c': 13,
                           '0xa1e5a149': 3,
                           '0xa1fbc372': 2,
                           '0xd6fcf3e4': 2,
                           '0xf0548bb7': 1024},
                'producer': 3871152},
 '0xc50d66d6': {'builder': 6274496,
                'fields': {'0xa1e5a149': 3,
                           '0xd6fcf3e4': 4,
                           '0xf0548bb7': 1024},
                'producer': 3812141},
 '0xe5b20b82': {'builder': 6269728,
                'fields': {'0x8c468e3c': 0, '0xa1e5a149': 3, '0xd6fcf3e4': 2},
                'producer': 2476394}}


def filter_source():
    p=_source(FILTER_SOURCE)
    if (p['schema']!='civ6-host.xp2-unit-event-filter.static.v1'
            or p['core_sha256']!=XP2_CORE_SHA256 or p['native_execution'] is not False
            or p['process_memory_read'] is not False
            or p['contract']['kind']!=0xC50D66D6 or p['contract']['filter_key']!=0xF0548BB7
            or p['contract']['value']!=1 or p['contract']['host_slot']!=0x98):
        raise ValueError('XP2 source-owned Unit filter changed')
    return p


def bodies(p=None):
    p=_source(SOURCE) if p is None else p
    return (*p['functions'].values(),filter_source()['body'])


def _validate_complete_bodies(p, filter_profile):
    """Check complete bodies once per pair of frozen proof objects."""
    global _VALIDATED_BODY_PROFILES
    key = (p, filter_profile)
    if (type(p) is MappingProxyType and type(filter_profile) is MappingProxyType
            and _VALIDATED_BODY_PROFILES is not None
            and _VALIDATED_BODY_PROFILES[0] is p
            and _VALIDATED_BODY_PROFILES[1] is filter_profile):
        return
    selected_bodies=(*p['functions'].values(),filter_profile['body'])
    starts=set()
    for body in selected_bodies:
        parts=[]
        for f in body['fragments']:
            raw=bytes.fromhex(f['raw_hex']);parts.append(raw)
            if (len(raw)!=f['length'] or hashlib.sha256(raw).hexdigest()!=f['sha256']
                    or ''.join(r['bytes'] for r in f['instructions'])!=raw.hex()):
                raise ValueError('XP2 notification native fragment changed')
            cursor=int(f['start_rva'],16)
            for row in f['instructions']:
                if int(row['rva'],16)!=cursor:raise ValueError('XP2 instruction boundary changed')
                starts.add(cursor);cursor+=len(bytes.fromhex(row['bytes']))
        raw=b''.join(parts)
        if len(raw)!=body['bytes'] or hashlib.sha256(raw).hexdigest()!=body['sha256']:
            raise ValueError('XP2 notification complete native body changed')
    for body in selected_bodies:
        for f in body['fragments']:
            for row in f['instructions']:
                if re.fullmatch(r'j(?!mp)[a-z]+ 0x[0-9a-f]+',row['text']):
                    if int(row['text'].split()[-1],16)-0x180000000 not in starts:
                        raise ValueError('XP2 notification conditional successor missing')
    if type(p) is MappingProxyType and type(filter_profile) is MappingProxyType:
        _VALIDATED_BODY_PROFILES=key


def source():
    p=_source(SOURCE)
    filter_profile=filter_source()
    if (p['schema']!='civ6-host.xp2-turn-notifications.static.v1'
            or p['image']['sha256']!=XP2_CORE_SHA256
            or any(p[k] is not False for k in ('native_execution','process_memory_read','runtime_modified'))
            or p['validation']['function_count']!=186 or p['validation']['total_bytes']!=37453
            or p['validation']['all_bytes_match_installed_image'] is not True
            or p['validation']['explicit_conditional_targets_closed'] is not True
            or tuple(p['validation']['code_relocations'])
            or {n:(r[0],{int(s):v for s,v in r[1].items()}) for n,r in p['tables'].items()}!=TABLES
            or dict(p['unit_snapshot'])!=SNAPSHOT
            or {k:dict(v) for k,v in p['private_events'].items()}!=PRIVATE_EVENTS
            or {k:dict(v) for k,v in p['event_builders'].items()}!=EVENT_BUILDERS
            or p['contracts']['native_effect_admission'] is not False
            or p['contracts']['internal_before_host_dispatch'] is not True):
        raise ValueError('XP2 first-turn notification source contract changed')
    _validate_complete_bodies(p,filter_profile)
    from .native.native_event_1be52206 import verify_source_evidence as verify54
    from .native.native_event_66ade3b3 import verify_source_evidence as verify57
    from .native.native_private_ring_consumer import verify_source_evidence as verify_consumer
    verify54();verify57();verify_consumer()
    return p


def source_dependencies():
    p=source();refs=[dict(path=SOURCE[0],sha256=SOURCE[1]),
                     dict(path=FILTER_SOURCE[0],sha256=FILTER_SOURCE[1]),filter_source()['extractor'],*p['references'],
                     *p['extractors'],*p['source_modules']]
    refs.extend(row['transcript'] for row in p['retained_intervals'])
    refs.extend(row['transcript'] for row in p['base_private_intervals'])
    pins={}
    for r in refs:
        path=str(_path(r['path']))
        if path in pins and pins[path]!=r['sha256']:raise ValueError('Conflicting notification source pins')
        pins[path]=r['sha256']
    verify_pinned_files(pins);verify_extracted_sources(p['source_modules'])
    return pins


def verify_live(base,read):
    if type(base) is not int or base<=0 or not callable(read):
        raise ValueError('XP2 notification source requires exact module/read binding')
    p=source();count=0
    for body in bodies(p):
        for f in body['fragments']:
            raw=bytes.fromhex(f['raw_hex'])
            if read(base+int(f['start_rva'],16),len(raw))!=raw:
                raise ValueError('XP2 notification native code differs')
            count+=1
    for table,slots in TABLES.values():
        for slot,target in slots.items():
            if read(base+table+slot,8)!=(base+target).to_bytes(8,'little'):
                raise ValueError('XP2 notification vtable slot changed')
    return dict(source_sha256=SOURCE[1],core_sha256=XP2_CORE_SHA256,
        verified_fragments=count,native_execution=False,private_receivers_generalized=False)
