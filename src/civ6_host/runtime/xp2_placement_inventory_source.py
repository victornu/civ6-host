"""Source and lifetime binding for XP2 visible own-city placement reads."""
from dataclasses import dataclass
import hashlib
from pathlib import Path

from .configuration_profiles import XP2_CORE_SHA256, _source
from .paths import resource_root
from .resource_resolution import resolve_path
from . import xp2_production_placement_source as placement

SOURCE = ('work/host-extensions/xp2-placement-inventory-static/source-profile-v1.json',
          '9d3c981e74510c06f0f2009268477eb91823f56af896c4d9119aaa7ba8d41165')
_EXTRA = (0x71450,0x1B0270,0x1B0590,0x11A30,0xBF4D0,0xBE000,0x2D9880,
          0x7D04A0,0x7D08E0,0x2209A0,0x1AEEC0)
_GROUPS = (
    ('placement',('City.GetDistricts','CityBuildings.HasBuilding','Plot.GetOwner','Plot.GetDistrictType',
        'Plot.GetDistrictID','Plot.GetWonderType','Visibility.IsRevealed','Cities.GetPlotPurchaseCity','CityDistricts.IsComplete')),
    ('choices',('Player.GetCities','PlayerCities.Members','City.GetID','City.GetOwner','City.GetBuildings',
        'Game.GetCurrentGameTurn','Game.GetLocalPlayer','Game.GetLocalObserver')),
    ('world',('Map.GetGridSize','Map.GetPlotCount','Map.GetPlotByIndex','Plot.GetIndex','Plot.GetX','Plot.GetY','Visibility.IsVisible')))
_READ_CONTRACT = dict(scope='native_visible_own_city',host_tracking_used=False,
    visibility_before_plot=True,owner_before_details=True,exact_own_city_join=True,
    independent_type_check_before_completion=True,placement_turn_inferred=False,
    district_filter='RequiresPlacement and not InternalOnly',building_filter='RequiresPlacement or IsWonder',
    hidden_plots_read=False,turn_activity_required=False)


def source_reference(core_sha256=XP2_CORE_SHA256):
    if core_sha256!=XP2_CORE_SHA256:
        raise ValueError('XP2 placement inventory requires its exact engine')
    return SOURCE


def verify_source(core_sha256=XP2_CORE_SHA256):
    from . import xp2_world_input_source as world
    from . import xp2_initial_choice_source as choices
    p=_source(source_reference(core_sha256))
    if (p['schema']!='civ6-host.xp2-placement-inventory-source.v1'
            or p['image']['sha256']!=core_sha256 or p['native_execution'] is not False
            or p['process_memory_read'] is not False or set(p['functions'])!={hex(r) for r in _EXTRA}
            or p['validation']!=dict(all_instruction_bytes_match_image=True,bindings=24,supplemental_bodies=11)
            or p['read_contract']!=_READ_CONTRACT):
        raise ValueError('XP2 placement inventory source contract changed')
    world._body_contracts(p)
    selected=dict(placement=placement.SOURCE,world=world.SOURCE,choices=choices.SOURCE)
    if set(p['bindings'])!={name for _,names in _GROUPS for name in names}:
        raise ValueError('XP2 placement inventory binding set changed')
    for group,names in _GROUPS:
        ref=selected[group];original=_source(ref)
        for name in names:
            binding=p['bindings'][name];rva=original['bindings'][name]['callback_rva']
            if (binding['source']['sha256']!=ref[1]
                    or resolve_path(resource_root()/binding['source']['path']).resolve()!=resolve_path(resource_root()/ref[0]).resolve()
                    or binding['callback_rva']!=(hex(rva) if type(rva) is int else rva)):
                raise ValueError('XP2 placement inventory selected binding changed: '+name)
    expected={
        'district_type_absent':dict(value=-1,callback_rva='0x1d0c0',callee_rva='0x5e720',field='district+0xf0'),
        'district_id':dict(absent=-1,callback_rva='0x1d060',field='plot+0x10',signed_lua_number=True),
        'wonder_type_absent':dict(value=-1,callback_rva='0x1d900',field='signed int16 plot+0x1e',value_kind='GameInfo.Buildings.Index'),
        'purchase_city':dict(callback_rva='0x687640',owner_field='signed int8 purchase+0x1c',city_field='purchase+0x0c',absent=-1),
        'district_complete':dict(callback_rva='0x68ed50',callee_rva='0x716c0',lookup_rva='0x71450',complete_field='district+0x34',nonnegative_plot_argument_checks_type=False),
        'building_complete':dict(callback_rva='0x68dab0',callee_rva='0x6e3b0',index_converter_rva='0x1b0270',argument='native type index, not hash')}
    if p['facts']!=expected:
        raise ValueError('XP2 placement inventory sentinel/type contract changed')
    for body,rows in {
        0x71450:{0x7146D:'call 0x180011a30',0x7147D:'idiv r8d',0x714DB:'call 0x1802d9880',
                 0x714E5:'cmp r15d, dword ptr [rax + 4]',0x714EB:'cmp r14d, dword ptr [rax + 8]'},
        0x1B0270:{0x1B0278:'call 0x1807d04a0',0x1B028C:'mov eax, ebx',0x1B02A1:'call 0x1802209a0',0x1B02AB:'mov eax, dword ptr [rax + 0x14]'},
        0x1B0590:{0x1B0598:'call 0x1807d08e0',0x1B05AC:'mov eax, ebx',0x1B05C1:'call 0x1801aeec0',0x1B05CB:'mov eax, dword ptr [rax + 0x14]'},
    }.items():placement._require_rows(p,body,rows)
    for ref in p['references']:_source((ref['path'],ref['sha256']))
    placement.verify_source(core_sha256)
    return p


