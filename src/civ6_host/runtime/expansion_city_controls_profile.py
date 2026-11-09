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
BBG_UI_SOURCE=('work/host-extensions/expansion-city-controls-static/bbg751-ui-gate-source-v1.json',
               '645596d5e71fdc70b29532bf78bc0d586d382a657b36486134510b7f80d2580a')
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
        # This is the historical source witness, not the newly selected world.
        # Environment registration must never relabel the proof's old inputs.
        options = {}
        if label == 'xp2':
            from .xp2_bundle_inputs import REFERENCE
            options['official_bundle'] = REFERENCE
        if p['captured_inputs'][label]['manifest']['sha256']!=select(core_sha256, **options).candidate.reference[1]:
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


def _current_bbg_gate(core_sha256, official_bundle, execution_image, source_gate):
    """Join the unchanged numerical UI contract to this captured MP context."""
    import json
    from . import xp2_bbg_inputs as bbg
    from .captured_session_profile import require_bbg_capture
    from .native.native_official_bundle import ROOT, _file
    from .resource_resolution import resolve_path
    reference = require_bbg_capture(official_bundle, execution_image=execution_image)
    capture = bbg._complete_capture(reference)
    folder = resolve_path(ROOT / reference[0]).resolve(strict=True).parent
    if (source_gate['selected_city_presentation_required'] is not False
            or source_gate['native_targets_and_revalidation_required'] is not True
            or capture['ui_availability'].get('observed_states_equal') is not True):
        raise ValueError('Current city-control capture lacks the numerical UI gate contract')
    witnesses = []
    for side in ('before', 'after'):
        pin = capture['artifacts']['ui-availability-' + side + '.json']
        if resolve_path(Path(pin['path'])).resolve(strict=True) != folder / ('ui-availability-' + side + '.json'):
            raise ValueError('Current city-control witness belongs to another capture directory')
        report = json.loads(_file(pin, {}, maximum=1024*1024))
        ui = report['diagnostics']['ui_availability']
        event = dict(kind='ui_availability',nonce=report.get('request_id'),sequence=report.get('sequence'))
        if capture['bridge_events'].count(event) != 1:
            raise ValueError('Current city-control witness differs from its bridge exchange')
        if (report.get('status') != 'ok' or report.get('type') != 'transport_status'
                or report.get('player_id') != 0 or ui.get('player_id') != 0
                or report.get('turn') != ui.get('turn')
                or ui.get('schema') != 'civ6rl.ui_availability.v2'
                or ui.get('read_only') is not True or ui.get('observed_unchanged') is not True
                or ui['tutorial']['any_multiplayer'] != {'status':'observed','value':True}
                or any(ui['tutorial'][key] != {'status':'observed','value':False}
                       for key in ('active','manager_active','overlay_enabled'))
                or any(ui['controls'][name][key] != {'status':'observed','value':False}
                       for name in ('city_yields','city_citizens') for key in ('hidden','disabled'))):
            raise ValueError('Current city-control MP/tutorial/visibility gate is not observed')
        witnesses.append(pin)
    manifest_path = resolve_path(ROOT / reference[0]).resolve(strict=True)
    return dict(schema='civ6-host.bbg751-city-ui-capture-binding.v1',
        official_bundle=dict(zip(('path','sha256'),reference)), core_sha256=core_sha256,
        captured_gamecore_sha256=capture['preflight']['process']['gamecore_module']['sha256'],
        historical_gate_source=dict(path=BBG_UI_SOURCE[0],sha256=BBG_UI_SOURCE[1]),
        ui_witness=witnesses[0], ui_witnesses=witnesses,
        selected_city_presentation_required=False, native_targets_and_revalidation_required=True,
        dependencies=[*source_gate['dependencies'], witnesses[1],
                      dict(path=str(manifest_path),sha256=reference[1])],
        native_execution=False, graphical_selected_city_state_qualified=False)


