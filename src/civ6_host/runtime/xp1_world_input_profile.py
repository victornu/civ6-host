"""Candidate XP1 source selection for the existing official world-click route.

This profile admits no public session and no new gameplay algorithm. Other
operations reached by the official click route are refused before submission.
MOVE_TO itself can encounter combat/entry effects: those remain native trial
boundaries, not a claim of complete XP1 movement or combat qualification.
"""
from dataclasses import dataclass
import hashlib
from pathlib import Path
from .configuration_profiles import BASE_CORE_SHA256, XP1_CORE_SHA256, XP2_CORE_SHA256, _source

SOURCE=('work/host-extensions/xp1-world-click-static/world-click-source-v1.json',
        '1aa9d771fcf0ffffe0d74b61412c50787d4911204b37d393fddc84ed5811998b')
CALLBACKS={'Unit.GetComponentID':0x5d8580,'Unit.GetPlotId':0x5d8db0,
 'Unit.GetCombat':0x5d8530,'Unit.GetRangedCombat':0x5d8f60,'Unit.GetBombardCombat':0x5d8490,
 'Map.GetGridSize':0x5bddd0,'Map.GetPlotCount':0x5be1b0,'Map.GetPlotByIndex':0x5be130,
 'Plot.GetIndex':0x1bf10,'Plot.GetX':0x1c650,'Plot.GetY':0x1c6a0,
 'Visibility.IsVisible':0x5d37e0,'CombatManager.IsAttackChangeWarState':0x4d57e0,
 'UnitManager.GetQueuedDestination':0x5ddab0}
REGISTRARS={'Unit':0x5d7410,'Map':0x5bcea0,'Plot':0x19f80,'Visibility':0x5d32e0,
            'CombatManager':0x4d4b30,'UnitManager':0x5db5b0}

def verify_source(core_sha256=XP1_CORE_SHA256):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_world_input_source import verify_source as selected
        return selected()
    if core_sha256!=XP1_CORE_SHA256:
        raise ValueError('World input profile requires its exact XP1 engine')
    proof=_source(SOURCE)
    if (proof['schema']!='civ6_host.xp1_world_click.static.v1'
            or proof['image']['sha256']!=core_sha256
            or proof['native_execution'] is not False or proof['process_memory_read'] is not False
            or proof['validation']['exact_registration_pairs']!=len(CALLBACKS)
            or proof['validation']['all_instruction_bytes_match_image'] is not True
            or proof['validation']['conditional_branches_included'] is not True
            or set(proof['bindings'])!=set(CALLBACKS)):
        raise ValueError('XP1 world input binding source changed')
    for name,rva in CALLBACKS.items():
        row=proof['bindings'][name]
        if (row['callback_rva']!=hex(rva)
                or row['registrar_rva']!=hex(REGISTRARS[name.split('.')[0]])
                or row['lua_callback_abi']!='int __cdecl(LuaState*) / Windows x64'
                or not proof['functions'][hex(rva)]['instructions']
                or not proof['functions']['registration:'+name]['instructions']):
            raise ValueError('XP1 world input binding changed: '+name)
    for reference in proof['references']:
        _source((reference['path'],reference['sha256']))
    from .resource_resolution import resolve_path
    for row in proof['official_ui']:
        if hashlib.sha256(resolve_path(Path(row['path'])).read_bytes()).hexdigest()!=row['sha256']:
            raise ValueError('Official world-input Lua changed')
    return proof

def source_dependencies(core_sha256=XP1_CORE_SHA256):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_world_input_source import source_dependencies as selected
        return selected()
    if core_sha256!=XP1_CORE_SHA256:raise ValueError('Unknown world-input engine')
    from .resource_resolution import resolve_path
    from .paths import resource_root
    from .xp1_status_profiles import source_dependencies as status
    from .unit_operation_ui_profile import source_dependencies as operation
    proof=verify_source()
    refs=[dict(path=SOURCE[0],sha256=SOURCE[1]),*proof['references'],proof['image'],*proof['official_ui']]
    result={str(resolve_path(resource_root()/r['path']).resolve()):r['sha256'] for r in refs}
    for provider in (status,operation):
        for path,sha in provider().items():
            if path in result and result[path]!=sha:raise ValueError('Conflicting world-input source pins')
            result[path]=sha
    return result