def source_dependencies(core_sha256=XP2_CORE_SHA256):
    result=dict(placement.source_dependencies(core_sha256));p=verify_source(core_sha256)
    for ref in (dict(path=SOURCE[0],sha256=SOURCE[1]),p['image'],p['extractor'],*p['references']):
        path=str(resolve_path(resource_root()/ref['path']).resolve())
        if (hashlib.sha256(Path(path).read_bytes()).hexdigest()!=ref['sha256']
                or path in result and result[path]!=ref['sha256']):
            raise ValueError('XP2 placement inventory dependency changed: '+path)
        result[path]=ref['sha256']
    return result


def verify_live(base,read,core_sha256=XP2_CORE_SHA256):
    if type(base) is not int or not 0<base<(1<<47)-0x1000000 or not callable(read):
        raise ValueError('XP2 placement inventory requires its live module and reader')
    p=verify_source(core_sha256);count=0
    for body in p['functions'].values():
        for fragment in body['fragments']:
            rva=int(fragment['start_rva'],16);raw=bytes.fromhex(fragment['raw_hex']);count+=1
            for offset in range(0,len(raw),4096):
                expected=raw[offset:offset+4096];actual=read(base+rva+offset,len(expected))
                if type(actual) is not bytes or actual!=expected:
                    raise ValueError('XP2 placement inventory descendant changed at '+hex(rva+offset))
    return count


@dataclass(frozen=True)
class VerifiedInventorySource:
    owner:object
    core:object
    base:int
    source_sha256:str
    core_sha256:str
    placement_receipt:object
    instruction_read_spans:int


def bind_owner(owner,core,read):
    """Bind the actual saved backend; reads need no active-turn prerequisite."""
    original=placement.bind_owner(owner,core,read)
    old=getattr(owner,'_xp2_placement_inventory_source_receipt',None)
    if old is not None:
        if (type(old) is not VerifiedInventorySource or old.owner is not owner or old.core is not core
                or old.base!=core._handle or old.source_sha256!=SOURCE[1] or old.core_sha256!=XP2_CORE_SHA256
                or old.placement_receipt is not original):
            raise ValueError('XP2 placement inventory belongs to another native lifetime')
        return old
    source_dependencies()
    result=VerifiedInventorySource(owner,core,core._handle,SOURCE[1],XP2_CORE_SHA256,original,verify_live(core._handle,read))
    owner._xp2_placement_inventory_source_receipt=result
    return result
