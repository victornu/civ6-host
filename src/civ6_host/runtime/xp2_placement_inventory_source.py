"""Source and lifetime binding for XP2 visible own-city placement reads."""
from dataclasses import dataclass
import hashlib
from pathlib import Path

from .configuration_profiles import XP2_CORE_SHA256, _source
from .paths import resource_root
from .resource_resolution import resolve_path
from .source_verification import file_sha256, verify_pinned_json_bytes
from . import xp2_production_placement_source as placement

SOURCE = ('work/host-extensions/xp2-placement-inventory-static/source-profile-v1.json',
          '9d3c981e74510c06f0f2009268477eb91823f56af896c4d9119aaa7ba8d41165')
PILLAGE_SOURCE = (
    'work/x1trade/xp2-placement-pillage-runtime-stage/'
    'dfec32db22009b605bc64ccbc5a98951454abe91f07c393904522ce89a7c367b.json',
    'dfec32db22009b605bc64ccbc5a98951454abe91f07c393904522ce89a7c367b',
)
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


def source_reference(core_sha256=XP2_CORE_SHA256, *, include_pillage=False):
    if core_sha256!=XP2_CORE_SHA256 or type(include_pillage) is not bool:
        raise ValueError('XP2 placement inventory requires its exact engine')
    return PILLAGE_SOURCE if include_pillage else SOURCE


def verify_pillage_source():
    from .execution_images import _PROFILE
    proof=_source(PILLAGE_SOURCE)
    fields=dict(binding='CityDistricts.IsPillaged',type_argument='Districts.Index',
        second_argument='Map plot index',retrieves_type_when_plot_specified=False,
        cache_pillage_byte=0x35,result_type='boolean',visible_own_city_only=True,
        independent_completion=True,buildings_read=False)
    expected_rvas=dict(register_city_districts=0x68e890,receiver_city_districts=0x68e730,
        lua_is_pillaged=0x68eea0,query_is_pillaged=0x71820,
        lookup_owned_district_at_plot=0x71450,cache_publication=0x7de00,
        cache_pillage_copy=0x7d8b0,native_pillage_flag=0x192910)
    if (proof['schema']!='civ6-host.xp2-placement-pillage-source.v1'
            or proof['image']['sha256']!=_PROFILE.image_sha256
            or proof['parents']['xp2_inventory_sha256']!=SOURCE[1]
            or proof['native_executed'] is not False or proof['process_memory_read'] is not False
            or proof['facts']!=fields or set(proof['bodies'])!=set(expected_rvas)
            or any(proof['bodies'][name][0]['rva']!=hex(rva) for name,rva in expected_rvas.items())
            or {name:row['rva'] for name,row in proof['literals'].items()}
                 !={'IsPillaged':'0xa2f938','CacheCityDistricts':'0xa2eef0'}):
        raise ValueError('XP2 placement pillage source contract changed')
    return proof


def verify_source(core_sha256=XP2_CORE_SHA256, *, include_pillage=False):
    from . import xp2_world_input_source as world
    from . import xp2_initial_choice_source as choices
    source_reference(core_sha256,include_pillage=include_pillage)
    p=_source(SOURCE)
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
        ref=selected[group]
        original=choices.source('status') if group=='choices' else _source(ref)
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
    for ref in p['references']:
        verify_pinned_json_bytes(resolve_path(resource_root()/ref['path']), ref['sha256'])
    placement.verify_source(core_sha256)
    if include_pillage:verify_pillage_source()
    return p


def source_dependencies(core_sha256=XP2_CORE_SHA256, *, execution_image=None, include_pillage=False):
    from .execution_images import _PROFILE
    if include_pillage is True and execution_image is not _PROFILE:
        raise ValueError('District pillage inventory supports the exact installed XP2 image')
    p=verify_source(core_sha256,include_pillage=include_pillage)
    result=dict(placement.source_dependencies(core_sha256,execution_image=execution_image))
    refs=[dict(path=SOURCE[0],sha256=SOURCE[1]),p['image'],p['extractor'],*p['references']]
    if include_pillage:
        refs.append(dict(path=PILLAGE_SOURCE[0],sha256=PILLAGE_SOURCE[1]))
    for ref in refs:
        if ref is p['image'] and execution_image is not None:
            continue
        path=str(resolve_path(resource_root()/ref['path']).resolve())
        if (file_sha256(Path(path))!=ref['sha256']
                or path in result and result[path]!=ref['sha256']):
            raise ValueError('XP2 placement inventory dependency changed: '+path)
        result[path]=ref['sha256']
    from .runtime_source_dependencies import materialize_runtime_source_pins
    return materialize_runtime_source_pins(
        result, execution_image=execution_image,
        provenance_images=(p['image'],),
    )


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


