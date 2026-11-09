"""Exact XP2 public combat bindings for the existing shared attack algorithms.

Source selection admits neither war confirmation nor an unwitnessed attack
outcome. Raw fractional city strength belongs to the administrative channel.
"""
from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from .configuration_profiles import XP2_CORE_SHA256, _source
from .paths import resource_root
from .resource_resolution import resolve_path

SOURCE=('work/host-extensions/xp2-unit-attacks-static/source-profile-v1.json',
        '94562a3ba9e6988fde63a146dd1228b2454b5b1dbee93ffc12a25d83756d95e2')
EXE_SHA256='e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
_IMAGE_BASE=0x180000000
CALLBACKS={
 'Game.GetCurrentGameTurn':0x69af50,'Game.GetLocalPlayer':0x69b8b0,'Game.GetLocalObserver':0x69b870,
 'Game.IsAllowStrategicCommands':0x69cc60,'Player.IsAlive':0x6aa490,'Player.IsTurnActive':0x6aa760,
 'Player.IsTurnActiveComplete':0x6aa7f0,'Player.GetUnits':0x6aa300,'Player.GetDistricts':0x6a99d0,
 'Player.GetDiplomacy':0x6a98d0,'Unit.GetOwner':0x6bd2a0,'Unit.GetID':0x6bcf00,'Unit.GetX':0x6bd7f0,
 'Unit.GetY':0x6bd840,'Unit.GetType':0x6bd750,'Unit.GetUnitType':0x6bd750,'Unit.GetDamage':0x6bcb60,
 'Unit.GetMovesRemaining':0x6bd180,'Unit.GetAttacksRemaining':0x6bc920,'Unit.IsReadyToSelect':0x6bdc50,
 'Unit.GetComponentID':0x6bcb00,'Unit.GetRangedCombat':0x6bd4f0,'Unit.GetCombat':0x6bcab0,
 'Unit.GetBombardCombat':0x6bca10,'PlayerUnits.Members':0x6ab2d0,'Map.GetGridSize':0x6a2430,
 'Map.GetPlotCount':0x6a2810,'Map.GetPlotByIndex':0x6a2790,'Map.GetPlotIndex':0x6a2960,
 'Map.GetAdjacentPlot':0x6a1ac0,'Plot.GetIndex':0x1d270,'Plot.GetX':0x1d9b0,'Plot.GetY':0x1da00,
 'Visibility.IsVisible':0x6b7d60,'Visibility.IsRevealed':0x6b7bf0,'Visibility.IsUnitVisible':0x6b7cd0,
 'Units.GetUnitsInPlotLayerID':0x6c4780,'UnitManager.GetOperationTargets':0x6c1e40,
 'UnitManager.CanStartOperation':0x6c0390,'UnitManager.RequestOperation':0x6c3150,
 'UnitManager.GetQueuedDestination':0x6c1fc0,'CityManager.GetCityAt':0x691620,
 'City.GetOwner':0x68ade0,'City.GetID':0x68ac10,'City.GetDistrictID':0x68aa60,
 'City.GetX':0x68b0a0,'City.GetY':0x68b0f0,'PlayerDistricts.FindID':0x6b0930,
 'District.GetDamage':0x696240,'District.GetMaxDamage':0x696440,'District.GetDefenseStrength':0x6962b0,
 'Diplomacy.IsAtWarWith':0x6b0270,'CombatManager.IsAttackChangeWarState':0x5ab9c0}
REGISTRARS=dict(Game=0x69a250,Player=0x6a8c90,Unit=0x6bb990,PlayerUnits=0x6b6c70,
    Map=0x6a1550,Plot=0x1b2e0,Visibility=0x6b7860,Units=0x6c3630,UnitManager=0x6bfac0,
    CityManager=0x690de0,City=0x689f60,PlayerDistricts=0x6b07f0,District=0x6957c0,
    Diplomacy=0x6ae510,CombatManager=0x5aacc0)


