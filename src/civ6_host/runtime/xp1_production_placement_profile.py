"""Source-selected native XP1 placement/resume readers, without new rules."""
from dataclasses import dataclass
from .configuration_profiles import BASE_CORE_SHA256, XP1_CORE_SHA256, XP2_CORE_SHA256, _source

SOURCE=('work/host-extensions/xp1-production-placement-static/placement-source-v1.json',
        '25094b1e71dfba16ba48e6d0642a1d4cd8f30240d47fa3dac96b47a98867757a')
CALLBACKS={'BuildQueue.HasBeenPlaced':0x5a86f0,'CityManager.GetOperationTargets':0x5ad190,
 'City.GetDistricts':0x5a6400,'CityBuildings.HasBuilding':0x5a9400,
 'Plot.GetOwner':0x1c150,'Plot.GetDistrictType':0x1bd60,'Plot.GetDistrictID':0x1bd00,
 'Plot.GetWonderType':0x1c5a0,'Visibility.IsRevealed':0x5d3670,
 'Cities.GetPlotPurchaseCity':0x5a2fd0,'CityDistricts.IsComplete':0x5aa6a0}
REGISTRARS={'BuildQueue':0x5a6e40,'CityManager':0x5ac730,'City':0x5a58f0,
 'CityBuildings':0x5a8930,'Plot':0x19f80,'Visibility':0x5d32e0,
 'Cities':0x5a2e50,'CityDistricts':0x5aa1e0}


def source_reference(core_sha256=XP1_CORE_SHA256):
    if core_sha256==XP1_CORE_SHA256:return SOURCE
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_production_placement_source import SOURCE as selected
        return selected
    raise ValueError('Unknown placement engine')


def verify_source(core_sha256=XP1_CORE_SHA256):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_production_placement_source import verify_source as selected
        return selected()
    if core_sha256!=XP1_CORE_SHA256:
        raise ValueError('Placement profile requires the exact XP1 engine')
    p=_source(SOURCE)
    if (p['schema']!='civ6_host.xp1_production_placement.static.v1'
            or p['image']['sha256']!=core_sha256
            or p['native_execution'] is not False or p['process_memory_read'] is not False
            or p['validation']!=dict(exact_registration_pairs=11,
                all_instruction_bytes_match_image=True,conditional_branches_included=True)
            or set(p['bindings'])!=set(CALLBACKS)):
        raise ValueError('XP1 placement source identity changed')
    for name,rva in CALLBACKS.items():
        b=p['bindings'][name]
        if (b['callback_rva']!=hex(rva)
                or b['registrar_rva']!=hex(REGISTRARS[name.split('.')[0]])
                or b['lua_callback_abi']!='int __cdecl(LuaState*) / Windows x64'
                or not p['functions'][hex(rva)]['instructions']
                or not p['functions']['registration:'+name]['instructions']):
            raise ValueError('XP1 placement native binding changed: '+name)
    for ref in p['references']:
        _source((ref['path'],ref['sha256']))
    return p


def selected_proof_sha256(core_sha256, retained):
    if core_sha256==BASE_CORE_SHA256:return retained
    verify_source(core_sha256)
    return source_reference(core_sha256)[1]


def source_dependencies(core_sha256=XP1_CORE_SHA256, *, execution_image=None):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_production_placement_source import source_dependencies as selected
        return selected(core_sha256,execution_image=execution_image)
    if execution_image is not None:
        raise ValueError('Selected execution image requires the XP2 placement ABI')
    if core_sha256!=XP1_CORE_SHA256:raise ValueError('Unknown placement engine')
    from .paths import resource_root
    from .resource_resolution import resolve_path
    from .xp1_production_profile import source_dependencies as production
    from .xp1_world_input_profile import source_dependencies as world
    from .foundation_event_profile import source_dependencies as foundation
    from . import script_event_source
    from .improvement_visibility_profile import source_dependencies as visibility
    from .faith_event_profile import source_dependencies as faith
    from .game_history_event_profile import source_dependencies as history
    from .game_era_score_event_profile import source_dependencies as score
    from .xp1_goody_hut_profile import source_dependencies as goody
    p=verify_source();pins={}
    for provider in (production,world,foundation,visibility,faith,history,score,goody):
        for path,sha in provider().items():
            if path in pins and pins[path]!=sha:raise ValueError('Conflicting placement dependencies')
            pins[path]=sha
    script=script_event_source.source()
    for r in (dict(path=SOURCE[0],sha256=SOURCE[1]),p['image'],*p['references'],*p['official_ui_sources'],
              dict(path=script_event_source.SOURCE[0],sha256=script_event_source.SOURCE[1]),
              *script['references'].values()):
        path=str(resolve_path(resource_root()/r['path']).resolve())
        if path in pins and pins[path]!=r['sha256']:raise ValueError('Conflicting placement source')
        pins[path]=r['sha256']
    return pins


def verify_live(base,read,core_sha256=XP1_CORE_SHA256):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_production_placement_source import verify_live as selected
        return selected(base,read)
    if core_sha256!=XP1_CORE_SHA256:raise ValueError('Unknown placement engine')
    from .xp1_status_profiles import _instruction_spans
    if type(base) is not int or base<=0 or not callable(read):
        raise ValueError('XP1 placement needs its exact module and reader')
    p=verify_source();spans=_instruction_spans(p)
    for rva,raw in spans:
        if read(base+rva,len(raw))!=raw:
            raise ValueError('XP1 placement instruction changed at '+hex(rva))
    for name,b in p['bindings'].items():
        raw=name.split('.')[1].encode('ascii')+b'\0'
        if read(base+int(b['name_va'],16)-0x180000000,len(raw))!=raw:
            raise ValueError('XP1 placement literal changed: '+name)
    return len(spans)


@dataclass(frozen=True)
class VerifiedPlacementSource:
    owner:object
    core:object
    base:int
    source_sha256:str
    instruction_read_spans:int


def bind_owner(owner,core,read):
    if owner.load_abi.core_sha256==XP2_CORE_SHA256:
        from .xp2_production_placement_source import bind_owner as selected
        return selected(owner,core,read)
    owner.check_thread()
    if (owner.core is not core or owner.load_abi.core_sha256!=XP1_CORE_SHA256
            or type(core._handle) is not int or core._handle<=0 or read!=owner.runtime.read):
        raise ValueError('XP1 placement source owner mismatch')
    old=getattr(owner,'_xp1_production_placement_source_receipt',None)
    if old is not None:
        if (type(old) is not VerifiedPlacementSource or old.owner is not owner
                or old.core is not core or old.base!=core._handle or old.source_sha256!=SOURCE[1]):
            raise ValueError('XP1 placement receipt belongs to another native lifetime')
        return old
    from .xp1_production_profile import bind_owner as production
    from .xp1_world_input_profile import bind_owner as world
    from .xp1_session_inputs import verify_xp1_session_pins
    production(owner,core,read);world(owner,core,read)
    verify_xp1_session_pins(source_dependencies(),core,family='placement')
    receipt=VerifiedPlacementSource(owner,core,core._handle,SOURCE[1],verify_live(core._handle,read))
    owner._xp1_production_placement_source_receipt=receipt
    return receipt
