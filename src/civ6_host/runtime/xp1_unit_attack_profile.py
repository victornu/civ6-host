"""Selected expansion sources for shared native unit/city attack input and readback.

This profile verifies native bindings; it does not assert complete attack
coverage, a successful combat outcome, or the retained Base lifecycle proof.
"""
from dataclasses import dataclass
from pathlib import Path
import hashlib
import re
import xml.etree.ElementTree as ET

from .configuration_profiles import BASE_CORE_SHA256, XP1_CORE_SHA256, XP2_CORE_SHA256, _source

SOURCE=('work/host-extensions/xp1-unit-attacks-static/source-v1.json',
        'b9251e3cd27c092d9dfce3015323a651a61d3b15af1a9da5251c6d95386aa3df')
PUBLIC_PRECISION_SOURCE=('work/host-extensions/xp1-unit-attacks-public-precision/source-v1.json',
                         '5a3982beb1ec8344dca783b5ca83a49dff606e24327046984c35c575c2075d14')
READINESS_SOURCE=('work/host-extensions/xp1-unit-attack-readiness-static/source-v1.json',
                  '3441a99fe192ace6b1d57af5813b834f54c7b57bd3237669d20667dbed4c7477')
READINESS_REPLACEMENTS={
    'unit_candidates':('if unit:IsReadyToSelect()==true then','do'),
    'unit_request':("assert(unit~=nil and unit:IsReadyToSelect()==true,'own combat unit is no longer ready')",
                    "assert(unit~=nil,'own combat unit is no longer present')"),
    'city_source':('if u:IsReadyToSelect() then','do')}
CALLBACKS={
 'Game.GetCurrentGameTurn':0x5b68a0,'Game.GetLocalPlayer':0x5b7200,'Game.GetLocalObserver':0x5b71c0,
 'Game.IsAllowStrategicCommands':0x5b85b0,'Player.IsAlive':0x5c5f00,'Player.IsTurnActive':0x5c61d0,
 'Player.IsTurnActiveComplete':0x5c6260,'Player.GetUnits':0x5c5d70,'Player.GetDistricts':0x5c5440,
 'Player.GetDiplomacy':0x5c5340,'Unit.GetOwner':0x5d8d10,'Unit.GetID':0x5d8970,'Unit.GetX':0x5d9260,
 'Unit.GetY':0x5d92b0,'Unit.GetType':0x5d91c0,'Unit.GetUnitType':0x5d91c0,'Unit.GetDamage':0x5d85e0,
 'Unit.GetMovesRemaining':0x5d8bf0,'Unit.GetAttacksRemaining':0x5d83a0,'Unit.IsReadyToSelect':0x5d96c0,
 'Unit.GetComponentID':0x5d8580,'Unit.GetRangedCombat':0x5d8f60,'Unit.GetCombat':0x5d8530,
 'Unit.GetBombardCombat':0x5d8490,'PlayerUnits.Members':0x5c6d50,'Map.GetGridSize':0x5bddd0,
 'Map.GetPlotCount':0x5be1b0,'Map.GetPlotByIndex':0x5be130,'Map.GetPlotIndex':0x5be300,
 'Map.GetAdjacentPlot':0x5bd460,'Plot.GetIndex':0x1bf10,'Plot.GetX':0x1c650,'Plot.GetY':0x1c6a0,
 'Visibility.IsVisible':0x5d37e0,'Visibility.IsRevealed':0x5d3670,'Visibility.IsUnitVisible':0x5d3750,
 'Units.GetUnitsInPlotLayerID':0x5e0270,'UnitManager.GetOperationTargets':0x5dd930,
 'UnitManager.CanStartOperation':0x5dbe80,'UnitManager.RequestOperation':0x5dec40,
 'UnitManager.GetQueuedDestination':0x5ddab0,'CityManager.GetCityAt':0x5acf70,
 'City.GetOwner':0x5a6730,'City.GetID':0x5a6560,'City.GetDistrictID':0x5a63b0,
 'City.GetX':0x5a69f0,'City.GetY':0x5a6a40,'PlayerDistricts.FindID':0x5cc3b0,
 'District.GetDamage':0x5b1b90,'District.GetMaxDamage':0x5b1d90,'District.GetDefenseStrength':0x5b1c00,
 'Diplomacy.IsAtWarWith':0x5cbcf0,'CombatManager.IsAttackChangeWarState':0x4d57e0}


