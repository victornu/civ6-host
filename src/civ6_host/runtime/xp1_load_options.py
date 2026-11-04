"""Captured Performance options for the existing XP1 saved-Load service owner.

The values come from the official startup log. Its process association is
temporal, not atomic; the log has no PID. Automatic hardware detection is not
implemented and raw AppOptions=-1 values are never passed to a derivation stub.
"""
import ctypes as C
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import re
import struct

from .configuration_profiles import XP1_CORE_SHA256, configuration_abi, _source, _body
from .paths import resource_root
from .resource_resolution import resolve_path
from .xp1_saved_load import REFERENCE
from .xp1_load_capability import _owner, _candidate_spec
from .saved_load_profiles import XP2_CORE_SHA256
from .native import native_configuration_finalization as setup

SOURCE=('work/host-extensions/xp1-options-static/options-source-and-input.json',
        '3d38e7af05b2d0c4fd0f830a21203ab0284260996012c1a0b44335806114d41a')
OWNER_SOURCE=('work/native-xp1-options896/capture896v2.json',
              '8bc505c5bd4fd4007f0e4f13c13876a0f34771f25198316182a9b973e37d809a')
DOMAIN=0xfbb4e6a9
KEYS=(0x7ec3df64,0xc181eb6e,0xe09781a7)
EXE_SHA='e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
INPUTS=('MaxJobThreads','MaxGameCoreThreads','GameCoreReserveThreads',
        'MaxGameCoreUnitMovementThreads','MaxGameCoreTradeRouteThreads')
_QUARANTINE=[]


def source_profile(core_sha256=XP1_CORE_SHA256):
    if core_sha256 == XP2_CORE_SHA256:
        from .xp2_load_options_capability_profile import performance_profile
        return performance_profile()
    if core_sha256 != XP1_CORE_SHA256:
        raise ValueError('Unknown Performance source profile')
    p,q=_source(SOURCE),_source(OWNER_SOURCE)
    abi=configuration_abi(XP1_CORE_SHA256)
    expected={'domain':DOMAIN,'keys':KEYS,'map_vtable_rva':abi.vtable_rva,
              'constructor_rva':abi.constructor_rva,'destructor_rva':abi.destructor_rva,
              'storage_size':88,'host_slot':0x158,'host_global_rva':0x9f2640}
    if (p['schema']!='civ6_host.xp1_load_options.static_and_recorded_input.v1'
            or p['native_execution'] is not False
            or p['images']['xp1']['sha256']!=XP1_CORE_SHA256 or p['images']['exe']['sha256']!=EXE_SHA
            or (p['source_reuse']['path'],p['source_reuse']['sha256'])!=OWNER_SOURCE
            or q['schema']!='civ6rl.native_xp1_options896.source.v1'
            or q['xp1_sha256']!=XP1_CORE_SHA256 or q['exe_sha256']!=EXE_SHA
            or q['native_execution'] is not False or q['automatic_hardware_detection_supported'] is not False
            or any(q['contract'][key]!=value for key,value in expected.items())
            or q['contract']['slots']!={'0x58':abi.lookup_rva,'0x68':0x845600,'0x130':abi.uint_setter_rva}
            or p['abi']['signature']!='borrowed ParameterMap*(host*, uint32 domain)'
            or p['abi']['provider_getter']!='slot0x68 borrowed Variant24*(ParameterMap*,uint32 key)'
            or p['abi']['domain']!=hex(DOMAIN)
            or p['exe_host_bridge']['slot']!='0x158'
            or p['exe_host_bridge']['body']['raw_sha256']!='edbcfb7d05589c90910f3c0cd0e33b365c801fecd3c6408155881bd27f2d0bd2'):
        raise ValueError('Recorded XP1 options source/owner ABI differs')
    for ref in q['parents'].values():_source((ref['path'],ref['sha256']))
    for body in (*p['consumers'].values(),q['xp1_dispatch'],q['xp1_numeric_setter'],
                 *q['xp1_owner_bodies'].values(),*q['xp1_getter_bodies'].values()):_body(body)
    return p,q