def verify_pillage_live(base,read):
    if type(base) is not int or not 0<base<(1<<47)-0x1000000 or not callable(read):
        raise ValueError('XP2 placement pillage requires its live module and reader')
    proof=verify_pillage_source()
    spans=[row for items in proof['bodies'].values() for row in items]
    spans.extend(proof['literals'].values())
    for row in spans:
        actual=read(base+int(row['rva'],16),row['length'])
        if type(actual) is not bytes or len(actual)!=row['length'] or hashlib.sha256(actual).hexdigest()!=row['sha256']:
            raise ValueError('XP2 placement pillage source changed at '+row['rva'])
    return len(spans)


@dataclass(frozen=True)
class VerifiedInventorySource:
    owner:object
    core:object
    base:int
    source_sha256:str
    core_sha256:str
    placement_receipt:object
    instruction_read_spans:int


def _verify_receipt(owner,core,receipt,original,source_sha256):
    if (type(receipt) is not VerifiedInventorySource or receipt.owner is not owner or receipt.core is not core
            or receipt.base!=core._handle or receipt.source_sha256!=source_sha256
            or receipt.core_sha256!=XP2_CORE_SHA256 or receipt.placement_receipt is not original):
        raise ValueError('XP2 placement inventory belongs to another native lifetime')
    return receipt


def bind_owner(owner,core,read,*,include_pillage=False):
    """Bind the actual saved backend; reads need no active-turn prerequisite."""
    from .execution_images import _PROFILE
    execution_image=getattr(core,'_civ6_host_execution_image',None)
    source_reference(XP2_CORE_SHA256,include_pillage=include_pillage)
    if include_pillage and execution_image is not _PROFILE:
        raise ValueError('District pillage inventory supports the exact installed XP2 image')
    original=placement.bind_owner(owner,core,read)
    old=getattr(owner,'_xp2_placement_inventory_source_receipt',None)
    if old is None:
        source_dependencies(XP2_CORE_SHA256,execution_image=execution_image)
        old=VerifiedInventorySource(owner,core,core._handle,SOURCE[1],XP2_CORE_SHA256,
                                    original,verify_live(core._handle,read))
        owner._xp2_placement_inventory_source_receipt=old
    else:
        _verify_receipt(owner,core,old,original,SOURCE[1])
    if not include_pillage:
        return old
    existing=getattr(owner,'_xp2_placement_pillage_source_receipt',None)
    if existing is not None:
        return _verify_receipt(owner,core,existing,old,PILLAGE_SOURCE[1])
    result=VerifiedInventorySource(owner,core,core._handle,PILLAGE_SOURCE[1],XP2_CORE_SHA256,
                                   old,verify_pillage_live(core._handle,read))
    owner._xp2_placement_pillage_source_receipt=result
    return result


def require_inventory_binding(owner):
    """Check the already verified source for the exact native lifetime."""
    from .native.native_official_load import OfficialLoadBackend
    if type(owner) is not OfficialLoadBackend:
        raise ValueError('XP2 placement inventory requires the actual saved Load backend')
    owner.check_thread()
    core=owner.core
    if owner.destroyed or owner.poisoned or owner.load_abi.core_sha256!=XP2_CORE_SHA256:
        raise ValueError('Placement inventory requires the selected XP2 lifetime')
    return _verify_receipt(owner,core,getattr(owner,'_xp2_placement_inventory_source_receipt',None),
                           getattr(owner,'_xp2_production_placement_source_receipt',None),SOURCE[1])


def require_pillage_binding(owner):
    from .execution_images import _PROFILE
    base=require_inventory_binding(owner)
    core=owner.core
    if getattr(core,'_civ6_host_execution_image',None) is not _PROFILE:
        raise ValueError('District pillage inventory requires the selected XP2 lifetime')
    return _verify_receipt(owner,core,getattr(owner,'_xp2_placement_pillage_source_receipt',None),
                           base,PILLAGE_SOURCE[1])
