"""Selected source/ABI for shared research, civics and scalar player requests.

The native managers and operation dispatcher keep all legality and rule logic.
This profile does not admit an XP1 action before its native grouped validation.
"""
from dataclasses import dataclass
from types import MappingProxyType
import hashlib
import struct

from .configuration_profiles import _source, BASE_CORE_SHA256, XP1_CORE_SHA256
from .paths import resource_root
from .resource_resolution import resolve_path

from .configuration_profiles import XP2_CORE_SHA256

SOURCE=('work/host-extensions/xp1-research-static/research-source-v2.json',
        '3bac7b55a9fe88d71e3614606877f146f2caa78a3ef4b5792f03195d9573c088')
BASE_REQUEST_SOURCE='e04deeffcd31ca8e0125ca595d998ad575acd149ecad00b0605820ee27a32468'
CALLBACKS={'Player.GetTechs':0x5c5bf0,'Player.GetCulture':0x5c52c0,
           'Techs.CanResearch':0x5d0ef0,'Techs.GetResearchingTech':0x5d12f0,
           'Culture.CanProgress':0x5c7e20,'Culture.GetProgressingCivic':0x5c8c10}
ENTRIES={'parameter_ctor':0x84b420,'parameter_dtor':0x84b4a0,
         'set_u32':0x84c9b0,'lookup':0x84c240,'reason_ctor':0x844460,
         'reason_dtor':0x844580,'can_start':0x4bca60,'request':0x4be350}
ENUMS={'RESEARCH':1848062833,'PROGRESS_CIVIC':2678441256,
       'PARAM_TECH_TYPE':347601064,'PARAM_CIVIC_TYPE':2786034420,
       'PARAM_INSERT_MODE':2888817673,'VALUE_EXCLUSIVE':2550048198}


def source_reference(core_sha256=XP1_CORE_SHA256):
    if core_sha256==XP1_CORE_SHA256:return SOURCE
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_initial_choice_source import SOURCE as selected
        return selected
    raise ValueError('Unknown initial-choice source engine')


def verify_source(core_sha256=XP1_CORE_SHA256):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_initial_choice_source import source
        return source('research')
    if core_sha256!=XP1_CORE_SHA256:
        raise ValueError('Unknown research source profile')
    p=_source(SOURCE)
    if (p['schema']!='civ6_host.xp1_research.static.v2'
            or p['image']['sha256']!=core_sha256
            or p['native_execution'] is not False or p['process_memory_read'] is not False
            or p['validation']['all_captured_instruction_bytes_match_image'] is not True
            or p['validation']['exact_named_registrations']!=6
            or p['validation']['official_enum_pairs']!=6
            or dict(p['vtables'])!={'outer':0x8a8df0,'parameters':0x93fe28,'reasons':0x93f590}
            or {k:v['callback_rva'] for k,v in p['bindings'].items()}!=CALLBACKS
            or {k:p['entries'][k] for k in ENTRIES}!=ENTRIES
            or {k:v['u32_value'] for k,v in p['enums'].items()}!=ENUMS):
        raise ValueError('XP1 research source contract changed')
    for row in p['chooser_sources'].values():
        path=resolve_path(resource_root()/row['path'])
        if hashlib.sha256(path.read_bytes()).hexdigest()!=row['sha256']:
            raise ValueError('Official research/civic chooser changed')
    return p


def source_dependencies(core_sha256=XP1_CORE_SHA256, *, execution_image=None):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_initial_choice_source import source_dependencies as selected
        return selected('research', execution_image=execution_image)
    if core_sha256!=XP1_CORE_SHA256:raise ValueError("Unknown research source engine")
    if execution_image is not None:
        raise ValueError('XP1 research source does not accept an XP2 execution image')
    from .xp1_status_profiles import source_dependencies as status_dependencies
    proof=verify_source();pins=dict(status_dependencies())
    for row in ({'path':SOURCE[0],'sha256':SOURCE[1]},*proof['references']):
        path=resolve_path(resource_root()/row['path']).resolve()
        with path.open('rb') as stream:
            actual=hashlib.file_digest(stream,'sha256').hexdigest()
        if actual!=row['sha256']:raise ValueError('Research source dependency changed: '+str(path))
        key=str(path)
        if key in pins and pins[key]!=actual:raise ValueError('Research source pin conflict')
        pins[key]=actual
    return pins