def verify_live(base,read,core_sha256=XP1_CORE_SHA256):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_world_input_source import verify_live as selected
        return selected(base,read)
    if core_sha256!=XP1_CORE_SHA256:raise ValueError('Unknown world-input engine')
    if type(base) is not int or base<=0 or not callable(read):raise ValueError('Expected XP1 module and reader')
    from .xp1_status_profiles import _instruction_spans
    proof=verify_source();spans=_instruction_spans(proof)
    for rva,raw in spans:
        if read(base+rva,len(raw))!=raw:raise ValueError('XP1 world-input instructions changed at '+hex(rva))
    for name,row in proof['bindings'].items():
        text=name.split('.')[1].encode('ascii')+b'\0'
        if read(base+int(row['name_va'],16)-0x180000000,len(text))!=text:
            raise ValueError('XP1 world-input binding name changed: '+name)
    return len(spans)

@dataclass(frozen=True)
class VerifiedWorldInputSource:
    owner:object
    core:object
    base:int
    source_sha256:str
    instruction_read_spans:int

def bind_owner(owner,core,read):
    if owner.load_abi.core_sha256==XP2_CORE_SHA256:
        from .xp2_world_input_source import bind_owner as selected
        return selected(owner,core,read)
    owner.check_thread()
    if (owner.core is not core or owner.load_abi.core_sha256!=XP1_CORE_SHA256
            or type(core._handle) is not int or core._handle<=0):
        raise ValueError('XP1 world-input source owner mismatch')
    from .xp1_status_profiles import bind_owner as bind_status
    bind_status(owner,core,read)
    prior=getattr(owner,'_xp1_world_input_source_receipt',None)
    if prior is not None:
        if (type(prior) is not VerifiedWorldInputSource or prior.owner is not owner
                or prior.core is not core or prior.base!=core._handle or prior.source_sha256!=SOURCE[1]):
            raise ValueError('World-input source receipt belongs to another lifetime')
        return prior
    from .unit_operation_ui_profile import verify_live as verify_operation
    verify_operation(core._handle,read,core_sha256=XP1_CORE_SHA256)
    receipt=VerifiedWorldInputSource(owner,core,core._handle,SOURCE[1],verify_live(core._handle,read))
    owner._xp1_world_input_source_receipt=receipt
    return receipt

def selected_statuses(default,core_sha256):
    if core_sha256==BASE_CORE_SHA256:return default
    if core_sha256 not in (XP1_CORE_SHA256,XP2_CORE_SHA256):raise ValueError('Unknown world-input engine')
    return frozenset((*default,'unsupported'))

def require_no_prompt(owner,player_id,core_sha256):
    if core_sha256==BASE_CORE_SHA256:return
    if core_sha256 not in (XP1_CORE_SHA256,XP2_CORE_SHA256):raise ValueError('Unknown world-input engine')
    if getattr(owner,'world_input_prompts',{}).get(player_id) is not None:
        raise ValueError('XP1 war confirmation is not qualified')

def adapt_request_source(raw,core_sha256):
    """Guard official route branches before the native transmission seam.

    All candidates remain public grid clicks. The generic refusal contains no
    operation, parameters, defender or hidden target state. The original UI
    algorithm decides its route; this host guard does not decide game legality.
    """
    if core_sha256==BASE_CORE_SHA256:return raw
    verify_source(core_sha256)
    changes=((b'local nativeUnitManager=UnitManager',b'local unqualified=false\nlocal nativeUnitManager=UnitManager'),
      (b' return nativeRequest(requestUnit,operation,parameters)',
       b" if operationName~='MOVE_TO' then unqualified=true;return end\n return nativeRequest(requestUnit,operation,parameters)"),
      (b"if warPrompt~=nil then\n assert(requestCount==0,'war prompt also issued a native request')",
       b"if unqualified or warPrompt~=nil then\n assert(requestCount==(unqualified and 1 or 0),'ambiguous unqualified click')\n return outcome('unsupported',nil,nil,nil,nil)\nend\nif warPrompt~=nil then\n assert(requestCount==0,'war prompt also issued a native request')"))
    for before,after in changes:
        if raw.count(before)!=1:raise ValueError('Shared official click seam changed')
        raw=raw.replace(before,after)
    return raw