def source_dependencies(core_sha256=XP1_CORE_SHA256):
    if core_sha256 == XP2_CORE_SHA256:
        from .xp2_load_options_capability_profile import source_dependencies as selected_dependencies
        return selected_dependencies()
    p,q=source_profile(core_sha256)
    refs=[SOURCE,OWNER_SOURCE,REFERENCE]
    refs.extend((r['path'],r['sha256']) for r in q['parents'].values())
    parent=Path(SOURCE[0]).parent
    refs.extend((str(parent/r['snapshot']),r['sha256']) for r in p['official_inputs'].values())
    return {str(resolve_path(resource_root()/path).resolve()):digest for path,digest in refs}


def _snapshot(p,name):
    row=p['official_inputs'][name]
    path=resolve_path(resource_root()/Path(SOURCE[0]).parent/row['snapshot'])
    if row['snapshot']!=name or path.stat().st_size!=row['bytes'] or not 0<row['bytes']<16384:
        raise ValueError('Recorded options input ownership/size differs')
    raw=path.read_bytes()
    if len(raw)!=row['bytes'] or sha256(raw).hexdigest()!=row['sha256']:
        raise ValueError('Recorded options input bytes differ')
    return raw.decode('utf-8-sig').replace('\r\n','\n')


@dataclass(frozen=True)
class _RecordedOptions:
    backend: object
    raw_settings: tuple
    values: tuple
    proof: object
    dependencies: tuple
    kind: str = 'recorded_native_values'


@dataclass(frozen=True)
class _ExplicitOptions:
    backend: object
    raw_settings: tuple
    values: tuple
    proof: object
    dependencies: tuple
    kind: str = 'explicit_host_configuration'


def explicit_input(backend):
    from .native.native_xp1_performance import derive
    from .xp2_load_options_capability_profile import SETTINGS, verify_dependency
    _owner(backend,backend.owner,backend.captured_bundle)
    if _candidate_spec(backend)[0] != XP2_CORE_SHA256:
        raise ValueError('Explicit XP2 options require their selected candidate')
    p,_ = source_profile(XP2_CORE_SHA256)
    dependencies=tuple(sorted(source_dependencies(XP2_CORE_SHA256).items()))
    for path,digest in dependencies:verify_dependency(path,digest)
    derived=derive(SETTINGS)
    if derived['values'] != dict.fromkeys(KEYS,1):
        raise ValueError('Explicit XP2 Performance derivation changed')
    return _ExplicitOptions(backend,tuple(SETTINGS.items()),tuple((key,derived['values'][key]) for key in KEYS),p,dependencies)


def recorded_input(backend):
    _owner(backend,backend.owner,backend.captured_bundle)
    p,_=source_profile();capture=_source(REFERENCE);association=p['capture_association']
    if ((association['manifest']['path'],association['manifest']['sha256'])!=REFERENCE
            or association['process_identity']!=capture['preflight']['process']['identity']
            or association['matches_creation_second'] is not True
            or association['atomic_performance_map_capture'] is not False
            or association['association_kind']!='same second / installed EXE version / bounded single startup log; log itself has no PID'
            or association['creation_local'][:19].replace('T',' ')!=association['startup_first_timestamp_local']):
        raise ValueError('Recorded options lack their explicit captured-process temporal join')
    startup=_snapshot(p,'Startup-official-20261030.log')
    options=_snapshot(p,'AppOptions-official-current.txt')
    if (startup.splitlines()[0]!=f"[{association['startup_first_timestamp_local']}]\tCiv6App::InitialInit start."
            or len(re.findall(r'Civ6App::InitialInit start\.',startup))!=1):
        raise ValueError('Recorded Startup is not the associated bounded startup log')
    settings=[]
    for name in INPUTS:
        rows=re.findall(r'^'+re.escape(name)+r'\s+(-?\d+)\s*$',options,re.MULTILINE)
        if rows!=['-1'] or p['raw_current_options'][name]!=-1:
            raise ValueError('AppOptions provenance differs from recorded automatic inputs')
        settings.append((name,-1))
    values=[]
    if set(p['native_recorded_derived_values'])!={hex(key) for key in KEYS}:
        raise ValueError('Recorded Performance key group differs')
    for key in KEYS:
        row=p['native_recorded_derived_values'][hex(key)]
        matches=re.findall(r'^\[([^\]]+)\]\t'+re.escape(row['label'])+r' = (\d+)\.$',startup,re.MULTILINE)
        if matches!=[(row['printed_at_local'],'5')] or type(row['value']) is not int or row['value']!=5:
            raise ValueError('Recorded native Performance value differs')
        values.append((key,row['value']))
    return _RecordedOptions(backend,tuple(settings),tuple(values),p,tuple(sorted(source_dependencies().items())))