def verify_live(core_base,read,core_sha256=XP1_CORE_SHA256,*,execution_image=None):
    """Check relocated code bytes and public slots, without calling the engine."""
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_initial_choice_source import verify_live as selected
        return selected(core_base,read,'research',execution_image=execution_image)
    if execution_image is not None:raise ValueError('Selected research image requires the XP2 source ABI')
    if core_sha256!=XP1_CORE_SHA256:raise ValueError("Unknown research live source engine")
    if type(core_base) is not int or core_base<=0 or not callable(read):
        raise ValueError('Live research source requires exact module/read binding')
    p=verify_source()
    for body in p['functions'].values():
        for fragment in body.get('fragments') or (body,):
            instructions=fragment['instructions']
            start=None;expected=bytearray()
            def check():
                # The shared operation primitive's OS-checked reader caps one
                # copy at 6784 bytes. Verify the entire body in smaller copies;
                # never weaken its guard or skip a long function tail.
                if start is not None:
                    for offset in range(0,len(expected),4096):
                        chunk=expected[offset:offset+4096]
                        if bytes(read(core_base+start+offset,len(chunk)))!=bytes(chunk):
                            raise ValueError('XP1 research native body differs')
            for row in instructions:
                rva=int(row['va'],16)-0x180000000;raw=bytes.fromhex(row['bytes'])
                if not raw or not 0<=rva<0x1000000:raise ValueError('Invalid research instruction')
                if start is None:start=rva
                elif rva!=start+len(expected):check();start=rva;expected=bytearray()
                expected.extend(raw)
            check()
    for table,offset,target in ((0x8a8df0,0x218,ENTRIES['request']),
            (0x8a8df0,0x220,ENTRIES['can_start']),
            (0x93fe28,0x60,ENTRIES['lookup']),(0x93fe28,0x130,ENTRIES['set_u32'])):
        if bytes(read(core_base+table+offset,8))!=struct.pack('<Q',core_base+target):
            raise ValueError('XP1 player-operation native slot differs')
    return {'core_sha256':XP1_CORE_SHA256,'source_sha256':SOURCE[1],
            'native_execution':False,'gameplay_effect_verified':False}


@dataclass(frozen=True)
class PlayerOperationABI:
    core_sha256:str
    outer:int
    parameters:int
    reasons:int
    methods:object
    source_sha256:str

    @property
    def slots(self):
        return ((self.outer,0x218,self.methods['request'][0]),
                (self.outer,0x220,self.methods['can_start'][0]),
                (self.parameters,0x130,self.methods['set_u32'][0]),
                (self.parameters,0x60,self.methods['lookup'][0]))


def player_operation_abi(core_sha256,base_methods):
    # ABI argument types remain the shared source contract, not a second helper.
    expected={'parameter_ctor':0x74b870,'parameter_dtor':0x74b8f0,
        'set_u32':0x74ce10,'lookup':0x74c5f0,'reason_ctor':0x744b80,
        'reason_dtor':0x744ca0,'can_start':0x42d960,'request':0x42f250}
    if {k:v[0] for k,v in base_methods.items()}!=expected:
        raise ValueError('Shared player-operation ABI methods changed')
    if core_sha256==BASE_CORE_SHA256:
        return PlayerOperationABI(core_sha256,0x79e020,0x81d838,0x81cfa0,
            MappingProxyType(dict(base_methods)),BASE_REQUEST_SOURCE)
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_initial_choice_source import ENTRIES as entries,VTABLES,SOURCE as selected
        verify_source(core_sha256)
        methods={k:(entries[k],*base_methods[k][1:]) for k in entries}
        return PlayerOperationABI(core_sha256,VTABLES['outer'],VTABLES['parameters'],VTABLES['reasons'],
                                  MappingProxyType(methods),selected[1])
    if core_sha256!=XP1_CORE_SHA256:raise ValueError('Unknown player-operation engine')
    verify_source(core_sha256)
    methods={k:(ENTRIES[k],*base_methods[k][1:]) for k in ENTRIES}
    return PlayerOperationABI(core_sha256,0x8a8df0,0x93fe28,0x93f590,
                             MappingProxyType(methods),SOURCE[1])


@dataclass(frozen=True)
class VerifiedResearchSource:
    owner:object
    core:object
    base:int
    source_sha256:str
    core_sha256:str


def bind_owner(owner,core,read):
    """Bind immutable native source verification to the existing load lifetime."""
    owner.check_thread()
    core_sha=owner.load_abi.core_sha256
    if core_sha==XP2_CORE_SHA256:
        from .xp2_initial_choice_source import SOURCE as selected_source
    elif core_sha==XP1_CORE_SHA256:selected_source=SOURCE
    else:raise ValueError("Unknown research source owner engine")
    if (owner.core is not core
            or type(core._handle) is not int or core._handle<=0):
        raise ValueError('XP1 research source owner mismatch')
    existing=getattr(owner,'_xp1_research_source_receipt',None)
    if existing is not None:
        if (type(existing) is not VerifiedResearchSource or existing.owner is not owner
                or existing.core is not core or existing.base!=core._handle
                or existing.source_sha256!=selected_source[1] or existing.core_sha256!=core_sha):
            raise ValueError('XP1 research source receipt belongs to another lifetime')
        return existing
    image = getattr(core, '_civ6_host_execution_image', None) if core_sha == XP2_CORE_SHA256 else None
    verify_live(core._handle,read,core_sha256=core_sha,
                **({'execution_image':image} if image is not None else {}))
    result=VerifiedResearchSource(owner,core,core._handle,selected_source[1],core_sha)
    owner._xp1_research_source_receipt=result
    return result