def bbg_gate(core_sha256,official_bundle,*,execution_image=None):
    if core_sha256!=XP2_CORE_SHA256 or official_bundle is None:
        return None
    from . import xp2_bbg_inputs as bbg
    if not bbg.is_reference(official_bundle):
        return None
    from .native.native_official_bundle import normalize_reference
    value=_source(BBG_UI_SOURCE)
    if (value.get('schema') != 'civ6-host.bbg751-city-ui-gate-source.v1'
            or value.get('core_sha256') != core_sha256):
        raise ValueError('City-control BBG numerical source contract differs')
    actual_reference=(normalize_reference(official_bundle) if type(official_bundle) is dict
                      else official_bundle if type(official_bundle) is tuple else None)
    if actual_reference != bbg.REFERENCE:
        return _current_bbg_gate(core_sha256, actual_reference, execution_image, value)
    if (value['schema']!='civ6-host.bbg751-city-ui-gate-source.v1'
            or normalize_reference(dict(value['official_bundle']))!=actual_reference
            or value['core_sha256']!=core_sha256
            or value['selected_city_presentation_required'] is not False
            or value['native_targets_and_revalidation_required'] is not True):
        raise ValueError('City-control BBG numerical gate belongs to another bundle')
    witness=_source((value['ui_witness']['path'],value['ui_witness']['sha256']))
    ui=witness['diagnostics']['ui_availability']
    if (ui['schema']!='civ6rl.ui_availability.v2' or ui['read_only'] is not True
            or ui['observed_unchanged'] is not True
            or ui['tutorial']['any_multiplayer']!={'status':'observed','value':True}
            or any(ui['tutorial'][key]!={'status':'observed','value':False}
                   for key in ('active','manager_active','overlay_enabled'))
            or any(ui['controls'][name][key]!={'status':'observed','value':False}
                   for name in ('city_yields','city_citizens') for key in ('hidden','disabled'))):
        raise ValueError('City-control BBG tutorial/visibility gate is not observed')
    return value


def source_dependencies(core_sha256=XP1_CORE_SHA256,*,official_bundle=None,execution_image=None):
    from .paths import resource_root
    from .resource_resolution import resolve_path
    p,s,selected=verify_source(core_sha256)
    refs=[dict(path=SOURCE[0],sha256=SOURCE[1]),dict(path=SUPPLEMENT[0],sha256=SUPPLEMENT[1]),
          p['exe'],selected['image'],p['capture_script'],s['capture_script'],
          *p['references'],*p['official_ui_sources'],*s['official_ui_sources']]
    if core_sha256!=BASE_CORE_SHA256:
        capture=p['captured_inputs'][_LABELS[core_sha256]]
        refs.extend((capture['manifest'],*capture['ui_witnesses']))
    gate=bbg_gate(core_sha256,official_bundle,execution_image=execution_image)
    if gate is not None:
        refs.extend((dict(path=BBG_UI_SOURCE[0],sha256=BBG_UI_SOURCE[1]),
                     gate['ui_witness'],*gate['dependencies']))
    result={}
    for ref in refs:
        path=resolve_path(resource_root()/ref['path']).resolve()
        if str(path) in result and result[str(path)]!=ref['sha256']:raise ValueError('Conflicting city-control dependency')
        result[str(path)]=ref['sha256']
    if execution_image is not None:
        if core_sha256!=XP2_CORE_SHA256:
            raise ValueError('Selected city-control execution image requires XP2')
        from .runtime_source_dependencies import materialize_runtime_source_pins
        result=materialize_runtime_source_pins(result,execution_image=execution_image,
            provenance_images=(p['exe'],selected['image']))
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
    gate_source_sha256:object=None
    execution_image:object=None



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
    bundle_reference=b.captured_bundle.reference
    image=getattr(b.core,'_civ6_host_execution_image',None)
    gate=bbg_gate(core,bundle_reference,execution_image=image)
    gate_sha256=BBG_UI_SOURCE[1] if gate is not None else None
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
                or receipt.gate_source_sha256!=gate_sha256
                or receipt.execution_image is not image
                or getattr(arguments,'_expansion_city_controls_source',None) is not receipt):
            raise ValueError('City-control source lost its exact live owners')
        if receipt.metadata!=_identities(source_dependencies(core,official_bundle=bundle_reference,execution_image=image)):
            raise ValueError('City-control immutable source changed within its owner')
        return receipt
    p0,s,_=verify_source(core);pins=source_dependencies(core,official_bundle=bundle_reference,execution_image=image)
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
        arguments,reader,reader.read,b.runtime.read,core,SOURCE[1],metadata,gate_sha256,image)
    b._expansion_city_controls_source=arguments._expansion_city_controls_source=receipt
    return receipt

