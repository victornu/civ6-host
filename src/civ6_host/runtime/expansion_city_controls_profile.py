"""Exact captured city-control sources; registered native Lua APIs stay native."""
from dataclasses import dataclass
from pathlib import Path
from types import MethodType
import ctypes as C
import hashlib

from .configuration_profiles import BASE_CORE_SHA256,XP1_CORE_SHA256,XP2_CORE_SHA256,_source

SOURCE=('work/host-extensions/expansion-city-controls-static/source-profile-v1.json',
        '7885524bb2ab007308b03fe134ae0fc4972cfec40c80fc7ba1d5f97010d54e73')
SUPPLEMENT=('work/host-extensions/expansion-city-controls-static/source-supplement-v1.json',
            '3861b860d36c308ea3681fee1886bdce16f76a418b1d4de3383b0a1f9fd60407')
EXE_SHA='e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
_LABELS={BASE_CORE_SHA256:'base',XP1_CORE_SHA256:'xp1',XP2_CORE_SHA256:'xp2'}
_CALLBACKS={
    'base':(0x511cb0,0x515200,0x5151a0,0x518e00,0x5189c0),
    'xp1':(0x5a62d0,0x5a9820,0x5a97c0,0x5ad420,0x5acfe0),
    'xp2':(0x68a980,0x68ded0,0x68de70,0x691ad0,0x691690),
}
NAMES=('GetCitizens','IsFavoredYield','IsDisfavoredYield','RequestCommand','GetCommandTargets')


def verify_source(core_sha256):
    if core_sha256 not in _LABELS:raise ValueError('Unknown city-control source engine')
    p,s=_source(SOURCE),_source(SUPPLEMENT);label=_LABELS[core_sha256];selected=p['profiles'][label]
    if (p['schema']!='civ6-host.expansion-city-controls.source.v1'
            or p['native_execution'] is not False or p['process_memory_read'] is not False
            or p['exe']['sha256']!=EXE_SHA or selected['image']['sha256']!=core_sha256
            or tuple(selected['bindings'][n]['callback_rva'] for n in NAMES)!=_CALLBACKS[label]
            or p['contract']['new_python_virtual_abi'] is not False
            or p['contract']['native_rules_reimplemented'] is not False
            or selected['absent_city_position']['kind']!=0x67001fe1
            or s['schema']!='civ6-host.expansion-city-controls.source-supplement.v1'
            or s['parent']['sha256']!=SOURCE[1]
            or s['city_support_yield_rendering_unchanged'] is not True
            or s['city_panel_click_handlers_inherited'] is not True
            or s['plot_info_not_replaced_by_expansions'] is not True
            or s['auxiliary_map_result']['slot']!=0xa8):
        raise ValueError('City-control native/UI source identity differs')
    for name in NAMES:
        comparison=s['callback_comparisons'][name]
        if (comparison['named_registration_pairs_verified'] is not True
                or comparison['win64_lua_callback_abi_unchanged'] is not True
                or comparison['complete_callback_instructions_correspond_after_native_target_relocation'] is not True
                or comparison['python_virtual_slot_selected'] is not False):
            raise ValueError('City-control registered callback correspondence differs')
    if label!='base':
        from .captured_session_profile import select
        if p['captured_inputs'][label]['manifest']['sha256']!=select(core_sha256).candidate.reference[1]:
            raise ValueError('City-control source belongs to another captured input')
        for ref in p['captured_inputs'][label]['ui_witnesses']:
            value=_source((ref['path'],ref['sha256']))
            ui=value.get('diagnostics',{}).get('ui_availability',value)
            if (ui['schema']!='civ6rl.ui_availability.v2' or ui['read_only'] is not True
                    or ui['observed_unchanged'] is not True
                    or any(ui['tutorial'][k]!={'status':'observed','value':False}
                           for k in ('active','manager_active','overlay_enabled'))
                    or any(ui['controls'][n][k]!={'status':'observed','value':False}
                           for n in ('city_yields','city_citizens') for k in ('hidden','disabled'))):
                raise ValueError('City-control captured UI gate is unknown, hidden or disabled')
    return p,s,selected


def source_dependencies(core_sha256=XP1_CORE_SHA256):
    from .paths import resource_root
    from .resource_resolution import resolve_path
    p,s,selected=verify_source(core_sha256)
    refs=[dict(path=SOURCE[0],sha256=SOURCE[1]),dict(path=SUPPLEMENT[0],sha256=SUPPLEMENT[1]),
          p['exe'],selected['image'],p['capture_script'],s['capture_script'],
          *p['references'],*p['official_ui_sources'],*s['official_ui_sources']]
    if core_sha256!=BASE_CORE_SHA256:
        capture=p['captured_inputs'][_LABELS[core_sha256]]
        refs.extend((capture['manifest'],*capture['ui_witnesses']))
    result={}
    for ref in refs:
        path=resolve_path(resource_root()/ref['path']).resolve()
        if str(path) in result and result[str(path)]!=ref['sha256']:raise ValueError('Conflicting city-control dependency')
        result[str(path)]=ref['sha256']
    return result