def source_reference(core_sha256=XP1_CORE_SHA256):
    if core_sha256==XP1_CORE_SHA256:return SOURCE
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_unit_attack_source import SOURCE as selected
        return selected
    raise ValueError('Unknown expansion attack engine')


def precision_reference(core_sha256=XP1_CORE_SHA256):
    if core_sha256==XP1_CORE_SHA256:return PUBLIC_PRECISION_SOURCE
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_unit_attack_source import SOURCE as selected
        return selected
    raise ValueError('Unknown expansion attack precision engine')


def verify_source(core_sha256=XP1_CORE_SHA256):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_unit_attack_source import verify_source as selected
        return selected(core_sha256)
    if core_sha256!=XP1_CORE_SHA256:
        raise ValueError('Unit-attack profile requires its exact XP1 engine')
    p=_source(SOURCE)
    if (p['schema']!='civ6-host.xp1-unit-attacks-source.v1' or p['image']['sha256']!=core_sha256
            or p['native_execution'] is not False or p['process_memory_read'] is not False
            or set(p['bindings'])!=set(CALLBACKS)
            or p['validation']!=dict(exact_registration_pairs=53,all_instruction_bytes_match_image=True,
                                    conditional_branches_included=True)):
        raise ValueError('XP1 unit-attack source identity changed')
    for name,rva in CALLBACKS.items():
        row=p['bindings'][name]
        if (row['callback_rva']!=hex(rva) or row['lua_callback_abi']!='int __cdecl(LuaState*) / Windows x64'
                or not p['functions'][hex(rva)]['instructions']
                or not p['functions']['registration:'+name]['instructions']):
            raise ValueError('XP1 unit-attack callback source changed: '+name)
    for ref in p['references']:_source((ref['path'],ref['sha256']))
    from .resource_resolution import resolve_path
    for ref in p['official_ui'].values():
        path=resolve_path(Path(ref['path']))
        if hashlib.sha256(path.read_bytes()).hexdigest()!=ref['sha256']:
            raise ValueError('Official XP1 attack UI changed: '+str(path))
    modinfo=ET.fromstring(resolve_path(Path(p['official_ui']['modinfo']['path'])).read_bytes())
    replacements={node.findtext('Properties/LuaContext'):node.findtext('Properties/LuaReplace')
                  for node in modinfo.iter('ReplaceUIScript')}
    if (replacements.get('WorldInput')!='UI/Replacements/WorldInput_Expansion1.lua'
            or any(name in replacements for name in ('UnitFlagManager','Civ6Common'))):
        raise ValueError('XP1 attack UI resolution changed')
    text=resolve_path(Path(p['official_ui']['world_xp1']['path'])).read_text(encoding='utf-8-sig')
    overrides=re.findall(r'^function\s+([A-Za-z_][A-Za-z_0-9]*)\s*\(',text,re.M)
    if ('include("WorldInput")' not in text or tuple(overrides)!=p['ui_resolution']['world_overrides']
            or {'UnitRangeAttack','MoveUnitToPlot','RequestMoveOperation','OnUnitFlagClick'}&set(overrides)):
        raise ValueError('XP1 inherited attack handler changed')
    return p