class _LoadOptionsBorrower:
    def __init__(self,backend):
        self.backend=backend;self.base=backend.core._handle;self.runtime=backend.runtime;self.read=backend.runtime.read
    def _check(self):
        b=self.backend
        if b.destroyed:
            from .xp1_loaded_lifetime import require_lifetime
            require_lifetime(getattr(b,'_loaded_lifetime',None),b).check_options_cleanup(self)
            return
        b.check_thread();_owner(b,b.owner,b.captured_bundle)
        if (b.busy is not True or self.base!=b.core._handle or self.runtime is not b.runtime
                or self.read!=b.runtime.read):
            raise ValueError('Recorded options native borrower owner changed')
    def _invoke(self,rva,result_type,arg_types,*arguments):
        self._check()
        if self.backend.destroyed:
            from .xp1_loaded_lifetime import require_lifetime
            require_lifetime(self.backend._loaded_lifetime,self.backend).check_options_cleanup(self,rva)
        return setup._invoke(None,self.base+rva,result_type,arguments[0],arg_types[1:],*arguments[1:])


def recorded_values(receipt,borrower):
    if type(receipt) not in (_RecordedOptions,_ExplicitOptions) or type(borrower) is not _LoadOptionsBorrower or receipt.backend is not borrower.backend:
        raise ValueError('Recorded options require their exact native borrower/input receipt')
    borrower._check()
    core=_candidate_spec(borrower.backend)[0]
    expected=1 if type(receipt) is _ExplicitOptions else 5
    if ((type(receipt) is _ExplicitOptions) != (core == XP2_CORE_SHA256)
            or tuple(receipt.values)!=tuple((key,expected) for key in KEYS)):
        raise ValueError('Recorded native options values changed')
    return dict(receipt.values)


class _OptionsService:
    def _check(self):
        b=self.backend;self.borrower._check();self.provider._guard()
        if (getattr(b.host,'_saved_load_performance_options',None) is not self
                or self.provider.bound is not True or self.provider.base!=b.core._handle
                or setup._qword(b.runtime.read,b.core._handle+self.host_global_rva)!=b.host.pointer):
            raise ValueError('Recorded options service owner/host changed')

    def get_domain(self,this,domain):
        self.backend.host._check(this);self._check()
        if type(domain) is not int or domain!=DOMAIN:
            raise ValueError('Unsupported recorded options domain')
        self.provider.snapshot();self.domain_calls+=1
        return C.addressof(self.object)

    def get_value(self,this,key):
        self._check()
        if this!=C.addressof(self.object) or type(key) is not int or key not in KEYS:
            raise ValueError('Unsupported recorded Performance receiver/key')
        node=self.borrower._invoke(getattr(self,'getter_rva',0x845600),C.c_void_p,(C.c_void_p,C.c_uint32),self.provider.pointer,key)
        if not node:raise ValueError('Recorded Performance native getter returned NULL')
        raw=setup._read(self.borrower.read,node,24)
        if (struct.unpack_from('<I',raw)[0]!=2 or struct.unpack_from('<Q',raw,16)[0]!=0
                or struct.unpack_from('<I',raw,8)[0]!=dict(self.input.values)[key]):
            raise ValueError('Recorded Performance native value changed')
        self.value_calls+=1
        if key not in self.observed_keys:
            self.observed_keys.add(key)
            self.backend.host.emit('saved_load_performance_option_consumed',
                key=hex(key), value=dict(self.input.values)[key],
                source_sha256=getattr(self,'source_reference',SOURCE)[1], native_borrowed_value=True)
        return node