def verify_live(base,read,core_sha256):
    _,_,p=verify_source(core_sha256);count=0
    for body in p['functions'].values():
        for fragment in body['fragments']:
            raw=bytes.fromhex(fragment['raw_hex'])
            rva=int(fragment['start_rva'],16) if 'start_rva' in fragment else int(fragment['start_va'],16)-0x180000000
            if read(base+rva,len(raw))!=raw:raise ValueError('City-control live native helper changed')
            count+=1
    for name,binding in p['bindings'].items():
        raw=name.encode()+b'\0'
        if read(base+binding['name_rva'],len(raw))!=raw:raise ValueError('City-control callback name changed')
        for row in binding['registration_instructions']:
            raw=bytes.fromhex(row['bytes']);rva=int(row['rva'],16) if 'rva' in row else int(row['va'],16)-0x180000000
            if read(base+rva,len(raw))!=raw:raise ValueError('City-control native registration changed')
    return count


def _identities(pins):
    return tuple((path,Path(path).stat().st_size,Path(path).stat().st_mtime_ns,Path(path).stat().st_ctime_ns)
                 for path in sorted(pins))


@dataclass(frozen=True)
class CityControlSource:
    saved:object
    backend:object
    continuation:object
    prefix:object
    core:object
    base:int
    inputs:object
    bundle:object
    arguments:object
    reader:object
    reader_read:object
    read:object
    core_sha256:str
    source_sha256:str
    metadata:tuple



def _same_reader(left,right):
    # The production OS reader is a bound _Runtime.read method. Re-accessing
    # that method creates a fresh wrapper; its exact instance/function remain
    # the authority, rather than wrapper identity or user-defined equality.
    return left is right or (type(left) is MethodType and type(right) is MethodType
        and left.__self__ is right.__self__ and left.__func__ is right.__func__)


def bind_owner(saved):
    from .xp1_saved_load_owner import SavedLoadOwner
    if type(saved) is not SavedLoadOwner:raise TypeError('City controls require the actual saved session')
    b,t,p=saved.backend,saved.continuation,saved.prefix
    core=b.load_abi.core_sha256
    if core not in (XP1_CORE_SHA256,XP2_CORE_SHA256):raise ValueError('City controls require their selected expansion owner')
    b.check_thread();p.check()
    arguments=p.event_arguments;reader=arguments.reader;arguments._check()
    if (reader.core is not b.core or reader.base!=b.core._handle or reader.core_sha256!=core
            or not _same_reader(reader.read,b.runtime.read)):
        raise ValueError('City-control argument reader belongs to another live source')
    receipt=getattr(b,'_expansion_city_controls_source',None)
    if receipt is not None:
        if (type(receipt) is not CityControlSource or receipt.saved is not saved
                or receipt.backend is not b or receipt.continuation is not t or receipt.prefix is not p
                or receipt.core is not b.core or receipt.base!=b.core._handle
                or receipt.inputs is not b.inputs or receipt.bundle is not b.captured_bundle
                or receipt.arguments is not arguments or receipt.reader is not reader or not _same_reader(receipt.read,b.runtime.read)
                or not _same_reader(receipt.reader_read,reader.read)
                or receipt.core_sha256!=core or receipt.source_sha256!=SOURCE[1]
                or getattr(arguments,'_expansion_city_controls_source',None) is not receipt):
            raise ValueError('City-control source lost its exact live owners')
        if receipt.metadata!=_identities(source_dependencies(core)):
            raise ValueError('City-control immutable source changed within its owner')
        return receipt
    p0,s,_=verify_source(core);pins=source_dependencies(core)
    metadata=_identities(pins)
    for path,sha in pins.items():
        with Path(path).open('rb') as stream:
            if hashlib.file_digest(stream,'sha256').hexdigest()!=sha:raise ValueError('City-control dependency changed')
    verify_live(b.core._handle,b.runtime.read,core)
    aux=s['auxiliary_map_result']['global_rvas'][_LABELS[core]]
    if int.from_bytes(b.runtime.read(b.core._handle+aux,8),'little')!=C.addressof(b.host.aux_object):
        raise ValueError('City-control command targets lost their actual auxiliary owner')
    if _identities(pins)!=metadata:raise ValueError('City-control source changed while binding')
    receipt=CityControlSource(saved,b,t,p,b.core,b.core._handle,b.inputs,b.captured_bundle,
        arguments,reader,reader.read,b.runtime.read,core,SOURCE[1],metadata)
    b._expansion_city_controls_source=arguments._expansion_city_controls_source=receipt
    return receipt