def _registration_contracts(proof):
    if set(proof['bindings'])!=set(CALLBACKS):raise ValueError('XP2 attack callback set changed')
    for name,rva in CALLBACKS.items():
        row=proof['bindings'][name]
        registrar=REGISTRARS[name.split('.')[0]]
        if (row['callback_rva']!=hex(rva) or row['registrar_rva']!=hex(registrar)
                or row['lua_callback_abi']!='int __cdecl(LuaState*) / Windows x64'):
            raise ValueError('XP2 attack registration identity changed: '+name)
        body={r['rva']:r for r in proof['functions'][hex(registrar)]['instructions']}
        window=row['registration_instructions']
        name_index=next((i for i,r in enumerate(window)
            if r['bytes'].startswith('4c8d05') and tuple(r.get('rip_targets',()))==(row['name_va'],)),None)
        if name_index is None:raise ValueError('XP2 attack binding has no actual name LEA: '+name)
        callbacks=[r for r in window[:name_index] if r['bytes'].startswith('488d15')]
        if not callbacks:raise ValueError('XP2 attack binding has no callback LEA: '+name)
        for insn,prefix,target in ((callbacks[-1],'488d15',_IMAGE_BASE+rva),
                (window[name_index],'4c8d05',int(row['name_va'],16))):
            raw=bytes.fromhex(insn['bytes']);address=int(insn['rva'],16)
            if (len(raw)!=7 or raw[:3].hex()!=prefix
                    or _IMAGE_BASE+address+7+int.from_bytes(raw[3:],'little',signed=True)!=target
                    or tuple(insn['rip_targets'])!=(hex(target),)):
                raise ValueError('XP2 attack registration LEA target changed: '+name)
        # Windows retain neighbouring bindings; join every byte to the complete
        # registrar, then require the selected literal's actual registration call.
        following=[insn for insn in body.values()
                   if int(insn['rva'],16)>int(window[name_index]['rva'],16)]
        next_call=next((insn for insn in following
                       if insn['text'].startswith(('call ','jmp '))),None)
        if (any(body.get(insn['rva'],{}).get('bytes')!=insn['bytes'] for insn in window)
                or next_call is None
                or next_call['text'] not in ('call 0x18000dab0','jmp 0x18000dab0')):
            raise ValueError('XP2 attack registration window changed: '+name)


def _contracts(proof):
    from .xp2_world_input_source import _body_contracts, _require_rows
    _body_contracts(proof)
    if len(proof['functions'])!=151:raise ValueError('XP2 attack body closure changed')
    _registration_contracts(proof)
    # Widths and nested services are native source, not inferred field aliases.
    for body,rows in {
      0x6bc920:{0x6bc93a:'movd xmm0, dword ptr [rax + 0x140]'},
      0x6c1e40:{0x6c1f1a:'movzx ecx, word ptr [rdi + 0xec]',
        0x6c1f34:'mov ecx, dword ptr [rdi + 0xd0]',0x6c1f5d:'mov byte ptr [rsp + 0x20], 0',
        0x6c1f62:'call 0x1800d0290',0x6c1f7c:'call qword ptr [r10 + 0xa8]'},
      0xd0290:{0xd02c8:'call qword ptr [rax + 0x40]',0xd0332:'call qword ptr [r10 + 0xf8]',
        0xd03dc:'call qword ptr [r10 + 0x48]',0xd0426:'call qword ptr [rax + 0x38]'},
      0x6962b0:{0x6962d7:'mov edx, dword ptr [rax]',0x6962de:'movzx ecx, dl',
        0x6962e1:'sar edx, 8',0x6962fa:'mulss xmm1, dword ptr [rip + 0x32a6f6]'},
      0x69cc60:{0x69cc87:'call 0x18063da00'},
      0x63da00:{0x63da02:'jmp 0x18005b5d0'},
      0x5b5d0:{0x5b5f6:'movzx eax, byte ptr [rax + 0x50]',0x5b5fa:'and al, 1'},
    }.items():_require_rows(proof,body,rows)
    from .xp2_foundation_query_source import source as facade_source
    facade=facade_source();selected=proof['facade_contracts']
    if (facade['operations']!=selected['query_operations']
            or facade['tables']!=selected['query_tables']
            or len(selected['query_operations'])!=35):
        raise ValueError('XP2 attack EXE facade source correspondence changed')
    enums=proof['enum_selection'];parent=_source((enums['body_reference']['path'],enums['body_reference']['sha256']))
    enum_body=parent['functions'][enums['body_key']]
    if enum_body['sha256']!=enums['body_sha256'] or len(enums['enums'])!=22:
        raise ValueError('XP2 attack enum closure changed')
    actual={row['rva']:row for part in enum_body['fragments'] for row in part['instructions']}
    for name,row in enums['enums'].items():
        if any(actual.get(insn['rva'],{}).get('bytes')!=insn['bytes']
               or actual[insn['rva']]['text']!=insn['text'] for insn in row['instructions']):
            raise ValueError('XP2 attack enum registration changed: '+name)
    from .xp1_unit_attack_profile import READINESS_REPLACEMENTS
    if (set(proof['readiness_replacements'])!=set(READINESS_REPLACEMENTS)
            or any((proof['readiness_replacements'][kind]['old'],proof['readiness_replacements'][kind]['new'],
                    proof['readiness_replacements'][kind]['count'])!=(old,new,1)
                   for kind,(old,new) in READINESS_REPLACEMENTS.items())):
        raise ValueError('XP2 attack readiness transform changed')