def install_saved_load_options(backend):
    from .native.native_host import DiagnosticHost
    from .native.native_xp1_performance import PerformanceDomain,UnsafeOwnership
    backend.check_thread();host=backend.host
    _owner(backend,backend.owner,backend.captured_bundle)
    if (type(host) is not DiagnosticHost or backend.stage!='prepared' or backend.prefix is not None
            or backend.busy is not True or hasattr(host,'_saved_load_performance_options')):
        raise ValueError('Recorded options require the existing prepared saved-Load candidate')
    address,prior=host._slot_bindings[C.addressof(host.vtable),0x158]
    if address!=host.vtable[0x158//8] or getattr(prior,'_native_unavailable',None)!=('host',0x158):
        raise ValueError('Recorded options callback has an unknown prior owner')
    core,reference,*_=_candidate_spec(backend)
    receipt=explicit_input(backend) if core == XP2_CORE_SHA256 else recorded_input(backend)
    p=receipt.proof
    _,owner_proof=source_profile(core)
    for body in p['consumers'].values():
        for fragment in _body(body)['fragments']:
            for row in fragment['instructions']:
                expected=bytes.fromhex(row['bytes'])
                if backend.runtime.read(backend.core._handle+int(row['va'],16)-0x180000000,len(expected))!=expected:
                    raise ValueError('Recorded options live consumer changed')
    service=_OptionsService();service.backend=backend;service.input=receipt
    service.host_global_rva=owner_proof['contract']['host_global_rva']
    service.getter_rva=owner_proof['contract']['slots']['0x68']
    service.source_reference=tuple(p.get('source_reference',SOURCE))
    service.borrower=_LoadOptionsBorrower(backend);service.domain_calls=service.value_calls=0
    service.observed_keys=set()
    service.provider=None
    try:
        service.provider=PerformanceDomain(service.borrower,root=resource_root(),recorded_input=receipt)
        # Interface-only receiver: known consumers dereference only its vtable
        # and call +68. Values are borrowed from the real native owned map.
        service.vtable=(C.c_void_p*65)();service.object=(C.c_void_p*1)(C.addressof(service.vtable))
        host._saved_load_performance_options=service
        service.provider.bound=True
        for index in range(len(service.vtable)):
            host._bind(service.vtable,index*8,None,[C.c_void_p],host._unsupported('captured Performance interface',index*8))
        host._bind(service.vtable,0x68,C.c_void_p,[C.c_void_p,C.c_uint32],service.get_value)
        host._bind(host.vtable,0x158,C.c_void_p,[C.c_void_p,C.c_uint32],service.get_domain)
        backend._xp1_service_roots.append(service)
    except BaseException as error:
        if service.provider is not None:service.provider.poisoned=True
        _QUARANTINE.append(service)
        raise UnsafeOwnership('Recorded options binding uncertain; terminate process') from error
    provenance=(dict(explicit_host_configuration=True,input_settings=dict(receipt.raw_settings),
                    captured_gameplay_state=False,historical_thread_count_reproduced=False,
                    startup_log_sha256=None,association_kind=None)
                if core == XP2_CORE_SHA256 else
                dict(startup_log_sha256=p['official_inputs']['Startup-official-20261030.log']['sha256'],
                    association_kind=p['capture_association']['association_kind']))
    host.emit('saved_load_performance_options_bound',source_sha256=service.source_reference[1],
              owner_source_sha256=service.source_reference[1] if core == XP2_CORE_SHA256 else OWNER_SOURCE[1],
              native_readbacks=service.provider.snapshot(),captured_bundle_sha256=reference[1],**provenance,
              atomic_performance_map_capture=False,log_contains_pid=False,automatic_hardware_detection_reproduced=False,
              native_map_owner=True,unknown_domains_and_keys_refused=True,public_session_admitted=False)
    return service
