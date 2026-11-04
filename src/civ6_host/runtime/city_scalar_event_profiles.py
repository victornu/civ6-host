"""Canonical expansion city/D6 aliases of the same EXE codec and receivers."""
from dataclasses import dataclass
from types import MappingProxyType
from .configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256, _source

SOURCE=('work/host-extensions/xp1-event0242-static/city-scalar-family-source-v1.json',
        '2e98e34dcebeb73a9c14476cc00ae960ad6cbf794d4c0688094fd1521bebf020')
RECEIVERS=('work/host-extensions/xp1-event0242-static/city-scalar-receivers-v1.json',
           'ad34427f90471b16ce2b2650efa745f698fd104153ac39c0c16cf6de4ebee97d')
CONTRACT=('work/host-extensions/xp1-event0242-static/city-scalar-contract-v2.json',
          '4c3c2c82733b4f58b904f552b9fd8269da85d373697bb436855a0d47e3c84439')
XP2_SOURCE=('work/host-extensions/xp2-city-scalar-static/source-profile-v1.json',
            'f230c9af05e61c8526ad90aea11531c50cc9801cc3bbf823f90bc48d9131f37e')
NEW_KINDS=MappingProxyType({0x0242e68c:0xf1,0x312df0f6:0xf2,0xcf61eb26:0xf3})
_EXE='e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'


@dataclass(frozen=True)
class CityScalarRecordProfile:
    kind:int
    record_type:int
    record_size:int
    core_sha256:str
    source_sha256:str
    receiver_sha256:str
    contract_sha256:str


_PROFILES={}
_RECEIVER_ROWS=None


def source(*,core_sha256=XP1_CORE_SHA256):
    if core_sha256==XP2_CORE_SHA256:
        p=_source(XP2_SOURCE)
        shared=source()
        if (p['schema']!='civ6_host.xp2_city_scalar_shared_exe.static.v1'
                or p['core_sha256']!=XP2_CORE_SHA256 or p['exe_sha256']!=_EXE
                or {int(k):tuple(v) for k,v in p['kind_to_record_types'].items()}!=
                    {k:(v,) for k,v in NEW_KINDS.items()}
                or p['normalization']!=shared['normalization']
                or p['core_query_contract']!=dict(native_queries=False,getters=(),vtables=(),
                    facade_dependencies=(),producer_reachability_qualified=False)
                or p['validation']!=dict(native_execution=False,process_memory_read=False,
                    installed_exe_bytes_verified=True,complete_retained_body_count=23,
                    complete_retained_body_bytes=12705,new_kinds_only=True,source_profiles_unchanged=True)):
            raise ValueError('XP2 city scalar shared EXE contract changed')
        expected=[{key:r[key] for key in p['callbacks'][0]} for r in shared['candidates']
                  if r['record_type'] in NEW_KINDS.values()]
        if list(p['callbacks'])!=expected:
            raise ValueError('XP2 city scalar callback/writer membership differs')
        return p
    if core_sha256!=XP1_CORE_SHA256:
        raise ValueError('Unknown city scalar engine')
    p=_source(SOURCE)
    expected={0x8d005711:0x5b,0x51c84cba:0x67,**NEW_KINDS}
    if (p['schema']!='civ6_host.xp1_city_scalar_family.static.v1'
            or p['images']['xp1']['sha256']!=XP1_CORE_SHA256
            or p['images']['exe']['sha256']!=_EXE or p['native_execution'] is not False
            or {int(r['event_kind'],16):r['record_type'] for r in p['candidates']}!=expected
            or any(r['record_size']!=112 or not r['direct_typed_descriptor_builder_calls']
                   for r in p['candidates'])
            or p['normalization']['callback_canonical_sha256']!=
                'dd985ade6bd4281596a1e62ff7c13653955691c946ed90b9a012b338e7367f51'
            or p['normalization']['writer_canonical_sha256']!=
                '427cfeaed44af32951637ac0ef4f0376c4d04736fd0f337d869c4ed0bd3c16db'):
        raise ValueError('City scalar callback/writer equivalence source changed')
    return p


