"""Source-qualified XP2 context bootstrap ABI, separate from saved Load.

Internal cleanup runs in the official DLL. This profile describes only its
host boundary and checks actual code/vtables before those calls are entered.
"""
import hashlib
import struct
from .configuration_profiles import _source
from .saved_load_profiles import XP2_CORE_SHA256

SOURCE = ('work/host-extensions/xp2-context-initialization/source-profile-v3.json', '5d386ab8de757623da143f4e3277d62827b35ba5f784f6b31e6a3d28d1a651fe')
BOUNDARY = ('evidence/native-expansion-init-boundary/fc1786d5b274a0e184e2314cbe0b30da8076a6b784f5a09a423496885f2937f6.json',
            'fc1786d5b274a0e184e2314cbe0b30da8076a6b784f5a09a423496885f2937f6')
SLOTS = {0x28:0x5905f0,0x38:0x590660,0x60:0x591750}
GLOBALS = (0xb8aa80,0xb8aa88,0xb8aa90)
EVENTS = (0xc1300ee7,0xa60328c5,0xe23b112d,0xc50d66d6,0xe992f3cd,
          0x6e8a2f93,0x1d355e83,0x2842ce14,0x4d2a6519,0x3182bc8e,
          0x10419f1f,0x51c84cba,0x99e85ec6,0x418bc436,0xc2f385c0)
DECLARATIONS = tuple((event,0xf0548bb7 if i<6 else 0x23739f42,1)
                     for i,event in enumerate(EVENTS)) + ((0xf74afc79,0xf343dc5a,1),)
HOST_SLOTS = (0,8,16,24,0x98,0x138,0x140)
LOGGER_SLOTS = (0x28,0x40)


def _fragments(proof):
    for name,body in proof['bodies'].items():
        raw=bytes.fromhex(body['raw_hex'])
        if (not 0<len(raw)==body['bytes']<=65536
                or hashlib.sha256(raw).hexdigest()!=body['sha256']):
            raise ValueError('XP2 context source body differs: '+name)
        for fragment in body['fragments']:
            data=bytes.fromhex(fragment['raw_hex'])
            if (not 0<len(data)==fragment['length']<=65536
                    or hashlib.sha256(data).hexdigest()!=fragment['sha256']):
                raise ValueError('XP2 context source fragment differs: '+name)
            yield name,int(fragment['start_rva'],16),data


def verify_source():
    proof=_source(SOURCE)
    if (proof['image']['sha256']!=XP2_CORE_SHA256
            or proof['image']['image_base']!='0x180000000'):
        raise ValueError('XP2 context source engine differs')
    if proof['schema']!='civ6rl.xp2-context-initialization.source-profile-v3':
        raise ValueError('XP2 context source schema differs')
    from pathlib import Path
    from .paths import resource_root
    from .resource_resolution import resolve_path
    root=resource_root().resolve()
    for row in (proof['capture_script'],*proof['extractors']):
        path=resolve_path(Path(row['path'])).resolve(strict=True)
        if not path.is_relative_to(root) or hashlib.sha256(path.read_bytes()).hexdigest()!=row['sha256']:
            raise ValueError('XP2 context extractor source changed')
    _source(('work/host-extensions/xp2-context-initialization/source-profile-v1.json',
             'ebd449da3a8652ff090086846819c77f53393716317cd412a951475971246a9a'))
    from .native.native_host import BOOTSTRAP_TYPE_NAMES, HOST_IID
    names=proof['registrar_removals']['ordered_names']
    if tuple(names)!=('Unit','Formation','City::Instance','Trade::Edge','Control::Contract',
            'District::Instance','AI::CityBuild','BehaviorTree','AI::Operation','DynamicModifier'):
        raise ValueError('XP2 context registrar removal order differs')
    if frozenset(names)!=BOOTSTRAP_TYPE_NAMES:
        raise ValueError('XP2 host type registry does not match this cleanup profile')
    iid=proof['host_iid_capture']
    if iid['rva']!='0x9bfba8' or bytes.fromhex(iid['capture']['raw_hex'])!=HOST_IID:
        raise ValueError('XP2 source host identifier differs')
    boundary=_source(BOUNDARY)['rulesets']['xp2']
    if boundary['gamecore_sha256']!=XP2_CORE_SHA256:
        raise ValueError('XP2 context forwarding source differs')
    table=bytes.fromhex(boundary['context_vtable_capture']['raw_hex'])
    for offset,rva in SLOTS.items():
        if struct.unpack_from('<Q',table,offset)[0]!=0x180000000+rva:
            raise ValueError('XP2 context source slot differs')
    observed=tuple((int(e,16),int(f,16),v)for e,f,v in
                   proof['event_registrations']['argument_tuples_edx_r8d_r9d'])
    if observed!=DECLARATIONS or any(type(v)is not int for row in observed for v in row):
        raise ValueError('XP2 ordered event registrations differ')
    fragments=list(_fragments(proof))
    receipt=dict(schema='civ6-host.xp2-context-bootstrap-source.v1',
        core_sha256=XP2_CORE_SHA256,source_path=SOURCE[0],source_sha256=SOURCE[1],
        forwarding_source_sha256=BOUNDARY[1],saved_load_admitted=False)
    return dict(receipt=receipt,proof=proof,slots=dict(SLOTS),globals_rvas=GLOBALS,
        declarations=DECLARATIONS,vtable_bytes=table,host_slots=HOST_SLOTS,
        logger_slots=LOGGER_SLOTS,fragments=fragments,teardown_names=tuple(names),aligned_free_iat_rva=0x9b7680)


def verify_live(base,read,contract):
    if type(base)is not int or not 0<base<(1<<47)-0x1000000 or not callable(read):
        raise ValueError('XP2 context live module/reader differs')
    seen={}
    for name,rva,raw in contract['fragments']:
        if not 0<rva<0x1000000 or (rva in seen and seen[rva]!=raw):
            raise ValueError('XP2 context source fragment overlaps inconsistently')
        if read(base+rva,len(raw))!=raw:
            raise ValueError('XP2 context live source differs: '+name)
        seen[rva]=raw
    for capture in contract['proof']['vtable_captures'].values():
        raw=bytes.fromhex(capture['raw_hex'])
        pointers=struct.unpack('<'+'Q'*(len(raw)//8),raw)
        relocated=struct.pack('<'+'Q'*len(pointers),*(base+p-0x180000000 for p in pointers))
        if read(base+int(capture['rva'],16),len(relocated))!=relocated:
            raise ValueError('XP2 context live vtable differs')
    from .native.native_host import HOST_IID
    if read(base+0x9bfba8,16)!=HOST_IID:
        raise ValueError('XP2 requested host interface identifier differs')
    return contract['receipt']