def _official_route(proof):
    route=proof['official_route'];texts={}
    for key,row in proof['official_ui'].items():
        raw=resolve_path(Path(row['path'])).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=row['sha256']:
            raise ValueError('Official XP2 attack UI changed: '+key)
        texts[key]=raw.decode(route['encodings'][key])
    replacements={node.findtext('Properties/LuaContext'):node.findtext('Properties/LuaReplace')
                  for node in ET.fromstring(texts['modinfo']).iter('ReplaceUIScript')}
    if (replacements.get('WorldInput')!='UI/Replacements/WorldInput_Expansion2.lua'
            or any(name in replacements for name in ('UnitFlagManager','Civ6Common'))
            or 'include("WorldInput_Expansion1")' not in texts['world_xp2']
            or 'include("WorldInput")' not in texts['world_inherited']):
        raise ValueError('XP2 attack official include chain changed')
    for key in ('world_xp2','world_inherited'):
        names=re.findall(r'^function\s+([A-Za-z_][A-Za-z_0-9]*)\s*\(',texts[key],re.M)
        if (tuple(names)!=route['overrides'][key]
                or set(names)&{'UnitRangeAttack','MoveUnitToPlot','RequestMoveOperation','OnUnitFlagClick'}):
            raise ValueError('XP2 overrides an inherited attack handler')
    for key,rows in route['precision_anchors'].items():
        lines=texts[key].splitlines()
        if any(lines[row['line']-1].strip()!=row['text'] for row in rows):
            raise ValueError('XP2 public city defense rounding changed')
    flag=texts['base_unit_flag']
    click=flag.split('function OnUnitFlagClick(',1)[1].split('elseif CanSelectUnit',1)[0]
    if ('IsReadyToSelect' in click or 'self:SetDim(not pUnit:IsReadyToSelect())' not in flag
            or not all(name in click for name in ('UnitOperationTypes.RANGE_ATTACK','UnitOperationTypes.MOVE_TO'))):
        raise ValueError('XP2 official flag readiness/attack route changed')


def verify_source(core_sha256=XP2_CORE_SHA256):
    if core_sha256!=XP2_CORE_SHA256:raise ValueError('XP2 attack source requires its exact engine')
    p=_source(SOURCE)
    if (p['schema']!='civ6-host.xp2-unit-attacks-source.v1' or p['image']['sha256']!=core_sha256
            or p['exe']['sha256']!=EXE_SHA256 or p['native_execution'] is not False
            or p['process_memory_read'] is not False
            or p['validation']!=dict(exact_registration_pairs=53,all_instruction_bytes_match_image=True,
                conditional_branches_included=True,body_count=151,first_level_native_helpers=69,extra_helpers=33)
            or p['precision_constant']!=dict(rva='0x9c09f8',raw_hex='0000803b')
            or p['contracts']!=dict(public_defense_strength='math.floor(raw + 0.5)',raw_scale=1/256,
                readiness_is_presentation=True,war_confirmation_admitted=False,arbitrary_routes_admitted=False,
                native_defender_selection=True,missing_effect_is_unqualified=True)):
        raise ValueError('XP2 public attack source identity changed')
    for row in p['references']:_source((row['path'],row['sha256']))
    _contracts(p);_official_route(p)
    return p


def source_dependencies(core_sha256=XP2_CORE_SHA256, *, execution_image=None):
    p=verify_source(core_sha256);result={}
    if execution_image is not None:
        image_path=Path(resolve_path(Path(p['image']['path'])).resolve())
        if (str(image_path)!=str(Path(execution_image.path).resolve())
                or p['image']['sha256']!=execution_image.reference_core_sha256):
            raise ValueError('XP2 attack provenance differs from the selected execution/reference pair')
    refs=[dict(path=SOURCE[0],sha256=SOURCE[1]),p['image'],p['exe'],*p['references'],
          *p['extractors'],*p['official_ui'].values(),p['enum_selection']['body_reference']]
    for row in refs:
        path=resolve_path(resource_root()/row['path']).resolve()
        if execution_image is None and hashlib.sha256(path.read_bytes()).hexdigest()!=row['sha256']:
            raise ValueError('XP2 public attack dependency changed: '+str(path))
        if str(path) in result and result[str(path)]!=row['sha256']:
            raise ValueError('Conflicting XP2 public attack dependency')
        result[str(path)]=row['sha256']
    from .runtime_source_dependencies import materialize_runtime_source_pins
    result=materialize_runtime_source_pins(result, execution_image=execution_image,
        provenance_images=(p['image'], p['exe']))
    from .xp2_world_input_source import source_dependencies as world
    from .combat_event_profile import source_dependencies as combat
    from .district_damage_profile import source_dependencies as district
    for provider in (world,combat,district):
        for path,sha in provider(core_sha256=core_sha256, execution_image=execution_image).items():
            if path in result and result[path]!=sha:raise ValueError('Conflicting XP2 attack source')
            result[path]=sha
    from .xp2_foundation_query_source import source_dependencies as facades
    from .xp2_aux_map_profile import source_dependencies as maps
    for path,sha in facades(execution_image=execution_image).items():
        if path in result and result[path]!=sha:raise ValueError('Conflicting XP2 attack helper source')
        result[path]=sha
    for path,sha in maps().items():
        if path in result and result[path]!=sha:raise ValueError('Conflicting XP2 attack helper source')
        result[path]=sha
    result=materialize_runtime_source_pins(result, execution_image=execution_image,
        provenance_images=(p['image'], p['exe']))
    from .a0_family_source import verify_pinned_files
    verify_pinned_files(result)
    return result