def _load(core_sha256=XP1_CORE_SHA256):
    global _PROFILES,_RECEIVER_ROWS
    if core_sha256 in _PROFILES:return
    source(core_sha256=core_sha256);contract(core_sha256=core_sha256);p=_source(RECEIVERS)
    if (p['schema']!='civ6_host.city_scalar_receivers.static.v1'
            or p['image_sha256']!=_EXE
            or p['validation']!=dict(native_execution=False,process_memory_read=False,
                exact_handler_effect_sequences=True,empty_setup_stores_verified=True,
                receiver_count=3,installed_rows_changed=False)
            or {int(k) for k in p['receivers']}!=set(NEW_KINDS.values())):
        raise ValueError('City scalar empty receiver source changed')
    rows={}
    for key,item in p['receivers'].items():
        kind=int(key);r=item['receiver']
        if r['record_type']!=kind or r['record_size']!=112:
            raise ValueError('City scalar receiver size/type differs')
        rows[kind]=MappingProxyType(dict(event_name=r['event_name'],handler_va=r['handler_va'],
            handler_body_sha256=r['handler_body_sha256'],record_sizes=frozenset({112})))
    selected=SOURCE if core_sha256==XP1_CORE_SHA256 else XP2_SOURCE
    selected_contract=CONTRACT if core_sha256==XP1_CORE_SHA256 else XP2_SOURCE
    profiles={kind:CityScalarRecordProfile(kind,record_type,112,core_sha256,selected[1],RECEIVERS[1],selected_contract[1])
              for kind,record_type in NEW_KINDS.items()}
    _RECEIVER_ROWS=MappingProxyType(rows)
    _PROFILES[core_sha256]=MappingProxyType(profiles)


def record_profile(kind,core_sha256=XP1_CORE_SHA256):
    """Explicit expansion aliases; Base codecs keep their existing default path."""
    if core_sha256 not in (XP1_CORE_SHA256,XP2_CORE_SHA256) or type(kind) is not int or kind not in NEW_KINDS:
        raise ValueError('No qualified city scalar alias for this engine/kind')
    _load(core_sha256)
    return _PROFILES[core_sha256][kind]


def require_record_profile(profile):
    if (type(profile) is not CityScalarRecordProfile
            or record_profile(profile.kind,profile.core_sha256) is not profile):
        raise ValueError('Canonical city scalar record profile required')
    return profile


def receiver_row(record_type):
    """Lazy pure source resolver: no mutation of native_deferred_empty_profile._ROWS."""
    if type(record_type) is not int or record_type not in NEW_KINDS.values():
        raise ValueError('No city scalar receiver for this type')
    _load()
    return _RECEIVER_ROWS[record_type]


def contract(*,core_sha256=XP1_CORE_SHA256):
    if core_sha256==XP2_CORE_SHA256:
        p=source(core_sha256=core_sha256)
        common=contract()['typed_contract']
        if ({k:v for k,v in p['typed_contract'].items() if k!='native_processing'}!=
                {k:v for k,v in common.items() if k!='native_processing'}):
            raise ValueError('XP2 city scalar typed/counter contract differs from shared EXE')
        return p
    if core_sha256!=XP1_CORE_SHA256:
        raise ValueError('Unknown city scalar engine')
    p=_source(CONTRACT);c=p['typed_contract']
    if (p['schema']!='civ6_host.xp1_city_scalar_contract.static.v2'
            or {int(k):tuple(v) for k,v in p['new_admission_kind_to_record_types'].items()}!=
                {k:(v,) for k,v in NEW_KINDS.items()}
            or c['record']!=dict(size=112,header_sequence_offset=8,payload_offset=80,metadata_flag=0)
            or c['counters']!='Callback/writer source does not read N or M. Preserve both; record metadata flag remains0.'
            or p['validation']!=dict(complete_source_bodies_verified=26,instruction_guard_count=41,
                candidate_set_exact=True,new_kinds_only=True,native_execution=False,installed_changes=False)):
        raise ValueError('City scalar typed/counter contract changed')
    return p


def require_notification_scope(n,m,*,core_sha256=XP1_CORE_SHA256):
    """Counter-neutral source branch; caller verifies both counters unchanged."""
    contract(core_sha256=core_sha256)
    if any(type(value) is not int or not 0<=value<=0xffffffff for value in (n,m)):
        raise ValueError('City scalar notification counters must be exact uint32')
    return n,m


def source_dependencies(*,core_sha256=XP1_CORE_SHA256):
    from .a0_family_source import _path,verify_pinned_files
    selected=source(core_sha256=core_sha256)
    p=source();c=contract()
    refs=[dict(path=SOURCE[0],sha256=SOURCE[1]),dict(path=RECEIVERS[0],sha256=RECEIVERS[1]),
          dict(path=CONTRACT[0],sha256=CONTRACT[1]),
          *p['references'],*p['source_modules'],*c['references'],*c['source_modules']]
    if core_sha256==XP2_CORE_SHA256:
        refs.extend([dict(path=XP2_SOURCE[0],sha256=XP2_SOURCE[1]),
                     *selected['references'],*selected['source_modules']])
    pins={}
    for ref in refs:
        path=str(_path(ref['path']))
        if path in pins and pins[path]!=ref['sha256']:
            raise ValueError('Conflicting city scalar proof source')
        pins[path]=ref['sha256']
    verify_pinned_files(pins);_load(core_sha256)
    return pins