def verify_public_precision_source(core_sha256=XP1_CORE_SHA256):
    """Verify UI precision separately from the unchanged native binding proof.

    Native defense strength has a 1/256 fractional component. Player-facing
    city strength uses the official UI's floor(raw + 0.5); the raw value remains
    available only through the separate administrative channel. This does not
    qualify all UI widget/visibility conditions or an actual combat outcome.
    """
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_unit_attack_source import verify_source as selected
        return selected(core_sha256)
    if core_sha256!=XP1_CORE_SHA256:raise ValueError('Unknown attack precision engine')
    p=_source(PUBLIC_PRECISION_SOURCE)
    if (p['schema']!='civ6-host.xp1-unit-attacks-public-precision-source.v1'
            or p['native_execution'] is not False or p['process_memory_read'] is not False
            or p['parent_source']['sha256']!=SOURCE[1] or p['image']['sha256']!=XP1_CORE_SHA256
            or p['compatibility']['callbacks_unchanged']!=len(CALLBACKS)
            or p['compatibility']['core_abi_unchanged'] is not True
            or p['compatibility']['gameplay_unchanged'] is not True):
        raise ValueError('XP1 attack public precision source identity changed')
    parent=_source((p['parent_source']['path'],p['parent_source']['sha256']))
    native=p['native_precision'];public=p['public_contract']
    if (native['callback']!='District.GetDefenseStrength'
            or native['callback_rva']!=hex(CALLBACKS['District.GetDefenseStrength'])
            or native['callee_rva']!='0x721c0'
            or native['centistrength'] is not False or native['integer_only'] is not False
            or native['constant']!=dict(va='0x180865ea8',rva='0x865ea8',
                                        raw_hex='0000803b',float32_value=1/256)
            or public['defense_strength']['public']!='math.floor(raw + 0.5)'
            or public['defense_strength']['public_type']!='nonnegative integer'
            or public['defense_strength']['projection_is_official_ui_rounding'] is not True
            or public['hitpoints']['fields']!=('garrison_damage','garrison_max','outer_damage','outer_max')
            or public['hitpoints']['native_callbacks']!={
                name:hex(CALLBACKS[name]) for name in ('District.GetDamage','District.GetMaxDamage')}):
        raise ValueError('XP1 attack public precision formula changed')
    instructions={row['va']:row for row in parent['functions'][native['callback_rva']]['instructions']}
    for row in native['existing_parent_instructions']:
        if instructions.get(row['va'])!=row:
            raise ValueError('XP1 defense precision no longer joins the native callback')
    from .resource_resolution import resolve_path
    sources=p['official_sources']
    if set(sources)!={'xp1_city_banner','xp1_city_support','base_unit_panel','xp1_unit_panel','xp1_modinfo'}:
        raise ValueError('XP1 public precision UI closure changed')
    for ref in sources.values():
        path=resolve_path(Path(ref['path']))
        if hashlib.sha256(path.read_bytes()).hexdigest()!=ref['sha256']:
            raise ValueError('Official XP1 public precision UI changed: '+str(path))
    return p


def selected_proof(base_proof,core_sha256):
    if core_sha256==BASE_CORE_SHA256:return base_proof
    verify_source(core_sha256)
    return source_reference(core_sha256)[1]


def verify_readiness_source(core_sha256=XP1_CORE_SHA256):
    """UI readiness dims a unit flag; native operation legality admits an attack.

    Each supplement selects its exact expansion. The historical Base
    collector remains unchanged and retains its separately documented gap.
    """
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_unit_attack_source import verify_source as selected
        return selected(core_sha256)
    if core_sha256!=XP1_CORE_SHA256:raise ValueError('Unknown attack readiness engine')
    p=_source(READINESS_SOURCE)
    if (p['schema']!='civ6-host.xp1-unit-attack-readiness-source.v1'
            or p['core_sha256']!=XP1_CORE_SHA256 or p['parent_source']['sha256']!=SOURCE[1]
            or p['native_execution'] is not False or p['engine_memory_read'] is not False
            or p['compatibility']['native_bindings_unchanged']!=len(CALLBACKS)
            or p['compatibility']['new_native_calls'] is not False
            or set(p['corrections'])!=set(READINESS_REPLACEMENTS)):
        raise ValueError('XP1 attack readiness source identity changed')
    _source((p['parent_source']['path'],p['parent_source']['sha256']))
    for kind,(old,new) in READINESS_REPLACEMENTS.items():
        row=p['corrections'][kind]
        if (row['old'],row['new'],row['count'])!=(old,new,1):
            raise ValueError('XP1 attack readiness correction changed: '+kind)
    from .resource_resolution import resolve_path
    if set(p['official_sources'])!={'unit_flag','world','common','modinfo','world_xp1'}:
        raise ValueError('XP1 attack readiness UI resolution changed')
    for ref in p['official_sources'].values():
        path=resolve_path(Path(ref['path']))
        if hashlib.sha256(path.read_bytes()).hexdigest()!=ref['sha256']:
            raise ValueError('Official XP1 attack readiness UI changed: '+str(path))
    return p


def selected_readiness_source(lua,core_sha256,kind):
    """Remove exactly the proven presentation gate from the shared expansion Lua."""
    if type(lua) is not bytes or kind not in READINESS_REPLACEMENTS:
        raise ValueError('Unknown shared attack readiness source')
    if core_sha256==BASE_CORE_SHA256:return lua
    if core_sha256 not in (XP1_CORE_SHA256,XP2_CORE_SHA256):raise ValueError('Unknown attack readiness engine')
    verify_readiness_source(core_sha256)
    old,new=(value.encode('ascii') for value in READINESS_REPLACEMENTS[kind])
    if lua.count(old)!=1:
        raise ValueError('Shared attack readiness seam changed: '+kind)
    return lua.replace(old,new,1)


