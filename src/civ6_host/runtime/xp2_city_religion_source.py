"""Exact installed Gathering Storm source for own-city religion details."""

from hashlib import sha256
from pathlib import Path

from . import xp2_bbg_inputs, xp2_bundle_inputs
from .a0_family_source import verify_pinned_files
from .configuration_profiles import XP2_CORE_SHA256, _source
from .execution_images import _PROFILE
from .paths import resource_root
from .resource_resolution import resolve_path


SOURCE = (
    'work/x1trade/xp2-city-religion-details-runtime-stage/'
    'd57d34e9b2e91248607627386586da4d1b2e5b31ef6eee5621318db73d7b0889.json',
    'd57d34e9b2e91248607627386586da4d1b2e5b31ef6eee5621318db73d7b0889',
)
_CAPTURES = {
    xp2_bundle_inputs.REFERENCE: 'xp2-stock',
    xp2_bbg_inputs.REFERENCE: 'xp2-bbg751',
}
_METHODS = {
    'City.GetReligion': '0x68b040',
    'CityReligion.GetMajorityReligion': '0x692230',
    'CityReligion.GetReligionsInCity': '0x692340',
    'CityReligion.GetTotalPressureOnCity': '0x692a70',
}
_FIELDS = ('majority_religion','religion_index','followers','pressure_per_turn','lifetime_pressure')


def supports(reference,image):
    return image is _PROFILE and type(reference) is tuple and reference in tuple(_CAPTURES)


def _identity(row):
    return row['path'],row['sha256']


def verify_source():
    from .xp1_city_religion import DETAILS_SOURCE
    from .xp2_religious_chain_source import SOURCE as chain_source

    proof = _source(SOURCE)
    image = proof['image']
    if (proof['schema'] != 'civ6-host.xp2-city-religion-details-source.static.v1'
            or (image['profile_id'],image['sha256'],image['reference_abi_sha256'],image['bytes']) !=
                (_PROFILE.id,_PROFILE.image_sha256,XP2_CORE_SHA256,_PROFILE.image_size_bytes)
            or _identity(proof['comparison']) != DETAILS_SOURCE
            or _identity(proof['selected_capture_provenance']) != chain_source
            or {name:row['callback_rva'] for name,row in proof['bindings'].items()} != _METHODS
            or set(proof['captured_inputs']) != set(_CAPTURES.values())
            or any(_identity(proof['captured_inputs'][name]['reference']) != ref
                   for ref,name in _CAPTURES.items())
            or proof['contract']['fields'] != _FIELDS
            or proof['contract']['displayed_round'] != 'math.floor(value + 0.5)'
            or proof['contract']['encoded_pressure_bounds'] != (-8388608,8388608)
            or tuple(row['value'] for row in proof['q8_constants']) != (1/256,256)
            or proof['bbg_ui_selection']['no_city_lens_replacement'] is not True
            or proof['native_execution'] is not False or proof['process_memory_read'] is not False):
        raise ValueError('Gathering Storm city religion source changed')
    return proof


def source_dependencies(image, *, reference):
    if not supports(reference,image):
        raise ValueError('Gathering Storm city religion needs its exact installed image and capture')
    proof = verify_source()
    capture = proof['captured_inputs'][_CAPTURES[reference]]
    rows = [dict(path=SOURCE[0],sha256=SOURCE[1]),proof['image'],proof['comparison'],
            proof['selected_capture_provenance'],capture['reference'],capture['database'],
            *proof['stock_ui']]
    if reference == xp2_bbg_inputs.REFERENCE:
        rows.append(proof['bbg_ui_selection'])
    pins = {}
    for row in rows:
        path = str(resolve_path(resource_root()/row['path']).resolve(strict=True))
        if pins.setdefault(path,row['sha256']) != row['sha256']:
            raise ValueError('Conflicting Gathering Storm city religion source dependency')
    verify_pinned_files(pins)
    return pins


def verify_live(base, read):
    if type(base) is not int or base <= 0 or not callable(read):
        raise ValueError('Gathering Storm city religion needs its live module and reader')
    proof = verify_source()
    spans = [span for function in proof['functions'].values() for span in function['fragments']]
    spans.extend(row[key] for row in proof['bindings'].values() for key in ('registration','literal'))
    spans.extend(proof['cache_and_fields'].values())
    spans.extend(proof['q8_constants'])
    for span in spans:
        raw = read(base+int(span['rva'],16),span['bytes'])
        if type(raw) is not bytes or len(raw) != span['bytes'] or sha256(raw).hexdigest() != span['sha256']:
            raise ValueError('Live Gathering Storm city religion binding differs at '+span['rva'])
    return len(spans)


def bind_prefix(prefix):
    from .core_script_services import check_bound
    from .native.native_script_runtime import NativeScriptRuntime
    from .saved_load_services import SavedLoadServices
    from .xp2_bbg_nested_events import BBGNestedScriptRuntime

    if type(prefix) is not SavedLoadServices:
        raise ValueError('Gathering Storm city religion requires the actual saved service owner')
    backend = prefix.backend
    backend.check_thread()
    core, runtime = backend.core,prefix.runtime
    reference = backend.captured_bundle.reference
    expected_runtime = BBGNestedScriptRuntime if reference == xp2_bbg_inputs.REFERENCE else NativeScriptRuntime
    if (prefix.closed or prefix.quarantined or backend.prefix is not prefix
            or prefix.core is not core or prefix.context != backend.context
            or backend.load_abi.core_sha256 != XP2_CORE_SHA256
            or not supports(reference,getattr(core,'_civ6_host_execution_image',None))
            or type(runtime) is not expected_runtime):
        raise ValueError('Gathering Storm city religion needs its exact saved capture and Lua owner')
    lease = check_bound(runtime,backend.context,core)
    runtime.registry.validate(prefix.ui_child)
    lifetime = (backend,core,prefix,runtime,prefix.ui_child,lease,reference)
    previous = getattr(prefix,'_xp2_city_religion_details_lifetime',None)
    if previous is not None:
        if previous != lifetime:
            raise ValueError('Gathering Storm city religion belongs to another saved lifetime')
        return
    verify_live(core._handle,backend.runtime.read)
    prefix._xp2_city_religion_details_lifetime = lifetime