def _live_spans(proof,base=_IMAGE_BASE):
    from .xp2_world_input_source import _fragments
    yield from _fragments(proof)
    for name,row in proof['bindings'].items():
        yield int(row['name_va'],16)-_IMAGE_BASE,name.split('.')[1].encode('ascii')+b'\0'
    for address,text in proof['typed_constructor_literals'].items():
        # Diagnostic file paths were captured as bounded prefixes, not strings.
        if '\\' not in text:yield int(address,16)-_IMAGE_BASE,text.encode('ascii')+b'\0'
    yield 0x9c09f8,bytes.fromhex(proof['precision_constant']['raw_hex'])
    for name,row in proof['enum_selection']['enums'].items():
        yield int(row['literal_va'],16)-_IMAGE_BASE,name.split('.')[1].encode('ascii')+b'\0'
        for insn in row['instructions']:yield int(insn['rva'],16),bytes.fromhex(insn['bytes'])
    for table in proof['facade_contracts']['query_tables'].values():
        for slot,target in table['slots'].items():
            yield int(table['vtable_rva'],16)+int(slot,16),(base+int(target,16)).to_bytes(8,'little')
    for slot in proof['facade_contracts']['ui_child']['slots']:
        yield slot['table_rva']+slot['slot'],(base+slot['target_rva']).to_bytes(8,'little')


def verify_live(base,read,core_sha256=XP2_CORE_SHA256):
    if type(base) is not int or not 0<base<(1<<47)-0x1000000 or not callable(read):
        raise ValueError('XP2 attack source needs its exact live module reader')
    p=verify_source(core_sha256);count=0
    for rva,raw in _live_spans(p,base):
        for offset in range(0,len(raw),4096):
            expected=raw[offset:offset+4096];actual=read(base+rva+offset,len(expected))
            if type(actual) is not bytes or actual!=expected:
                raise ValueError('XP2 unit-attack live source changed at '+hex(rva+offset))
        count+=1
    return count


@dataclass(frozen=True)
class VerifiedAttackSource:
    owner:object
    core:object
    base:int
    core_sha256:str
    source_sha256:str
    instruction_read_spans:int
    public_precision_source_sha256:str
    readiness_source_sha256:str


def bind_owner(owner,core,read):
    owner.check_thread()
    if (owner.core is not core or owner.load_abi.core_sha256!=XP2_CORE_SHA256
            or type(core._handle) is not int or core._handle<=0 or read!=owner.runtime.read):
        raise ValueError('XP2 unit-attack source owner mismatch')
    previous=getattr(owner,'_xp2_unit_attack_source_receipt',None)
    if previous is not None:
        if (type(previous) is not VerifiedAttackSource or previous.owner is not owner
                or previous.core is not core or previous.base!=core._handle
                or previous.core_sha256!=XP2_CORE_SHA256 or previous.source_sha256!=SOURCE[1]
                or previous.public_precision_source_sha256!=SOURCE[1]
                or previous.readiness_source_sha256!=SOURCE[1]):
            raise ValueError('XP2 unit-attack source belongs to another lifetime')
        return previous
    from .xp2_world_input_source import bind_owner as bind_world
    bind_world(owner,core,read)
    # Pin the source closure once on this actual owned lifetime. Every call keeps
    # thread/module/reader checks; native live data is never cached here.
    source_dependencies(execution_image=getattr(core, '_civ6_host_execution_image', None))
    receipt=VerifiedAttackSource(owner,core,core._handle,XP2_CORE_SHA256,SOURCE[1],
                                verify_live(core._handle,read),SOURCE[1],SOURCE[1])
    owner._xp2_unit_attack_source_receipt=receipt
    return receipt