def selected_queued_proof(base_proof,core_sha256):
    if core_sha256==BASE_CORE_SHA256:return base_proof
    verify_source(core_sha256)
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_world_input_source import SOURCE as queued_source
        return queued_source[1]
    from .xp1_world_input_profile import SOURCE as queued_source
    return queued_source[1]


def source_dependencies(core_sha256=XP1_CORE_SHA256):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_unit_attack_source import source_dependencies as selected
        return selected(core_sha256)
    if core_sha256!=XP1_CORE_SHA256:raise ValueError('Unknown attack dependency engine')
    from .paths import resource_root
    from .resource_resolution import resolve_path
    from .xp1_world_input_profile import source_dependencies as world
    from .xp1_combat_profile import source_dependencies as combat
    p=verify_source();precision=verify_public_precision_source();readiness=verify_readiness_source();result={}
    for provider in (world,combat):
        for path,sha in provider().items():
            if path in result and result[path]!=sha:raise ValueError('Conflicting XP1 attack source')
            result[path]=sha
    for ref in (dict(path=SOURCE[0],sha256=SOURCE[1]),p['image'],p['extractor'],
                *p['references'],*p['official_ui'].values(),
                dict(path=PUBLIC_PRECISION_SOURCE[0],sha256=PUBLIC_PRECISION_SOURCE[1]),
                precision['parent_source'],*precision['official_sources'].values(),
                dict(path=READINESS_SOURCE[0],sha256=READINESS_SOURCE[1]),
                readiness['parent_source'],*readiness['official_sources'].values(),
                *readiness['shared_original_sources']):
        path=str(resolve_path(resource_root()/ref['path']).resolve())
        if path in result and result[path]!=ref['sha256']:raise ValueError('Conflicting XP1 attack dependency')
        result[path]=ref['sha256']
    return result


def verify_live(base,read,core_sha256=XP1_CORE_SHA256):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_unit_attack_source import verify_live as selected
        return selected(base,read,core_sha256)
    if core_sha256!=XP1_CORE_SHA256:raise ValueError('Unknown live attack engine')
    from .xp1_status_profiles import _instruction_spans
    if type(base) is not int or base<=0 or not callable(read):
        raise ValueError('XP1 attack source needs the live selected engine reader')
    p=verify_source();spans=_instruction_spans(p)
    for rva,raw in spans:
        if read(base+rva,len(raw))!=raw:
            raise ValueError('XP1 unit-attack instruction changed at '+hex(rva))
    for name,binding in p['bindings'].items():
        raw=name.split('.')[1].encode('ascii')+b'\0'
        if read(base+int(binding['name_va'],16)-0x180000000,len(raw))!=raw:
            raise ValueError('XP1 unit-attack binding literal changed: '+name)
    return len(spans)


@dataclass(frozen=True)
class VerifiedAttackSource:
    owner:object
    core:object
    base:int
    source_sha256:str
    instruction_read_spans:int
    public_precision_source_sha256:str
    readiness_source_sha256:str


def bind_owner(owner,core,read):
    if owner.load_abi.core_sha256==XP2_CORE_SHA256:
        from .xp2_unit_attack_source import bind_owner as selected
        return selected(owner,core,read)
    owner.check_thread()
    if (owner.core is not core or owner.load_abi.core_sha256!=XP1_CORE_SHA256
            or type(core._handle) is not int or core._handle<=0 or read!=owner.runtime.read):
        raise ValueError('XP1 unit-attack source owner mismatch')
    old=getattr(owner,'_xp1_unit_attack_source_receipt',None)
    if old is not None:
        if (type(old) is not VerifiedAttackSource or old.owner is not owner or old.core is not core
                or old.base!=core._handle or old.source_sha256!=SOURCE[1]
                or old.public_precision_source_sha256!=PUBLIC_PRECISION_SOURCE[1]
                or old.readiness_source_sha256!=READINESS_SOURCE[1]):
            raise ValueError('XP1 unit-attack source belongs to another lifetime')
        return old
    from .xp1_world_input_profile import bind_owner as bind_world
    from .resource_resolution import resolve_path
    bind_world(owner,core,read)
    for path,sha in source_dependencies().items():
        with resolve_path(Path(path)).open('rb') as stream:
            if hashlib.file_digest(stream,'sha256').hexdigest()!=sha:
                raise ValueError('XP1 unit-attack dependency changed: '+path)
    receipt=VerifiedAttackSource(owner,core,core._handle,SOURCE[1],verify_live(core._handle,read),
                                 PUBLIC_PRECISION_SOURCE[1],READINESS_SOURCE[1])
    owner._xp1_unit_attack_source_receipt=receipt
    return receipt
